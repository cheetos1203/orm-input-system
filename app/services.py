from __future__ import annotations

import csv
import uuid
from datetime import datetime
from pathlib import Path

import cv2
from fastapi import UploadFile

from app.config import Settings
from app.explain import explain_mark_issue
from app.models import QuestionRecognition, ReviewItem, SheetResult
from app.pipeline.fallback_api import fallback_recognize_choice
from app.pipeline.layout import crop_with_layout, load_layout
from app.pipeline.ocr import extract_student_fields
from app.pipeline.omr import detect_omr_rows
from app.pipeline.preprocess import normalize_page, read_document_pages, threshold_for_marks
from app.storage import (
    add_review_items,
    get_answer_key,
    get_review_item,
    get_sheet_result,
    list_sheet_results,
    replace_review_item,
    replace_sheet_result,
    save_sheet_results,
)


def _safe_filename(name: str) -> str:
    allowed = []
    for ch in name:
        if ch.isalnum() or ch in ("-", "_", "."):
            allowed.append(ch)
        else:
            allowed.append("_")
    return "".join(allowed).strip("_") or "upload"


def save_upload_file(upload: UploadFile, settings: Settings, run_id: str) -> Path:
    suffix = Path(upload.filename or "").suffix.lower() or ".bin"
    filename = _safe_filename(Path(upload.filename or "input").stem) + suffix
    out_path = settings.uploads_dir / f"{run_id}_{filename}"
    with out_path.open("wb") as f:
        f.write(upload.file.read())
    return out_path


def _save_question_roi(
    settings: Settings,
    run_id: str,
    sheet_id: str,
    question_no: int,
    image,
    row_box: tuple[int, int, int, int],
) -> Path | None:
    if not settings.debug_save_rois:
        return None
    x1, y1, x2, y2 = row_box
    pad = 8
    x1 = max(0, x1 - pad)
    y1 = max(0, y1 - pad)
    x2 = min(image.shape[1], x2 + pad)
    y2 = min(image.shape[0], y2 + pad)
    roi = image[y1:y2, x1:x2]
    if roi.size == 0:
        return None
    out = settings.review_dir / f"{run_id}_{sheet_id}_q{question_no:03d}.png"
    cv2.imwrite(str(out), roi)
    return out


def _final_choice(question: QuestionRecognition) -> str | None:
    if question.fallback_selected:
        return question.fallback_selected
    return question.selected


def _score_sheet(sheet: SheetResult, answer_key: dict[str, str]) -> float | None:
    if not answer_key:
        return None
    score = 0.0
    for question in sheet.questions:
        key = answer_key.get(str(question.question_no))
        if not key:
            continue
        if _final_choice(question) == key:
            score += 1.0
    return score


