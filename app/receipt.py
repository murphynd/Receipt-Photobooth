"""Scuptee "Arcade Pixel" receipt -- drawn as one tall 1-bit bitmap.

The whole receipt (logo, framed photo, fortune block, itemized list, QR code,
footer) is composed into a single 576px-wide image so it can be sent to the
thermal printer the same way a photo is. See design_handoff_scuptee_receipt/
for the reference design this recreates.

Entry point: build_receipt_image(photo_path, fortune) -> 1-bit PIL Image.

Everything is sized off PROTO_W (the 360px on-screen prototype) scaled up by
SCALE to the 576-dot print head, so the numbers below match the design doc's
prototype pixels x 1.6.
"""

import os
import glob
import random
from datetime import datetime

from config import (
    FONT_DIR,
    FONT_VT323,
    FONT_BUNGEE,
    WORDMARK,
    TAGLINE,
    ARTIST_HANDLE,
    QR_URL,
    LUCKY_COUNT,
    LUCKY_MAX,
    ICON_DIR,
    ICON_COUNT,
    HEADER_ICON,
)
from imaging import prep_photo

_HERE = os.path.dirname(os.path.abspath(__file__))

# --- print geometry ---------------------------------------------------------
WIDTH = 576                 # dots across an 80mm head
PROTO_W = 360              # the design prototype's CSS width
SCALE = WIDTH / PROTO_W   # 1.6 -- multiply any prototype px by this
INK = 0                    # black in an "L" image
PAPER = 255               # white

PAD = round(26 * SCALE)             # card side padding
PAD_BOTTOM = round(30 * SCALE)
GAP = round(16 * SCALE)             # vertical margin around dash bands
LEFT = PAD
RIGHT = WIDTH - PAD
CONTENT_W = RIGHT - LEFT
CENTER = WIDTH // 2


def px(proto_px):
    """Prototype pixels -> print dots."""
    return round(proto_px * SCALE)


# ----------------------------------------------------------------------------
# Fonts
# ----------------------------------------------------------------------------
def _font(filename, proto_size):
    """Load a TrueType font at the print-scaled size, or fall back to default."""
    from PIL import ImageFont

    path = os.path.join(_HERE, FONT_DIR, filename)
    try:
        return ImageFont.truetype(path, px(proto_size))
    except OSError:
        print(f"[receipt] font {filename} not found in {FONT_DIR}/ "
              "-- using default (lower fidelity). See fonts/README.md.")
        try:
            return ImageFont.truetype("DejaVuSansMono.ttf", px(proto_size))
        except OSError:
            return ImageFont.load_default()


def _fonts():
    """All the fonts the receipt needs, keyed by role (prototype px sizes)."""
    return {
        "wordmark": _font(FONT_BUNGEE, 38),
        "tag": _font(FONT_VT323, 18),
        "stamp": _font(FONT_VT323, 18),
        "fortune_head": _font(FONT_VT323, 22),
        "fortune": _font(FONT_VT323, 21),
        "lucky": _font(FONT_VT323, 20),
        "item": _font(FONT_VT323, 19),
        "total": _font(FONT_VT323, 23),
        "qr_cap": _font(FONT_VT323, 19),
        "handle": _font(FONT_VT323, 24),
        "footer": _font(FONT_VT323, 22),
        "footer_sub": _font(FONT_VT323, 18),
        "rec": _font(FONT_VT323, 16),
    }


# ----------------------------------------------------------------------------
# Text helpers (letter-spacing aware)
# ----------------------------------------------------------------------------
def _line_h(font, factor=1.0):
    asc, desc = font.getmetrics()
    return round((asc + desc) * factor)


def _text_w(draw, text, font, ls=0):
    w = sum(draw.textlength(ch, font=font) for ch in text)
    return w + ls * max(0, len(text) - 1)


def _draw_run(draw, x, y, text, font, ls=0, fill=INK):
    cx = x
    for ch in text:
        draw.text((cx, y), ch, font=font, fill=fill)
        cx += draw.textlength(ch, font=font) + ls
    return cx


def _draw_center(draw, y, text, font, ls=0, fill=INK):
    x = CENTER - _text_w(draw, text, font, ls) / 2
    _draw_run(draw, x, y, text, font, ls, fill)


def _wrap(draw, text, font, max_w, ls=0):
    """Greedy word-wrap to fit max_w pixels."""
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if _text_w(draw, trial, font, ls) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


