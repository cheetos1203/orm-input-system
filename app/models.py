from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class QuestionRecognition(BaseModel):
    question_no: int
    selected: str | None = None
    confidence: float = 0.0
    fill_scores: list[float] = Field(default_factory=list)
    needs_review: bool = False
    review_reason: str | None = None
    roi_path: str | None = None
    fallback_selected: str | None = None
    fallback_confidence: float | None = None


class SheetResult(BaseModel):
    sheet_id: str
    source_file: str
    page_no: int
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    student_id: str | None = None
    student_name: str | None = None
    student_id_confidence: float | None = None
    student_name_confidence: float | None = None
    questions: list[QuestionRecognition] = Field(default_factory=list)
    answer_key_version: str | None = None
    raw_score: float | None = None
    unresolved_count: int = 0


class ReviewItem(BaseModel):
    review_id: str
    sheet_id: str
    question_no: int
    image_path: str | None = None
    local_selected: str | None = None
    local_confidence: float = 0.0
    reason: str
    status: Literal["pending", "resolved"] = "pending"
    resolved_selected: str | None = None
    reviewer_note: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: datetime | None = None


class ResolveReviewRequest(BaseModel):
    resolved_selected: str
    reviewer_note: str | None = None


class IngestResponse(BaseModel):
    run_id: str
    files: int
    sheets: int
    pending_reviews: int
    sheet_ids: list[str] = Field(default_factory=list)
    result_urls: list[str] = Field(default_factory=list)
