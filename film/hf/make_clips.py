"""Cut the product recordings into 1920x1080 clips, one camera framing each, speed baked in.

    python3 make_clips.py

The recordings are 2560x1600 (a 1280x800 page at 2x). Each framing is a crop of the source,
scaled to 1920x1080 with Lanczos, so text stays sharp and the composition needs no transforms.
Writes assets/video/clips/<id>.mp4 and clips.json (local start, duration per clip).
"""

import json
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE / "assets" / "video"
OUT = SRC / "clips"
OUT.mkdir(exist_ok=True)

# Source-pixel crops (x, y, w); h = w * 9 / 16.
FRAMES = {
    "full": (0, 40, 2560),          # the whole demo: citizen and team side by side, with the controls
    "cit": (0, 300, 1300),          # the citizen's chat, newest messages
    "team_top": (1260, 40, 1300),   # the team's chat: who is alerted, and the alert
    "team_low": (1260, 300, 1300),  # the team's chat, newest messages
    "dfull": (0, 0, 2560),          # the dashboard
    "ddetail": (1400, 0, 1160),     # the dashboard's case panel
}

# Media times come from the recorder's event log, so a new take lines up without retiming.
EV = json.loads((HERE.parent / "raw" / "events.json").read_text())
S, DSH = EV["sandbox"], EV["dashboard"]

# id, source, framing, local start in scene, media start, media end (speed = media span / slot)
PRODUCT = [
    ("a1", "sandbox", "full", 0.0, S["photo_sent"] - 1.8, S["photo_sent"] - 0.8),
    ("a2", "sandbox", "cit", 1.4, S["photo_sent"] - 0.8, S["triage_reply"] + 2.43),
    ("b", "sandbox", "cit", 16.0, S["triage_reply"] + 2.43, S["merged"] + 0.8),
    ("c1", "sandbox", "cit", 21.5, S["merged"] + 0.8, S["back_to_citizen"] + 0.14),
    ("c2", "sandbox", "team_top", 26.1, S["back_to_citizen"] + 0.14, S["back_to_citizen"] + 4.94),
    ("d", "sandbox", "team_top", 31.6, S["back_to_citizen"] + 4.94, S["next_team_alert"] + 2.15),
    ("e1", "sandbox", "team_low", 38.6, S["next_team_alert"] + 2.15, S["resolved"] + 1.55),
    ("e2", "sandbox", "cit", 42.9, S["resolved"] + 1.55, S["rated"] + 2.32),
]
PRODUCT_END = 46.0
OFFICIALS = [
    ("o1", "dashboard", "dfull", 0.0, DSH["dashboard_ready"] - 0.29, DSH["case_detail"] + 0.1),
    ("o2", "dashboard", "ddetail", 4.4, DSH["case_detail"] + 0.1, DSH["audit_trail"] + 1.66),
]
OFFICIALS_END = 8.8


def plan(rows, end):
    out = []
    for i, (cid, src, frame, start, m0, m1) in enumerate(rows):
        nxt = rows[i + 1][3] if i + 1 < len(rows) else end
        out.append({"id": cid, "src": src, "frame": frame, "start": start, "duration": round(nxt - start, 3),
                    "m0": m0, "m1": m1, "speed": round((m1 - m0) / (nxt - start), 4)})
    return out


def cut(c) -> None:
    x, y, w = FRAMES[c["frame"]]
    h = round(w * 9 / 16)
    frames = round(c["duration"] * 30)
    vf = (f"trim=start={c['m0']}:end={c['m1'] + 0.5},setpts=(PTS-STARTPTS)/{c['speed']},"
          f"crop={w}:{h}:{x}:{y},scale=1920:1080:flags=lanczos,fps=30")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(SRC / f"{c['src']}.mp4"), "-vf", vf,
                    "-frames:v", str(frames), "-c:v", "libx264", "-preset", "medium", "-crf", "14",
                    "-pix_fmt", "yuv420p", "-g", "15", "-an", str(OUT / f"{c['id']}.mp4")], check=True)


clips = {"product": plan(PRODUCT, PRODUCT_END), "officials": plan(OFFICIALS, OFFICIALS_END)}
for group in clips.values():
    for c in group:
        cut(c)
        print(f"{c['id']:3} {c['frame']:8} start {c['start']:6.2f} dur {c['duration']:5.2f} speed {c['speed']:.3f}x")
(HERE / "clips.json").write_text(json.dumps(clips, indent=2))
