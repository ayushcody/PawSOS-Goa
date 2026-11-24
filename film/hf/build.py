"""Generate index.html and compositions/*.html for the PawSOS Goa film.

    python3 build.py

Timings come from ../voice_report.json (measured narration) and ../raw/events.json (logged
moments in the product recording), so the edit follows what was said and what happened.
Edit this file and rebuild rather than hand-editing the generated HTML.
"""

import json
import re
from pathlib import Path

HERE = Path(__file__).parent
FILM = HERE.parent
COMP = HERE / "compositions"
COMP.mkdir(exist_ok=True)

VOICE = json.loads((FILM / "voice_report.json").read_text())
SCRIPT = {l["id"]: l["text"] for l in json.loads((FILM / "script.json").read_text())}
EVENTS = json.loads((FILM / "raw" / "events.json").read_text())
GOA = json.loads((FILM / "goa_map.json").read_text())
ICONS = {}
for f in (HERE / "assets" / "icons").glob("*.svg"):
    ICONS[f.stem] = re.findall(r'<path d="([^"]+)"', f.read_text())[0]

W, H, TOTAL = 1920, 1080, 130.0

# ---------------------------------------------------------------- the clock: voice start times
VO_START = {
    "l01": 0.6, "l02": 4.6, "l03": 11.8, "l04": 16.0, "l05": 21.0, "l06": 28.2,
    "l07": 35.4, "l08": 40.6, "l09": 51.4, "l10": 60.5, "l11": 66.5, "l12": 74.0,
    "l13": 81.6, "l14": 90.5, "l15": 95.4, "l16": 101.5, "l17": 113.6, "l18": 121.8,
}
SCENES = [  # id, start, duration
    ("hook", 0.0, 11.4), ("tension", 11.4, 16.4), ("reveal", 27.8, 7.4), ("product", 35.2, 46.0),
    ("officials", 81.2, 8.8), ("arch", 90.0, 23.2), ("honest", 113.2, 8.2), ("finale", 121.4, 8.6),
]
for k, v in VO_START.items():  # no line may overlap the next
    end = v + VOICE[k]["duration"]
    nxt = [s for s in VO_START.values() if s > v]
    assert not nxt or end < min(nxt), f"{k} overlaps the next line"
assert VO_START["l18"] + VOICE["l18"]["duration"] < TOTAL

FONTS = """
@font-face { font-family: "Bricolage Grotesque"; src: url("assets/fonts/BricolageGrotesque.woff2") format("woff2"); font-weight: 500 800; }
@font-face { font-family: "Geist"; src: url("assets/fonts/Geist.woff2") format("woff2"); font-weight: 400 600; }
@font-face { font-family: "Geist Mono"; src: url("assets/fonts/GeistMono.woff2") format("woff2"); font-weight: 500; }
"""
BASE = """
#root { position: absolute; inset: 0; overflow: hidden; background: #f3f6f4; color: #10211e;
  font-family: "Geist", sans-serif; }
.display { font-family: "Bricolage Grotesque", sans-serif; font-weight: 780; letter-spacing: -0.03em; }
.mono { font-family: "Geist Mono", monospace; font-weight: 500; }
.coral { color: #d8432a; } .teal { color: #0f6b5c; } .soft { color: #4a5c57; }
.mask { display: inline-block; overflow: hidden; vertical-align: top; padding-bottom: 0.08em; }
.mask > span { display: inline-block; }
"""


def icon(name: str, size: int, color: str = "currentColor", extra: str = "") -> str:
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 256 256" {extra}>'
            f'<path d="{ICONS[name]}" fill="{color}"/></svg>')


def scene(sid: str, dur: float, css: str, body: str, js: str) -> None:
    html = f"""<template>
  <style>{FONTS}{BASE}{css}</style>
  <div id="root" data-composition-id="{sid}" data-width="{W}" data-height="{H}" data-duration="{dur}">
{body}
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
{js}
    window.__timelines["{sid}"] = tl;
  </script>
</template>
"""
    (COMP / f"{sid}.html").write_text(html)


def clip(eid: str, start: float, dur: float, inner: str, cls: str = "", style: str = "", attrs: str = "") -> str:
    return (f'    <div id="{eid}" class="clip {cls}" data-start="{start:.2f}" data-duration="{dur:.2f}" '
            f'style="{style}" {attrs}>{inner}</div>')


def words(text: str, cls: str = "w") -> str:
    """Each word in its own mask, so it can rise into place."""
    return " ".join(f'<span class="mask"><span class="{cls}">{w}</span></span>' for w in text.split())


def local(sid: str, t: float) -> float:
    start = dict((s[0], s[1]) for s in SCENES)[sid]
    return round(t - start, 2)


