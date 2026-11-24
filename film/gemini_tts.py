"""Gemini text-to-speech for the study videos, using the rotating keys in .env.

AUDIO RULES (why this file looks the way it does, found 2026-11-12):
  * gemini-3.8-flash-tts returns a COMPLETE WAV FILE (mimeType audio/wav): a 'fmt ' chunk, a
    'data' chunk, then a ~6 KB 'C2PA' provenance chunk. Treating those bytes as raw PCM plays
    the header as a click at the start and the C2PA chunk as ~130 ms of loud digital noise at
    the end of every clip, which is the glitch heard at every transition. Older models
    returned raw PCM (mimeType audio/L16;rate=24000). decode_audio() handles both and
    keeps ONLY the speech samples.
  * Each clip is then trimmed to a fixed pad of silence, DC-centred and given short fades,
    so no clip starts or ends mid-waveform.
  * Loudness: two-pass ffmpeg loudnorm in LINEAR mode (-16 LUFS, -1.5 dBTP). One-pass
    loudnorm runs in dynamic mode and can pump the gain at the start of a clip.
  * check_edges() refuses a clip whose first/last 30 ms are not quiet or that has a burst
    after the speech ends.

    from gemini_tts import synthesize
    synthesize("Hello", "out.wav", voice="Charon")

CLI:  python3 gemini_tts.py --voice Charon --out sample.wav "Text to speak"
"""

import argparse
import base64
import json
import re
import struct
import subprocess
import tempfile
import urllib.error
import urllib.request
import wave
from pathlib import Path

import numpy as np

from gemini_keys import KeyRotator

MODEL = "gemini-3.8-flash-tts"
# Structured prompt: with a plain "Say ...:" prefix, gemini-3.8-flash-tts read the
# instruction aloud; with this layout it speaks only the transcript (checked 2026-11-12).
STYLE = ("# AUDIO PROFILE: A calm, confident narrator from Goa, India, voicing a short product film.\n"
         "### DIRECTOR'S NOTES\n"
         "Style: warm and assured, quietly serious about the problem, clear for a first-time listener. "
         "Not salesy, not dramatic.\n"
         "Accent: natural Indian English.\n"
         "Pace: measured, with short natural pauses at commas and full stops.\n\n"
         "#### TRANSCRIPT\n")
LANGUAGE_CODE = "en-IN"
RATE = 24000
LEAD_PAD, TAIL_PAD = 0.12, 0.20     # seconds of silence kept before / after the speech
FADE_IN, FADE_OUT = 0.010, 0.030    # seconds
SILENCE_DB = -45.0                  # below this counts as silence when trimming

_keys = None


class GeminiHTTPError(Exception):
    def __init__(self, code, body):
        self.code = code
        super().__init__(f"HTTP {code}: {body[:500]}")


def _request(text, voice, model, key):
    """Return (audio_bytes, mime_type) for one TTS call."""
    body = {
        "contents": [{"parts": [{"text": STYLE + text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "languageCode": LANGUAGE_CODE,
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}},
            },
        },
    }
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(body).encode(),
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        raise GeminiHTTPError(e.code, e.read().decode(errors="ignore")) from None
    parts = data["candidates"][0]["content"]["parts"]
    inline = next(p["inlineData"] for p in parts if "inlineData" in p)
    return base64.b64decode(inline["data"]), inline.get("mimeType", "")


def decode_audio(blob, mime=""):
    """Return (samples float32 in [-1, 1], sample_rate) with only the speech samples.

    Handles a full WAV (keeps just the 'data' chunk; drops headers and C2PA/LIST metadata)
    or raw 16-bit little-endian PCM (rate read from the mime type, default 24 kHz)."""
    if blob[:4] == b"RIFF" and blob[8:12] == b"WAVE":
        pos, rate, bits, ch, pcm = 12, RATE, 16, 1, None
        while pos + 8 <= len(blob):
            cid, size = blob[pos:pos + 4], struct.unpack("<I", blob[pos + 4:pos + 8])[0]
            body = blob[pos + 8:pos + 8 + size]
            if cid == b"fmt ":
                fmt_tag, ch, rate = struct.unpack("<HHI", body[:8]); bits = struct.unpack("<H", body[14:16])[0]
                if fmt_tag not in (1, 0xFFFE) or bits != 16:
                    raise ValueError(f"unsupported WAV format tag={fmt_tag} bits={bits}")
            elif cid == b"data":
                pcm = body
            pos += 8 + size + (size & 1)
        if pcm is None:
            raise ValueError("WAV has no data chunk")
    else:
        m = re.search(r"rate=(\d+)", mime)
        rate, ch, pcm = int(m.group(1)) if m else RATE, 1, blob
    x = np.frombuffer(pcm[: len(pcm) // 2 * 2], dtype="<i2").astype(np.float32) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x, rate


def clean(x, sr):
    """Centre, trim edge silence to fixed pads, and fade both ends."""
    x = x - float(np.mean(x))
    thr = 10 ** (SILENCE_DB / 20)
    win = max(1, int(0.005 * sr))
    env = np.sqrt(np.convolve(x * x, np.ones(win) / win, mode="same"))
    loud = np.where(env > thr)[0]
    if len(loud) == 0:
        raise ValueError("clip is silent")
    lead, tail = int(LEAD_PAD * sr), int(TAIL_PAD * sr)
    a = max(0, loud[0] - lead)
    b = min(len(x), loud[-1] + tail)
    # if the speech runs too close to an edge, add digital silence instead of fading into a word
    x = np.concatenate([np.zeros(max(0, lead - loud[0]), np.float32), x[a:b],
                        np.zeros(max(0, loud[-1] + tail - len(x)), np.float32)])
    fi, fo = int(FADE_IN * sr), int(FADE_OUT * sr)
    x[:fi] *= np.linspace(0.0, 1.0, fi)
    x[-fo:] *= np.linspace(1.0, 0.0, fo)
    return x


def _write_wav(path, x, sr):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def normalize(src, dst, lufs=-16.0, tp=-1.5, lra=11):
    """Two-pass ffmpeg loudnorm in linear mode (no gain pumping)."""
    first = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(src), "-af",
                            f"loudnorm=I={lufs}:TP={tp}:LRA={lra}:print_format=json", "-f", "null", "-"],
                           capture_output=True, text=True, check=True).stderr
    m = json.loads(first[first.rindex("{"): first.rindex("}") + 1])
    af = (f"loudnorm=I={lufs}:TP={tp}:LRA={lra}:linear=true:"
          f"measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
          f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af", af,
                    "-ar", str(RATE), "-ac", "1", "-c:a", "pcm_s16le", str(dst)], check=True)


