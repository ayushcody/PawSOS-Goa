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
| Replies stop after a day of silence | WhatsApp only allows free-form replies within 24 hours of the person's last message | Send any message from the phone to reopen the window |

## Limits to know about

- **24-hour window.** Outside it, WhatsApp only allows pre-approved template messages, which PawSOS does not use yet. A camp reminder sent the day before to someone who booked several days earlier will be refused by WhatsApp. On the simulator it works.
- **Sending photos out over WhatsApp is untested.** It uses a link to your ngrok address, and ngrok's free plan may show a warning page in place of the photo. It does not affect the run above: only teams are sent photos, and the placeholder teams are in the simulator.
- **Test number only.** Moving to a real number needs Meta business verification, which is outside the hackathon.
