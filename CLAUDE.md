# CLAUDE.md — Furby Photobooth (Raspberry Pi)

Context brief for working on this repo with Claude Code. Read before editing.

## What this is

A motion-triggered photobooth built into a Furby-sculpture art installation,
running on a **Raspberry Pi 4B**. Flow:

```
IDLE → BECKON (audio) → ARMED → CAPTURE → PRINT (thermal receipt) → COOLDOWN
```

Main script: `app/photobooth.py`. State machine in `main()`. Hardware: PIR motion
sensor (GPIO 17), Pi camera (picamera2), optional GPIO button (GPIO 27), and an
80mm thermal receipt printer over USB.

## Repo layout

Everything the Pi needs to run lives in **`app/`** — that's the only folder you
copy to the device. Everything else is supporting material that never ships.

```
app/    <- runtime: copy ONLY this to the Pi, run from inside it
  photobooth.py config.py audio.py hardware.py imaging.py printing.py receipt.py
  requirements.txt fortunes.txt magicsounds.wav
  fonts/  fortune_icons_svg/
docs/   <- design handoff, contact sheet, HTML preview (not needed to run)
README.md  CLAUDE.md  LICENSE   <- repo meta
```

Run from inside `app/` so relative asset paths resolve:
`cd app && python3 photobooth.py`. Some paths are resolved against the current
working directory (`magicsounds.wav`, `photos/`, `fortunes.txt`) and some against
the source dir (`fonts/`, `fortune_icons_svg/`); running from `app/` makes both
the same directory, so everything just works.

## Hardware that's confirmed working

- **PIR sensor** on GPIO 17 — working.
- **Pi camera** via `picamera2` — working.
- **Thermal printer**: 80mm POS-80, NXP-based controller.
  - USB ID: **`1fc9:2016`** (vendor `0x1fc9` NXP, product `0x2016`). Confirmed via `lsusb`.
  - Serial in URI: `A02416693632`.
  - The print mechanism responds to raw bytes (it physically advances paper),
    but does NOT print usable output through CUPS' generic `POS-80` PPD.
    **Decision: bypass CUPS entirely and drive it with `python-escpos` raw.**

## Printer config in photobooth.py

The printer section must be set to the USB backend with the correct IDs:

```python
PRINTER_BACKEND = "usb"
PRINTER_USB_VENDOR = 0x1fc9
PRINTER_USB_PRODUCT = 0x2016
```

`PRINT_WIDTH = 576` (80mm head). If output looks shifted/garbled, try 512.

## Critical gotchas (learned the hard way)

### 1. CUPS vs python-escpos fight over the USB device
CUPS grabs the printer via its usb backend and blocks escpos (and vice versa).
Before running the script, disable the CUPS queues:

```bash
sudo cupsdisable Printer_POS-80 POS80_raw
```

Long term, removing the CUPS queues entirely is fine — this project does not
use CUPS at all. If escpos raises a "device busy" / "Resource busy" error,
this is almost certainly the cause.

### 2. USB permissions
Run requires access to the USB device. A udev rule avoids needing sudo:

```bash
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="1fc9", ATTRS{idProduct}=="2016", MODE="0666"' | sudo tee /etc/udev/rules.d/99-pos80.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

### 3. escpos may not auto-detect the OUT endpoint
NXP-based 80mm printers sometimes expose multiple endpoints and python-escpos
can't always pick the right OUT endpoint, causing a USBError or silent no-op.
If `Usb(0x1fc9, 0x2016)` fails or prints nothing, find the OUT endpoint:

```bash
lsusb -v -d 1fc9:2016 2>/dev/null | grep -E "bEndpointAddress|wMaxPacketSize"
```

Then pass it explicitly, e.g.:

```python
escpos_printer.Usb(0x1fc9, 0x2016, out_ep=0x03)
```

If escpos complains about a missing printer profile, pass `profile="default"`
or `profile="TM-T88III"` as a fallback — most 80mm printers accept it.

## Minimal hardware smoke test

Run this (with CUPS disabled) to confirm the escpos path before touching the
full script:

```python
from escpos.printer import Usb
p = Usb(0x1fc9, 0x2016)
p.text("HELLO FROM PI\n\n\n")
p.cut()
```

Expected: text prints, paper feeds, paper cuts. If it moves but prints blank →
endpoint/profile issue (see gotcha #3). If "busy" → CUPS conflict (gotcha #1).

## Image pipeline

`_prep_image()` → `_enhance_gray()` (grayscale → CLAHE local contrast → gamma →
unsharp mask) → dither (Atkinson default, Floyd fallback) → 1-bit at 576px wide.

Tunables live at the top of the file: `CLAHE_CLIP`, `CLAHE_GRID`, `GAMMA`,
`SHARPEN_RADIUS`, `SHARPEN_PERCENT`, `DITHER`. These need on-site tuning against
real receipts under booth lighting — faces tend to print muddy, hence
`GAMMA = 0.85` to lift midtones.

`PRINTER_BACKEND = "console"` renders an ASCII preview + saves the true 576px
1-bit PNG (`*_print.png`) so the pipeline can be tuned with no hardware attached.

## Dev workflow notes

- Test trigger via `INPUT_MODE = "keyboard"` (Enter key) before wiring the
  physical button on GPIO 27.
- Keep `PRINTER_BACKEND = "console"` for image-tuning iterations; switch to
  `"usb"` only for real print tests.
- Environment: Raspberry Pi OS, Python 3. Install deps with
  `pip3 install python-escpos --break-system-packages` and
  `sudo apt install libusb-1.0-0 alsa-utils`.

## Running as a gallery service

For unattended gallery runs the app installs as a **systemd service** (auto-start
on boot, auto-restart on crash, logs to the journal). The unit + full runbook
(install, SSH, Tailscale, static IP, dry run, troubleshooting) live in `deploy/`:
`deploy/photobooth.service` and `deploy/DEPLOY.md`.

Key points:
- The service sets `PHOTOBOOTH_INPUT_MODE=button` (env override read in
  `config.py`). Keyboard mode calls `input()`, which has no stdin under systemd
  and would crash — so headless runs must use button mode. Bench runs with no
  env var still default to keyboard.
- Logging goes through `app/log.py` (Python `logging` -> stdout -> journald).
  One clean line per event: `journalctl -u photobooth -f` tells the whole story
  (PIR -> beckon -> trigger -> capture -> print -> cooldown). Tune verbosity with
  `PHOTOBOOTH_LOG_LEVEL`.

## Open TODOs (from script notes)

- Randomized fortune from a text doc + randomized set of 3 emoji on the receipt
- Audio countdown / delay after button press before capture
- Physical button (pink or purple) on GPIO 27
- Printer paper + power source sourcing
- Artist statement; sticker/frame/speech-bubble around the printed image
