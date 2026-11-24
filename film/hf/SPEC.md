# PawSOS Goa: demo film spec

GOAL:    A judge who has never heard of PawSOS understands the problem, sees the real product
         handle one animal from report to resolved, understands how it is built, and knows what
         is real today. Ends wanting to try goa.ayushchougula.in.
OUTPUT:  HyperFrames, 1920 x 1080, 30 fps, MP4.
TIME:    130 s x 30 = 3900 frames. Narrated: the voice is the clock (Gemini TTS gemini-3.8-flash-tts,
         voice Charon, en-IN, Indian English). 18 lines, timings from film/voice_report.json.

LOOK:    The website's medium: product UI on a cool green-grey ground.
         Ground #f3f6f4 (flat, no texture). Ink #10211e. Soft ink #4a5c57. Line #d5dfdb.
         Brand teal #0f6b5c: structure, the mark, "resolved", active states.
         Coral #d8432a: urgency only (the 19,368, the zero-camp towns, a timed-out alert). One coral focus per frame.
         Display: Bricolage Grotesque 750-800, -3% tracking; hero numbers 300 px, titles 96-120 px, cards 44 px.
         Body: Geist 500, 30-34 px. Labels: Geist Mono 500 24 px.
         Product footage: real screen recordings at 2x density (2560x1600), shown at 1.0-2.0x with
         20 px radius and a teal-tinted shadow (0 30 70 -30, 45%). No 3D tilt, no glass.
OBJECTS: the real map of Goa (OSM boundary, seed/goa_boundary.json) with the 14 municipalities at
         their seed coordinates; a clock face with a sweeping hand; the paw mark (Phosphor paw-print,
         the site's logo) in a teal rounded square; the product's own chat, team alert and dashboard.
MOTION:  enter expo.out 0.7 s; move power3.inOut 0.6 s; exit power2.in 0.35 s; camera power3.inOut 0.7 s.
         Staggers 3-4 frames. One hero move per shot; secondaries travel 60% and start 0.15 s later.
SHOTS:
  0.0-11.4   hook: clock sweeps once while "Every 27 minutes" lands; 19,368 rolls up in coral; source line.
  11.4-27.8  tension: Goa's outline draws; 14 municipality dots pop one by one with a phone each;
             "Who do you call?"; Panaji's 8 am to 8 pm tag; four towns turn coral "0 camps in 2025".
  27.8-35.2  reveal: the 14 dots converge into one point that becomes the paw mark; wordmark wipes;
             "One WhatsApp number. No app to install."
  35.2-81.2  product: the real sandbox recording. Full view, push into the citizen chat for report and
             triage, hold through the merge, cut to the team chat for the alert, escalation sped up
             2.7x (labelled), accept/on site/resolved 2x, back to the citizen for the closed loop.
  81.2-90.0  officials: the real dashboard recording 1.8x, case list, case detail, audit trail.
  90.0-113.2 architecture: one service + one database draw; three channels send tokens into one
             message; six steps light in order; state machine strip; two failure callouts.
  113.2-121.4 honest: working today / waiting / placeholders, one line each.
  121.4-130  end: the mark is pressed in, the wordmark wipes, the line and the URL hold 3 s.
BANNED:  dark void; glow; purple or blue gradients; glass cards; three cards in a row; KPI grids;
         a title over a dimmed screenshot; product UI tilted in 3D; text that moves while read;
         everything fading in at once; logo docked in a corner; invented numbers or screens.
QA:      2.0 (clock + 27), 7.5 (19,368 settled), 18 (map with dots), 25 (coral towns), 31 (mark),
         47.5 (triage reply readable), 60 (merge), 63 (team alert), 70 (escalation), 79 (resolved),
         85 (dashboard), 108 (diagram), 117 (status), 127 (end card).
