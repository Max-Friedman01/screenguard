"""Screen capture (mss) and helpers for blanking our own preview window."""
import sys

import cv2
import numpy as np


def make_dpi_aware():
    """Make window coordinates match physical screen pixels on Windows
    (otherwise display scaling like 125% puts the self-blanking box in the wrong place)."""
    if sys.platform != "win32":
        return
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor aware
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


class ScreenCapture:
    """Grabs one monitor as a BGR numpy array. Must be used from the thread that created it."""

    def __init__(self, monitor: int = 1):
        import mss
        self._sct = mss.mss()
        self.monitor = self._sct.monitors[monitor]

    @property
    def origin(self):
        return self.monitor["left"], self.monitor["top"]

    @property
    def size(self):
        return self.monitor["width"], self.monitor["height"]

    def grab(self) -> np.ndarray:
        raw = np.asarray(self._sct.grab(self.monitor))  # BGRA
        return np.ascontiguousarray(raw[:, :, :3])       # BGR copy


class ImageSource:
    """Feeds a static image instead of the screen (testing and merge checks)."""

    def __init__(self, path: str):
        img = cv2.imread(path)
        if img is None:
            raise FileNotFoundError(path)
        self._img = img
        self.origin = (0, 0)
        self.size = (img.shape[1], img.shape[0])

    def grab(self) -> np.ndarray:
        return self._img.copy()


def blank_window_area(frame: np.ndarray, window_name: str, origin) -> None:
    """Paint our own preview window black in the captured frame, so it is never
    analysed, never streamed, and never shows itself inside itself."""
    try:
        x, y, w, h = cv2.getWindowImageRect(window_name)
    except cv2.error:
        return
    if w <= 0 or h <= 0:
        return
    # rect is the image area in screen coords; widen to cover title bar and borders
    left = x - origin[0] - 12
    top = y - origin[1] - 45
    right = x - origin[0] + w + 12
    bottom = y - origin[1] + h + 12
    fh, fw = frame.shape[:2]
    left, top = max(0, left), max(0, top)
    right, bottom = min(fw, right), min(fh, bottom)
    if right > left and bottom > top:
        frame[top:bottom, left:right] = 0