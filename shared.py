"""Shared interface between ai/ (Person A) and app/ (Person B).

FROZEN: do not change without telling the other person.

Contract for ai/analyze.py:

    async def analyze_frame(img: np.ndarray) -> list[Box]

    Input  img: a full-resolution screen capture, numpy uint8 array of shape
                (height, width, 3) in BGR channel order (OpenCV's default).
                Treat it as read-only.
    Output:     every region that must be hidden, as Box objects whose
                x, y, w, h are in the INPUT image's pixel coordinates.
                If you downscale internally for speed, scale boxes back up.

    It is always awaited from the same thread and event loop, so it is safe
    to keep a global QVAC Client / loaded model between calls.
    If it raises, the app treats the frame as unchecked (stays covered).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Box:
    x: int
    y: int
    w: int
    h: int
    label: str   # "email", "card", "phone", "postcode", "ni", "bank", "name", "checking"
    text: str
    confidence: float = 1.0
