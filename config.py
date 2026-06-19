"""Config -- the knobs you'll tune on-site.

Every other module pulls its settings from here (``from config import *``),
so this is the one file to edit when adjusting behaviour on the Pi.
"""

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
