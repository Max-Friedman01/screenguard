from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np


@dataclass(frozen=True)
class OCRBlock:
    x: int
    y: int
    w: int
    h: int
    text: str
    confidence: float


def bbox_to_xywh(bbox: Any) -> tuple[int, int, int, int]:
    if bbox is None:
        raise ValueError("OCR result has no bounding box")

    if isinstance(bbox, dict):
        if {"x", "y", "width", "height"} <= bbox.keys():
            return (round(float(bbox["x"])), round(float(bbox["y"])), max(1, round(float(bbox["width"]))), max(1, round(float(bbox["height"]))))
        if {"x", "y", "w", "h"} <= bbox.keys():
            return (round(float(bbox["x"])), round(float(bbox["y"])), max(1, round(float(bbox["w"]))), max(1, round(float(bbox["h"]))))

    array = np.asarray(bbox, dtype=np.float32)
    if array.ndim == 1 and array.size == 4:
        x1, y1, x2, y2 = array.tolist()
        x_values = (x1, x2)
        y_values = (y1, y2)
    else:
        points = array.reshape(-1, 2)
        if len(points) < 2:
            raise ValueError(f"Unsupported bounding box: {bbox!r}")
        x_values = points[:, 0]
        y_values = points[:, 1]

    x_min, x_max = float(min(x_values)), float(max(x_values))
    y_min, y_max = float(min(y_values)), float(max(y_values))
    return round(x_min), round(y_min), max(1, round(x_max - x_min)), max(1, round(y_max - y_min))


def clamp_box(x: int, y: int, w: int, h: int, image_width: int, image_height: int) -> tuple[int, int, int, int]:
    if image_width <= 0 or image_height <= 0:
        raise ValueError("Image dimensions must be positive")
    x = max(0, min(x, image_width - 1))
    y = max(0, min(y, image_height - 1))
    x2 = max(x + 1, min(x + w, image_width))
    y2 = max(y + 1, min(y + h, image_height))
    return x, y, x2 - x, y2 - y


def _repo_path() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_sidecar(image_path: Path) -> dict[str, Any]:
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("Node.js is required for the local QVAC OCR sidecar")

    environment = os.environ.copy()
    environment["QVAC_WORKER_PATH"] = str(_repo_path() / "node_modules" / "@qvac" / "sdk" / "dist" / "src" / "worker" / "index.js")
    environment.setdefault("QVAC_RPC_INIT_TIMEOUT_MS", "120000")
    completed = subprocess.run(
        [node, str(_repo_path() / "ai" / "qvac_sidecar" / "ocr.mjs"), str(image_path)],
        cwd=str(_repo_path()),
        capture_output=True,
        text=True,
        check=False,
        env=environment,
        timeout=180,
    )

    if completed.returncode != 0:
        diagnostics = completed.stderr.strip()
        raise RuntimeError(f"QVAC OCR sidecar failed with exit code {completed.returncode}: {diagnostics or 'no diagnostics'}")

    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"QVAC OCR sidecar returned invalid JSON: {completed.stdout!r}") from error
    if result.get("status") != "checked":
        raise RuntimeError(f"QVAC OCR sidecar returned an invalid result: {result!r}")
    return result


def _normalise_blocks(result: dict[str, Any], image: np.ndarray) -> list[OCRBlock]:
    image_height, image_width = image.shape[:2]
    normalised: list[OCRBlock] = []
    seen: set[tuple[str, int, int, int, int]] = set()

    for raw_block in result.get("blocks", []):
        text = str(raw_block.get("text", "")).strip()
        if not text or raw_block.get("bbox") is None:
            continue
        x, y, w, h = bbox_to_xywh(raw_block["bbox"])
        x, y, w, h = clamp_box(x, y, w, h, image_width, image_height)
        key = (text, x, y, w, h)
        if key in seen:
            continue
        seen.add(key)
        normalised.append(OCRBlock(x, y, w, h, text, float(raw_block.get("confidence") or 0.0)))

    return normalised


async def run_ocr(image: np.ndarray) -> list[OCRBlock]:
    if not isinstance(image, np.ndarray):
        raise TypeError("img must be a NumPy array")
    if image.size == 0:
        raise ValueError("Cannot OCR an empty image")

    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temporary_file:
            temporary_path = Path(temporary_file.name)
        if not cv2.imwrite(str(temporary_path), image):
            raise RuntimeError("OpenCV failed to write temporary OCR image")
        result = await asyncio.to_thread(_run_sidecar, temporary_path)
        return _normalise_blocks(result, image)
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass


async def start_ocr() -> None:
    return None


async def stop_ocr() -> None:
    return None
