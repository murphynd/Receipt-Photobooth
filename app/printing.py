"""Receipt rendering + printer backends (console / cups / usb / serial / network).

print_receipt() is the entry point. Fortune and emoji extras live here since
they're only ever stamped onto a receipt.
"""

from datetime import datetime
import subprocess
import random
import os

from config import (
    FORTUNE_FILE,
    FORTUNES_FALLBACK,
    EMOJI_POOL,
    EMOJI_COUNT,
    RECEIPT_STYLE,
    PRINTER_BACKEND,
    CUPS_PRINTER_NAME,
    PRINTER_USB_VENDOR,
    PRINTER_USB_PRODUCT,
    PRINTER_USB_OUT_EP,
    PRINTER_PROFILE,
    PRINTER_SERIAL_PORT,
    PRINTER_SERIAL_BAUD,
    PRINTER_NETWORK_HOST,
    RECEIPT_COLS,
    ASCII_RAMP,
    SAVE_PRINT_PREVIEW,
)
from imaging import _prep_image


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
# Printer setup
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


# ----------------------------------------------------------------------------
# python-escpos rendering (usb/serial/network backends)
# ----------------------------------------------------------------------------
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


# ----------------------------------------------------------------------------
# Native ESC/POS byte stream (cups backend -- no python-escpos)
# ----------------------------------------------------------------------------
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


# ----------------------------------------------------------------------------
# Print dispatch
# ----------------------------------------------------------------------------
def print_receipt(prn, photo_path, caption):
    fortune = pick_fortune()

    if RECEIPT_STYLE == "scuptee":
        _print_scuptee(prn, photo_path, fortune)
        return

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


# ----------------------------------------------------------------------------
# Scuptee graphic receipt (the whole receipt is one bitmap)
# ----------------------------------------------------------------------------
def _print_scuptee(prn, photo_path, fortune):
    """Build the full Scuptee receipt image and send it via the active backend."""
    from receipt import build_receipt_image

    img = build_receipt_image(photo_path, fortune)

    if PRINTER_BACKEND == "cups":
        try:
            out = bytearray()
            out += _ESC + b"@"            # initialize
            out += _ESC + b"a" + b"\x01"  # center align
            out += _raster_bytes(img)
            out += b"\n\n\n"             # feed past the tear bar
            out += _GS + b"V" + b"\x00"   # full cut
            subprocess.run(["lp", "-d", CUPS_PRINTER_NAME],
                           input=bytes(out), check=True)
        except Exception as exc:
            print(f"[printer] cups path failed ({exc}); saving preview")
            _scuptee_console(img, photo_path)
        return

    if prn is None:
        _scuptee_console(img, photo_path)
        return
    try:
        prn.set(align="center")
        prn.image(img)
        prn.cut()
    except Exception as exc:
        print(f"[printer] print failed ({exc}); saving preview")
        _scuptee_console(img, photo_path)


def _scuptee_console(img, photo_path):
    """No-hardware preview: save the full receipt PNG + ASCII it to stdout."""
    preview_path = os.path.splitext(photo_path)[0] + "_receipt.png"
    try:
        img.save(preview_path)
    except Exception as exc:
        preview_path = None
        print(f"[receipt] could not save preview ({exc})")
    print("\n+" + "-" * (RECEIPT_COLS + 2) + "+")
    for line in _ascii_art(img):
        print("| " + line.ljust(RECEIPT_COLS) + " |")
    print("+" + "-" * (RECEIPT_COLS + 2) + "+")
    print("  ( -- printer would cut here -- )")
    if preview_path:
        print(f"  full-res receipt preview: {preview_path}")
    print()


# ----------------------------------------------------------------------------
# Console preview (no hardware)
# ----------------------------------------------------------------------------
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
