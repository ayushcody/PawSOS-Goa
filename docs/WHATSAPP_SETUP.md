# Connecting real WhatsApp

This connects PawSOS to a Meta test number, so a message from your own phone reaches the server on your laptop. Allow 30 to 45 minutes the first time. Meta's and ngrok's screens change often, so a label may differ slightly from what is written here.

Written against Meta's documentation on 11 Nov 2026 (Graph API v27.0). **Not yet run end to end**: until someone completes the last section, treat this as untested.

## How it fits together

```
your phone --WhatsApp--> Meta --HTTPS--> ngrok --> localhost:8040/webhooks/whatsapp
your phone <--WhatsApp-- Meta <--HTTPS-- PawSOS (Graph API)
```

- **Webhook.** Meta calls our server each time someone messages the number. Meta needs a public HTTPS address, which a laptop does not have.
- **ngrok.** A small program that gives your laptop a temporary public HTTPS address and forwards it to port 8040.
- **Placeholder teams stay in the simulator.** Their numbers are invented, so their alerts appear at `/sim`. You report from your phone, accept as the team in the simulator, and the status update comes back to your phone.

## Rules for secrets

- Every value below goes in `.env`, which git ignores. Never paste one into chat, a commit, a screenshot or a slide.
- Your own phone number will be stored in your local database once you message the test number. That database stays on your laptop.

## Part 1. ngrok

1. Go to `https://ngrok.com` and sign up for a free account.
2. Install it. On a Mac with Homebrew:
   ```bash
   brew install ngrok
   ```
3. In the ngrok dashboard, open **Your Authtoken**, copy the command shown there (it starts `ngrok config add-authtoken`), and run it in your own terminal. Do this once.
4. Start the tunnel and leave this terminal open:
   ```bash
   ngrok http 8040
   ```
5. Copy the **Forwarding** address, which looks like `https://something.ngrok-free.app`. This is your public address.

On the free plan this address can change each time ngrok restarts. When it does, repeat Part 3 step 2 and Part 4 step 3. If your ngrok dashboard offers a free static domain, use the command it shows for that domain and the address will stay the same.

## Part 2. Meta app and test number

1. Go to `https://developers.facebook.com`, log in, and open **My Apps**, then **Create App**.
2. Choose the use case that mentions WhatsApp (for example "Connect with customers through WhatsApp"). If asked for a business portfolio, create one or pick an existing one. Finish the wizard.
3. In the app's left menu open **WhatsApp**, then **API Setup**. Meta gives you a test number. On this page:
   - Under **From**, note the **Phone number ID** (a long number, not the phone number itself).
   - Under **To**, add your own phone number and enter the code WhatsApp sends you. A test number can only message numbers added here.
   - Press **Generate access token** and copy it. This temporary token stops working after some hours (Meta's docs say only that it must be regenerated "every few hours"), so generate a fresh one on demo day.
4. In the left menu open **App settings**, then **Basic**. Next to **App secret** press **Show** and copy it.
5. Make up a verify token. Any long random string works; this prints one:
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(24))"
   ```

## Part 3. Put the values in `.env`

1. If you have no `.env` yet:
   ```bash
   cp .env.example .env
   ```
2. Open `.env` in your editor and set these lines:
   ```
   CHANNEL=whatsapp
   PUBLIC_BASE_URL=<your ngrok https address, no trailing slash>
   DASHBOARD_PASSWORD=<a password you choose>
   WHATSAPP_ACCESS_TOKEN=<the access token>
   WHATSAPP_PHONE_NUMBER_ID=<the phone number ID>
   WHATSAPP_VERIFY_TOKEN=<the verify token you made up>
   WHATSAPP_APP_SECRET=<the app secret>
   ```
   `DASHBOARD_PASSWORD` matters now: with ngrok running, anyone who has the address can reach the server. The password protects `/sim` and `/dashboard`.
3. Restart the server:
   ```bash
   .venv/bin/uvicorn app.main:app --port 8040
   ```
4. Check it picked the settings up:
   ```bash
   curl -s localhost:8040/health
   ```
   You should see `"whatsapp_ready":true`. If it says `false`, the server's terminal names the setting that is missing.

## Part 4. Point Meta at your server

1. The server and ngrok must both be running.
2. In the Meta app, open **WhatsApp**, then **Configuration**.
3. Under **Webhook**, press **Edit**. Set:
   - **Callback URL**: your ngrok address followed by `/webhooks/whatsapp`
   - **Verify token**: the verify token from your `.env`
4. Press **Verify and save**. Meta calls your server once; if the tokens match it saves.
5. Under **Webhook fields**, find **messages** and press **Subscribe**. Without this, Meta sends nothing.

## Part 5. The end-to-end run

1. On your phone, send `hi` to the test number. You should get the welcome message.
2. Send a photo of an animal, then share your location (the paper-clip or plus button, then **Location**, then **Send your current location**). You should get a case ID such as `PAW-0046`.
   - Outside Goa? The app accepts any location until `in_goa()` is written, so this works from anywhere for now.
3. Open `http://localhost:8040/sim` (it will ask for the password; any user name works). Choose the partner team for the area you were placed in. Its alert should be there with **Accept** and **Decline**.
4. Press **Accept**. Your phone should get "accepted and on the way". Press **On site**, then **Resolved**, and check each update reaches your phone.
5. Open `http://localhost:8040/dashboard` and find your case on the map, without a "demo" tag.

