"""Audio: beckon clip + pre-capture countdown, played through aplay."""

from pathlib import Path
import subprocess
import time

from log import log
from config import (
    BECKON_WAV,
    BECKON_COOLDOWN,
    CAPTURE_COUNTDOWN,
    COUNTDOWN_WAV,
)

_last_beckon = 0.0


def _play_wav(path, blocking=False):
    """Play a wav via aplay. Returns the Popen handle, or None if unavailable."""
    if not path or not Path(path).exists():
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


def play_beckon():
    """Play the beckon clip, but not more often than BECKON_COOLDOWN."""
    global _last_beckon
    now = time.monotonic()
    if now - _last_beckon < BECKON_COOLDOWN:
        return
    _last_beckon = now

    if not Path(BECKON_WAV).exists():
        log.warning("audio: beckon clip not found: %s (skipping)", BECKON_WAV)
        return
    log.info("beckon: playing clip")
    _play_wav(BECKON_WAV)


def countdown():
    """Count down before the shutter, with an optional per-tick beep."""
    for i in range(CAPTURE_COUNTDOWN, 0, -1):
        print(f"   {i}...")
        _play_wav(COUNTDOWN_WAV)
        time.sleep(1)
    if CAPTURE_COUNTDOWN > 0:
        print("   *click*")
