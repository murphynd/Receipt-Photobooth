"""Audio: the kiz voice clips + pre-capture countdown, played through aplay."""

from pathlib import Path
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
)

_last_greeting = 0.0


def _play_wav(path, blocking=False):
    """Play a wav via aplay. Returns the Popen handle, or None if unavailable."""
    if not path or not Path(path).exists():
        log.warning("audio: clip not found: %s (skipping)", path)
        return None
    try:
        proc = subprocess.Popen(
            ["aplay", "-q", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if blocking:
            proc.wait()
        return proc
    except FileNotFoundError:
        log.warning("audio: 'aplay' not found -- install alsa-utils or swap the player")
        return None


def play_greeting():
    """Intro greeting, then one of the beckons at random.

    Rate-limited so the same lingering person isn't re-greeted more often than
    BECKON_COOLDOWN. The intro plays blocking so the beckon doesn't talk over it.
    """
    global _last_greeting
    now = time.monotonic()
    if now - _last_greeting < BECKON_COOLDOWN:
        return
    _last_greeting = now

    log.info("greeting: playing intro")
    _play_wav(INTRO_WAV, blocking=True)

    clip = random.choice(BECKON_WAVS)
    log.info("beckon: playing %s", Path(clip).name)
    _play_wav(clip)


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
