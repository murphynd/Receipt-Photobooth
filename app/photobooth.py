#!/usr/bin/env python3
"""Round 2.2: PIR detect -> audio beckon -> trigger -> countdown -> capture -> print.

Flow:
    IDLE      wait for the PIR to see someone
    BECKON    play an audio clip inviting them over (rate-limited)
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
from config import CAPTION, INPUT_MODE, COOLDOWN_AFTER_PRINT, PRINTER_BACKEND
from audio import play_beckon, countdown
from printing import setup_printer, print_receipt
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
def main():
    prn = setup_printer()
    where = "console" if prn is None else PRINTER_BACKEND
    log.info("photobooth ready (trigger=%s, printer=%s); waiting for motion",
             INPUT_MODE, where)
    try:
        while True:
            # Guard each cycle so one bad capture/print logs and re-arms
            # instead of crashing the whole service (gallery runs unattended).
            try:
                pir.wait_for_motion()
                log.info("PIR: motion detected")
                play_beckon()

                if not wait_for_trigger():
                    log.info("trigger: none within timeout; standing down")
                    pir.wait_for_no_motion()
                    continue

                countdown(on_tick=flash_led)   # LED flashes once per count
                photo_path = capture_photo()
                # The photo is only needed to build the receipt; don't keep it
                # around (storage fills fast). Delete it once the receipt is sent.
                try:
                    print_receipt(prn, photo_path, CAPTION)
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
