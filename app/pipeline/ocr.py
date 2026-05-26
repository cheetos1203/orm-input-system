from __future__ import annotations

import re
from typing import Any

import cv2
import pytesseract
from pytesseract import Output


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def extract_student_fields(
    image,
    tesseract_cmd: str | None = None,
) -> dict[str, str | float | None]:
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    try:
        data = pytesseract.image_to_data(gray, output_type=Output.DICT, lang="kor+eng")
    except Exception:
        try:
            data = pytesseract.image_to_data(gray, output_type=Output.DICT, lang="eng")
        except Exception:
            return {
                "student_id": None,
                "student_id_confidence": None,
                "student_name": None,
                "student_name_confidence": None,
            }

    tokens: list[tuple[str, float]] = []
    for text, conf in zip(data.get("text", []), data.get("conf", []), strict=False):
        text = (text or "").strip()
        confidence = _safe_float(conf)
        if not text:
            continue
        tokens.append((text, confidence))

    joined = " ".join(token for token, _ in tokens)
    id_match = re.search(r"\b\d{5,12}\b", joined)
    student_id = id_match.group(0) if id_match else None

    id_conf = None
    if student_id:
        id_parts = set(re.findall(r"\d+", student_id))
        selected = [c for t, c in tokens if any(part in t for part in id_parts)]
        if selected:
            id_conf = float(sum(selected) / len(selected))

    name_candidates = []
    for token, conf in tokens:
        if re.search(r"\d", token):
            continue
        if len(token) < 2:
            continue
        if re.match(r"^[가-힣A-Za-z]+$", token):
            name_candidates.append((token, conf))

    student_name = None
    name_conf = None
    if name_candidates:
        name_candidates.sort(key=lambda x: x[1], reverse=True)
        student_name = name_candidates[0][0]
        name_conf = float(name_candidates[0][1])

    return {
        "student_id": student_id,
        "student_id_confidence": id_conf,
        "student_name": student_name,
        "student_name_confidence": name_conf,
    }
