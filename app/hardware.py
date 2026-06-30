"""Hardware setup + I/O: PIR motion sensor, trigger button, and the camera.

Importing this module initialises the GPIO devices and the camera (matching the
original script's module-level setup), so import it only on the Pi.
"""

from gpiozero import MotionSensor, Button
from picamera2 import Picamera2
from datetime import datetime
import time
import os

from log import log
from config import (
    PIR_PIN,
    BUTTON_PIN,
    INPUT_MODE,
    PHOTO_DIR,
    ARM_TIMEOUT,
)

os.makedirs(PHOTO_DIR, exist_ok=True)

pir = MotionSensor(PIR_PIN)

button = None
if INPUT_MODE == "button":
    button = Button(BUTTON_PIN, bounce_time=0.05)

camera = Picamera2()
camera.configure(camera.create_still_configuration())
camera.start()
time.sleep(2)  # camera warm-up
log.info("camera: initialized (PIR on GPIO %d, trigger=%s)", PIR_PIN, INPUT_MODE)


def wait_for_trigger():
    """Block until the user triggers a capture. Returns True if triggered."""
    if INPUT_MODE == "keyboard":
        # No stdin under systemd -> input() raises EOFError; treat as no-go
        # rather than crashing (the service uses button mode regardless).
        try:
            input("Press Enter to take a photo... ")
            return True
        except EOFError:
            log.warning("trigger: keyboard mode has no stdin; cannot arm")
            return False
    # button mode
    log.info("armed: waiting for button press (up to %.0fs)", ARM_TIMEOUT)
    pressed = button.wait_for_press(timeout=ARM_TIMEOUT)
    if pressed:
        log.info("trigger: button pressed")
    return pressed


def capture_photo():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(PHOTO_DIR, f"photo_{ts}.jpg")
    camera.capture_file(path)
    try:
        kb = os.path.getsize(path) / 1024
        log.info("capture: saved %s (%.0f KB)", os.path.basename(path), kb)
    except OSError:
        log.info("capture: saved %s", os.path.basename(path))
    return path
