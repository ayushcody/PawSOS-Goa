# Telegram setup

Telegram is the live channel for the demo (D-092). It needs no business verification, no payment and no public address. Checked against Telegram's Bot API documentation on 16 Nov 2026 (Bot API 10.4). **Not yet tried with a real bot.**

## 1. Create the bot (about two minutes, on your phone)

1. In Telegram, open a chat with **@BotFather** (the one with the blue tick).
2. Send `/newbot`.
3. Give it a name people will see, for example `PawSOS Goa`.
4. Give it a username ending in `bot`, for example `pawsos_goa_bot`. It must be unused.
5. BotFather replies with a **token**, a long string with a colon in it. Treat it like a password: anyone who has it controls the bot.

## 2. Put the token in `.env`

Open `.env` and set these two lines. Do not paste the token into a chat or commit it.

```
CHANNEL=telegram
TELEGRAM_BOT_TOKEN=<the token from BotFather>
```

## 3. Start the server

```bash
docker compose up -d
```

```bash
.venv/bin/uvicorn app.main:app --port 8040
```

Check `http://localhost:8040/health`: it should say `"telegram_ready": true`.

There is no webhook and no tunnel. The server asks Telegram for new messages every few seconds ("long polling"), so it works from a laptop on any network.

## 4. Try it

1. In Telegram, search for your bot's username and press **Start**. It replies with the welcome message.
2. Send a photo of an animal.
3. Tap **Send my location** when the button appears under the reply.
4. You get a case number and the triage result.

The placeholder rescue teams still live in the simulator: open `http://localhost:8040/sim`, pick the team for that area and press Accept, On site, Resolved. The status updates, the rating buttons and the team's photo arrive in Telegram.

## Good to know

- **Who is who:** a person on Telegram has no phone number we can see. They are stored as `tg:<chat id>`.
- **Private chats only:** the bot ignores groups.
- **Photos sent "as a file"** are not accepted yet (an open `TODO(me)`). Send them as ordinary photos.
- **Voice notes** work the same way as on WhatsApp and need Bhashini set up (`docs/VOICE_SETUP.md`).
- **If the token leaks:** send `/revoke` to @BotFather, pick the bot, and put the new token in `.env`.
- **Only one server per bot:** two servers polling the same bot take each other's messages.
