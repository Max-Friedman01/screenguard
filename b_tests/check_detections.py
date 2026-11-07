"""Score Person A's analyze_frame against the synthetic test screens.

Usage (repo root, venv active):
    python b_tests/make_screens.py        # once, creates b_tests/screens/
    python b_tests/check_detections.py

For each screen it prints which expected items were masked (HIT), missed (MISS),
and whether the Luhn decoy was wrongly masked as a card (FALSE ALARM).
"""
import asyncio
import json
import os
import re
import sys
import time

import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ai.analyze import analyze_frame  # noqa: E402

SCREENS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screens")  # next to this script


def norm(s: str) -> str:
    # compare ignoring spaces, dashes and case, since OCR splits/joins these unpredictably
    return re.sub(r"[\s\-]", "", s).lower()


async def main():
    with open(os.path.join(SCREENS, "expected.json"), encoding="utf-8") as f:
        expected = json.load(f)

    total_hit = total_items = false_alarms = 0
    for name, exp in expected.items():
        img = cv2.imread(os.path.join(SCREENS, name))  # BGR, like an mss frame after BGRA->BGR
        t0 = time.perf_counter()
        boxes = await analyze_frame(img)
        dt = time.perf_counter() - t0
        masked = [norm(b.text) for b in boxes]

        print(f"\n{name}  ({len(boxes)} boxes, {dt:.2f}s)")
        for item in exp["should_mask"]:
            target = norm(item["text"])
            hit = any(target in m or (m and m in target and len(m) >= 4) for m in masked)
            total_items += 1
            total_hit += hit
            print(f"  {'HIT ' if hit else 'MISS'}  {item['label']:<9} {item['text']}")
        for decoy in exp["decoys"]:
            bad = [b for b in boxes if b.label == "card" and norm(decoy) in norm(b.text)]
            if bad:
                false_alarms += 1
                print(f"  FALSE ALARM  card  {decoy}  (fails Luhn, should not be a card)")

    print(f"\nScore: {total_hit}/{total_items} masked, {false_alarms} false alarm(s)")


if __name__ == "__main__":
    asyncio.run(main())