# ----------------------------------------------------------------------------
# Decorative pieces
# ----------------------------------------------------------------------------
def _dash_band(draw, y, thick_proto=6, ink_proto=8, gap_proto=6):
    """A repeating dash divider; returns the y just below it."""
    thick = max(2, px(thick_proto))
    ink = max(2, px(ink_proto))
    gap = max(1, px(gap_proto))
    cx = LEFT
    while cx < RIGHT:
        draw.rectangle([cx, y, min(cx + ink, RIGHT), y + thick - 1], fill=INK)
        cx += ink + gap
    return y + thick


def _crop_marks(draw, x0, y0, x1, y1):
    """Four L-shaped corner crop marks around a box."""
    s = px(16)        # arm length
    t = max(2, px(2))  # stroke thickness

    def rect(ax, ay, bx, by):
        draw.rectangle([min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)], fill=INK)

    for (cx, cy, dx, dy) in (
        (x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)
    ):
        rect(cx, cy, cx + dx * s, cy + dy * (t - 1))   # horizontal arm
        rect(cx, cy, cx + dx * (t - 1), cy + dy * s)   # vertical arm


# --- small ornaments (the design's geometric accents; VT323 lacks the glyphs) ---
def _orn_square(draw, cx, cy, s, fill=INK):
    draw.rectangle([cx - s / 2, cy - s / 2, cx + s / 2, cy + s / 2], fill=fill)


def _orn_circle(draw, cx, cy, r, fill=INK):
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)


def _orn_tri(draw, cx, cy, s, fill=INK):
    """A right-pointing filled triangle (the design's ▸ / ▶)."""
    draw.polygon([(cx - s / 2, cy - s / 2), (cx - s / 2, cy + s / 2),
                  (cx + s / 2, cy)], fill=fill)


def _orn_shade(draw, cx, cy, s, fill=INK):
    """A shaded checkerboard block (the design's ▓)."""
    n = 4
    step = s / n
    x0, y0 = cx - s / 2, cy - s / 2
    for r in range(n):
        for c in range(n):
            if (r + c) % 2 == 0:
                draw.rectangle([x0 + c * step, y0 + r * step,
                                x0 + (c + 1) * step, y0 + (r + 1) * step], fill=fill)


def _quad(p0, p1, p2, n=24):
    """Sample a quadratic bezier into n+1 points."""
    pts = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        x = u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0]
        y = u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]
        pts.append((x, y))
    return pts


def _draw_robot(draw, ox, oy, scale):
    """Draw the line-art robot mascot from the design's SVG primitives.

    Coordinates are the SVG's (viewBox 0 0 120 150); scale + offset map them
    onto the receipt. Drawn directly with PIL so no SVG renderer is required.
    """
    def P(x, y):
        return (ox + x * scale, oy + y * scale)

    w = max(2, round(4 * scale))   # SVG stroke-width 4
    def line(a, b):
        draw.line([P(*a), P(*b)], fill=INK, width=w, joint="curve")
    def dot(cx, cy, r):
        rr = r * scale
        c = P(cx, cy)
        draw.ellipse([c[0] - rr, c[1] - rr, c[0] + rr, c[1] + rr], fill=INK)
    def ring(cx, cy, r):
        rr = r * scale
        c = P(cx, cy)
        draw.ellipse([c[0] - rr, c[1] - rr, c[0] + rr, c[1] + rr],
                     outline=INK, width=w)
    def rrect(x, y, ww, hh, rad):
        box = [P(x, y), P(x + ww, y + hh)]
        # rounded_rectangle was added in Pillow 8.2; fall back to a plain
        # rectangle on older builds so the robot still draws instead of crashing.
        if hasattr(draw, "rounded_rectangle"):
            draw.rounded_rectangle(box, radius=rad * scale, outline=INK, width=w)
        else:
            draw.rectangle(box, outline=INK, width=w)
    def curve(pts):
        draw.line([P(x, y) for (x, y) in pts], fill=INK, width=w, joint="curve")

    line((60, 20), (60, 34))                 # antenna
    dot(60, 14, 5)                            # antenna tip
    rrect(27, 34, 66, 50, 15)                 # head
    dot(48, 55, 4.5); dot(72, 55, 4.5)        # eyes
    curve(_quad((46, 67), (60, 77), (74, 67)))   # smile
    rrect(34, 90, 52, 40, 11)                 # body
    # heart on the chest (simple filled heart approximating the SVG path)
    hx, hy, hs = 60, 104, 11
    lobe = hs * 0.5 * scale
    cL = P(hx - hs * 0.45, hy - hs * 0.25)
    cR = P(hx + hs * 0.45, hy - hs * 0.25)
    draw.ellipse([cL[0] - lobe, cL[1] - lobe, cL[0] + lobe, cL[1] + lobe], fill=INK)
    draw.ellipse([cR[0] - lobe, cR[1] - lobe, cR[0] + lobe, cR[1] + lobe], fill=INK)
    draw.polygon([P(hx - hs * 0.78, hy - hs * 0.1),
                  P(hx + hs * 0.78, hy - hs * 0.1),
                  P(hx, hy + hs * 0.85)], fill=INK)
    curve(_quad((34, 99), (21, 103), (19, 116)))   # left arm
    curve(_quad((86, 99), (99, 103), (101, 116)))  # right arm
    line((48, 130), (48, 142)); line((72, 130), (72, 142))  # legs
    line((41, 143), (55, 143)); line((65, 143), (79, 143))  # feet


