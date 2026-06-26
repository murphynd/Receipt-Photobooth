"""Hardware setup + I/O: PIR motion sensor, trigger button, and the camera.

Importing this module initialises the GPIO devices and the camera (matching the
original script's module-level setup), so import it only on the Pi.
"""

from gpiozero import MotionSensor, Button
from picamera2 import Picamera2
from datetime import datetime
import time
import os

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


def wait_for_trigger():
    """Block until the user triggers a capture. Returns True if triggered."""
    if INPUT_MODE == "keyboard":
        input("Press Enter to take a photo... ")
        return True
    # button mode
    print(f"Waiting for button press (up to {ARM_TIMEOUT:.0f}s)...")
    return button.wait_for_press(timeout=ARM_TIMEOUT)


def capture_photo():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(PHOTO_DIR, f"photo_{ts}.jpg")
    camera.capture_file(path)
    return path
