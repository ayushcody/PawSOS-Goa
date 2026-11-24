"""Generate, clean, gate and transcribe every narration line in script.json.

    python make_voice.py [--voice Charon] [--only l01,l02] [--model gemini-3.8-flash-tts]

Writes assets/voice/<id>.wav (cleaned, two-pass loudnorm -16 LUFS / -1.5 dBTP) and
voice_report.json with each clip's duration, edge-check result and transcript diff.
Follows the Gemini TTS rules in ~/.claude/CLAUDE.md.
"""

import argparse
import difflib
import json
import re
from pathlib import Path

import gemini_tts as tts

HERE = Path(__file__).parent
OUT = HERE / "assets" / "voice"
OUT.mkdir(parents=True, exist_ok=True)

# Spoken forms in the script mapped to the digits a transcriber writes, so a correct
# reading is not counted as a mismatch (a misread number still is).
NUMBER_PHRASES = [
    ("paw s o s", "pawsos"),
    ("paw sos", "pawsos"),
    ("sanghalem", "sankhalim"),
    ("mapsa", "mapusa"),
    ("sterilization", "sterilisation"),
    ("nineteen thousand three hundred and sixty eight", "19368"),
    ("nineteen thousand three hundred sixty eight", "19368"),
    ("twenty twenty five", "2025"),
    ("twenty seven", "27"),
    ("eight", "8"),
    ("two", "2"),
    ("three", "3"),
    ("one", "1"),
]


def norm(s: str) -> list[str]:
    s = s.lower().replace("-", " ")
    s = re.sub(r"(?<=\d),(?=\d)", "", s)  # 19,368 -> 19368
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    s = " ".join(s.split())
    for phrase, digits in NUMBER_PHRASES:
        s = re.sub(rf"\b{phrase}\b", digits, s)
    s = s.replace("p m", "pm")
    return s.split()


def diff(expected: str, heard: str) -> float:
    return difflib.SequenceMatcher(None, norm(expected), norm(heard)).ratio()


ap = argparse.ArgumentParser()
ap.add_argument("--voice", default="Charon")
ap.add_argument("--model", default=tts.MODEL)
ap.add_argument("--only", default="")
ap.add_argument("--retries", type=int, default=3)
a = ap.parse_args()

lines = json.loads((HERE / "script.json").read_text())
only = set(filter(None, a.only.split(",")))
report_path = HERE / "voice_report.json"
report = json.loads(report_path.read_text()) if report_path.exists() else {}

for line in lines:
    if only and line["id"] not in only:
        continue
    path = OUT / f"{line['id']}.wav"
    best = None
    for attempt in range(1, a.retries + 1):
        try:
            dur = tts.synthesize(line["text"], path, voice=a.voice, model=a.model)
        except RuntimeError as error:  # the edge gate refused the clip: generate it again
            print(f"{line['id']} try {attempt}: rejected ({error})")
            continue
        problems = tts.check_edges(path)
        heard = tts.transcribe(path)
        score = diff(line["text"], heard)
        best = {"duration": round(dur, 3), "edges": problems, "heard": heard, "match": round(score, 3),
                "attempt": attempt, "voice": a.voice, "model": a.model}
        print(f"{line['id']} try {attempt}: {dur:5.2f}s match={score:.3f} edges={problems or 'ok'}")
        if not problems and score >= 0.93:
            break
    report[line["id"]] = best
    report_path.write_text(json.dumps(report, indent=2))

bad = {k: v for k, v in report.items() if v["edges"] or v["match"] < 0.93}
print("\nNeeds attention:" if bad else "\nAll clips passed edges and transcript checks.")
for k, v in bad.items():
    print(f"  {k}: match={v['match']} edges={v['edges']} heard={v['heard']!r}")
print(f"Total narration: {sum(v['duration'] for v in report.values()):.1f}s")
