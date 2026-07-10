"""Audio: the kiz voice clips + pre-capture countdown, played through aplay.

Also owns the headless error cues (see ``alert``/``chime``): synthesised tones,
so there are no extra wav assets to ship and no dependency beyond the stdlib.
"""

from pathlib import Path
import math
import struct
import tempfile
import wave
import os
import random
import subprocess
import time

from log import log
from config import (
    INTRO_WAV,
    BECKON_WAVS,
    SMILE_WAV,
    BYE_WAVS,
    BECKON_COOLDOWN,
    CAPTURE_COUNTDOWN,
    COUNTDOWN_WAV,
    ERROR_CUES,
)

_last_greeting = 0.0


def _play_wav(path, blocking=False):
    """Play a wav via aplay.

    Returns the Popen handle (non-blocking) or True/False for success (blocking).
    ``aplay``'s stderr is captured, not discarded, so a real audio failure --
    muted card, wrong device -- gets logged instead of vanishing silently (that
    hidden failure is exactly why a dead speaker used to look "fine" in the log).
    """
    if not path or not Path(path).exists():
        log.warning("audio: clip not found: %s (skipping)", path)
        return False if blocking else None
    try:
        proc = subprocess.Popen(
            ["aplay", "-q", str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        log.warning("audio: 'aplay' not found -- install alsa-utils or swap the player")
        return False if blocking else None
    if blocking:
        _, err = proc.communicate()
        if proc.returncode != 0:
            log.warning("audio: aplay failed on %s (%s)", Path(path).name,
                        (err or b"").decode(errors="replace").strip())
            return False
        return True
    return proc


# ----------------------------------------------------------------------------
# Error cues -- synthesised tones for a headless booth (no wav assets needed)
# ----------------------------------------------------------------------------
_RATE = 22050
_tone_cache = {}


def _synth_tone(name, notes, volume=0.6):
    """Render a sequence of (freq_hz, seconds) notes to a mono 16-bit wav.

    Cached on disk under the temp dir and reused for the life of the process.
    A short linear fade on each note's edges keeps aplay from clicking.
    """
    if name in _tone_cache:
        return _tone_cache[name]
    path = os.path.join(tempfile.gettempdir(), f"photobooth_{name}.wav")
    try:
        frames = bytearray()
        fade = int(_RATE * 0.008)
        for freq, dur in notes:
            n = int(_RATE * dur)
            for i in range(n):
                env = min(1.0, i / fade if fade else 1.0,
                          (n - i) / fade if fade else 1.0)
                sample = int(volume * env * 32767 * math.sin(2 * math.pi * freq * i / _RATE))
                frames += struct.pack("<h", sample)
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(_RATE)
            w.writeframes(bytes(frames))
        _tone_cache[name] = path
        return path
    except Exception:
        log.debug("audio: tone synth failed for %s", name, exc_info=True)
        return None


def alert(reason=""):
    """Play the 'something is wrong' cue: a low, descending double buzz.

    Blocking, so it's heard in full. No-op if cues are disabled. Never raises --
    the alert must not be able to crash the cycle it's reporting on.
    """
    if not ERROR_CUES:
        return
    if reason:
        log.warning("alert: %s", reason)
    try:
        path = _synth_tone("error", [(340, 0.18), (0, 0.05), (340, 0.18),
                                     (0, 0.05), (240, 0.32)], volume=0.7)
        if path:
            _play_wav(path, blocking=True)
    except Exception:
        log.debug("audio: alert failed", exc_info=True)


def chime():
    """Play the 'all good' cue: a short rising three-note chime (boot self-test)."""
    if not ERROR_CUES:
        return
    try:
        path = _synth_tone("ready", [(523, 0.13), (659, 0.13), (784, 0.2)])
        if path:
            _play_wav(path, blocking=True)
    except Exception:
        log.debug("audio: chime failed", exc_info=True)


def audio_ok():
    """Boot self-test for the audio path: can aplay actually open the device?

    Plays a very short, quiet blip and reports whether aplay exited cleanly.
    Returns True/False so the caller can fold it into the startup health cue.
    """
    path = _synth_tone("selftest", [(660, 0.12)], volume=0.25)
    if path is None:
        return False
    return _play_wav(path, blocking=True) is True


def play_greeting():
    """One of the beckons at random, then the intro greeting.

    Rate-limited so the same lingering person isn't re-greeted more often than
    BECKON_COOLDOWN. Both clips play blocking so the intro doesn't talk over
    the beckon, and the caller can wait for the button as soon as this returns.
    """
    global _last_greeting
    now = time.monotonic()
    if now - _last_greeting < BECKON_COOLDOWN:
        return
    _last_greeting = now

    clip = random.choice(BECKON_WAVS)
    log.info("beckon: playing %s", Path(clip).name)
    _play_wav(clip, blocking=True)

    time.sleep(0.25)  # brief pause between beckon + intro

    log.info("greeting: playing intro")
    _play_wav(INTRO_WAV, blocking=True)


def play_smile():
    """"Give me a smile" -- plays right after the button press, before the count.

    Blocking, so the countdown clip doesn't start until this one finishes.
    """
    log.info("smile: playing clip")
    _play_wav(SMILE_WAV, blocking=True)


def play_bye():
    """One of the bye clips at random, after the shutter (non-blocking)."""
    clip = random.choice(BYE_WAVS)
    log.info("bye: playing %s", Path(clip).name)
    _play_wav(clip)


def countdown(on_tick=None):
    """Count down before the shutter, over the single countdown voice clip.

    The clip covers the whole count, so it starts once (non-blocking) and the
    loop just paces the seconds. ``on_tick`` is called once at the start of each
    second (e.g. to flash the button LED in time with the count); it's kept out
    of audio.py so this module stays free of the Pi-only hardware imports.
    """
    if CAPTURE_COUNTDOWN <= 0:
        return
    _play_wav(COUNTDOWN_WAV)
    for i in range(CAPTURE_COUNTDOWN, 0, -1):
        print(f"   {i}...")
        if on_tick is not None:
            on_tick()
        time.sleep(1)
    print("   *click*")