# ================================================================ 1. hook
def build_hook() -> None:
    sid, dur = "hook", 11.4
    ticks = "".join(
        f'<line x1="0" y1="-190" x2="0" y2="{-168 if i % 3 else -156}" stroke="#10211e" stroke-width="{6 if i % 3 == 0 else 3}" '
        f'transform="rotate({i * 30})" stroke-linecap="round"/>' for i in range(12))
    body = "\n".join([
        clip("h-clock", 0.0, 4.5, f'''<svg width="460" height="460" viewBox="-230 -230 460 460">
          <circle r="208" fill="#ffffff" stroke="#10211e" stroke-width="8"/>{ticks}
          <g id="h-hand"><line x1="0" y1="18" x2="0" y2="-150" stroke="#d8432a" stroke-width="9" stroke-linecap="round"/></g>
          <circle r="14" fill="#10211e"/></svg>''', style="position:absolute; left:1280px; top:310px; width:460px; height:460px;"),
        clip("h-every", 0.5, 4.0, f'<div class="display" style="font-size:124px; line-height:1.02;">{words("Every")} <span class="mask"><span class="w coral">27</span></span><br>{words("minutes")}</div>',
             style="position:absolute; left:160px; top:300px;"),
        clip("h-bitten", 1.9, 2.6, f'<div style="font-size:46px; font-weight:500;" class="soft">{words("someone in Goa is bitten by a dog.")}</div>',
             style="position:absolute; left:164px; top:600px;"),
        clip("h-num", 4.4, 7.0, '<div class="display coral" style="font-size:300px; line-height:0.9; font-weight:800; font-variant-numeric: tabular-nums;"><span id="h-count">0</span></div>',
             style="position:absolute; left:150px; top:250px;"),
        clip("h-numlabel", 6.4, 5.0, f'<div class="display" style="font-size:64px; line-height:1.1;">{words("dog bite cases in Goa in 2025.")}</div>',
             style="position:absolute; left:164px; top:560px;"),
        clip("h-src", 7.0, 4.4, '<div class="mono soft" style="font-size:28px;">Source: Health Intelligence Bureau data tabled in the Goa Legislative Assembly (LAQ 097), via Goemkarponn</div>',
             style="position:absolute; left:164px; top:880px;"),
    ])
    js = """
    tl.fromTo("#h-clock svg", { scale: 0.92, opacity: 1 }, { scale: 1, opacity: 1, duration: 0.9, ease: "expo.out", transformOrigin: "50% 50%" }, 0);
    tl.fromTo("#h-hand", { rotation: -40 }, { rotation: 320, duration: 3.4, ease: "power1.inOut", svgOrigin: "0 0" }, 0.6);
    tl.fromTo("#h-every .w", { yPercent: 110 }, { yPercent: 0, duration: 0.7, ease: "expo.out", stagger: 0.09 }, 0.5);
    tl.fromTo("#h-bitten .w", { yPercent: 110 }, { yPercent: 0, duration: 0.55, ease: "expo.out", stagger: 0.04 }, 1.9);
    tl.to(["#h-every > div", "#h-bitten > div", "#h-clock svg"], { yPercent: -12, opacity: 0, duration: 0.35, ease: "power2.in" }, 4.05);
    const n = { v: 0 };
    tl.fromTo("#h-num > div", { yPercent: 18, opacity: 0 }, { yPercent: 0, opacity: 1, duration: 0.5, ease: "expo.out" }, 4.4);
    tl.fromTo(n, { v: 0 }, { v: 19368, duration: 2.1, ease: "power3.out",
      onUpdate: () => { document.getElementById("h-count").textContent = Math.round(n.v).toLocaleString("en-IN"); } }, 4.6);
    tl.fromTo("#h-numlabel .w", { yPercent: 110 }, { yPercent: 0, duration: 0.6, ease: "expo.out", stagger: 0.05 }, 6.4);
    tl.fromTo("#h-src > div", { opacity: 0 }, { opacity: 1, duration: 0.5 }, 7.0);
    tl.to(["#h-num > div", "#h-numlabel > div", "#h-src > div"], { opacity: 0, duration: 0.35, ease: "power2.in" }, 11.0);
"""
    scene(sid, dur, "", body, js)


# ================================================================ 2. tension
MAP_X, MAP_Y, MAP_SCALE = 170, 80, 0.98
ZERO_CAMPS = ["canacona", "sankhalim", "valpoi", "mapusa"]
# Where each "0 camps" label sits relative to its dot, so the three northern towns do not collide.
LABEL_OFFSET = {"mapusa": (-110, -78), "sankhalim": (-70, 26), "valpoi": (26, -74), "canacona": (26, -22)}


def zone_xy(z) -> tuple[float, float]:
    return MAP_X + z["x"] * MAP_SCALE, MAP_Y + z["y"] * MAP_SCALE