def process_uploaded_file(
    settings: Settings,
    run_id: str,
    input_path: Path,
) -> tuple[list[SheetResult], list[ReviewItem]]:
    pages = read_document_pages(input_path, dpi=300)
    version, answer_key = get_answer_key(settings)
    layout = load_layout(settings.data_dir / "layout.json")

    sheet_results: list[SheetResult] = []
    review_items: list[ReviewItem] = []

    for page_index, page in enumerate(pages, start=1):
        warped_color, warped_gray = normalize_page(page)
        question_color = warped_color
        question_gray = warped_gray
        offset = (0, 0)
        if isinstance(layout.get("question_region"), list) and len(layout["question_region"]) == 4:
            question_color, offset = crop_with_layout(warped_color, layout["question_region"])
            question_gray, _ = crop_with_layout(warped_gray, layout["question_region"])

        binary = threshold_for_marks(question_gray)

        detected_rows = detect_omr_rows(
            binary=binary,
            choices=settings.omr_choices,
            row_group_tolerance=settings.row_group_tolerance,
            min_bubble_area=settings.min_bubble_area,
            max_bubble_area=settings.max_bubble_area,
            mark_min_fill=settings.mark_min_fill,
            confidence_threshold=settings.confidence_threshold,
        )

        expected_questions = layout.get("expected_questions")
        if isinstance(expected_questions, int) and expected_questions > 0:
            detected_rows = detected_rows[:expected_questions]

        if offset != (0, 0):
            for row in detected_rows:
                x1, y1, x2, y2 = row.row_box
                row.row_box = (x1 + offset[0], y1 + offset[1], x2 + offset[0], y2 + offset[1])

        sheet_id = f"{run_id}-{input_path.stem}-p{page_index}"
        ocr_image = warped_color
        if isinstance(layout.get("student_region"), list) and len(layout["student_region"]) == 4:
            ocr_image, _ = crop_with_layout(warped_color, layout["student_region"])
        ocr_fields = extract_student_fields(ocr_image, tesseract_cmd=settings.tesseract_cmd)

        questions: list[QuestionRecognition] = []
        pending_for_this_sheet: list[ReviewItem] = []

        for row in detected_rows:
            question = QuestionRecognition(
                question_no=row.question_no,
                selected=row.selected,
                confidence=row.confidence,
                fill_scores=[round(v, 4) for v in row.fill_scores],
                needs_review=row.needs_review,
            )

            roi_path = _save_question_roi(
                settings=settings,
                run_id=run_id,
                sheet_id=sheet_id,
                question_no=row.question_no,
                image=warped_color,
                row_box=row.row_box,
            )
            if roi_path:
                question.roi_path = str(roi_path)

            if row.needs_review:
                question.review_reason = explain_mark_issue(
                    fill_scores=row.fill_scores,
                    confidence=row.confidence,
                    mark_min_fill=settings.mark_min_fill,
                    confidence_threshold=settings.confidence_threshold,
                )

                if roi_path and settings.enable_fallback_api:
                    fallback_selected, fallback_conf, fallback_reason = fallback_recognize_choice(
                        settings=settings,
                        roi_image_path=roi_path,
                        choices=settings.omr_choices,
                    )
                    if fallback_selected:
                        question.fallback_selected = fallback_selected
                        question.fallback_confidence = fallback_conf
                        if fallback_conf is not None and fallback_conf >= 0.90:
                            question.needs_review = False
                            question.review_reason = (
                                "API 재인식 확신도 높음으로 자동 확정"
                                if not fallback_reason
                                else f"API 재인식: {fallback_reason}"
                            )
                        elif fallback_reason:
                            question.review_reason = f"{question.review_reason} / API: {fallback_reason}"

                if question.needs_review:
                    review_id = str(uuid.uuid4())
                    pending_for_this_sheet.append(
                        ReviewItem(
                            review_id=review_id,
                            sheet_id=sheet_id,
                            question_no=row.question_no,
                            image_path=question.roi_path,
                            local_selected=question.selected,
                            local_confidence=question.confidence,
                            reason=question.review_reason or "검수 필요",
                        )
                    )

            questions.append(question)

        sheet = SheetResult(
            sheet_id=sheet_id,
            source_file=str(input_path),
            page_no=page_index,
            student_id=ocr_fields.get("student_id"),
            student_name=ocr_fields.get("student_name"),
            student_id_confidence=ocr_fields.get("student_id_confidence"),
            student_name_confidence=ocr_fields.get("student_name_confidence"),
            questions=questions,
            answer_key_version=version,
        )
        sheet.unresolved_count = sum(1 for question in questions if question.needs_review)
        sheet.raw_score = _score_sheet(sheet, answer_key)

        sheet_results.append(sheet)
        review_items.extend(pending_for_this_sheet)

    return sheet_results, review_items


def ingest_and_persist(
    settings: Settings,
    run_id: str,
    upload_paths: list[Path],
) -> tuple[int, int, list[str]]:
    all_sheets: list[SheetResult] = []
    all_reviews: list[ReviewItem] = []

    for input_path in upload_paths:
        sheets, reviews = process_uploaded_file(settings=settings, run_id=run_id, input_path=input_path)
        all_sheets.extend(sheets)
        all_reviews.extend(reviews)

    save_sheet_results(settings, all_sheets)
    add_review_items(settings, all_reviews)
    return len(all_sheets), len(all_reviews), [sheet.sheet_id for sheet in all_sheets]


def resolve_review(
    settings: Settings,
    review_id: str,
    resolved_selected: str,
    reviewer_note: str | None = None,
) -> ReviewItem:
    review_item = get_review_item(settings, review_id)
    if review_item is None:
        raise ValueError("review_not_found")
    if review_item.status == "resolved":
        return review_item

    review_item.status = "resolved"
    review_item.resolved_selected = resolved_selected
    review_item.reviewer_note = reviewer_note
    review_item.resolved_at = datetime.utcnow()
    replace_review_item(settings, review_item)

    sheet = get_sheet_result(settings, review_item.sheet_id)
    if sheet is None:
        return review_item

    for question in sheet.questions:
        if question.question_no == review_item.question_no:
            question.selected = resolved_selected
            question.needs_review = False
            question.review_reason = "검수자가 수동 확정"
            break

    _, answer_key = get_answer_key(settings)
    sheet.unresolved_count = sum(1 for question in sheet.questions if question.needs_review)
    sheet.raw_score = _score_sheet(sheet, answer_key)
    replace_sheet_result(settings, sheet)
    return review_item


def export_results_csv(settings: Settings) -> Path:
    rows = list_sheet_results(settings)
    if not rows:
        raise ValueError("no_results")

    max_questions = max((len(row.questions) for row in rows), default=0)
    headers = ["sheet_id", "source_file", "page_no", "student_id", "student_name", "raw_score", "unresolved_count"]
    headers.extend([f"Q{idx}" for idx in range(1, max_questions + 1)])

    output_name = f"results_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    output_path = settings.outputs_dir / output_name

    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            payload = {
                "sheet_id": row.sheet_id,
                "source_file": row.source_file,
                "page_no": row.page_no,
                "student_id": row.student_id or "",
                "student_name": row.student_name or "",
                "raw_score": row.raw_score if row.raw_score is not None else "",
                "unresolved_count": row.unresolved_count,
            }
            for question in row.questions:
                payload[f"Q{question.question_no}"] = _final_choice(question) or ""
            writer.writerow(payload)

    return output_path
