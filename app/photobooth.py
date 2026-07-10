#!/usr/bin/env python3
"""Round 2.2: PIR detect -> audio beckon -> trigger -> countdown -> capture -> print.

Flow:
    IDLE      wait for the PIR to see someone
    BECKON    play a random beckon clip + the intro greeting (rate-limited)
    ARMED     wait for the trigger (keyboard Enter for testing, or a GPIO button)
    COUNTDOWN audible/visible countdown so people can pose
    CAPTURE   take the photo
    PRINT     render the receipt (console ASCII preview now; ESC/POS later)
    COOLDOWN  wait for the area to clear before re-arming

This file is just the state-machine loop. The pieces live in:
    config.py    -- all the on-site tunable knobs
    audio.py     -- beckon clip + countdown
    imaging.py   -- the enhance/dither image pipeline
    printing.py  -- receipt rendering + printer backends
    hardware.py  -- PIR, button, camera, capture
"""

import os
import time

from log import log
from config import (
    CAPTION,
    INPUT_MODE,
    COOLDOWN_AFTER_PRINT,
    PAUSE_BEFORE_BYE,
    PRINTER_BACKEND,
)
from audio import play_greeting, play_smile, play_bye, countdown, alert, chime, audio_ok
from printing import setup_printer, print_receipt, printer_ok
from hardware import pir, camera, wait_for_trigger, capture_photo, flash_led


# ----------------------------------------------------------------------------
# TODOs (tracked in CLAUDE.md)
# ----------------------------------------------------------------------------
# - DONE: randomized fortune from a text doc + randomized set of 3 emoji
# - DONE: audio countdown / delay after the trigger before capture
# - order pink or purple physical button (wired to GPIO 23, LED on GPIO 24,
#   INPUT_MODE="button"); LED flashes through the countdown
# - order printer with paper + sort a power source
# - write an artist statement
# - sticker of the sculpture / dorky frame / speech bubble around the image


# ----------------------------------------------------------------------------
# Main loop
# ----------------------------------------------------------------------------
def _signal_error(reason):
    """Announce a fault on a headless booth: the audio buzz + a burst of LED
    flashes (the LED is the fallback for the one case audio can't cover -- when
    audio itself is the thing that's broken). Never raises."""
    try:
        alert(reason)
    finally:
        for _ in range(4):
            flash_led()
            time.sleep(0.12)


def _boot_selftest(prn):
    """Check the printer + audio at startup and say so out loud.

    Rising chime = came up healthy; error buzz = something's wrong (and the
    reason is in the journal). This is the whole point of the cues headless:
    power on, walk away, and hear whether the booth is good to go.
    """
    p_ok, p_reason = printer_ok(prn)
    a_ok = audio_ok()
    if p_ok and a_ok:
        log.info("selftest: OK (printer=%s, audio=OK)", p_reason)
        chime()
        return
    if not p_ok:
        log.error("selftest: printer NOT ready -- %s", p_reason)
    if not a_ok:
        log.error("selftest: audio NOT working -- check volume/device (aplay -l)")
    # If audio is the failure, the buzz may not be audible either -- the LED
    # burst inside _signal_error still fires, so there's a visible tell too.
    _signal_error("boot self-test failed")


def main():
    prn = setup_printer()
    where = "console" if prn is None else PRINTER_BACKEND
    log.info("photobooth ready (trigger=%s, printer=%s); waiting for motion",
             INPUT_MODE, where)
    _boot_selftest(prn)
    try:
        while True:
            # Guard each cycle so one bad capture/print logs and re-arms
            # instead of crashing the whole service (gallery runs unattended).
            try:
                pir.wait_for_motion()
                log.info("PIR: motion detected")
                play_greeting()                # a random beckon, then the intro

                if not wait_for_trigger():
                    log.info("trigger: none within timeout; standing down")
                    pir.wait_for_no_motion()
                    continue

                play_smile()                   # "give me a smile" (blocks)
                countdown(on_tick=flash_led)   # 4s voice clip; LED flashes per count
                photo_path = capture_photo()
                time.sleep(PAUSE_BEFORE_BYE)
                play_bye()                     # random bye/bye2 while the receipt prints
                # The photo is only needed to build the receipt; don't keep it
                # around (storage fills fast). Delete it once the receipt is sent.
                try:
                    if not print_receipt(prn, photo_path, CAPTION):
                        _signal_error("print failed -- receipt did not print")
                finally:
                    try:
                        os.remove(photo_path)
                    except OSError:
                        pass

                log.info("cooldown: %.1fs; waiting for area to clear",
                         COOLDOWN_AFTER_PRINT)
                time.sleep(COOLDOWN_AFTER_PRINT)
                pir.wait_for_no_motion()
                log.info("re-armed; waiting for motion")
            except KeyboardInterrupt:
                raise
            except Exception:
                log.exception("cycle error; recovering and re-arming")
                _signal_error("cycle error -- see the journal")
                time.sleep(2)
    except KeyboardInterrupt:
        log.info("shutting down (keyboard interrupt)")
    finally:
        camera.stop()
        if prn is not None:
            try:
                prn.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
