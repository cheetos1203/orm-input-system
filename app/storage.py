from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import Settings
from app.models import ReviewItem, SheetResult


RESULTS_FILE = "results.json"
REVIEWS_FILE = "reviews.json"
ANSWER_KEY_FILE = "answer_key.json"


def ensure_data_dirs(settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.outputs_dir.mkdir(parents=True, exist_ok=True)
    settings.review_dir.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def _results_path(settings: Settings) -> Path:
    return settings.outputs_dir / RESULTS_FILE


def _reviews_path(settings: Settings) -> Path:
    return settings.review_dir / REVIEWS_FILE


def _answer_key_path(settings: Settings) -> Path:
    return settings.outputs_dir / ANSWER_KEY_FILE


def save_sheet_results(settings: Settings, items: list[SheetResult]) -> None:
    current = list_sheet_results(settings)
    current.extend(items)
    payload = [item.model_dump() for item in current]
    _write_json(_results_path(settings), payload)


def list_sheet_results(settings: Settings) -> list[SheetResult]:
    raw = _read_json(_results_path(settings), [])
    out: list[SheetResult] = []
    for row in raw:
        try:
            out.append(SheetResult.model_validate(row))
        except Exception:
            continue
    return out


def get_sheet_result(settings: Settings, sheet_id: str) -> SheetResult | None:
    for item in list_sheet_results(settings):
        if item.sheet_id == sheet_id:
            return item
    return None


def replace_sheet_result(settings: Settings, item: SheetResult) -> None:
    rows = list_sheet_results(settings)
    replaced = False
    for idx, existing in enumerate(rows):
        if existing.sheet_id == item.sheet_id:
            rows[idx] = item
            replaced = True
            break
    if not replaced:
        rows.append(item)
    _write_json(_results_path(settings), [row.model_dump() for row in rows])


def add_review_items(settings: Settings, items: list[ReviewItem]) -> None:
    current = list_review_items(settings)
    current.extend(items)
    _write_json(_reviews_path(settings), [item.model_dump() for item in current])


def list_review_items(settings: Settings, status: str | None = None) -> list[ReviewItem]:
    raw = _read_json(_reviews_path(settings), [])
    out: list[ReviewItem] = []
    for row in raw:
        try:
            item = ReviewItem.model_validate(row)
        except Exception:
            continue
        if status and item.status != status:
            continue
        out.append(item)
    return out


def get_review_item(settings: Settings, review_id: str) -> ReviewItem | None:
    for item in list_review_items(settings):
        if item.review_id == review_id:
            return item
    return None


def replace_review_item(settings: Settings, review_item: ReviewItem) -> None:
    rows = list_review_items(settings)
    replaced = False
    for idx, existing in enumerate(rows):
        if existing.review_id == review_item.review_id:
            rows[idx] = review_item
            replaced = True
            break
    if not replaced:
        rows.append(review_item)
    _write_json(_reviews_path(settings), [row.model_dump() for row in rows])


def set_answer_key(settings: Settings, answer_key: dict[str, str], version: str = "v1") -> None:
    payload = {"version": version, "answer_key": answer_key}
    _write_json(_answer_key_path(settings), payload)


def get_answer_key(settings: Settings) -> tuple[str | None, dict[str, str]]:
    raw = _read_json(_answer_key_path(settings), {})
    if not raw:
        return None, {}
    version = raw.get("version")
    answer_key = raw.get("answer_key", {})
    return version, answer_key

