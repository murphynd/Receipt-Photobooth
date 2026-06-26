"""Image pipeline: scale to head width -> enhance -> dither to 1-bit.

_prep_image() is the entry point used by the printing backends. CLAHE uses
OpenCV when available and falls back to Pillow so the Pi install can stay light.
"""

from config import (
    PRINT_WIDTH,
    ENHANCE,
    CLAHE_CLIP,
    CLAHE_GRID,
    GAMMA,
    SHARPEN_RADIUS,
    SHARPEN_PERCENT,
    DITHER,
)


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


def prep_photo(photo_path, width, aspect=(4, 5)):
    """Enhance + dither a capture to a fixed WIDTH x (width*aspect) 1-bit image.

    Unlike _prep_image (which keeps the photo's own ratio at full head width),
    this center-crops to a fixed aspect ratio -- used by the scuptee receipt,
    where the photo sits in a framed 4:5 box inside the layout.
    """
    from PIL import Image, ImageOps

    img = ImageOps.exif_transpose(Image.open(photo_path))   # honour rotation
    target_h = max(1, round(width * aspect[1] / aspect[0]))
    img = ImageOps.fit(img, (width, target_h), method=Image.LANCZOS)  # crop-to-fill
    gray = _enhance_gray(img)
    if DITHER == "atkinson":
        return _atkinson_dither(gray)
    return gray.convert("1")
