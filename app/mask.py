"""Drawing solid, labelled masks. Solid fill, never blur: blur can stay readable."""
import cv2
import numpy as np

PII_FILL = (35, 35, 35)          # dark grey: detected personal data
CHECK_FILL = (150, 150, 150)     # light grey: not yet checked by the AI
TEXT_COLOUR = (255, 255, 255)
PAD = 4


def _clip(img, x, y, w, h, pad=PAD):
    H, W = img.shape[:2]
    x1, y1 = max(0, int(x) - pad), max(0, int(y) - pad)
    x2, y2 = min(W, int(x + w) + pad), min(H, int(y + h) + pad)
    return x1, y1, x2, y2


def draw_mask(img: np.ndarray, x, y, w, h, label: str, fill) -> None:
    x1, y1, x2, y2 = _clip(img, x, y, w, h)
    if x2 <= x1 or y2 <= y1:
        return
    img[y1:y2, x1:x2] = fill
    text = f"[{label}]"
    bh, bw = y2 - y1, x2 - x1
    scale = min(0.7, max(0.35, bh / 45))
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
    if tw + 6 <= bw and th + 4 <= bh:
        cv2.putText(img, text, (x1 + 3, y1 + (bh + th) // 2), cv2.FONT_HERSHEY_SIMPLEX,
                    scale, TEXT_COLOUR, 1, cv2.LINE_AA)


def draw_boxes(img: np.ndarray, boxes) -> None:
    for b in boxes:
        draw_mask(img, b.x, b.y, b.w, b.h, b.label, PII_FILL)


def draw_checking(img: np.ndarray, rects) -> None:
    for (x, y, w, h) in rects:
        draw_mask(img, x, y, w, h, "checking...", CHECK_FILL)


def draw_status(img: np.ndarray, text: str, warn: bool = False) -> None:
    """Small badge in the bottom-left corner: 'ScreenGuard active' etc."""
    scale = 0.55
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
    H = img.shape[0]
    x1, y1 = 10, H - th - 22
    colour = (0, 0, 190) if warn else (40, 120, 30)
    cv2.rectangle(img, (x1, y1), (x1 + tw + 16, H - 10), colour, -1)
    cv2.putText(img, text, (x1 + 8, H - 17), cv2.FONT_HERSHEY_SIMPLEX, scale, TEXT_COLOUR, 1, cv2.LINE_AA)


def panic_frame(shape, message="Screen sharing paused by sharer") -> np.ndarray:
    img = np.zeros(shape, dtype=np.uint8)
    H, W = shape[:2]
    (tw, th), _ = cv2.getTextSize(message, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)
    cv2.putText(img, message, ((W - tw) // 2, (H + th) // 2), cv2.FONT_HERSHEY_SIMPLEX,
                1.0, (200, 200, 200), 2, cv2.LINE_AA)
    return img