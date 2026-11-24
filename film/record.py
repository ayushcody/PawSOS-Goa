"""Record the real product for the film: the public demo sandbox and the officials' dashboard.

    python record.py http://localhost:8043

Writes raw/sandbox.webm, raw/dashboard.webm and raw/events.json (seconds from the start of
each recording for every event, so the edit cuts on what happened, not on guesses).
Nothing is staged: every reply comes from the running app, triage from the real model.
"""

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8043"
RAW = Path(__file__).with_name("raw")
RAW.mkdir(exist_ok=True)
VIEW = {"width": 2560, "height": 1600}  # a 1280x800 layout zoomed 2x: real 2560x1600 pixels
VIDEO = {"width": 2560, "height": 1600}

# A large visible cursor that follows the real mouse, so viewers see what is clicked.
CURSOR = """
(() => {
  const add = () => {
    if (document.getElementById('__cursor')) return;
    const c = document.createElement('div');
    c.id = '__cursor';
    c.innerHTML = '<svg width="34" height="34" viewBox="0 0 24 24"><path d="M4 2l15 9-6.5 1.5L9.5 19z" fill="#10211e" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    Object.assign(c.style, {position:'fixed', left:'0', top:'0', zIndex: 2147483647, pointerEvents:'none',
      transform:'translate(-200px,-200px)', transition:'transform .05s linear', filter:'drop-shadow(0 3px 6px rgba(0,0,0,.25))'});
    const ring = document.createElement('div');
    Object.assign(ring.style, {position:'fixed', width:'44px', height:'44px', margin:'-22px 0 0 -22px', borderRadius:'50%',
      border:'3px solid #0f6b5c', opacity:'0', zIndex: 2147483646, pointerEvents:'none', left:'0', top:'0'});
    document.body.append(c, ring);
    addEventListener('mousemove', e => { c.style.transform = `translate(${e.clientX - 4}px, ${e.clientY - 3}px)`; }, true);
    addEventListener('mousedown', e => {
      ring.style.left = e.clientX + 'px'; ring.style.top = e.clientY + 'px';
      ring.animate([{opacity: .9, transform: 'scale(.4)'}, {opacity: 0, transform: 'scale(1.4)'}], {duration: 450, easing: 'ease-out'});
    }, true);
  };
  document.readyState === 'loading' ? addEventListener('DOMContentLoaded', add) : add();
})();
"""


class Clock:
    def __init__(self) -> None:
        self.t0 = time.monotonic()
        self.events: dict[str, float] = {}

    def mark(self, name: str) -> None:
        self.events[name] = round(time.monotonic() - self.t0, 2)
        print(f"{self.events[name]:7.2f}s  {name}")


def glide(page, selector: str, steps: int = 28) -> None:
    box = page.locator(selector).first.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=steps)
    page.wait_for_timeout(250)


def click(page, selector: str) -> None:
    glide(page, selector)
    page.mouse.down()
    page.wait_for_timeout(90)
    page.mouse.up()


def wait_text(page, chat: str, text: str, timeout: float = 90) -> None:
    try:
        page.wait_for_function(
            "([c, t]) => [...document.querySelectorAll(c + ' .msg')].some(m => m.textContent.includes(t))",
            arg=[chat, text], timeout=timeout * 1000,
        )
    except Exception:
        page.screenshot(path=str(RAW / "fail.png"))
        print("status line:", page.text_content("#sb-status") if page.query_selector("#sb-status") else "-")
        print("dom:", page.evaluate(f"[...document.querySelectorAll('{chat} .msg')].map(m => m.textContent.slice(0, 50))"))
        print("server c1:", page.evaluate("fetch('/sandbox/messages?who=c1').then(r => r.status + ' ' + r.statusText)"))
        print("server c1 tail:", page.evaluate("fetch('/sandbox/messages?who=c1').then(r => r.json()).then(j => j.slice(-4).map(m => m.text.slice(0, 50)))"))
        raise