def build_tension() -> None:
    sid, dur = "tension", 16.4
    vb = GOA["viewBox"].split()
    mw, mh = float(vb[2]) * MAP_SCALE, float(vb[3]) * MAP_SCALE
    dots = []
    for i, z in enumerate(GOA["zones"]):
        x, y = zone_xy(z)
        dots.append(f'<g class="t-dot" id="t-dot-{z["slug"]}" transform="translate({x - MAP_X:.1f} {y - MAP_Y:.1f})">'
                    f'<circle class="t-halo" r="24" fill="#0f6b5c" opacity="0.14"/><circle class="t-core" r="11" fill="#0f6b5c"/></g>')
    labels = []
    for slug in ZERO_CAMPS:
        z = next(z for z in GOA["zones"] if z["slug"] == slug)
        x, y = zone_xy(z)
        name = z["name"].replace(" Municipal Council", "")
        dx, dy = LABEL_OFFSET[slug]
        labels.append(f'<div class="t-zero" id="t-zero-{slug}" style="position:absolute; left:{x + dx:.0f}px; top:{y + dy:.0f}px;">'
                      f'<b>{name}</b> <span>0 camps</span></div>')
    pz = next(z for z in GOA["zones"] if z["slug"] == "panaji")
    px, py = zone_xy(pz)
    css = """
    .t-zero { font: 600 28px "Geist", sans-serif; color: #10211e; background: #ffffff; border: 2px solid #d8432a;
      border-radius: 10px; padding: 4px 12px; white-space: nowrap; }
    .t-zero span { color: #d8432a; font-family: "Geist Mono", monospace; font-weight: 500; }
    #t-panaji-tag { font: 600 28px "Geist", sans-serif; background: #10211e; color: #f3f6f4; border-radius: 10px; padding: 6px 14px; white-space: nowrap; }
"""
    body = "\n".join([
        clip("t-map", 0.0, 16.4, f'''<svg width="{mw:.0f}" height="{mh:.0f}" viewBox="{GOA["viewBox"]}" style="overflow:visible">
          <path id="t-outline" d="{GOA["path"]}" fill="#e3ece8" stroke="#10211e" stroke-width="3" stroke-linejoin="round"/>
          <g transform="scale({1 / MAP_SCALE:.4f})">{"".join(dots)}</g></svg>''',
             style=f"position:absolute; left:{MAP_X}px; top:{MAP_Y}px;", attrs="data-layout-allow-overflow"),
        clip("t-q", 0.3, 16.1, f'<div class="display" style="font-size:112px; line-height:1.02;">{words("Who do you")}<br>{words("call?")}</div>',
             style="position:absolute; left:900px; top:190px;"),
        clip("t-helplines", 4.6, 11.8, f'<div style="font-size:44px; font-weight:500; line-height:1.3;" class="soft">{words("14 municipalities.")}<br>{words("A different helpline in each.")}</div>',
             style="position:absolute; left:904px; top:470px;"),
        clip("t-panaji", 7.6, 8.8, '<div id="t-panaji-tag">Panaji helpline: 8 am to 8 pm</div>',
             style=f"position:absolute; left:{px + 26:.0f}px; top:{py - 64:.0f}px;"),
        clip("t-zerohead", 9.8, 6.6, f'<div class="display coral" style="font-size:58px; line-height:1.1;">{words("No sterilisation camps in 2025")}</div>',
             style="position:absolute; left:904px; top:690px;"),
        *[clip(f"t-zl-{s}", 10.4 + i * 0.55, 6.0 - i * 0.55, lab, attrs="data-layout-allow-overlap")
          for i, (s, lab) in enumerate(zip(ZERO_CAMPS, labels))],
    ])
    js = f"""
    const outline = document.getElementById("t-outline");
    const len = outline.getTotalLength();
    tl.fromTo(outline, {{ strokeDasharray: len, strokeDashoffset: len, fillOpacity: 0 }},
      {{ strokeDashoffset: 0, duration: 1.6, ease: "power2.inOut" }}, 0.0);
    tl.to(outline, {{ fillOpacity: 1, duration: 0.6 }}, 1.2);
    tl.fromTo("#t-q .w", {{ yPercent: 110 }}, {{ yPercent: 0, duration: 0.7, ease: "expo.out", stagger: 0.08 }}, 0.3);
    tl.fromTo(".t-dot", {{ scale: 0, transformOrigin: "50% 50%" }}, {{ scale: 1, duration: 0.45, ease: "back.out(2.2)", stagger: 0.13 }}, 4.7);
    tl.fromTo("#t-helplines .w", {{ yPercent: 110 }}, {{ yPercent: 0, duration: 0.6, ease: "expo.out", stagger: 0.04 }}, 4.6);
    tl.fromTo("#t-panaji-tag", {{ y: 14, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.45, ease: "expo.out" }}, 7.6);
    tl.to("#t-panaji-tag", {{ opacity: 0, duration: 0.3 }}, 9.6);
    tl.fromTo("#t-zerohead .w", {{ yPercent: 110 }}, {{ yPercent: 0, duration: 0.6, ease: "expo.out", stagger: 0.05 }}, 9.8);
    {"".join(f'''
    tl.to("#t-dot-{s} .t-core, #t-dot-{s} .t-halo", {{ fill: "#d8432a", duration: 0.3 }}, {10.4 + i * 0.55});
    tl.fromTo("#t-zero-{s}", {{ x: -10, opacity: 0 }}, {{ x: 0, opacity: 1, duration: 0.4, ease: "expo.out" }}, {10.4 + i * 0.55});''' for i, s in enumerate(ZERO_CAMPS))}
    // The four towns keep pulsing while the line lands, so the frame never sits dead.
    tl.fromTo("#t-dot-canacona .t-halo, #t-dot-sankhalim .t-halo, #t-dot-valpoi .t-halo, #t-dot-mapusa .t-halo", {{ scale: 1, transformOrigin: "50% 50%" }}, {{ scale: 1.9, opacity: 0.05, duration: 0.9, ease: "power1.out", repeat: 2 }}, 12.6);
    tl.to(["#t-q > div", "#t-helplines > div", "#t-zerohead > div", ".t-zero", "#t-outline"], {{ opacity: 0, duration: 0.4, ease: "power2.in" }}, 15.9);
"""
    scene(sid, dur, css, body, js)


