"""Capture prototype screenshots for the hackathon submission from a running local server.

    python docs/submission/capture.py http://localhost:8043 PAW-0051

Needs Playwright (pip install playwright). Writes PNGs next to this file, in shots/.
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8043"
CASE = sys.argv[2] if len(sys.argv) > 2 else "PAW-0051"
OUT = Path(__file__).with_name("shots")
OUT.mkdir(exist_ok=True)


def sim_chat(page, persona_label: str, name: str, scroll_to_text: str | None = None) -> None:
    page.goto(f"{BASE}/sim")
    page.wait_for_selector("#persona option", state="attached")
    value = page.eval_on_selector(
        "#persona",
        "(s, label) => [...s.options].find(o => o.textContent.startsWith(label)).value",
        persona_label,
    )
    page.select_option("#persona", value)
    page.wait_for_timeout(1500)
    if scroll_to_text:
        # Put the named message near the top of the chat.
        page.evaluate(
            """(t) => { const chat = document.getElementById('chat');
                 const el = [...chat.querySelectorAll('*')].reverse().find(e => e.children.length === 0 && e.textContent.includes(t));
                 if (el) chat.scrollTop = el.getBoundingClientRect().top - chat.getBoundingClientRect().top + chat.scrollTop - 12; }""",
            scroll_to_text,
        )
        page.wait_for_timeout(400)
    page.screenshot(path=OUT / name)


with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome")  # the installed Google Chrome

    phone = browser.new_context(viewport={"width": 430, "height": 900}, device_scale_factor=2, color_scheme="light")
    page = phone.new_page()
    sim_chat(page, "Citizen 1", "2_citizen_report_and_triage.png", f"Case {CASE}:")
    sim_chat(page, "Tiswadi taluka officer", "3_escalated_alert_to_officer.png", f"New case {CASE}")
    phone.close()

    desk = browser.new_context(viewport={"width": 1600, "height": 1000}, device_scale_factor=1.5, color_scheme="light")
    page = desk.new_page()
    page.goto(f"{BASE}/")
    page.wait_for_timeout(9000)  # let the hero conversation play
    page.screenshot(path=OUT / "1_website_hero.png")

    page.goto(f"{BASE}/dashboard")
    page.wait_for_selector("table.cases tbody tr")
    page.wait_for_timeout(3000)  # map tiles
    page.screenshot(path=OUT / "4_dashboard_map_and_cases.png")

    page.click(f'button[data-act="details"][data-id="{CASE}"]')
    page.wait_for_timeout(2500)
    page.screenshot(path=OUT / "5_case_detail_audit_trail.png")
    desk.close()
    browser.close()

print("saved to", OUT)