When this works, tell Claude, so `docs/PLAN.md` can record that the real run has been done.

## If something goes wrong

| What you see | Likely cause | Fix |
|---|---|---|
| **Verify and save** fails | Server or ngrok not running; verify token differs; `CHANNEL` is not `whatsapp` | Check `curl -s localhost:8040/health` shows `"whatsapp_ready":true`; compare the token in `.env` with the one typed into Meta |
| Message sent, no reply, nothing in the server's terminal | **messages** field not subscribed, or the ngrok address changed | Part 4 step 5; or update the callback URL and `PUBLIC_BASE_URL` |
| Server terminal shows `403` for `POST /webhooks/whatsapp` | Wrong app secret in `.env` | Copy it again from **App settings**, **Basic**, and restart |
| Server terminal shows `WhatsApp refused a message … (401)` | The access token has expired | Generate a new one on **API Setup**, put it in `.env`, restart |
| `WhatsApp refused a message` with a reason about the recipient | Your phone is not on the **To** list | Part 2 step 3 |
| "Sorry, I could not read that photo" | The photo was not JPEG, PNG or WebP, or is over 10 MB | Send an ordinary camera photo |
| Replies stop after a day of silence | WhatsApp only allows free-form replies within 24 hours of the person's last message | Send any message from the phone to reopen the window, or set up the templates below |
| Server terminal shows `no template is configured for team_alert` | The 24-hour window is closed and `WHATSAPP_TEMPLATE_TEAM_ALERT` is empty | Create the template (next section) and put its name in `.env` |
| A template send fails with `132001` | The template is not approved yet, or its name or language differs from `.env` | Check the name and language in WhatsApp Manager; the language must match `WHATSAPP_TEMPLATE_LANGUAGE` exactly (`en` is not `en_US`) |
| A template send fails with `132000` | The template has a different number of `{{n}}` placeholders from the list below | Edit the template so its body matches the text below exactly |

## Templates for the 24-hour window

**Not yet tried against Meta.** The code and this section were written from Meta's documentation on 11 Nov 2026 (Graph API v27.0); no template has been created, approved or sent.

WhatsApp lets PawSOS send an ordinary message only to someone who has written to the number in the last 24 hours. Outside that window Meta refuses it (error `131047`, "Re-engagement message") and only pre-approved **template** messages go through. Rescue teams are the people most likely to be outside the window: a team that has not tapped anything for a day cannot receive a new case alert.

What PawSOS does: it sends the normal message first. If Meta refuses it with `131047`, straight away or later in a delivery-status webhook, PawSOS sends the matching template once instead. If no template is configured for that message, it logs `no template is configured for …` and the message is not delivered, as before. Only real numbers are affected; invented `+91000000` numbers always go to the simulator.

### Creating them