# ================================================================ 3. reveal
def build_reveal() -> None:
    sid, dur = "reveal", 7.4
    cx, cy = 960, 400
    dots = []
    for z in GOA["zones"]:
        x, y = zone_xy(z)
        col = "#d8432a" if z["slug"] in ZERO_CAMPS else "#0f6b5c"
        dots.append(f'<div class="r-dot" style="left:{x - 11:.0f}px; top:{y - 11:.0f}px; background:{col};" '
                    f'data-dx="{cx - x:.0f}" data-dy="{cy - y:.0f}"></div>')
    css = """
    .r-dot { position: absolute; width: 22px; height: 22px; border-radius: 50%; }
    #r-mark-box { width: 210px; height: 210px; border-radius: 52px; background: #0f6b5c; display: grid; place-items: center;
      box-shadow: 0 30px 70px -30px rgba(15,107,92,.55); }
"""
    body = "\n".join([
        clip("r-dots", 0.0, 1.6, "".join(dots), style="position:absolute; inset:0;", attrs="data-layout-allow-overlap"),
        clip("r-mark", 1.0, 6.4, f'<div id="r-mark-box">{icon("paw-print-fill", 128, "#f3f6f4", "id=\"r-paw\"")}</div>',
             style=f"position:absolute; left:{cx - 105}px; top:{cy - 105}px;"),
        clip("r-word", 1.5, 5.9, '<div class="display" style="font-size:120px; white-space:nowrap;">PawSOS <span class="teal">Goa</span></div>',
             style="position:absolute; left:0; right:0; top:540px; text-align:center;"),
        clip("r-line", 2.3, 5.1, f'<div style="font-size:48px; font-weight:500;">{words("One WhatsApp number for every animal emergency.")}</div>',
             style="position:absolute; left:0; right:0; top:700px; text-align:center;"),
        clip("r-noapp", 5.3, 2.1, f'<div class="mono teal" style="font-size:30px;">No app to install.</div>',
             style="position:absolute; left:0; right:0; top:790px; text-align:center;"),
    ])
    js = """
    document.querySelectorAll(".r-dot").forEach((d, i) => {
      tl.fromTo(d, { x: 0, y: 0, scale: 1 }, { x: +d.dataset.dx, y: +d.dataset.dy, scale: 0.6, duration: 0.9, ease: "power3.inOut" }, 0.15 + i * 0.03);
    });
    tl.fromTo("#r-mark-box", { scale: 0.1, borderRadius: "50%" }, { scale: 1, borderRadius: "52px", duration: 0.8, ease: "expo.out" }, 1.0);
    tl.fromTo("#r-paw", { scale: 0.4, opacity: 0, transformOrigin: "50% 50%" }, { scale: 1, opacity: 1, duration: 0.6, ease: "back.out(2)" }, 1.25);
    tl.fromTo("#r-word > div", { clipPath: "inset(0 100% 0 0)" }, { clipPath: "inset(0 0% 0 0)", duration: 0.8, ease: "power3.inOut" }, 1.5);
    tl.fromTo("#r-line .w", { yPercent: 110 }, { yPercent: 0, duration: 0.6, ease: "expo.out", stagger: 0.05 }, 2.3);
    tl.fromTo("#r-noapp > div", { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: 0.45, ease: "expo.out" }, 5.3);
    tl.to(["#r-mark-box", "#r-word > div", "#r-line > div", "#r-noapp > div"], { opacity: 0, scale: 0.96, duration: 0.35, ease: "power2.in" }, 7.0);
"""
    scene(sid, dur, css, body, js)


# ================================================================ 4. product (the real recording)
E = EVENTS["sandbox"]
D = EVENTS["dashboard"]
CLIPS = json.loads((HERE / "clips.json").read_text())  # made by make_clips.py: one framing per clip


def media_to_local(t: float, group: str = "product") -> float:
    for c in CLIPS[group]:
        if c["m0"] <= t <= c["m1"]:
            return round(c["start"] + (t - c["m0"]) / c["speed"], 2)
    raise ValueError(t)


def video_clips(group: str, prefix: str) -> str:
    rows = []
    for z, c in enumerate(CLIPS[group]):
        rows.append(
            f'    <video id="{prefix}-{c["id"]}" class="clip" src="assets/video/clips/{c["id"]}.mp4" muted playsinline '
            f'data-start="{c["start"]:.2f}" data-duration="{c["duration"]:.2f}" data-track-index="{z % 2}" '
            f'style="position:absolute; left:0; top:0; width:1920px; height:1080px; object-fit:cover; z-index:{z + 1};"></video>')
    return "\n".join(rows)


def speed_tags(group: str, prefix: str) -> list[str]:
    tags = []
    for c in CLIPS[group]:
        if c["speed"] >= 1.3:
            tags.append(clip(f'{prefix}-sp-{c["id"]}', c["start"], c["duration"],
                             f'<div class="speed">Sped up {c["speed"]:.1f}x</div>', style="z-index:40;"))
    return tags


