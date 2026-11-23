from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

NAVY = RGBColor(0x0B, 0x2E, 0x59)
TEAL = RGBColor(0x0F, 0x9D, 0x8F)
INK = RGBColor(0x22, 0x22, 0x22)
GREY = RGBColor(0x66, 0x66, 0x66)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]


def box(slide, x, y, w, h, text, size=20, color=INK, bold=False, align=None):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    lines = text if isinstance(text, list) else [text]
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = line
        p.font.size = Pt(size)
        p.font.color.rgb = color
        p.font.bold = bold
        p.space_after = Pt(10)
        if align:
            p.alignment = align
    return tb


def header(slide, title):
    bar = slide.shapes.add_shape(1, 0, 0, prs.slide_width, Inches(1.2))
    bar.fill.solid()
    bar.fill.fore_color.rgb = NAVY
    bar.line.fill.background()
    box(slide, 0.6, 0.25, 12, 0.8, title, size=32, color=WHITE, bold=True)


def slide_content(title, bullets, size=22):
    s = prs.slides.add_slide(BLANK)
    header(s, title)
    box(s, 0.8, 1.6, 11.8, 5.5, ["•  " + b for b in bullets], size=size)
    return s


# 1. Title
s = prs.slides.add_slide(BLANK)
bg = s.shapes.add_shape(1, 0, 0, prs.slide_width, prs.slide_height)
bg.fill.solid()
bg.fill.fore_color.rgb = NAVY
bg.line.fill.background()
box(s, 0.9, 2.3, 11.5, 1.2, "PawSOS Goa", size=54, color=WHITE, bold=True)
box(s, 0.9, 3.5, 11.5, 1.0,
    "One WhatsApp number for animal emergencies across Goa", size=26, color=WHITE)
box(s, 0.9, 4.6, 11.5, 0.8,
    "Goa AI Hackathon 2026  |  Track 3: AI-Powered Emergency Management for Animal Welfare",
    size=18, color=TEAL)

# 2. Problem
slide_content("The problem", [
    "Goa recorded 19,368 dog bite cases in 2025, about one every 27 minutes (Goa Legislative Assembly, LAQ 097).",
    "Sterilisation is uneven: Canacona, Sankhalim, Valpoi and Mapusa held zero camps in 2025.",
    "Helplines are fragmented: each municipality runs its own number, some with limited hours.",
    "Rescue teams get scattered, duplicate reports, and the reporter never hears what happened.",
])

# 3. Solution
slide_content("The solution", [
    "One Goa-wide WhatsApp number. No app to install.",
    "Citizen sends a photo and live location, or a voice note in Konkani, Marathi, Hindi or English.",
    "AI triages the case and gives 2 to 3 safe first-aid steps. It never claims a diagnosis.",
    "Duplicates are merged, the zone's team is alerted, and the reporter gets updates until resolved.",
])

# 4. How it works
slide_content("How a report moves", [
    "1. Report: photo and location arrive on WhatsApp; a case opens.",
    "2. Triage: species, injury, urgency, aggression risk, first-aid steps.",
    "3. Dedup: a similar open case within 200 m and 2 hours absorbs the report.",
    "4. Route: the zone's team gets Accept / Decline buttons.",
    "5. Escalate: no answer in 10 minutes, or a closed team, goes to the next team, then the taluka officer.",
    "6. Close the loop: accepted, on site, resolved, each sent to every reporter.",
], size=20)

# 5. Bite flow and booking
slide_content("Beyond emergencies", [
    "Bite flow: a bite report sends the nearest health centre offering anti-rabies treatment, and flags a bite hotspot.",
    "Camp booking: a pet owner replies BOOK and picks a sterilisation or vaccination slot; a reminder goes out the day before.",
    "Officials' dashboard: map of bites, rescues and camps; case list with filters; sterilisation counts; a suggestion for the next camp.",
])

# 6. AI approach
slide_content("How AI is used", [
    "Claude vision (claude-haiku-5-5) reads the photo and returns a fixed JSON schema.",
    "The output is checked with Pydantic; one retry on invalid output, then a person is alerted at high urgency.",
    "Prompt and copy forbid any diagnosis; only safe first-aid steps are sent.",
    "Routing, dedup, escalation and the case state machine are rules, not AI.",
])

# 7. Status
slide_content("Where it stands (honest status)", [
    "Built and tested: case flow, dedup, routing, escalation, bite flow, booking, dashboard, Konkani, Marathi and Hindi replies.",
    "Tested against stand-ins: Claude triage, WhatsApp Cloud API, Bhashini speech-to-text.",
    "Not yet run live: the Claude photo call, a real WhatsApp number, Bhashini keys, Google Calendar sync.",
    "Nothing has been checked by hand by a person yet; translations need a fluent reader.",
], size=21)

# 8. Pilot and ask
slide_content("Pilot proposal", [
    "Start in one urban local body: Panaji, with its partner team.",
    "Run alongside the existing helpline, with the team's agreement and the council's.",
    "Track: median minutes to team acceptance, share of reports merged, share of cases where the reporter got every update, bite referrals the same day.",
    "Extend to the next municipality only after the pilot shows it works.",
])

# 9. Close
s = prs.slides.add_slide(BLANK)
bg = s.shapes.add_shape(1, 0, 0, prs.slide_width, prs.slide_height)
bg.fill.solid()
bg.fill.fore_color.rgb = NAVY
bg.line.fill.background()
box(s, 0.9, 2.6, 11.5, 1.0, "One number. Every report heard.", size=44, color=WHITE, bold=True)
box(s, 0.9, 3.9, 11.5, 1.0, "Thank you  |  Ayush Chougula", size=24, color=TEAL)

prs.save("/Users/ayushchougula/Desktop/Ayush/Projects/PawSOS-Goa/docs/pitch/PawSOS_Goa_deck.pptx")
print("saved")
