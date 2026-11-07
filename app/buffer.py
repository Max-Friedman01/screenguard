"""Fail-closed guard.

Rule: a pixel may be shown only if it is identical to the last frame the AI
finished checking. Anything that differs from that frame is covered with a
grey "checking..." box until a newer analysis covers it.

There is no timeout that ever releases content: if the AI is slow, paused,
or crashes, changed areas simply stay covered.
"""
import threading

import cv2
import numpy as np

from app.mask import draw_boxes, draw_checking

DOWNSCALE = 4          # group pixels into 4x4 blocks when finding changed areas
DIFF_THRESHOLD = 4     # colour difference (0-255) that counts as "changed"
DILATE_PX = 3          # grow changed areas (in downscaled pixels) so edges are covered
FULL_COVER_FRACTION = 0.5  # if more than half the screen changed, cover it all


def _block_max(diff: np.ndarray) -> np.ndarray:
    """Downscale by taking the MAX of each DOWNSCALE x DOWNSCALE block, so even a
    1-pixel change survives (averaging could dilute a thin text stroke away)."""
    H, W = diff.shape
    Hp, Wp = -(-H // DOWNSCALE) * DOWNSCALE, -(-W // DOWNSCALE) * DOWNSCALE
    if (Hp, Wp) != (H, W):
        diff = np.pad(diff, ((0, Hp - H), (0, Wp - W)))
    return diff.reshape(Hp // DOWNSCALE, DOWNSCALE, Wp // DOWNSCALE, DOWNSCALE).max(axis=(1, 3))


def changed_rects(ref: np.ndarray, cur: np.ndarray):
    """Rectangles (x, y, w, h, full-res coords) where cur differs from ref.
    Over-approximates on purpose: covering a bit too much is fine, too little is not."""
    if ref.shape != cur.shape:
        return [(0, 0, cur.shape[1], cur.shape[0])]
    # largest change across B, G, R at full resolution, so a colour-only change still counts
    colour_diff = cv2.absdiff(ref, cur).max(axis=2)
    mask = (_block_max(colour_diff) > DIFF_THRESHOLD).astype(np.uint8)
    if not mask.any():
        return []
    if mask.mean() > FULL_COVER_FRACTION:
        return [(0, 0, cur.shape[1], cur.shape[0])]
    mask = cv2.dilate(mask, np.ones((2 * DILATE_PX + 1, 2 * DILATE_PX + 1), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rects = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        rects.append((x * DOWNSCALE, y * DOWNSCALE, w * DOWNSCALE, h * DOWNSCALE))
    return rects


class FailClosedGuard:
    def __init__(self):
        self._lock = threading.Lock()
        self._ref = None      # last frame the AI finished checking
        self._boxes = []      # what the AI said to hide in that frame
        self.last_analysis_s = None

    def submit_result(self, frame: np.ndarray, boxes, seconds: float = None) -> None:
        """Called by the analyser thread when a frame has been fully checked."""
        with self._lock:
            self._ref = frame
            self._boxes = list(boxes)
            if seconds is not None:
                self.last_analysis_s = seconds

    def compose(self, cur: np.ndarray):
        """Return (safe_frame, n_unchecked_areas). safe_frame is a new array."""
        with self._lock:
            ref, boxes = self._ref, self._boxes
        out = cur.copy()
        if ref is None:  # nothing checked yet: everything is unchecked
            rects = [(0, 0, cur.shape[1], cur.shape[0])]
        else:
            rects = changed_rects(ref, cur)
            draw_boxes(out, boxes)
        draw_checking(out, rects)
        return out, len(rects)