CARD_CSS = """
    .card { position: absolute; right: 90px; top: 170px; max-width: 640px; background: #10211e; color: #f3f6f4; z-index: 50;
      border-radius: 18px; padding: 22px 30px 24px; font: 760 46px/1.12 "Bricolage Grotesque", sans-serif; letter-spacing: -0.02em;
      box-shadow: 0 24px 60px -24px rgba(16,33,30,.55); }
    .card small { display: block; margin-top: 8px; font: 500 28px/1.3 "Geist", sans-serif; letter-spacing: 0; color: #b9cdc6; }
    .card .coral { color: #ff8a73; }
    .speed { position: absolute; right: 110px; top: 104px; font: 500 28px "Geist Mono", monospace; color: #f3f6f4; z-index: 50;
      background: #0f6b5c; border-radius: 10px; padding: 8px 16px; }
    .steps span { display: inline-block; margin-right: 18px; }
    .card.low { top: auto; bottom: 200px; }   /* team views: the alert is at the top, the bottom is empty */
"""
CARD_JS = """
    document.querySelectorAll(".card, .speed").forEach((c) => {
      const host = c.parentElement; const s = +host.dataset.start, d = +host.dataset.duration;
      tl.fromTo(c, { y: -14, opacity: 0 }, { y: 0, opacity: 1, duration: 0.45, ease: "expo.out" }, s);
      tl.to(c, { opacity: 0, duration: 0.28, ease: "power2.in" }, s + d - 0.3);
    });
"""


def build_product() -> None:
    sid, dur = "product", 46.0
    t_triage = media_to_local(E["triage_reply"])
    t_merge = media_to_local(E["merged"])
    t_esc = media_to_local(E["escalated"])
    t_acc, t_on, t_res = (media_to_local(E[k]) for k in ("accepted", "on_site", "resolved"))
    cards = [
        clip("p-c1", 2.3, 4.9, '<div class="card">A photo and a location.<small>That is the whole report. No form, no app.</small></div>', style="z-index:50;"),
        clip("p-c2", t_triage + 0.2, 3.9, '<div class="card">Real Claude triage, in seconds.<small>Urgency and safe steps. Never a diagnosis.</small></div>', style="z-index:50;"),
        clip("p-c3", t_merge + 0.1, 25.9 - t_merge - 0.1, '<div class="card">Same animal, second report.<small>Merged into one case. One alert for the team.</small></div>', style="z-index:50;"),
        clip("p-c4", 26.6, 4.8, '<div class="card low">The nearest team is alerted.<small>Photo, map link, Accept or Decline.</small></div>', style="z-index:50;"),
        clip("p-c5", 32.2, t_esc - 32.2 + 1.6, '<div class="card low"><span class="coral">No answer in time.</span><small>The case moves to the next team, then the taluka officer.</small></div>', style="z-index:50;"),
        clip("p-c6", t_acc - 0.1, dur - t_acc + 0.1,
             '<div class="card steps"><span id="p-s1">Accepted.</span><span id="p-s2">On site.</span><span id="p-s3">Resolved.</span>'
             '<small>Everyone who reported it is told each step.</small></div>', style="z-index:50;"),
    ] + speed_tags("product", "p")
    body = video_clips("product", "p") + "\n" + "\n".join(cards)
    js = CARD_JS + f"""
    tl.fromTo(["#p-s2", "#p-s3"], {{ opacity: 0.2 }}, {{ opacity: 0.2, duration: 0.01 }}, 0);
    tl.to("#p-s2", {{ opacity: 1, duration: 0.3 }}, {t_on});
    tl.to("#p-s3", {{ opacity: 1, duration: 0.3 }}, {t_res});
"""
    scene(sid, dur, CARD_CSS, body, js)


# ================================================================ 5. officials (dashboard recording)
def build_officials() -> None:
    sid, dur = "officials", 8.8
    t_detail = CLIPS["officials"][1]["start"]
    cards = [
        clip("o-c1", 0.3, t_detail - 0.3, '<div class="card">Every case on one map.<small>Demo data, tagged "demo". Phone numbers never shown.</small></div>', style="z-index:50;"),
        clip("o-c2", t_detail + 0.2, dur - t_detail - 0.2, '<div class="card">Every step on record.<small>Who was alerted, who timed out, who accepted.</small></div>', style="z-index:50;"),
    ] + speed_tags("officials", "o")
    body = video_clips("officials", "o") + "\n" + "\n".join(cards)
    scene(sid, dur, CARD_CSS + """
    .card { left: 110px; right: auto; top: auto; bottom: 150px; }
""", body, CARD_JS)


