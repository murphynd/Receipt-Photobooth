"""Scuptee "Arcade Pixel" receipt -- drawn as one tall 1-bit bitmap.

The whole receipt (header lockup, framed photo, fortune block, QR code,
footer) is composed into a single 576px-wide image so it can be sent to the
thermal printer the same way a photo is. See docs/80mm-receipt-photo-design/
for the reference design this recreates ("Scuptee Receipt Arcade").

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
    ARTIST_HANDLE,
    QR_URL,
    LUCKY_COUNT,
    LUCKY_MAX,
    ICON_DIR,
    ICON_COUNT,
    HEADER_ICON_DIR,
    HEADER_WORDMARK_SVG,
    HEADER_MASCOT_SVG,
    HEADER_TITLE,
    HEADER_TAGLINE,
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
        "title": _font(FONT_VT323, 22),      # "TOMORROW FRIENDS" over the wordmark
        "wordmark": _font(FONT_BUNGEE, 30),  # text fallback if the wordmark SVG fails
        "tag": _font(FONT_VT323, 17),        # the "say cheese ..." tagline
        "stamp": _font(FONT_VT323, 18),
        "fortune_head": _font(FONT_VT323, 22),
        "fortune": _font(FONT_VT323, 21),
        "lucky": _font(FONT_VT323, 20),
        "qr_cap": _font(FONT_VT323, 19),
        "handle": _font(FONT_VT323, 24),
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


def _wrap_tokens(draw, text, font, max_w, tri_w, ls=0):
    """Word-wrap for the header tagline, where a standalone "▸" renders as a
    drawn triangle (VT323 lacks the glyph). Returns a list of
    (tokens, line_width) tuples; each token is (word, width)."""
    space_w = draw.textlength(" ", font=font) + ls
    lines, cur, cur_w = [], [], 0
    for tok in text.split():
        w = tri_w if tok == "▸" else _text_w(draw, tok, font, ls)
        add = w if not cur else w + space_w
        if cur and cur_w + add > max_w:
            lines.append((cur, cur_w))
            cur, cur_w, add = [], 0, w
        cur.append((tok, w))
        cur_w += add
    if cur:
        lines.append((cur, cur_w))
    return lines


# ----------------------------------------------------------------------------
# Decorative pieces
# ----------------------------------------------------------------------------
def _squiggle_band(draw, y):
    """The design's wavy divider (squiggle.svg): an S-curve repeating every
    26 prototype px inside a 7px-tall band. Returns the y just below it."""
    h = px(7)
    half = px(13)                       # half a wave period
    stroke = max(2, round(1.4 * SCALE))
    mid = y + h / 2
    amp = h * 3.0 / 7.0                 # control-point offset from the midline
    pts = []
    x, up = LEFT, True
    while x < RIGHT:
        ctrl_y = mid - amp if up else mid + amp
        seg = _quad((x, mid), (x + half / 2, ctrl_y), (x + half, mid), n=8)
        pts.extend(p for p in seg if p[0] <= RIGHT)
        up = not up
        x += half
    draw.line(pts, fill=INK, width=stroke, joint="curve")
    return y + h


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


def _render_svg(path, width):
    """Rasterize an SVG to a 1-bit PIL image ``width`` px wide, keeping its
    aspect ratio (for the header wordmark / mascot art). Returns None when
    cairosvg is unavailable or the file can't be rendered."""
    try:
        import cairosvg
    except Exception:
        return None
    from PIL import Image
    import io

    try:
        png = cairosvg.svg2png(url=path, output_width=width,
                               background_color="white")
        img = Image.open(io.BytesIO(png)).convert("L")
        return img.point(lambda p: INK if p < 128 else PAPER)
    except Exception:
        return None


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

    # 1) HEADER -- title, "Jeanie n Me" wordmark art, mascot + tagline -------
    _draw_center(draw, y, HEADER_TITLE, f["title"], ls=px(2))
    y += _line_h(f["title"]) + px(4)

    hdr = os.path.join(_HERE, HEADER_ICON_DIR)
    wordmark = _render_svg(os.path.join(hdr, HEADER_WORDMARK_SVG), px(279))
    if wordmark is not None:
        canvas.paste(wordmark.convert("L"),
                     (CENTER - wordmark.width // 2, round(y)))
        y += wordmark.height + px(4)
    else:
        # no cairosvg -- fall back to the wordmark as plain text
        _draw_center(draw, y + px(4), WORDMARK, f["wordmark"])
        y += px(4) + _line_h(f["wordmark"]) + px(6)

    # mascot (tilted 5 degrees, like the design's rotate(-5deg)) + tagline
    mascot = _render_svg(os.path.join(hdr, HEADER_MASCOT_SVG), px(104))
    if mascot is not None:
        mascot = mascot.rotate(5, resample=Image.BICUBIC, expand=True,
                               fillcolor=PAPER)
        mascot = mascot.point(lambda p: INK if p < 128 else PAPER)
    m_w = mascot.width if mascot is not None else 0
    m_h = mascot.height if mascot is not None else 0
    m_gap = px(14) if mascot is not None else 0
    tri_s = px(8)
    tag_ls = px(1)
    tag_max = CONTENT_W - px(12) - m_w - m_gap
    tag_lines = _wrap_tokens(draw, HEADER_TAGLINE, f["tag"], tag_max, tri_s,
                             ls=tag_ls)
    tag_lh = _line_h(f["tag"], 1.15)
    text_h = tag_lh * len(tag_lines)
    text_w = max(lw for _, lw in tag_lines)
    space_w = draw.textlength(" ", font=f["tag"]) + tag_ls
    row_h = max(m_h, text_h)
    gx = CENTER - (m_w + m_gap + text_w) / 2
    if mascot is not None:
        canvas.paste(mascot.convert("L"),
                     (round(gx), round(y + (row_h - m_h) / 2)))
    ty = y + (row_h - text_h) / 2
    for toks, _lw in tag_lines:
        cx = gx + m_w + m_gap
        for tok, w in toks:
            if tok == "▸":
                _orn_tri(draw, cx + w / 2, ty + tag_lh * 0.5, tri_s)
            else:
                _draw_run(draw, cx, ty, tok, f["tag"], ls=tag_ls)
            cx += w + space_w
        ty += tag_lh
    y += row_h + GAP

    # squiggle divider
    y = _squiggle_band(draw, y) + GAP

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
    # the design runs the fortune header right after the stamp, no divider
    y += _line_h(f["stamp"]) + px(12)

    # 4) FORTUNE BLOCK ------------------------------------------------------
    _draw_center(draw, y, "=== YOUR FORTUNE ===", f["fortune_head"], ls=px(3))
    y += _line_h(f["fortune_head"]) + px(8)

    # icon row -- three random glyphs across the receipt, the visual fortune
    # (optional: only if cairosvg is installed, else this block is skipped).
    # Sized close to the header mascot so the row reads as the main event.
    icon_size = px(66)
    icons = [im for im in (_render_icon(p, icon_size) for p in _pick_icons(ICON_COUNT)) if im]
    if icons:
        gap = px(18)
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
    # squiggle divider
    y = _squiggle_band(draw, y) + GAP

    # 5) QR BLOCK -----------------------------------------------------------
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
    y += _line_h(f["handle"]) + PAD_BOTTOM

    # crop to used height and threshold to 1-bit (no dither -- keep text crisp;
    # the photo is already dithered).
    out = canvas.crop((0, 0, WIDTH, y))
    return out.convert("1", dither=Image.NONE)
