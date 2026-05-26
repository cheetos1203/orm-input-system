from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def load_layout(layout_path: Path) -> dict:
    if not layout_path.exists():
        return {}
    try:
        return json.loads(layout_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def resolve_box(image: np.ndarray, box: list[float] | tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    h, w = image.shape[:2]
    x1, y1, x2, y2 = box

    # 0~1 범위로 오면 비율 좌표로 해석
    if 0 <= x1 <= 1 and 0 <= y1 <= 1 and 0 <= x2 <= 1 and 0 <= y2 <= 1:
        x1, x2 = x1 * w, x2 * w
        y1, y2 = y1 * h, y2 * h

    x1_i = max(0, min(int(x1), w - 1))
    x2_i = max(x1_i + 1, min(int(x2), w))
    y1_i = max(0, min(int(y1), h - 1))
    y2_i = max(y1_i + 1, min(int(y2), h))
    return x1_i, y1_i, x2_i, y2_i


def crop_with_layout(image: np.ndarray, box: list[float] | tuple[float, float, float, float]) -> tuple[np.ndarray, tuple[int, int]]:
    x1, y1, x2, y2 = resolve_box(image, box)
    return image[y1:y2, x1:x2], (x1, y1)