In Meta Business Manager open **WhatsApp Manager**, then **Message templates**, then **Create template**. For each template below choose category **Utility**, language **English** (code `en`), and type the body exactly as shown, with each line break. Meta asks for an example value for every `{{n}}`; the examples below are invented. Approval usually takes minutes but can take longer, and a template Meta judges to be marketing may be re-categorised or rejected.

Then put the names in `.env` and restart:

```
WHATSAPP_TEMPLATE_LANGUAGE=en
WHATSAPP_TEMPLATE_TEAM_ALERT=pawsos_team_alert
WHATSAPP_TEMPLATE_TEAM_ALERT_EXPIRED=pawsos_team_alert_expired
WHATSAPP_TEMPLATE_BOOK_REMINDER=pawsos_camp_reminder
```

The names are suggestions; any lowercase name with underscores works as long as `.env` matches. The order of the `{{n}}` placeholders matters: PawSOS fills them in the order listed in `app/channels/templates.py`.

#### 1. `pawsos_team_alert` (a new case for a rescue team)

Body:

```
New case {{1}} in {{2}}. Urgency: {{3}}.
{{4}}
Location: {{5}}
Reports so far: {{6}}.
Please answer within {{7}} using the buttons below.
```

| Placeholder | Filled with | Example for Meta |
|---|---|---|
| `{{1}}` | case ID | `PAW-0042` |
| `{{2}}` | zone | `Panaji` |
| `{{3}}` | urgency | `HIGH` |
| `{{4}}` | what the photo shows, and the reporter's own words, on one line | `From the photo (not a diagnosis): dog, wound on the leg. Reporter says: "Near the bus stand."` |
| `{{5}}` | map link | `https://maps.google.com/?q=15.49090,73.82780` |
| `{{6}}` | number of reports | `1` |
| `{{7}}` | time to answer | `10 minutes` |

Buttons: add two **Quick reply** buttons, in this order: `Accept`, then `Decline`. The order matters: PawSOS sends `accept:<case ID>` to the first and `decline:<case ID>` to the second, and a tap comes back to the webhook carrying that value, exactly like the buttons on the normal alert.

The template cannot carry the photo, so a team alerted this way sees the text and buttons but not the photo. A template line cannot contain line breaks, so `{{4}}` puts the photo assessment and the reporter's words on one line, trimmed to 600 characters.

#### 2. `pawsos_team_alert_expired` (the team did not answer in time)

Body:

```
No answer was received in time, so case {{1}} has been passed to the next team. No action is needed.
```

| Placeholder | Filled with | Example for Meta |
|---|---|---|
| `{{1}}` | case ID | `PAW-0042` |

No buttons.

#### 3. `pawsos_camp_reminder` (a camp booking reminder)

Body:

```
Reminder: your pet's camp slot is coming up.
{{1}}
{{2}}, {{3}}
{{4}}
Reference {{5}}. Please bring your pet on a leash or in a carrier.
```

| Placeholder | Filled with | Example for Meta |
|---|---|---|
| `{{1}}` | camp name | `Panaji sterilisation camp` |
| `{{2}}` | date | `Sat 21 Nov` |
| `{{3}}` | time | `10:00 to 10:30` |
| `{{4}}` | venue | `Community hall, Panaji` |
| `{{5}}` | booking reference | `BK-0007` |

No buttons. The reminder in `app/booking/flow.py` attaches this template. The normal reminder is sent in the person's chosen language, but the template is in `WHATSAPP_TEMPLATE_LANGUAGE` (English), so someone outside the window gets the reminder in English.

## Limits to know about

- **24-hour window.** Outside it, WhatsApp only allows pre-approved template messages. PawSOS falls back to a template for team alerts, "no answer in time" notices and camp reminders when one is configured (previous section); every other message outside the window is still refused. On the simulator everything works.
- **The fallback is remembered in memory.** When Meta reports the refusal later (in a status webhook) rather than at once, PawSOS needs to remember the message to retry it. A server restart in between forgets it, and that one message is lost.
- **Sending photos out over WhatsApp is untested.** It uses a link to your ngrok address, and ngrok's free plan may show a warning page in place of the photo. It does not affect the run above: only teams are sent photos, and the placeholder teams are in the simulator.
- **Test number only.** Moving to a real number needs Meta business verification, which is outside the hackathon.