with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome")
    ctx = browser.new_context(viewport=VIEW, device_scale_factor=1, color_scheme="light",
                              record_video_dir=str(RAW / "tmp"), record_video_size=VIDEO)
    ctx.add_init_script(CURSOR)
    page = ctx.new_page()
    clock = Clock()

    # ---------- the sandbox ----------
    page.goto(f"{BASE}/")
    page.evaluate("document.documentElement.style.scrollBehavior = 'auto'")
    # The film shows the demo itself: hide the site's sticky nav so nothing covers it.
    page.add_style_tag(content="html { zoom: 2; } .nav { display: none !important; }")
    page.wait_for_timeout(300)
    page.evaluate("document.getElementById('sandbox').scrollIntoView({block: 'start'}); window.scrollBy(0, -20)")
    page.mouse.move(1280, 1520)
    page.wait_for_timeout(1500)
    clock.mark("sandbox_ready")

    click(page, "#sb-sample")
    wait_text(page, "#sb-citizen", "photo received")
    clock.mark("photo_sent")
    page.wait_for_timeout(900)

    click(page, "#sb-loc")
    clock.mark("location_sent")
    wait_text(page, "#sb-citizen", "Case ID")
    clock.mark("case_created")
    wait_text(page, "#sb-citizen", "While you wait")
    clock.mark("triage_reply")
    wait_text(page, "#sb-team", "New case")
    clock.mark("team_alert")
    page.wait_for_timeout(3500)

    # A second person reports the same animal.
    click(page, ".seg button[data-who='c2']")
    page.wait_for_timeout(800)
    click(page, "#sb-sample")
    wait_text(page, "#sb-citizen", "photo received")
    page.wait_for_timeout(600)
    click(page, "#sb-loc")
    wait_text(page, "#sb-citizen", "already been reported")
    clock.mark("merged")
    page.wait_for_timeout(3000)
    click(page, ".seg button[data-who='c1']")
    clock.mark("back_to_citizen")

    # Nobody answers: wait for the escalation to the next team.
    page.mouse.move(1980, 1180, steps=30)  # park in the team chat's empty space, off every button
    first_team = page.eval_on_selector("#sb-teams", "s => s.value")
    page.wait_for_function("t => document.getElementById('sb-teams').value !== t", arg=first_team, timeout=120000)
    clock.mark("escalated")
    wait_text(page, "#sb-team", "New case")
    page.wait_for_timeout(2500)
    clock.mark("next_team_alert")

    for label, mark in [("Accept", "accepted"), ("On site", "on_site"), ("Resolved", "resolved")]:
        btn = f"#sb-team .msg-btns button:text-is('{label}'):not([disabled])"
        page.wait_for_selector(btn, timeout=30000)
        click(page, f"{btn} >> nth=-1")
        page.wait_for_timeout(2200)
        clock.mark(mark)

    wait_text(page, "#sb-citizen", "is resolved")
    page.wait_for_timeout(1200)
    page.eval_on_selector("#sb-citizen", "c => c.scrollTop = c.scrollHeight")
    page.wait_for_timeout(1200)
    good = "#sb-citizen .msg-btns button:text-is('Good')"
    page.wait_for_selector(good)
    # Scroll the chat itself (not the page) so the framing stays put.
    page.eval_on_selector("#sb-citizen", "c => { c.style.scrollBehavior = 'auto'; c.scrollTop = c.scrollHeight; }")
    page.wait_for_timeout(1000)
    click(page, f"{good} >> nth=-1")
    wait_text(page, "#sb-citizen", "rating for case")
    clock.mark("rated")
    page.wait_for_timeout(2500)
    # The first case is the one both reports ended up in (the second was merged into it).
    case_id = page.evaluate("fetch('/sandbox/session').then(r => r.json()).then(j => j.cases[0])")
    clock.mark("sandbox_end")
    sandbox_video = page.video
    page.close()

    # ---------- the dashboard ----------
    page = ctx.new_page()
    dash = Clock()
    page.goto(f"{BASE}/dashboard")
    page.add_style_tag(content="html { zoom: 2; }")
    page.wait_for_selector("table.cases tbody tr")
    page.mouse.move(800, 600)
    page.wait_for_timeout(2500)  # map tiles
    dash.mark("dashboard_ready")
    page.mouse.move(1040, 840, steps=40)
    page.wait_for_timeout(1500)
    page.mouse.wheel(0, 1040)
    page.wait_for_timeout(1800)
    dash.mark("case_list")
    sel = f'button[data-act="details"][data-id="{case_id}"]'
    page.locator(sel).scroll_into_view_if_needed()
    page.wait_for_timeout(800)
    click(page, sel)
    page.wait_for_timeout(1800)
    dash.mark("case_detail")
    page.mouse.move(2100, 1000, steps=20)
    page.mouse.wheel(0, 1400)
    page.wait_for_timeout(2500)
    page.mouse.wheel(0, 1800)
    page.wait_for_timeout(3000)
    dash.mark("audit_trail")
    dash_video = page.video
    page.close()
    ctx.close()

    sandbox_video.save_as(RAW / "sandbox.webm")
    dash_video.save_as(RAW / "dashboard.webm")
    browser.close()

(RAW / "events.json").write_text(json.dumps({"sandbox": clock.events, "dashboard": dash.events, "case": case_id}, indent=2))
print("case", case_id)