def finish(x, sr, out_path, lufs=-16.0):
    """clean -> normalise -> edge check. Writes out_path and returns its duration."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    _write_wav(tmp_path, clean(x, sr), sr)
    normalize(tmp_path, out_path, lufs)
    tmp_path.unlink(missing_ok=True)
    problems = check_edges(out_path)
    if problems:
        raise RuntimeError(f"{out_path.name}: {problems}")
    return duration(out_path)


def check_edges(path):
    """Return a list of problems: loud edges, clicks, or a burst after the speech ends."""
    with wave.open(str(path)) as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
    db = lambda s: 20 * np.log10(np.sqrt(np.mean(s * s)) + 1e-12)
    n = int(0.03 * sr)
    out = []
    if db(x[:n]) > -50: out.append(f"start not quiet ({db(x[:n]):.0f} dB)")
    if db(x[-n:]) > -50: out.append(f"end not quiet ({db(x[-n:]):.0f} dB)")
    if abs(x[0]) > 0.01 or abs(x[-1]) > 0.01: out.append("first/last sample not near zero")
    # a burst in the last 400 ms that follows a quiet gap = metadata or a glitch, not speech
    s = int(0.02 * sr)
    tail = [db(x[len(x) - (k + 1) * s: len(x) - k * s]) for k in range(20)][::-1]
    for k in range(1, len(tail)):
        if tail[k] > -25 and min(tail[:k]) < -55 and k > 10:
            out.append("burst after the speech ends"); break
    return out


def synthesize(text, out_path, voice="Charon", model=MODEL, lufs=-16.0):
    """Speak `text`, write a clean loudness-normalised WAV to out_path, return its duration."""
    global _keys
    if len(text.encode()) > 4000:
        raise ValueError("Text is over 4,000 bytes; split it into shorter chunks")
    _keys = _keys or KeyRotator()
    blob, mime = _keys.call(lambda key: _request(text, voice, model, key))
    x, sr = decode_audio(blob, mime)
    return finish(x, sr, out_path, lufs)


TRANSCRIBE_MODELS = ("gemini-2.5-flash", "gemini-3.5-flash", "gemini-flash-latest", "gemini-3-flash-preview",
                     "gemini-2.5-flash-lite", "gemini-flash-lite-latest")


def transcribe(path, models=TRANSCRIBE_MODELS):
    """QA helper: ask Gemini to transcribe a WAV, to catch read-aloud instructions or skipped words.

    Free-tier quotas are per model per key, and several agents share the keys, so try every key on
    each model before moving to the next model. If all fail, fall back to the local Parakeet
    transcriber (HyperFrames), so a quota error never stops audio generation."""
    from gemini_keys import load_keys
    b = base64.b64encode(Path(path).read_bytes()).decode()
    body = {"contents": [{"parts": [{"inlineData": {"mimeType": "audio/wav", "data": b}},
                                    {"text": "Transcribe this audio word for word. Nothing else."}]}]}
    last = None
    for model in models:
        for key in load_keys():
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                data=json.dumps(body).encode(), headers={"x-goog-api-key": key, "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    return json.load(r)["candidates"][0]["content"]["parts"][0]["text"].strip()
            except (urllib.error.HTTPError, urllib.error.URLError, KeyError, TimeoutError) as e:
                last = e
    try:
        return transcribe_local(path)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"transcription failed on every key and model ({last}), and locally ({e})")


def transcribe_local(path):
    """Offline transcript via `npx hyperframes transcribe` (Parakeet/whisper), run on a temp copy."""
    import shutil
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "clip.wav"
        shutil.copy(path, src)
        subprocess.run(["npx", "hyperframes", "transcribe", str(src), "--json", "--language", "en"],
                       cwd=d, capture_output=True, text=True, check=True, timeout=600)
        words = json.loads((Path(d) / "transcript.json").read_text())
        return " ".join(w["text"] for w in words)


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("text"); ap.add_argument("--voice", default="Charon")
    ap.add_argument("--out", required=True); ap.add_argument("--model", default=MODEL)
    a = ap.parse_args()
    print(f"{a.out}: {synthesize(a.text, a.out, a.voice, a.model):.2f} s")