# ================================================================ 6. architecture
def build_arch() -> None:
    sid, dur = "arch", 23.2
    steps = ["Intake", "Triage", "Dedup", "Route", "Escalate", "Close the loop"]
    notes = ["Photo + place = a case", "Claude vision, checked", "PostGIS: 200 m, 2 h",
             "Nearest zone's team", "No answer: next team", "Every reporter told"]
    states = ["REPORTED", "ROUTED", "ACCEPTED", "ON SITE", "RESOLVED"]
    chan = [("whatsapp-logo-fill", "WhatsApp"), ("telegram-logo-fill", "Telegram"), ("browser-fill", "Web demo")]
    css = """
    .a-box { position: absolute; background: #ffffff; border: 2px solid #d5dfdb; border-radius: 18px; }
    .a-chan { width: 290px; height: 104px; display: flex; align-items: center; gap: 18px; padding: 0 24px;
      font: 700 32px "Bricolage Grotesque", sans-serif; }
    #a-engine { left: 690px; top: 170px; width: 850px; height: 610px; border: 3px solid #0f6b5c; background: #eaf2ef; }
    #a-engine-title { position: absolute; left: 32px; top: 24px; font: 760 36px "Bricolage Grotesque", sans-serif; letter-spacing: -0.02em; }
    #a-engine-title small { font: 500 28px "Geist Mono", monospace; color: #4a5c57; margin-left: 12px; }
    .a-step { position: absolute; width: 396px; height: 112px; padding: 16px 20px; background: #ffffff; border: 2px solid #d5dfdb; border-radius: 14px; }
    .a-step b { display: block; font: 740 30px "Bricolage Grotesque", sans-serif; }
    .a-step span { font: 500 28px "Geist", sans-serif; color: #4a5c57; }
    .a-step.on { border-color: #0f6b5c; }
    #a-states { position: absolute; left: 32px; right: 32px; bottom: 26px; display: flex; gap: 8px; }
    .a-state { flex: 1; text-align: center; padding: 10px 0; border-radius: 10px; background: #ffffff; border: 2px solid #d5dfdb;
      font: 500 28px "Geist Mono", monospace; color: #4a5c57; }
    .a-store { width: 290px; height: 176px; padding: 20px 24px; }
    .a-store b { display: block; font: 740 30px "Bricolage Grotesque", sans-serif; margin-top: 6px; }
    .a-store span { font: 500 28px "Geist", sans-serif; color: #4a5c57; }
    .a-token { position: absolute; width: 22px; height: 22px; border-radius: 50%; background: #0f6b5c; }
    .a-call { position: absolute; background: #10211e; color: #f3f6f4; border-radius: 14px; padding: 14px 20px;
      font: 600 28px/1.25 "Geist", sans-serif; width: 800px; box-shadow: 0 20px 50px -20px rgba(16,33,30,.5); }
    .a-call b { color: #ff8a73; }
"""
    step_xy = [(718 + (i % 2) * 410, 250 + (i // 2) * 124) for i in range(6)]
    chan_y = [220, 400, 580]
    body_parts = [
        clip("a-title", 0.3, 22.9, f'<div class="display" style="font-size:54px;">{words("One service. One database.")}</div>',
             style="position:absolute; left:110px; top:64px;"),
        clip("a-eng", 0.6, 22.6, '<div id="a-engine" class="a-box"><div id="a-engine-title">One Python service <small>FastAPI</small></div>'
             + "".join(f'<div class="a-step" id="a-step-{i}" style="left:{x - 690}px; top:{y - 170}px;"><b>{s}</b><span>{n}</span></div>'
                       for i, ((x, y), s, n) in enumerate(zip(step_xy, steps, notes)))
             + '<div id="a-states">' + "".join(f'<div class="a-state" id="a-st-{i}">{s}</div>' for i, s in enumerate(states)) + "</div></div>",
             style="position:absolute; inset:0;", attrs="data-layout-allow-overlap"),
        clip("a-db", 3.0, 20.2, f'<div class="a-box a-store" style="left:1580px; top:200px;">{icon("database-fill", 40, "#0f6b5c")}<b>Postgres + PostGIS</b><span>Cases, audit log</span></div>'
             f'<div class="a-box a-store" style="left:1580px; top:404px;">{icon("clock-countdown-fill", 40, "#0f6b5c")}<b>Scheduler</b><span>Deadlines in the DB</span></div>'
             f'<div class="a-box a-store" style="left:1580px; top:608px;">{icon("map-pin-fill", 40, "#0f6b5c")}<b>Dashboard</b><span>Map, audit trail</span></div>',
             style="position:absolute; inset:0;"),
        clip("a-chans", 5.5, 17.7, "".join(
            f'<div class="a-box a-chan" style="left:110px; top:{y}px;">{icon(ic, 46, "#0f6b5c")}{label}</div>'
            for (ic, label), y in zip(chan, chan_y))
             + '<div class="mono soft" style="position:absolute; left:110px; top:712px; font-size:28px;">all become one message</div>',
             style="position:absolute; inset:0;"),
        clip("a-tokens", 7.4, 2.8, "".join(f'<div class="a-token" id="a-tok-{i}" style="left:{400 - 11}px; top:{y + 52 - 11}px;"></div>' for i, y in enumerate(chan_y)),
             style="position:absolute; inset:0;", attrs="data-layout-allow-overlap"),
        clip("a-call1", 15.4, 7.8, '<div class="a-call"><b>Model slow or down?</b> The case is routed anyway, flagged for a person.</div>',
             style="position:absolute; left:1000px; top:800px;"),
        clip("a-end", 20.9, 2.3, f'<div class="display teal" style="font-size:40px;">{words("Nothing waits. Nothing is lost.")}</div>',
             style="position:absolute; left:1060px; top:96px;"),
        clip("a-call2", 18.7, 4.5, '<div class="a-call"><b>A message fails to send?</b> The case is already saved. A job picks it up.</div>',
             style="position:absolute; left:110px; top:800px;"),
    ]
    js = """
    tl.fromTo("#a-title .w", { yPercent: 110 }, { yPercent: 0, duration: 0.6, ease: "expo.out", stagger: 0.06 }, 0.3);
    tl.fromTo("#a-engine", { opacity: 0, scale: 0.97, transformOrigin: "50% 50%" }, { opacity: 1, scale: 1, duration: 0.7, ease: "expo.out" }, 0.6);
    tl.fromTo(".a-step", { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: 0.45, ease: "expo.out", stagger: 0.08 }, 1.0);
    tl.fromTo(".a-state", { opacity: 0 }, { opacity: 1, duration: 0.3, stagger: 0.05 }, 1.6);
    tl.fromTo(".a-store", { opacity: 0, x: 24 }, { opacity: 1, x: 0, duration: 0.5, ease: "expo.out", stagger: 0.12 }, 3.0);
    tl.fromTo(".a-chan", { opacity: 0, x: -24 }, { opacity: 1, x: 0, duration: 0.5, ease: "expo.out", stagger: 0.4 }, 5.5);
    // Three messages travel in, become one, and enter the engine.
    [0, 1, 2].forEach((i) => {
      tl.fromTo(`#a-tok-${i}`, { x: 0, y: 0, scale: 0 }, { scale: 1, duration: 0.2 }, 7.4 + i * 0.12);
      tl.to(`#a-tok-${i}`, { x: 180, y: 400 - [220, 400, 580][i], duration: 0.8, ease: "power3.inOut" }, 7.6 + i * 0.12);
      tl.to(`#a-tok-${i}`, { x: 330, duration: 0.6, ease: "power2.in" }, 8.7);
      tl.to(`#a-tok-${i}`, { scale: 0, duration: 0.2 }, 9.25);
    });
    [0, 1, 2, 3, 4, 5].forEach((i) => {
      tl.to(`#a-step-${i}`, { borderColor: "#0f6b5c", backgroundColor: "#f6fbf9", duration: 0.25 }, 9.4 + i * 0.32);
    });
    [0, 1, 2, 3, 4].forEach((i) => {
      tl.to(`#a-st-${i}`, { backgroundColor: "#0f6b5c", color: "#f3f6f4", borderColor: "#0f6b5c", duration: 0.2 }, 11.9 + i * 0.5);
    });
    tl.to("#a-step-1", { borderColor: "#d8432a", duration: 0.25 }, 15.4);
    document.querySelectorAll(".a-call").forEach((c) => {
      const host = c.parentElement; const s = +host.dataset.start;
      tl.fromTo(c, { y: 16, opacity: 0 }, { y: 0, opacity: 1, duration: 0.5, ease: "expo.out" }, s);
    });
    tl.fromTo("#a-end .w", { yPercent: 110 }, { yPercent: 0, duration: 0.6, ease: "expo.out", stagger: 0.06 }, 20.9);
"""
    scene(sid, dur, css, "\n".join(body_parts), js)


# ================================================================ 7. honest status
def build_honest() -> None:
    sid, dur = "honest", 8.2
    rows = [
        (0.5, "warning-circle-fill", "#4a5c57", "Placeholders", "Rescue teams, zones and health centres in this demo."),
        (2.9, "hourglass-medium-fill", "#b07d00", "Waiting", "WhatsApp replies, until Meta verifies the business."),
        (5.6, "check-circle-fill", "#0f6b5c", "Working today", "Report, triage, merge, route, escalate, resolve."),
    ]
    css = """
    .hn-row { display: flex; align-items: center; gap: 30px; }
    .hn-row b { display: block; font: 780 52px "Bricolage Grotesque", sans-serif; letter-spacing: -0.02em; }
    .hn-row span { font: 500 34px "Geist", sans-serif; color: #4a5c57; }
"""
    body = clip("hn-title", 0.2, 8.0, f'<div class="display" style="font-size:72px;">{words("What is real today.")}</div>',
                style="position:absolute; left:160px; top:150px;") + "\n" + "\n".join(
        clip(f"hn-r{i}", t, dur - t, f'<div class="hn-row">{icon(ic, 72, col)}<div><b>{head}</b><span>{text}</span></div></div>',
             style=f"position:absolute; left:160px; top:{330 + i * 190}px;")
        for i, (t, ic, col, head, text) in enumerate(rows))
    js = """
    tl.fromTo("#hn-title .w", { yPercent: 110 }, { yPercent: 0, duration: 0.6, ease: "expo.out", stagger: 0.06 }, 0.2);
    document.querySelectorAll(".hn-row").forEach((r) => {
      const s = +r.parentElement.dataset.start;
      tl.fromTo(r, { x: -30, opacity: 0 }, { x: 0, opacity: 1, duration: 0.6, ease: "expo.out" }, s);
    });
    tl.to(".hn-row, #hn-title > div", { opacity: 0, duration: 0.35, ease: "power2.in" }, 7.8);
"""
    scene(sid, dur, css, body, js)


# ================================================================ 8. finale (end card)
def build_finale() -> None:
    sid, dur = "finale", 8.6
    css = """
    #f-box { position: relative; width: 230px; height: 230px; border-radius: 56px; background: #dfe9e5; overflow: hidden;
      box-shadow: 0 30px 70px -30px rgba(15,107,92,.55); }
    #f-fill { position: absolute; inset: 0; background: #0f6b5c; }
    #f-paw { position: absolute; left: 50%; top: 50%; margin: -70px 0 0 -70px; }
"""
    body = "\n".join([
        clip("f-mark", 0.3, 8.3, f'<div id="f-box"><div id="f-fill"></div>{icon("paw-print-fill", 140, "#f3f6f4", "id=\"f-paw\"")}</div>',
             style="position:absolute; left:845px; top:200px;"),
        clip("f-word", 1.3, 7.3, '<div class="display" style="font-size:128px; white-space:nowrap;">PawSOS <span class="teal">Goa</span></div>',
             style="position:absolute; left:0; right:0; top:470px; text-align:center;"),
        clip("f-line", 2.3, 6.3, f'<div class="display" style="font-size:56px;">{words("One number. Every report heard.")}</div>',
             style="position:absolute; left:0; right:0; top:640px; text-align:center;"),
        clip("f-url", 4.0, 4.6, '<div class="mono teal" style="font-size:40px;">Try it: goa.ayushchougula.in</div>',
             style="position:absolute; left:0; right:0; top:760px; text-align:center;"),
    ])
    js = """
    tl.fromTo("#f-box", { scale: 0.7, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.6, ease: "expo.out", transformOrigin: "50% 50%" }, 0.3);
    tl.fromTo("#f-fill", { yPercent: 100 }, { yPercent: 0, duration: 0.8, ease: "power3.inOut" }, 0.55);
    tl.fromTo("#f-paw", { scale: 0.3, opacity: 0, transformOrigin: "50% 50%" }, { scale: 1, opacity: 1, duration: 0.6, ease: "back.out(2)" }, 1.0);
    tl.fromTo("#f-word > div", { clipPath: "inset(0 100% 0 0)" }, { clipPath: "inset(0 0% 0 0)", duration: 0.8, ease: "power3.inOut" }, 1.3);
    tl.fromTo("#f-line .w", { yPercent: 110 }, { yPercent: 0, duration: 0.6, ease: "expo.out", stagger: 0.07 }, 2.3);
    tl.fromTo("#f-url > div", { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: 0.5, ease: "expo.out" }, 4.0);
"""
    scene(sid, dur, css, body, js)


# ================================================================ captions
def caption_chunks() -> list[tuple[float, float, str]]:
    chunks = []
    for lid, start in VO_START.items():
        text = SCRIPT[lid].replace("Paw S.O.S.", "PawSOS")
        dur = VOICE[lid]["duration"] - 0.25
        parts = [p.strip() for p in re.split(r"(?<=[.?!])\s+", text) if p.strip()]
        # Join short sentences so each chunk is about one line of reading.
        merged, cur = [], ""
        for p in parts:
            if cur and len(cur) + len(p) > 64:
                merged.append(cur); cur = p
            else:
                cur = f"{cur} {p}".strip()
        merged.append(cur)
        total = sum(len(m) for m in merged)
        t = start + 0.1
        for m in merged:
            d = dur * len(m) / total
            chunks.append((round(t, 2), round(d, 2), m))
            t += d
    return chunks


def build_captions() -> None:
    sid = "captions"
    css = """
    #root { background: transparent; }
    .cap { position: absolute; left: 0; right: 0; bottom: 58px; text-align: center; }
    .cap span { display: inline-block; max-width: 1500px; background: rgba(16,33,30,.86); color: #f3f6f4;
      font: 500 34px/1.3 "Geist", sans-serif; padding: 10px 22px; border-radius: 12px; }
"""
    body = "\n".join(clip(f"cap-{i}", s, d, f"<span>{t}</span>", cls="cap", attrs="data-layout-allow-caption-zone")
                     for i, (s, d, t) in enumerate(caption_chunks()))
    scene(sid, TOTAL, css, body, "")


# ================================================================ root
def build_root() -> None:
    hosts = "\n".join(
        f'      <div id="{sid}" data-composition-id="{sid}" data-composition-src="compositions/{sid}.html" '
        f'data-start="{s}" data-duration="{d}" data-track-index="{1}" data-track-kind="graphics" data-width="{W}" data-height="{H}"></div>'
        for sid, s, d in SCENES)
    audio = "\n".join(
        f'      <audio id="vo-{lid}" class="clip" src="assets/voice/{lid}.wav" data-start="{s}" '
        f'data-duration="{VOICE[lid]["duration"]}" data-track-index="10" data-volume="0.708"></audio>'
        for lid, s in VO_START.items())
    html = f"""<!doctype html>
<html lang="en-IN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/gsap.min.js"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: #f3f6f4; }}
      #root {{ position: relative; width: 100%; height: 100%; }}
      #ground {{ position: absolute; inset: 0; background: #f3f6f4; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="{W}" data-height="{H}">
      <div id="ground"></div>
{hosts}
      <div id="captions" data-composition-id="captions" data-composition-src="compositions/captions.html" data-start="0"
        data-duration="{TOTAL}" data-track-index="5" data-track-kind="captions" data-width="{W}" data-height="{H}" style="z-index: 100;"></div>
{audio}
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      window.__timelines["main"] = gsap.timeline({{ paused: true }});
    </script>
  </body>
</html>
"""
    (HERE / "index.html").write_text(html)


for f in (build_hook, build_tension, build_reveal, build_product, build_officials, build_arch,
          build_honest, build_finale, build_captions, build_root):
    f()
print("built", sorted(p.name for p in COMP.glob("*.html")))
print("product beats:", {k: media_to_local(E[k]) for k in ("triage_reply", "merged", "escalated", "accepted", "on_site", "resolved")})
