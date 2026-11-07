from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

import cv2

from ai.analyze import analyze_frame


async def main(image_path: Path) -> None:
    image_path = image_path.resolve()

    if not image_path.exists():
        raise FileNotFoundError(
            f"Image does not exist: {image_path}"
        )

    image = cv2.imread(
        str(image_path),
        cv2.IMREAD_COLOR,
    )

    if image is None:
        raise RuntimeError(
            f"OpenCV could not read: {image_path}"
        )

    started = perf_counter()
    boxes = await analyze_frame(image)
    elapsed = perf_counter() - started

    result = {
        "status": "checked",
        "image": str(image_path),
        "width": int(image.shape[1]),
        "height": int(image.shape[0]),
        "processing_seconds": round(elapsed, 4),
        "detection_count": len(boxes),
        "boxes": [
            asdict(box)
            for box in boxes
        ],
    }

    print(
        json.dumps(
            result,
            indent=2,
        )
    )


def run() -> None:
    parser = argparse.ArgumentParser(
        description="Test the ScreenGuard analysis interface."
    )

    parser.add_argument(
        "image",
        type=Path,
        help="Path to the screenshot to analyse",
    )

    arguments = parser.parse_args()

    try:
        asyncio.run(main(arguments.image))

    except Exception as error:
        failure = {
            "status": "failed",
            "error_type": type(error).__name__,
            "error": str(error),
        }

        print(
            json.dumps(
                failure,
                indent=2,
            )
        )

        raise SystemExit(1)


if __name__ == "__main__":
    run()