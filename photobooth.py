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
"""

from gpiozero import MotionSensor, Button
from picamera2 import Picamera2
from datetime import datetime
from pathlib import Path
import subprocess
import random
import time
import os

# ----------------------------------------------------------------------------
# Config -- the knobs you'll tune on-site
# ----------------------------------------------------------------------------
PIR_PIN = 17
BUTTON_PIN = 27          # only used when INPUT_MODE == "button"

# How the photo gets triggered:
#   "keyboard" -> press Enter in the terminal (great for testing)
#   "button"   -> a physical GPIO button on BUTTON_PIN
INPUT_MODE = "keyboard"

PHOTO_DIR = "photos"
CAPTION = "Smile! You've been spotted."

# Audio beckon
BECKON_WAV = "magicsounds.wav"   # a short "come on over!" clip
BECKON_COOLDOWN = 15.0             # seconds before we'll beckon the same person again

# Button arming (button mode only)
ARM_TIMEOUT = 20.0       # seconds to wait for a press before giving up and re-idling

# Pre-capture countdown (gives people a beat to pose after they trigger)
CAPTURE_COUNTDOWN = 3        # seconds to count down before the shutter (0 disables)
COUNTDOWN_WAV = "beep.wav"   # optional per-tick sound; skipped silently if missing

# Re-trigger pacing
COOLDOWN_AFTER_PRINT = 3.0   # seconds to settle after a print

# Printer (80mm / ESC-POS)
#   "console" -> no hardware: render an ASCII preview of the receipt to stdout
#   "cups"    -> build ESC/POS bytes and pipe them to a raw CUPS queue via `lp`
#                (use this when `lp -d POS80_raw file` already prints for you;
#                 it sidesteps the CUPS-vs-escpos fight over the USB device)
#   "usb"     -> python-escpos Usb backend, direct (needs CUPS queues disabled)
#   "serial"  -> python-escpos Serial backend
#   "network" -> python-escpos Network backend
#
# Keep "console" for image-tuning iterations; switch to "cups" for real prints.
PRINTER_BACKEND = "cups"
CUPS_PRINTER_NAME = "POS80_raw"   # the raw queue name from your working `lp -d ...`
PRINTER_USB_VENDOR = 0x1fc9     # POS-80, NXP-based controller (confirmed via lsusb)
PRINTER_USB_PRODUCT = 0x2016
# escpos can't always auto-pick the OUT endpoint on these NXP printers. If a USB
# print moves paper but prints nothing, find it with:
#   lsusb -v -d 1fc9:2016 2>/dev/null | grep -E "bEndpointAddress|wMaxPacketSize"
# and set it here, e.g. 0x03.
PRINTER_USB_OUT_EP = None
# If escpos complains about a missing printer profile, set "default" or
# "TM-T88III" -- most 80mm printers accept it.
PRINTER_PROFILE = None
PRINTER_SERIAL_PORT = "/dev/serial0"
PRINTER_SERIAL_BAUD = 19200
PRINTER_NETWORK_HOST = "192.168.1.100"
PRINT_WIDTH = 576        # dots across an 80mm head (512 on some printers)

# Receipt extras (fortune + emoji)
FORTUNE_FILE = "fortunes.txt"   # one fortune per line; blank lines ignored
FORTUNES_FALLBACK = [
    "A good day to smile at strangers.",
    "Something delightful is heading your way.",
    "The Furby sees great things in your future.",
    "Today, you are exactly where you need to be.",
    "Adventure favors the curious.",
    "Your reflection approves of you.",
]
EMOJI_POOL = ["*", "@", "#", "%", "+", "~", "^", "o", "x", "=", "$", "&"]
EMOJI_COUNT = 3          # how many random emoji to print across the receipt

# Console preview
RECEIPT_COLS = 42        # character width of the ASCII receipt preview
ASCII_RAMP = "@%#*+=-:. "  # dark -> light
SAVE_PRINT_PREVIEW = True  # also save the real 576px 1-bit bitmap as a PNG to open

# Receipt photo enhancement (tune these for your lighting/printer)
ENHANCE = True           # run the grayscale->CLAHE->gamma->unsharp->dither pipeline
CLAHE_CLIP = 2.0         # local-contrast strength (higher = punchier, more noise)
CLAHE_GRID = 8           # CLAHE tile grid (NxN)
GAMMA = 0.85             # <1 brightens midtones (faces print dark otherwise)
SHARPEN_RADIUS = 2       # unsharp-mask radius
SHARPEN_PERCENT = 150    # unsharp-mask strength
DITHER = "atkinson"      # "atkinson" (cleaner highlights) or "floyd" (faster, Pillow)

# ----------------------------------------------------------------------------
# Hardware setup
# ----------------------------------------------------------------------------
os.makedirs(PHOTO_DIR, exist_ok=True)

pir = MotionSensor(PIR_PIN)

button = None
if INPUT_MODE == "button":
    button = Button(BUTTON_PIN, bounce_time=0.05)

camera = Picamera2()
camera.configure(camera.create_still_configuration())
camera.start()
time.sleep(2)  # camera warm-up


# ----------------------------------------------------------------------------
# Audio
# ----------------------------------------------------------------------------
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
        print("[audio] 'aplay' not found -- install alsa-utils or swap the player")
        return None


def play_beckon():
    """Play the beckon clip, but not more often than BECKON_COOLDOWN."""
    global _last_beckon
    now = time.monotonic()
    if now - _last_beckon < BECKON_COOLDOWN:
        return
    _last_beckon = now

    if not Path(BECKON_WAV).exists():
        print(f"[audio] beckon clip not found: {BECKON_WAV} (skipping)")
        return
    _play_wav(BECKON_WAV)


def countdown():
    """Count down before the shutter, with an optional per-tick beep."""
    for i in range(CAPTURE_COUNTDOWN, 0, -1):
        print(f"   {i}...")
        _play_wav(COUNTDOWN_WAV)
        time.sleep(1)
    if CAPTURE_COUNTDOWN > 0:
        print("   *click*")


# ----------------------------------------------------------------------------
# Receipt extras
# ----------------------------------------------------------------------------
def pick_fortune():
    """Return a random fortune from FORTUNE_FILE, falling back to the built-ins."""
    fortunes = []
    try:
        with open(FORTUNE_FILE, encoding="utf-8") as fh:
            fortunes = [line.strip() for line in fh if line.strip()]
    except OSError:
        pass
    if not fortunes:
        fortunes = FORTUNES_FALLBACK
    return random.choice(fortunes)


def pick_emoji():
    """Return a string of EMOJI_COUNT random emoji/symbols, space-separated."""
    n = min(EMOJI_COUNT, len(EMOJI_POOL))
    return " ".join(random.sample(EMOJI_POOL, n))


# ----------------------------------------------------------------------------
# Trigger
# ----------------------------------------------------------------------------
def wait_for_trigger():
    """Block until the user triggers a capture. Returns True if triggered."""
    if INPUT_MODE == "keyboard":
        input("Press Enter to take a photo... ")
        return True
    # button mode
    print(f"Waiting for button press (up to {ARM_TIMEOUT:.0f}s)...")
    return button.wait_for_press(timeout=ARM_TIMEOUT)


# ----------------------------------------------------------------------------
# Printing
# ----------------------------------------------------------------------------
class _CupsPrinter:
    """Marker for the CUPS-raw backend.

    The actual printing is done in print_receipt(): we build the ESC/POS byte
    stream ourselves (no python-escpos needed) and pipe it to
    `lp -d CUPS_PRINTER_NAME`, so there's no device handle to hold open here.
    """

    def close(self):
        pass


def setup_printer():
    """Return an ESC-POS printer object, or None to render to the console."""
    if PRINTER_BACKEND == "console":
        return None
    if PRINTER_BACKEND == "cups":
        # No library needed -- bytes are built natively and piped to `lp`.
        # Just confirm `lp` exists so we fail loudly here, not mid-print.
        from shutil import which
        if which("lp") is None:
            print("[printer] 'lp' not found (is CUPS installed?); using console")
            return None
        return _CupsPrinter()
    try:
        from escpos import printer as escpos_printer

        if PRINTER_BACKEND == "usb":
            kwargs = {}
            if PRINTER_USB_OUT_EP is not None:
                kwargs["out_ep"] = PRINTER_USB_OUT_EP
            if PRINTER_PROFILE is not None:
                kwargs["profile"] = PRINTER_PROFILE
            return escpos_printer.Usb(
                PRINTER_USB_VENDOR, PRINTER_USB_PRODUCT, **kwargs
            )
        if PRINTER_BACKEND == "serial":
            return escpos_printer.Serial(
                devfile=PRINTER_SERIAL_PORT, baudrate=PRINTER_SERIAL_BAUD
            )
        if PRINTER_BACKEND == "network":
            return escpos_printer.Network(PRINTER_NETWORK_HOST)
        print(f"[printer] unknown backend {PRINTER_BACKEND!r}; using console")
    except Exception as exc:  # missing lib, wrong IDs, no permissions, etc.
        print(f"[printer] init failed ({exc}); falling back to console")
    return None


def _enhance_gray(img):
    """Grayscale + contrast/gamma/sharpen pass. Returns an 'L' PIL image.

    CLAHE (local contrast) uses OpenCV if it's installed; otherwise it falls
    back to Pillow's global autocontrast so the Pi install can stay light.
    """
    from PIL import ImageOps, ImageFilter

    gray = ImageOps.grayscale(img)
    if not ENHANCE:
        return gray

    # 1) local contrast -- the biggest win for faces under uneven booth light
    try:
        import cv2
        import numpy as np

        clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP,
                                tileGridSize=(CLAHE_GRID, CLAHE_GRID))
        gray = ImageOps.grayscale(ImageOps.exif_transpose(img))  # honour rotation
        from PIL import Image
        gray = Image.fromarray(clahe.apply(np.asarray(gray)))
    except Exception:
        gray = ImageOps.autocontrast(gray)

    # 2) gamma -- lift midtones so faces don't print muddy
    inv = 1.0 / GAMMA
    lut = [min(255, int((i / 255) ** inv * 255 + 0.5)) for i in range(256)]
    gray = gray.point(lut)

    # 3) sharpen -- thermal printing softens detail, so pre-sharpen
    gray = gray.filter(
        ImageFilter.UnsharpMask(radius=SHARPEN_RADIUS, percent=SHARPEN_PERCENT)
    )
    return gray


def _atkinson_dither(gray):
    """1-bit Atkinson dither (cleaner highlights than Floyd-Steinberg)."""
    import numpy as np
    from PIL import Image

    w, h = gray.size
    buf = np.asarray(gray, dtype=np.float32).reshape(-1).tolist()  # flat = fast
    for y in range(h):
        base = y * w
        for x in range(w):
            i = base + x
            old = buf[i]
            new = 255.0 if old >= 128 else 0.0
            buf[i] = new
            err = (old - new) / 8.0  # Atkinson diffuses only 6/8 of the error
            if x + 1 < w: buf[i + 1] += err
            if x + 2 < w: buf[i + 2] += err
            if y + 1 < h:
                if x > 0: buf[i + w - 1] += err
                buf[i + w] += err
                if x + 1 < w: buf[i + w + 1] += err
            if y + 2 < h: buf[i + 2 * w] += err
    out = np.clip(np.array(buf), 0, 255).reshape(h, w).astype("uint8")
    return Image.fromarray(out).convert("1")


def _prep_image(photo_path):
    """Scale the capture to the print head width, enhance, and dither to 1-bit."""
    from PIL import Image

    img = Image.open(photo_path)
    w, h = img.size
    new_h = max(1, round(h * PRINT_WIDTH / w))
    img = img.resize((PRINT_WIDTH, new_h))
    gray = _enhance_gray(img)
    if DITHER == "atkinson":
        return _atkinson_dither(gray)
    return gray.convert("1")  # Floyd-Steinberg (Pillow built-in)


def _render_receipt(prn, photo_path, caption, fortune, emoji):
    """Issue the ESC/POS commands for one receipt onto an escpos printer object.

    Used by the usb/serial/network backends (the cups backend builds bytes
    natively in _escpos_receipt_bytes() and needs no python-escpos).
    """
    prn.set(align="center")
    prn.image(_prep_image(photo_path))
    prn.text("\n")
    prn.set(align="center", bold=True)
    prn.text(caption + "\n")
    prn.set(align="center", bold=False)
    prn.text(emoji + "\n")
    prn.text(fortune + "\n")
    prn.text(f"{datetime.now():%Y-%m-%d %H:%M:%S}\n")
    prn.cut()


# Raw ESC/POS control codes (so the cups backend needs no python-escpos).
_ESC = b"\x1b"
_GS = b"\x1d"


def _raster_bytes(img_1bit):
    """Encode a 1-bit PIL image as ESC/POS GS v 0 raster data.

    Sent in horizontal bands so each command stays small (some printers choke
    on one giant raster). Black pixels (value 0 in mode '1') become set bits.
    """
    img = img_1bit.convert("1")
    w, h = img.size
    width_bytes = (w + 7) // 8
    px = list(img.getdata())  # 0 = black, 255 = white

    out = bytearray()
    band = 128                # rows per GS v 0 command
    y = 0
    while y < h:
        rows = min(band, h - y)
        out += _GS + b"v0" + bytes([
            0,                                      # m = normal
            width_bytes & 0xFF, (width_bytes >> 8) & 0xFF,
            rows & 0xFF, (rows >> 8) & 0xFF,
        ])
        for ry in range(rows):
            base = (y + ry) * w
            line = bytearray(width_bytes)
            for x in range(w):
                if px[base + x] == 0:               # black dot -> set the bit
                    line[x >> 3] |= 0x80 >> (x & 7)
            out += line
        y += rows
    return bytes(out)


def _line(text):
    """ASCII-encode a line for the printer (non-ASCII -> '?')."""
    return text.encode("ascii", "replace") + b"\n"


def _escpos_receipt_bytes(photo_path, caption, fortune, emoji):
    """Build the full ESC/POS byte stream for one receipt, no library needed."""
    out = bytearray()
    out += _ESC + b"@"            # initialize
    out += _ESC + b"a" + b"\x01"  # center align
    out += _raster_bytes(_prep_image(photo_path))
    out += b"\n"
    out += _ESC + b"E" + b"\x01"  # bold on
    out += _line(caption)
    out += _ESC + b"E" + b"\x00"  # bold off
    out += _line(emoji)
    out += _line(fortune)
    out += _line(f"{datetime.now():%Y-%m-%d %H:%M:%S}")
    out += b"\n\n\n"             # feed past the tear bar
    out += _GS + b"V" + b"\x00"   # full cut
    return bytes(out)


def print_receipt(prn, photo_path, caption):
    fortune = pick_fortune()
    emoji = pick_emoji()

    # CUPS-raw path: build the ESC/POS bytes ourselves and pipe them to
    # `lp -d <queue>` -- the exact queue you proved works (`lp -d POS80_raw`).
    # No python-escpos, and no escpos-vs-CUPS fight over the USB device.
    if PRINTER_BACKEND == "cups":
        try:
            data = _escpos_receipt_bytes(photo_path, caption, fortune, emoji)
            subprocess.run(
                ["lp", "-d", CUPS_PRINTER_NAME],
                input=data,                # raw ESC/POS bytes on stdin
                check=True,
            )
        except Exception as exc:
            print(f"[printer] cups path failed ({exc}); dumping to console")
            _console_receipt(photo_path, caption, fortune, emoji)
        return

    if prn is None:
        _console_receipt(photo_path, caption, fortune, emoji)
        return
    try:
        _render_receipt(prn, photo_path, caption, fortune, emoji)
    except Exception as exc:
        print(f"[printer] print failed ({exc}); dumping to console")
        _console_receipt(photo_path, caption, fortune, emoji)


def _ascii_art(bits, cols=RECEIPT_COLS):
    """ASCII preview built from the SAME 1-bit bitmap the printer receives.

    We convert the dithered image to 'L' and downscale -- shrinking averages
    the dot density back into grayscale, so the preview reflects the real
    enhancement + dither, not just the photo.
    """
    img = bits.convert("L")
    w, h = img.size
    # terminal chars are roughly twice as tall as wide -> squash the rows
    rows = max(1, round(h / w * cols * 0.5))
    img = img.resize((cols, rows))           # 'L' downscale averages the dots
    px = list(img.getdata())
    n = len(ASCII_RAMP) - 1
    lines = []
    for r in range(rows):
        row = px[r * cols:(r + 1) * cols]
        lines.append("".join(ASCII_RAMP[p * n // 255] for p in row))
    return lines


def _center(text, width):
    return text.center(width)


def _wrap(text, width):
    """Greedy word-wrap so long fortunes fit the receipt width."""
    import textwrap
    return textwrap.wrap(text, width) or [""]


def _console_receipt(photo_path, caption, fortune, emoji):
    """Render a receipt-shaped preview, including an ASCII version of the photo."""
    inner = RECEIPT_COLS
    bar = "+" + "-" * (inner + 2) + "+"

    def row(text):
        print("| " + _center(text, inner) + " |")

    print("\n" + bar)
    row("PHOTOBOOTH")
    row("")
    preview_path = None
    try:
        bits = _prep_image(photo_path)       # dither once, reuse below
        for line in _ascii_art(bits):
            print("| " + line.ljust(inner) + " |")
        if SAVE_PRINT_PREVIEW:
            preview_path = os.path.splitext(photo_path)[0] + "_print.png"
            bits.save(preview_path)          # the true 576px bitmap, openable
    except Exception as exc:
        row(f"[photo preview failed: {exc}]")
    row("")
    row(caption)
    row(emoji)
    for line in _wrap(fortune, inner):
        row(line)
    row(f"{datetime.now():%Y-%m-%d %H:%M:%S}")
    row(os.path.basename(photo_path))
    print(bar)
    print("  ( -- printer would cut here -- )")
    if preview_path:
        print(f"  full-res print preview: {preview_path}")
    print()


# ----------------------------------------------------------------------------
# Camera
# ----------------------------------------------------------------------------
def capture_photo():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(PHOTO_DIR, f"photo_{ts}.jpg")
    camera.capture_file(path)
    return path


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
            print_receipt(prn, photo_path, CAPTION)
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
