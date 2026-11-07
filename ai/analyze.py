from __future__ import annotations

import os

import cv2
import numpy as np

from ai.detectors import find_sensitive_types
from ai.ocr import OCRBlock, run_ocr
from shared import Box

# ---- incremental OCR settings -------------------------------------------------
# Only re-OCR horizontal strips of the screen that changed since the last
# analysed frame. Unchanged areas reuse the previous OCR result, which is valid
# because those pixels are identical. Strips are full-width so a text line is
# never cut in half.
BAND_PAD = 40               # extra pixels above/below each changed strip
FULL_OCR_FRACTION = 0.5     # if more than half the screen height changed, OCR it all
DIFF_THRESHOLD = 4

_previous_image: np.ndarray | None = None
_previous_blocks: list[OCRBlock] | None = None


def make_test_box(
    image_width: int,
    image_height: int,
) -> Box:
    """
    Create one centred box for end-to-end integration testing.
    """

    width = min(
        500,
        max(1, image_width // 2),
    )

    height = min(
        80,
        max(1, image_height // 8),
    )

    x = max(
        0,
        (image_width - width) // 2,
    )

    y = max(
        0,
        (image_height - height) // 2,
    )

    return Box(
        x=x,
        y=y,
        w=width,
        h=height,
        label="integration_test",
        text="test region",
        confidence=1.0,
    )


async def analyze_frame(
    img: np.ndarray,
) -> list[Box]:
    """
    Analyse one image and return redaction boxes.

    SCREENGUARD_TEST_BOX=1 enables a synthetic box for testing the
    masking, MJPEG and Holesail pipeline.
    SCREENGUARD_FULL_OCR=1 disables incremental OCR (always OCR the whole frame).

    Without test mode, OCR and sensitive-data detection run locally.
    """

    if not isinstance(img, np.ndarray):
        raise TypeError(
            "img must be a NumPy array"
        )

    if img.size == 0:
        raise ValueError(
            "img cannot be empty"
        )

    if img.ndim not in {2, 3}:
        raise ValueError(
            "img must be a 2D or 3D image array"
        )

    image_height, image_width = img.shape[:2]

    test_mode = (
        os.getenv(
            "SCREENGUARD_TEST_BOX",
            "0",
        )
        == "1"
    )

    if test_mode:
        return [
            make_test_box(
                image_width,
                image_height,
            )
        ]

    blocks = await ocr_incremental(img)
    return boxes_from_ocr(blocks)


# ---- incremental OCR ----------------------------------------------------------

def changed_bands(previous: np.ndarray, current: np.ndarray) -> list[tuple[int, int]]:
    """Vertical ranges [top, bottom) of rows that differ, padded and merged."""
    diff = cv2.absdiff(previous, current)
    if diff.ndim == 3:
        diff = diff.max(axis=2)
    changed_rows = np.flatnonzero((diff > DIFF_THRESHOLD).any(axis=1))
    if changed_rows.size == 0:
        return []

    height = current.shape[0]
    bands: list[tuple[int, int]] = []
    start = previous_row = int(changed_rows[0])
    for row in changed_rows[1:]:
        row = int(row)
        if row - previous_row > 2 * BAND_PAD:  # big gap: close this band
            bands.append((start, previous_row + 1))
            start = row
        previous_row = row
    bands.append((start, previous_row + 1))

    padded: list[tuple[int, int]] = []
    for top, bottom in bands:
        top, bottom = max(0, top - BAND_PAD), min(height, bottom + BAND_PAD)
        if padded and top <= padded[-1][1]:
            padded[-1] = (padded[-1][0], max(padded[-1][1], bottom))
        else:
            padded.append((top, bottom))
    return padded


async def ocr_incremental(img: np.ndarray) -> list[OCRBlock]:
    global _previous_image, _previous_blocks

    full = (
        os.getenv("SCREENGUARD_FULL_OCR") == "1"
        or _previous_image is None
        or _previous_blocks is None
        or _previous_image.shape != img.shape
    )

    if not full:
        bands = changed_bands(_previous_image, img)
        if not bands:
            blocks = list(_previous_blocks)
        elif sum(b - t for t, b in bands) > FULL_OCR_FRACTION * img.shape[0]:
            full = True
        else:
            # keep previous blocks that sit entirely outside every changed band
            blocks = [
                block for block in _previous_blocks
                if all(block.y + block.h <= top or block.y >= bottom for top, bottom in bands)
            ]
            for top, bottom in bands:
                strip = np.ascontiguousarray(img[top:bottom])
                for block in await run_ocr(strip):
                    blocks.append(OCRBlock(block.x, block.y + top, block.w, block.h,
                                           block.text, block.confidence))

    if full:
        blocks = await run_ocr(img)

    # only remember the result once OCR fully succeeded (an exception skips this)
    _previous_image = img.copy()
    _previous_blocks = blocks
    return blocks


# ---- detection ----------------------------------------------------------------

def boxes_from_ocr(blocks: list[OCRBlock]) -> list[Box]:
    boxes: list[Box] = []

    for block in merge_line_blocks(blocks):
        detections = find_sensitive_types(block.text)
        uncertain = (
            block.confidence < 0.5
            and any(character.isdigit() or character == "@" for character in block.text)
        )

        if detections:
            labels = ", ".join(dict.fromkeys(detection.label for detection in detections))
            boxes.append(Box(block.x, block.y, block.w, block.h, labels, block.text, block.confidence))
        elif uncertain:
            boxes.append(Box(block.x, block.y, block.w, block.h, "uncertain", block.text, block.confidence))

    return boxes


def merge_line_blocks(blocks: list[OCRBlock]) -> list[OCRBlock]:
    merged: list[OCRBlock] = []

    for block in sorted(blocks, key=lambda item: (item.y, item.x)):
        previous = merged[-1] if merged else None
        same_line = (
            previous is not None
            and min(previous.y + previous.h, block.y + block.h) - max(previous.y, block.y)
            >= min(previous.h, block.h) * 0.5
            and block.x - (previous.x + previous.w) <= max(previous.h, block.h)
        )

        if not same_line:
            merged.append(block)
            continue

        x = min(previous.x, block.x)
        y = min(previous.y, block.y)
        right = max(previous.x + previous.w, block.x + block.w)
        bottom = max(previous.y + previous.h, block.y + block.h)
        merged[-1] = OCRBlock(
            x,
            y,
            right - x,
            bottom - y,
            f"{previous.text} {block.text}",
            min(previous.confidence, block.confidence),
        )

    return merged
