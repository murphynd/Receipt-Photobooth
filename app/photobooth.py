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

from config import CAPTION, INPUT_MODE, COOLDOWN_AFTER_PRINT, PRINTER_BACKEND
from audio import play_beckon, countdown
from printing import setup_printer, print_receipt
from hardware import pir, camera, wait_for_trigger, capture_photo


# ----------------------------------------------------------------------------
# TODOs (tracked in CLAUDE.md)
# ----------------------------------------------------------------------------
# - DONE: randomized fortune from a text doc + randomized set of 3 emoji
# - DONE: audio countdown / delay after the trigger before capture
# - order pink or purple physical button (wired to GPIO 27, INPUT_MODE="button")
# - order printer with paper + sort a power source
# - write an artist statement
# - sticker of the sculpture / dorky frame / speech bubble around the image


# ----------------------------------------------------------------------------
# Main loop
# ----------------------------------------------------------------------------
def main():
    prn = setup_printer()
    where = "console" if prn is None else PRINTER_BACKEND
    print(
        f"Photobooth ready (trigger: {INPUT_MODE}, printer: {where}). "
        "Waiting for motion... (Ctrl+C to quit)"
    )
    try:
        while True:
            pir.wait_for_motion()
            print("\n>>> Someone is there! <<<")
            play_beckon()

            if not wait_for_trigger():
                print("No trigger -- standing down.")
                pir.wait_for_no_motion()
                continue

            countdown()
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
            time.sleep(COOLDOWN_AFTER_PRINT)

            pir.wait_for_no_motion()
            print("Waiting for motion...")
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        camera.stop()
        if prn is not None:
            try:
                prn.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