# ----------------------------------------------------------------------------
# QR code
# ----------------------------------------------------------------------------
def _qr_image(url, target):
    """Return a 1-bit QR PIL image (target x target px), or None if no library."""
    try:
        import qrcode
    except ImportError:
        print("[receipt] 'qrcode' not installed -- skipping QR. "
              "Install with: pip3 install qrcode --break-system-packages")
        return None
    from PIL import Image

    qr = qrcode.QRCode(border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(url)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    n = len(matrix)
    box = max(1, target // n)
    size = box * n
    img = Image.new("L", (size, size), PAPER)
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    for r, rowvals in enumerate(matrix):
        for c, on in enumerate(rowvals):
            if on:
                d.rectangle([c * box, r * box, (c + 1) * box - 1, (r + 1) * box - 1],
                            fill=INK)
    return img


# ----------------------------------------------------------------------------
# Fortune icons (optional -- needs cairosvg)
# ----------------------------------------------------------------------------
def _render_icon(path, size):
    """Rasterize one SVG icon to a 1-bit PIL image, or None if unsupported."""
    try:
        import cairosvg
    except Exception:
        return None
    from PIL import Image
    import io

    try:
        png = cairosvg.svg2png(url=path, output_width=size, output_height=size,
                               background_color="white")
        img = Image.open(io.BytesIO(png)).convert("L")
        return img.point(lambda p: INK if p < 128 else PAPER)
    except Exception:
        return None


def _pick_icons(n):
    files = glob.glob(os.path.join(_HERE, ICON_DIR, "*.svg"))
    if not files:
        return []
    return random.sample(files, min(n, len(files)))


def _header_icon(size):
    """The mascot for the header lockup: the configured SVG (HEADER_ICON)
    rasterized to ``size`` px, or None when cairosvg / the file is unavailable
    (the caller then falls back to the hand-drawn robot)."""
    return _render_icon(os.path.join(_HERE, ICON_DIR, HEADER_ICON), size)


# ----------------------------------------------------------------------------
# State generated per print job
# ----------------------------------------------------------------------------
def pick_lucky_numbers():
    nums = random.sample(range(1, LUCKY_MAX + 1), LUCKY_COUNT)
    return " ".join(f"{n:02d}" for n in nums)


# ----------------------------------------------------------------------------
# Build the receipt
# ----------------------------------------------------------------------------
def build_receipt_image(photo_path, fortune):
    """Compose the full Scuptee receipt and return a 1-bit PIL Image."""
    from PIL import Image, ImageDraw

    f = _fonts()
    # Draw onto a tall canvas, then crop to the content height at the end.
    canvas = Image.new("L", (WIDTH, 6000), PAPER)
    draw = ImageDraw.Draw(canvas)
    y = PAD

    # 1) HEADER LOCKUP -- mascot + wordmark, centered as a group -------------
    mascot_h = px(74)
    mascot = _header_icon(mascot_h)               # clown-cat SVG (None -> robot)
    mascot_w = mascot.width if mascot is not None else px(58)
    word_w = _text_w(draw, WORDMARK, f["wordmark"])
    sq = px(10)            # the ■ accents flanking the tagline
    sq_gap = px(8)
    tag_core_w = _text_w(draw, TAGLINE, f["tag"], ls=px(5))
    tag_w = sq + sq_gap + tag_core_w + sq_gap + sq
    block_w = max(word_w, tag_w)
    group_w = mascot_w + px(12) + block_w
    gx = CENTER - group_w / 2
    if mascot is not None:
        canvas.paste(mascot.convert("L"), (round(gx), round(y)))
    else:
        _draw_robot(draw, gx, y, mascot_h / 150.0)
    tx = gx + mascot_w + px(12)
    draw.text((tx, y + px(2)), WORDMARK, font=f["wordmark"], fill=INK)
    word_h = _line_h(f["wordmark"], 0.85)
    tag_y = y + px(2) + word_h + px(4)
    tag_cy = tag_y + _line_h(f["tag"]) * 0.5
    _orn_square(draw, tx + sq / 2, tag_cy, sq)
    sx = _draw_run(draw, tx + sq + sq_gap, tag_y, TAGLINE, f["tag"], ls=px(5))
    _orn_square(draw, sx + sq_gap - px(5) + sq / 2, tag_cy, sq)
    y += mascot_h + GAP

    # dash band
    y = _dash_band(draw, y) + GAP

    # 2) PHOTO BLOCK with crop marks ----------------------------------------
    block_pad = px(14)
    photo_w = CONTENT_W - 2 * block_pad
    photo = prep_photo(photo_path, photo_w)        # 1-bit, 4:5
    photo_h = photo.height
    bx0, by0 = LEFT, y
    bx1, by1 = RIGHT, y + photo_h + 2 * block_pad
    _crop_marks(draw, bx0, by0, bx1, by1)
    photo_x = LEFT + block_pad
    photo_y = y + block_pad
    canvas.paste(photo.convert("L"), (photo_x, photo_y))
    # "● REC" badge top-left of the photo (white dot + text on a black pill)
    rec = "REC"
    dot_r = px(3)
    dot_gap = px(4)
    rw = dot_r * 2 + dot_gap + _text_w(draw, rec, f["rec"], ls=px(1))
    rh = _line_h(f["rec"], 0.9)
    pad_b = px(4)
    bx = photo_x + px(4)
    byb = photo_y + px(4)
    draw.rectangle([bx, byb, bx + rw + 2 * pad_b, byb + rh + pad_b], fill=INK)
    badge_cy = byb + (rh + pad_b) / 2
    _orn_circle(draw, bx + pad_b + dot_r, badge_cy, dot_r, fill=PAPER)
    _draw_run(draw, bx + pad_b + dot_r * 2 + dot_gap, byb + pad_b // 2,
              rec, f["rec"], ls=px(1), fill=PAPER)
    y = by1 + px(6)

    # 3) TIMESTAMP ----------------------------------------------------------
    stamp = f"{datetime.now():%m/%d/%y  %H:%M}"
    dot_r = px(3)
    dot_gap = px(6)
    sw = _text_w(draw, stamp, f["stamp"], ls=px(2))
    total = dot_r * 2 + dot_gap + sw
    sx = CENTER - total / 2
    _orn_circle(draw, sx + dot_r, y + _line_h(f["stamp"]) * 0.5, dot_r)
    _draw_run(draw, sx + dot_r * 2 + dot_gap, y, stamp, f["stamp"], ls=px(2))
    y += _line_h(f["stamp"]) + GAP

    # dash band
    y = _dash_band(draw, y) + GAP

    # 4) FORTUNE BLOCK ------------------------------------------------------
    _draw_center(draw, y, "=== YOUR FORTUNE ===", f["fortune_head"], ls=px(3))
    y += _line_h(f["fortune_head"]) + px(8)

    # icon row -- three random glyphs across the receipt, the visual fortune
    # (optional: only if cairosvg is installed, else this block is skipped)
    icon_size = px(34)
    icons = [im for im in (_render_icon(p, icon_size) for p in _pick_icons(ICON_COUNT)) if im]
    if icons:
        gap = px(16)
        total = sum(im.width for im in icons) + gap * (len(icons) - 1)
        ix = CENTER - total / 2
        for im in icons:
            canvas.paste(im.convert("L"), (round(ix), y))
            ix += im.width + gap
        y += icon_size + px(12)

    for ln in _wrap(draw, fortune, f["fortune"], CONTENT_W - px(8)):
        _draw_center(draw, y, ln, f["fortune"])
        y += _line_h(f["fortune"], 1.25)
    y += px(6)
    nums = pick_lucky_numbers()
    tri_s = px(10)
    lgap = px(8)
    lw = _text_w(draw, "LUCKY", f["lucky"], ls=px(3))
    nw = _text_w(draw, nums, f["lucky"], ls=px(3))
    total = lw + lgap + tri_s + lgap + nw
    lx = CENTER - total / 2
    _draw_run(draw, lx, y, "LUCKY", f["lucky"], ls=px(3))
    _orn_tri(draw, lx + lw + lgap + tri_s / 2, y + _line_h(f["lucky"]) * 0.5, tri_s)
    _draw_run(draw, lx + lw + lgap + tri_s + lgap, y, nums, f["lucky"], ls=px(3))
    y += _line_h(f["lucky"]) + px(12)

    y += GAP
    # dash band
    y = _dash_band(draw, y) + GAP

    # 5) ITEMIZED BLOCK -----------------------------------------------------
    item_lh = _line_h(f["item"], 1.0)
    rows = [("1x PHOTO CAPTURE", "1 PLAY"),
            ("1x GOOD VIBES", "INCL."),
            ("1x FORTUNE", "INCL.")]
    for left_t, right_t in rows:
        draw.text((LEFT, y), left_t, font=f["item"], fill=INK)
        rwid = _text_w(draw, right_t, f["item"])
        draw.text((RIGHT - rwid, y), right_t, font=f["item"], fill=INK)
        y += item_lh
    y += px(7)
    y = _dash_band(draw, y, thick_proto=2, ink_proto=6, gap_proto=4) + px(7)
    draw.text((LEFT, y), "TOTAL", font=f["total"], fill=INK)
    rwid = _text_w(draw, "FREE :)", f["total"])
    draw.text((RIGHT - rwid, y), "FREE :)", font=f["total"], fill=INK)
    y += _line_h(f["total"]) + GAP

    # dash band
    y = _dash_band(draw, y) + GAP

    # 6) QR BLOCK -----------------------------------------------------------
    qr = _qr_image(QR_URL, px(116))
    if qr is not None:
        qx = CENTER - qr.width // 2
        canvas.paste(qr.convert("L"), (qx, y))
        y += qr.height + px(8)
    cap = "FOLLOW THE ARTIST"
    blk = px(11)
    bgap = px(8)
    cw = _text_w(draw, cap, f["qr_cap"], ls=px(2))
    total = blk + bgap + cw + bgap + blk
    cx = CENTER - total / 2
    ccy = y + _line_h(f["qr_cap"]) * 0.5
    _orn_shade(draw, cx + blk / 2, ccy, blk)
    _draw_run(draw, cx + blk + bgap, y, cap, f["qr_cap"], ls=px(2))
    _orn_shade(draw, cx + blk + bgap + cw + bgap + blk / 2, ccy, blk)
    y += _line_h(f["qr_cap"]) + px(2)
    _draw_center(draw, y, ARTIST_HANDLE, f["handle"], ls=px(1))
    y += _line_h(f["handle"]) + GAP

    # dash band
    y = _dash_band(draw, y) + GAP

    # 7) FOOTER -------------------------------------------------------------
    _draw_center(draw, y, "PLAYER 1 -- KEEP THIS COPY", f["footer"], ls=px(3))
    y += _line_h(f["footer"]) + px(4)
    sub = "PRESS THE BUTTON TO PLAY AGAIN"
    tri_s = px(10)
    sgap = px(6)
    sw = _text_w(draw, sub, f["footer_sub"], ls=px(1))
    total = tri_s + sgap + sw
    fx = CENTER - total / 2
    _orn_tri(draw, fx + tri_s / 2, y + _line_h(f["footer_sub"]) * 0.5, tri_s)
    _draw_run(draw, fx + tri_s + sgap, y, sub, f["footer_sub"], ls=px(1))
    y += _line_h(f["footer_sub"]) + PAD_BOTTOM

    # crop to used height and threshold to 1-bit (no dither -- keep text crisp;
    # the photo is already dithered).
    out = canvas.crop((0, 0, WIDTH, y))
    return out.convert("1", dither=Image.NONE)
