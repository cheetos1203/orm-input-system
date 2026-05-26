from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from pathlib import Path

from app.config import Settings


def _to_data_url(image_path: Path) -> str:
    raw = image_path.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _extract_output_text(payload: dict) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]

    output = payload.get("output", [])
    if not output:
        return ""
    for item in output:
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                return text
    return ""


def fallback_recognize_choice(
    settings: Settings,
    roi_image_path: Path,
    choices: str,
) -> tuple[str | None, float | None, str | None]:
    if not settings.enable_fallback_api:
        return None, None, "fallback_api_disabled"
    if not settings.fallback_api_key:
        return None, None, "missing_api_key"
    if not roi_image_path.exists():
        return None, None, "roi_not_found"

    schema = {
        "type": "object",
        "properties": {
            "selected": {"type": "string", "enum": list(choices)},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reason": {"type": "string"},
        },
        "required": ["selected", "confidence", "reason"],
        "additionalProperties": False,
    }

    prompt = (
        "이 이미지는 OMR 한 문제의 선택지 영역입니다. "
        "가장 진하게 마킹된 선택지를 하나만 고르세요. "
        "복수표기로 보이면 가장 가능성이 높은 하나를 선택하고 reason에 근거를 쓰세요."
    )

    payload = {
        "model": settings.fallback_model,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": _to_data_url(roi_image_path), "detail": "high"},
                ],
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "omr_fallback",
                "schema": schema,
                "strict": True,
            }
        },
    }

    req = urllib.request.Request(
        settings.fallback_api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.fallback_api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            raw = res.read().decode("utf-8")
            data = json.loads(raw)
    except urllib.error.HTTPError as exc:
        return None, None, f"http_error_{exc.code}"
    except Exception:
        return None, None, "fallback_api_failed"

    output_text = _extract_output_text(data)
    if not output_text:
        return None, None, "empty_fallback_output"

    try:
        parsed = json.loads(output_text)
        selected = parsed.get("selected")
        confidence = parsed.get("confidence")
        if selected not in set(choices):
            return None, None, "invalid_fallback_choice"
        try:
            confidence_value = float(confidence)
        except Exception:
            confidence_value = None
        return selected, confidence_value, parsed.get("reason")
    except Exception:
        return None, None, "fallback_parse_failed"

