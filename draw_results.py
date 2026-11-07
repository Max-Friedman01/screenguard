import argparse
import asyncio
from pathlib import Path

import cv2

from ai.analyze import analyze_frame


MASK_COLOUR = (24, 24, 24)
TEXT_COLOUR = (255, 255, 255)
PADDING = 10


def clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


async def main(input_path, output_path):
    input_path = input_path.resolve()
    output_path = output_path.resolve()

    image = cv2.imread(
        str(input_path),
        cv2.IMREAD_COLOR,
    )

    if image is None:
        raise FileNotFoundError(
            f"Could not read input image: {input_path}"
        )

    boxes = await analyze_frame(image)

    image_height, image_width = image.shape[:2]

    for box in boxes:
        x1 = clamp(
            box.x - PADDING,
            0,
            image_width - 1,
        )

        y1 = clamp(
            box.y - PADDING,
            0,
            image_height - 1,
        )

        x2 = clamp(
            box.x + box.w + PADDING,
            x1 + 1,
            image_width,
        )

        y2 = clamp(
            box.y + box.h + PADDING,
            y1 + 1,
            image_height,
        )

        cv2.rectangle(
            image,
            (x1, y1),
            (x2, y2),
            MASK_COLOUR,
            thickness=-1,
        )

        label = f"[{box.label} hidden]"

        cv2.putText(
            image,
            label,
            (x1 + 8, min(y2 - 8, y1 + 28)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            TEXT_COLOUR,
            2,
            cv2.LINE_AA,
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    saved = cv2.imwrite(
        str(output_path),
        image,
    )

    if not saved:
        raise RuntimeError(
            f"Could not save output image: {output_path}"
        )

    print(f"Saved {len(boxes)} masked region(s) to:")
    print(output_path)


def run():
    parser = argparse.ArgumentParser(
        description="Draw ScreenGuard masks on a test image."
    )

    parser.add_argument(
        "input",
        type=Path,
    )

    parser.add_argument(
        "output",
        type=Path,
    )

    arguments = parser.parse_args()

    try:
        asyncio.run(
            main(
                arguments.input,
                arguments.output,
            )
        )

    except Exception as error:
        print(f"{type(error).__name__}: {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    run()
