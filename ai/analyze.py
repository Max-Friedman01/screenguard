from __future__ import annotations

import os

import numpy as np

from ai.detectors import find_sensitive_types
from ai.ocr import OCRBlock, run_ocr
from shared import Box


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

    blocks = await run_ocr(img)
    return boxes_from_ocr(blocks)


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