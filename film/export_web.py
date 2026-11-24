"""Publish the rendered film to the website's /demo page.

    python export_web.py

Copies the MP4 (web-optimised, moov atom first) to app/static/site/film/, writes captions.vtt
from the same caption chunks the film shows, and a poster frame from the reveal scene.
"""

import subprocess
from pathlib import Path

HERE = Path(__file__).parent
RENDER = HERE / "hf" / "renders" / "PawSOS_Goa_demo.mp4"
DEST = HERE.parent / "app" / "static" / "site" / "film"
DEST.mkdir(parents=True, exist_ok=True)

subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(RENDER), "-c", "copy", "-movflags", "+faststart",
                str(DEST / "PawSOS_Goa_demo.mp4")], check=True)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "31.5", "-i", str(RENDER), "-frames:v", "1", "-q:v", "3",
                str(DEST / "poster.jpg")], check=True)

# Reuse build.py's caption chunks so the web captions match the film word for word.
src = (HERE / "hf" / "build.py").read_text().split("for f in (build_hook")[0]
ns: dict = {"__file__": str(HERE / "hf" / "build.py")}
exec(compile(src, "build.py", "exec"), ns)


def ts(t: float) -> str:
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


lines = ["WEBVTT", ""]
for i, (start, dur, text) in enumerate(ns["caption_chunks"](), 1):
    lines += [str(i), f"{ts(start)} --> {ts(start + dur)}", text, ""]
(DEST / "captions.vtt").write_text("\n".join(lines))
for f in sorted(DEST.iterdir()):
    print(f"{f.name:28} {f.stat().st_size / 1024 / 1024:6.2f} MB")
