# Voice notes with Bhashini

How to turn on real speech recognition for WhatsApp voice notes, using Bhashini (the Government of India's language platform).

**Status: written from Bhashini's documentation (read 11 Nov 2026) and checked only against a stand-in. It has not been tried with real Bhashini keys or a real voice note.** Expect to correct this guide the first time you do it.

## What happens to a voice note

1. WhatsApp sends the voice note as OGG/Opus audio. We download it once.
2. `ffmpeg` turns it into 16 kHz mono WAV in memory (OGG/Opus is not in Bhashini's list of audio formats). Nothing is written to disk.
3. The first time, we ask Bhashini which speech models the pipeline has for each language (the "config call"). The answer is kept for 6 hours.
4. We send the WAV to Bhashini's speech recognition (the "compute call") and get the words back.
5. The words are said back to the person and kept with the report. The audio is dropped.

If any step fails (no keys, no ffmpeg, Bhashini slow or down, no model for that language), the person gets the usual "please type your message" reply. The simulator's pretend voice notes keep working whichever service is chosen.

## Language

WhatsApp does not say which language a voice note is in, so we use `BHASHINI_DEFAULT_LANGUAGE` (default `kok`, Konkani). Choose `mr`, `hi` or `en` instead if most callers will speak that. The language is recorded with the words.

Konkani: Bhashini lists speech models for "Goan Konkani" and "Konkani", and its language list (ULCA) has both codes `gom` and `kok`. We ask for whichever of the two the pipeline offers, `gom` first. Which one the default pipeline really offers is not yet known; the app logs the languages it found the first time it calls Bhashini.

## Steps

1. **Register** at the Bhashini integrator page, `https://dashboard.bhashini.co.in/user/register`. Confirm the email (check spam) and wait for the Bhashini team to approve you. This can take time, so do it early.
2. **Copy your keys.** Once approved, your **User ID** and **API key** are in your account profile.
3. **Install ffmpeg** on the machine running the app, and check `ffmpeg -version` works in a terminal. On Windows: `winget install ffmpeg`; on macOS: `brew install ffmpeg`; on Debian or Ubuntu: `sudo apt install ffmpeg`. If it is not on the PATH, put its full path in `FFMPEG_PATH`.
4. **Fill in `.env`** (never commit it, never paste keys into chat):
   ```
   SPEECH_TO_TEXT=bhashini
   BHASHINI_USER_ID=your user id
   BHASHINI_API_KEY=your api key
   BHASHINI_PIPELINE_ID=64392f96daac500b55c543cd
   BHASHINI_DEFAULT_LANGUAGE=kok
   BHASHINI_TIMEOUT_SECONDS=20
   FFMPEG_PATH=ffmpeg
   ```
   `64392f96daac500b55c543cd` is the "Initial Pipeline Models" pipeline from Bhashini's documentation, listed as offering speech recognition. The IIT Madras pipeline, `660fa5bec7fb5b0328229016`, is also listed with speech recognition.
5. **Restart the app.** If a key is missing or ffmpeg cannot be found, a warning is logged when the first message arrives, and voice notes are declined.
6. **Try it** with a real phone (see `docs/WHATSAPP_SETUP.md`): send a short voice note. The reply starts with what we heard. If you get "please type your message" instead, the log line `Voice note not transcribed: ...` says why. The log never contains the audio or the phone number.

## Settings

| Setting | Default | Meaning |
|---|---|---|
| `SPEECH_TO_TEXT` | `stub` | `bhashini` to use Bhashini, `stub` for the simulator only, `off` to decline all voice notes |
| `BHASHINI_USER_ID` | empty | Your Bhashini user id |
| `BHASHINI_API_KEY` | empty | Your Bhashini (ULCA) API key |
| `BHASHINI_PIPELINE_ID` | `64392f96daac500b55c543cd` | Which Bhashini pipeline to use |
| `BHASHINI_DEFAULT_LANGUAGE` | `kok` | Language assumed for a voice note: `kok`, `mr`, `hi` or `en` |
| `BHASHINI_TIMEOUT_SECONDS` | `20` | How long to wait for each Bhashini call |
| `FFMPEG_PATH` | `ffmpeg` | The ffmpeg program, if it is not on the PATH |

## Not yet known

- Whether the default pipeline offers Konkani, and under `gom` or `kok`.
- How long Bhashini takes for a 30-second voice note, and whether 20 seconds is enough.
- How well it understands Konkani spoken in a noisy street.
- Voice notes longer than 2 minutes are cut at 2 minutes; ones over 30 seconds ask Bhashini to split on silence (`vad`), as its documentation suggests.

## Sources

- How the calls fit together: https://dibd-bhashini.gitbook.io/bhashini-apis/
- Registration: https://dibd-bhashini.gitbook.io/bhashini-apis/pre-requisites-and-onboarding
- Config call: https://dibd-bhashini.gitbook.io/bhashini-apis/pipeline-config-call
- Compute call: https://dibd-bhashini.gitbook.io/bhashini-apis/pipeline-compute-call
- Speech models per language: https://dibd-bhashini.gitbook.io/bhashini-apis/available-models-for-usage
- Pipeline ids: https://dibd-bhashini.gitbook.io/bhashini-apis/pipeline-search-call
- Language codes and audio formats: https://github.com/ULCA-IN/ulca/blob/master/specs/common-schemas.yml
