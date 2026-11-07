"""Drawing the masks. Every mask is 100% opaque (solid fill / solid stripes):
nothing underneath can show through. Labels are drawn ON TOP of the fill.
"""
import os

import cv2
import numpy as np

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # fall back to OpenCV's built-in font
    Image = None

PAD = 4

# BGR colours
PII_FILL = (38, 34, 32)          # charcoal block for detected personal data
PII_TEXT = (240, 240, 240)
STRIPE_A = (206, 203, 200)       # "checking" hatch, two light greys
STRIPE_B = (188, 184, 181)
CHECK_TEXT = (70, 66, 62)
STRIPE_PERIOD = 14

ACCENT = {                        # per-category accent bar (BGR)
    "email": (235, 140, 60),      # blue
    "card": (40, 140, 245),       # orange
    "phone": (90, 190, 80),       # green
    "bank": (200, 90, 150),       # purple
    "postcode": (180, 170, 40),   # teal
    "ni": (150, 90, 230),         # pink
    "name": (60, 200, 230),       # yellow
}
DEFAULT_ACCENT = (150, 150, 150)

FONT_FILES = [
    r"C:\Windows\Fonts\seguisb.ttf",   # Segoe UI Semibold
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
_FONT_PATH = next((p for p in FONT_FILES if os.path.exists(p)), None)
_font_cache, _text_cache = {}, {}
_stripes = None


# ---------- text rendering (anti-aliased, cached) ----------

def _font(size):
    if size not in _font_cache:
        _font_cache[size] = ImageFont.truetype(_FONT_PATH, size)
    return _font_cache[size]


def _text_alpha(text: str, size: int) -> np.ndarray:
    """Alpha mask (float 0..1, H x W) of the rendered text. Cached."""
    key = (text, size)
    if key not in _text_cache:
        if Image is not None and _FONT_PATH:
            f = _font(size)
            l, t, r, b = f.getbbox(text)
            im = Image.new("L", (r - l + 2, b - t + 2), 0)
            ImageDraw.Draw(im).text((1 - l, 1 - t), text, font=f, fill=255)
            arr = np.asarray(im, dtype=np.float32) / 255.0
        else:
            scale = size / 22
            (tw, th), base = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
            im = np.zeros((th + base + 2, tw + 2), np.uint8)
            cv2.putText(im, text, (1, th + 1), cv2.FONT_HERSHEY_SIMPLEX, scale, 255, 1, cv2.LINE_AA)
            arr = im.astype(np.float32) / 255.0
        _text_cache[key] = arr
    return _text_cache[key]


def _blend_text(img, x, y, text, size, colour, max_w=None, max_h=None) -> bool:
    """Draw text with top-left at (x, y) if it fits. Returns False if it didn't fit."""
    a = _text_alpha(text, size)
    h, w = a.shape
    H, W = img.shape[:2]
    if (max_w is not None and w > max_w) or (max_h is not None and h > max_h):
        return False
    if x < 0 or y < 0 or x + w > W or y + h > H:
        return False
    region = img[y:y + h, x:x + w].astype(np.float32)
    col = np.array(colour, np.float32)
    img[y:y + h, x:x + w] = (region * (1 - a[..., None]) + col * a[..., None]).astype(np.uint8)
    return True


def _fit_text(img, x1, y1, x2, y2, text, colour, left_inset=8, centre=False):
    bw, bh = x2 - x1, y2 - y1
    size = int(min(20, max(11, bh * 0.45)))
    while size >= 10:
        a = _text_alpha(text, size)
        th, tw = a.shape
        if tw + left_inset + 6 <= bw and th + 2 <= bh:
            tx = x1 + (bw - tw) // 2 if centre else x1 + left_inset
            ty = y1 + (bh - th) // 2
            _blend_text(img, tx, ty, text, size, colour)
            return
        size -= 2


# ---------- masks ----------

def _clip(img, x, y, w, h, pad=PAD):
    H, W = img.shape[:2]
    x1, y1 = max(0, int(x) - pad), max(0, int(y) - pad)
    x2, y2 = min(W, int(x + w) + pad), min(H, int(y + h) + pad)
    return x1, y1, x2, y2


def _stripe_tile(H, W):
    """Full-frame opaque diagonal stripes, anchored to the screen so they don't 'crawl'."""
    global _stripes
    if _stripes is None or _stripes.shape[0] < H or _stripes.shape[1] < W:
        yy, xx = np.mgrid[0:H, 0:W]
        band = ((xx + yy) // (STRIPE_PERIOD // 2)) % 2 == 0
        tile = np.empty((H, W, 3), np.uint8)
        tile[band] = STRIPE_A
        tile[~band] = STRIPE_B
        _stripes = tile
    return _stripes


def draw_mask(img: np.ndarray, x, y, w, h, label: str) -> None:
    """Solid charcoal block + coloured accent bar + '<label> hidden'."""
    x1, y1, x2, y2 = _clip(img, x, y, w, h)
    if x2 <= x1 or y2 <= y1:
        return
    img[y1:y2, x1:x2] = PII_FILL
    accent = ACCENT.get(label, DEFAULT_ACCENT)
    bar = min(4, x2 - x1)
    img[y1:y2, x1:x1 + bar] = accent
    _fit_text(img, x1, y1, x2, y2, f"{label} hidden", PII_TEXT, left_inset=bar + 6)


def draw_checking_area(img: np.ndarray, x, y, w, h) -> None:
    x1, y1, x2, y2 = _clip(img, x, y, w, h)
    if x2 <= x1 or y2 <= y1:
        return
    H, W = img.shape[:2]
    img[y1:y2, x1:x2] = _stripe_tile(H, W)[y1:y2, x1:x2]
    full = (x2 - x1) >= W * 0.9 and (y2 - y1) >= H * 0.9
    if full:
        msg = "ScreenGuard is checking this screen\u2026"
        a = _text_alpha(msg, 30)
        _blend_text(img, (W - a.shape[1]) // 2, (H - a.shape[0]) // 2, msg, 30, CHECK_TEXT)
    else:
        _fit_text(img, x1, y1, x2, y2, "checking\u2026", CHECK_TEXT, centre=True)


def draw_boxes(img: np.ndarray, boxes) -> None:
    for b in boxes:
        draw_mask(img, b.x, b.y, b.w, b.h, b.label)


def draw_checking(img: np.ndarray, rects) -> None:
    for (x, y, w, h) in rects:
        draw_checking_area(img, x, y, w, h)


# ---------- badge and panic ----------

def draw_status(img: np.ndarray, text: str, warn: bool = False) -> None:
    """Rounded pill in the bottom-left: dot + text."""
    size = 16
    a = _text_alpha(text, size)
    th, tw = a.shape
    H = img.shape[0]
    pill_h = th + 14
    pill_w = tw + 40
    x1, y1 = 12, H - pill_h - 12
    x2, y2 = x1 + pill_w, y1 + pill_h
    bg = (20, 20, 150) if warn else (28, 28, 28)
    r = pill_h // 2
    cv2.rectangle(img, (x1 + r, y1), (x2 - r, y2), bg, -1)
    cv2.circle(img, (x1 + r, y1 + r), r, bg, -1, cv2.LINE_AA)
    cv2.circle(img, (x2 - r, y1 + r), r, bg, -1, cv2.LINE_AA)
    dot = (60, 200, 255) if warn else (90, 210, 90)
    cv2.circle(img, (x1 + 16, y1 + pill_h // 2), 5, dot, -1, cv2.LINE_AA)
    _blend_text(img, x1 + 28, y1 + (pill_h - th) // 2, text, size, (245, 245, 245))


def panic_frame(shape, message="Screen sharing paused by sharer") -> np.ndarray:
    img = np.zeros(shape, dtype=np.uint8)
    img[:] = (24, 22, 20)
    H, W = shape[:2]
    a = _text_alpha(message, 32)
    _blend_text(img, (W - a.shape[1]) // 2, (H - a.shape[0]) // 2, message, 32, (210, 210, 210))
    return img