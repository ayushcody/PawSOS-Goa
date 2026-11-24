"""Round-robin rotation over several Gemini API keys stored in .env.

Keys are read from .env (or the environment) as a comma-separated list:
GEMINI_API_KEYS=key_one,key_two,key_three
GEMINI_API_KEY and numbered GEMINI_API_KEY_1, _2, ... are also accepted. Each call uses the next key in turn, and the
position is saved to .gemini_key_state.json so separate script runs keep rotating.
If a key hits a rate limit or quota error, it is rested for a while and the call is
retried on the next key.

Usage:
    from gemini_keys import KeyRotator
    keys = KeyRotator()
    audio = keys.call(lambda key: synthesize(text, api_key=key))
"""

import json
import os
import re
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENV_FILE = HERE / ".env"
STATE_FILE = HERE / ".gemini_key_state.json"

RATE_LIMIT_MARKERS = ("429", "RESOURCE_EXHAUSTED", "quota", "rate limit", "Too Many Requests")


def load_keys(env_file=ENV_FILE):
    """Return the non-empty Gemini keys from .env, falling back to the environment."""
    found = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            found[name.strip()] = value.strip().strip('"').strip("'")
    for name, value in os.environ.items():
        if name.startswith("GEMINI_API_KEY"):
            found.setdefault(name, value)

    def order(name):
        m = re.fullmatch(r"GEMINI_API_KEY_(\d+)", name)
        return int(m.group(1)) if m else 0

    names = sorted((n for n in found if re.fullmatch(r"GEMINI_API_KEYS?(_\d+)?", n)), key=order)
    keys = []
    for n in names:
        for key in found[n].split(","):
            key = key.strip().strip('"').strip("'")
            if key and key not in keys:
                keys.append(key)
    return keys


def is_bad_key(err):
    code = getattr(err, "code", None) or getattr(err, "status_code", None)
    return code in (401, 403) or "API_KEY_INVALID" in str(err)


def is_rate_limit(err):
    if getattr(err, "code", None) == 429 or getattr(err, "status_code", None) == 429:
        return True
    text = str(err)
    return any(marker.lower() in text.lower() for marker in RATE_LIMIT_MARKERS)


class KeyRotator:
    def __init__(self, keys=None, cooldown_s=60.0, state_file=STATE_FILE):
        self.keys = keys if keys is not None else load_keys()
        if not self.keys:
            raise RuntimeError("No Gemini keys found. Fill in GEMINI_API_KEYS=key1,key2,... in .env")
        self.cooldown_s = cooldown_s
        self.state_file = state_file
        self.resting_until = [0.0] * len(self.keys)
        self.index = self._load_index()

    def _load_index(self):
        try:
            return json.loads(self.state_file.read_text())["next"] % len(self.keys)
        except Exception:
            return 0

    def _save_index(self):
        try:
            self.state_file.write_text(json.dumps({"next": self.index}))
        except OSError:
            pass

    def _take(self):
        """Pick the next key that isn't resting; wait if every key is resting."""
        while True:
            now = time.time()
            for step in range(len(self.keys)):
                i = (self.index + step) % len(self.keys)
                if self.resting_until[i] <= now:
                    self.index = (i + 1) % len(self.keys)
                    self._save_index()
                    return i
            if all(t == float("inf") for t in self.resting_until):
                raise RuntimeError("Every Gemini key was rejected")
            wait = min(self.resting_until) - now
            live = sum(t != float("inf") for t in self.resting_until)
            print(f"[keys] all {live} working keys rate-limited, waiting {wait:.0f}s")
            time.sleep(max(wait, 1.0))

    def next_key(self):
        return self.keys[self._take()]

    def call(self, fn, max_attempts=None):
        """Run fn(api_key), moving to the next key on rate-limit errors."""
        attempts = max_attempts or len(self.keys) * 3
        last_err = None
        for _ in range(attempts):
            i = self._take()
            try:
                return fn(self.keys[i])
            except Exception as err:
                last_err = err
                if is_bad_key(err):
                    self.resting_until[i] = float("inf")
                    print(f"[keys] key #{i + 1} was rejected (invalid or no access), skipping it from now on")
                    if all(t == float("inf") for t in self.resting_until):
                        raise RuntimeError("Every Gemini key was rejected") from err
                elif is_rate_limit(err):
                    self.resting_until[i] = time.time() + self.cooldown_s
                    print(f"[keys] key #{i + 1} rate-limited, switching to the next one")
                else:
                    raise
        raise RuntimeError(f"Gave up after {attempts} attempts") from last_err


if __name__ == "__main__":
    ks = load_keys()
    print(f"{len(ks)} Gemini key(s) loaded from .env: "
          + ", ".join(f"#{i + 1} …{k[-4:]}" for i, k in enumerate(ks)))
