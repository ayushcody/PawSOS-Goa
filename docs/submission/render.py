"""Render the submission files from the HTML in this folder (needs Playwright and Google Chrome).

    python docs/submission/render.py

Writes out/: PawSOS_Goa_Architecture.png and .pdf, PawSOS_Goa_Presentation.pdf,
PawSOS_Goa_Evidence_and_Status.pdf.
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome")
    page = browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)

    page.goto((HERE / "architecture.html").as_uri())
    page.wait_for_timeout(1500)  # web fonts
    page.screenshot(path=HERE / "architecture.png")  # used by the presentation
    page.screenshot(path=OUT / "PawSOS_Goa_Architecture.png")
    page.pdf(path=OUT / "PawSOS_Goa_Architecture.pdf", width="1920px", height="1080px", print_background=True)

    page.goto((HERE / "presentation.html").as_uri())
    page.wait_for_timeout(2000)
    page.pdf(path=OUT / "PawSOS_Goa_Presentation.pdf", width="1920px", height="1080px", print_background=True)

    page.goto((HERE / "supporting.html").as_uri())
    page.wait_for_timeout(1500)
    page.pdf(path=OUT / "PawSOS_Goa_Evidence_and_Status.pdf", format="A4", print_background=True,
             margin={"top": "18mm", "bottom": "18mm", "left": "16mm", "right": "16mm"})
    browser.close()

for f in sorted(OUT.iterdir()):
    print(f"{f.name:42} {f.stat().st_size / 1024:8.0f} KB")
