"""Stand-in for Person A's analyzer, used until ai/analyze.py is ready.

Returns two hard-coded boxes and sleeps to mimic OCR latency, so the
"checking..." covers are visible while testing the app.
"""
import asyncio

from shared import Box

FAKE_LATENCY_S = 0.8


async def analyze_frame(img):
    await asyncio.sleep(FAKE_LATENCY_S)
    h, w = img.shape[:2]
    return [
        Box(x=int(w * 0.05), y=int(h * 0.10), w=int(w * 0.25), h=40, label="email", text="fake@example.com"),
        Box(x=int(w * 0.05), y=int(h * 0.20), w=int(w * 0.30), h=40, label="card", text="4111 1111 1111 1111"),
    ]
