"""Check the rendered film's narration against the Gemini TTS audio rules (~/.claude/CLAUDE.md, rule 6).

    python verify_audio.py hf/renders/PawSOS_Goa_demo.mp4

For every narration clip in the final mix: the first and last 30 ms must be below -50 dB, the
gaps between clips must be digital silence (below -90 dB), and clip loudness must sit within
about 1 LU of the median. Also reports integrated loudness and true peak of the whole film.
"""

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
FILM = Path(sys.argv[1] if len(sys.argv) > 1 else HERE / "hf" / "renders" / "PawSOS_Goa_demo.mp4")
sys.path.insert(0, str(HERE / "hf"))
VOICE = json.loads((HERE / "voice_report.json").read_text())
SRC = (HERE / "hf" / "build.py").read_text()
VO_START = ast.literal_eval("{" + re.search(r"VO_START = \{(.*?)\}", SRC, re.S).group(1) + "}")
RATE = 48000


def pcm(path: Path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(RATE), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype="<f4")


def db(x: np.ndarray) -> float:
    rms = float(np.sqrt(np.mean(x.astype(np.float64) ** 2))) if len(x) else 0.0
    return -120.0 if rms <= 1e-6 else 20 * np.log10(rms)


def lufs(path: Path, start: float, dur: float) -> float:
    out = subprocess.run(["ffmpeg", "-v", "info", "-ss", f"{start}", "-t", f"{dur}", "-i", str(path),
                          "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", out)
    return float(m[-1]) if m else float("nan")


x = pcm(FILM)
ms30 = int(0.030 * RATE)
rows, fails = [], []
ids = sorted(VO_START, key=VO_START.get)
for i, lid in enumerate(ids):
    s, d = VO_START[lid], VOICE[lid]["duration"]
    a, b = int(s * RATE), int((s + d) * RATE)
    head, tail = db(x[a:a + ms30]), db(x[b - ms30:b])
    loud = lufs(FILM, s, d)
    gap = None
    if i + 1 < len(ids):
        g0, g1 = b + int(0.02 * RATE), int(VO_START[ids[i + 1]] * RATE) - int(0.02 * RATE)
        gap = db(x[g0:g1]) if g1 > g0 else None
    rows.append((lid, head, tail, gap, loud))
    if head > -50: fails.append(f"{lid}: start {head:.1f} dB")
    if tail > -50: fails.append(f"{lid}: end {tail:.1f} dB")
    if gap is not None and gap > -90: fails.append(f"{lid}->{ids[i + 1]}: gap {gap:.1f} dB")

med = float(np.median([r[4] for r in rows]))
for lid, head, tail, gap, loud in rows:
    flag = "" if abs(loud - med) <= 1.0 else "  <- loudness off median"
    if flag: fails.append(f"{lid}: {loud:.1f} LUFS vs median {med:.1f}")
    print(f"{lid}  start {head:7.1f} dB  end {tail:7.1f} dB  gap {'' if gap is None else f'{gap:7.1f} dB':>11}  {loud:6.1f} LUFS{flag}")

whole = subprocess.run(["ffmpeg", "-v", "info", "-i", str(FILM), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
I = re.findall(r"I:\s+(-?[\d.]+) LUFS", whole)[-1]
TP = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", whole)[-1]
print(f"\nWhole film: {I} LUFS integrated, true peak {TP} dBFS. Clip loudness median {med:.1f} LUFS.")
print("PASS: every edge, gap and level check." if not fails else "FAIL:\n  " + "\n  ".join(fails))
