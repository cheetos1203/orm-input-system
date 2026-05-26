from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.config import get_settings
from app.models import IngestResponse, ResolveReviewRequest
from app.reporting import build_result_page_context, write_report_config_example
from app.services import export_results_csv, ingest_and_persist, resolve_review, save_upload_file
from app.storage import (
    ensure_data_dirs,
    get_answer_key,
    get_sheet_result,
    list_review_items,
    list_sheet_results,
    set_answer_key,
)


settings = get_settings()
ensure_data_dirs(settings)
write_report_config_example(settings)

app = FastAPI(title="OMR 자동입력 + 성적처리 시스템", version="0.1.0")
app.mount("/review-assets", StaticFiles(directory=str(settings.review_dir)), name="review-assets")
templates = Jinja2Templates(directory="app/templates")


class AnswerKeyRequest(BaseModel):
    version: str = Field(default="v1")
    answer_key: dict[str, str]


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="index.html", context={})


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "service": "omr-scoring"}


@app.post("/api/ingest", response_model=IngestResponse)
async def ingest(files: list[UploadFile] = File(...)) -> IngestResponse:
    if not files:
        raise HTTPException(status_code=400, detail="업로드 파일이 없습니다.")

    try:
        run_id = datetime_run_id()
        paths: list[Path] = []
        for upload in files:
            path = save_upload_file(upload, settings=settings, run_id=run_id)
            paths.append(path)

        sheets, _created_reviews, sheet_ids = ingest_and_persist(settings=settings, run_id=run_id, upload_paths=paths)
        pending = len(list_review_items(settings, status="pending"))
        result_urls = [f"/result/{sheet_id}" for sheet_id in sheet_ids]
        return IngestResponse(
            run_id=run_id,
            files=len(paths),
            sheets=sheets,
            pending_reviews=pending,
            sheet_ids=sheet_ids,
            result_urls=result_urls,
        )
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"처리 오류: {type(exc).__name__}: {exc}")


@app.get("/api/results")
async def get_results() -> list[dict]:
    return [item.model_dump() for item in list_sheet_results(settings)]


@app.get("/api/results/{sheet_id}")
async def get_result(sheet_id: str) -> dict:
    result = get_sheet_result(settings, sheet_id)
    if result is None:
        raise HTTPException(status_code=404, detail="결과를 찾지 못했습니다.")
    return result.model_dump()


@app.get("/api/reviews")
async def get_reviews(status: str | None = "pending") -> list[dict]:
    if status == "all":
        status = None
    return [item.model_dump() for item in list_review_items(settings, status=status)]


@app.post("/api/reviews/{review_id}/resolve")
async def resolve(review_id: str, req: ResolveReviewRequest) -> dict:
    resolved_selected = req.resolved_selected.upper().strip()
    if resolved_selected not in set(settings.omr_choices):
        raise HTTPException(status_code=400, detail=f"선택지는 {settings.omr_choices} 중 하나여야 합니다.")
    try:
        item = resolve_review(
            settings=settings,
            review_id=review_id,
            resolved_selected=resolved_selected,
            reviewer_note=req.reviewer_note,
        )
    except ValueError as exc:
        if str(exc) == "review_not_found":
            raise HTTPException(status_code=404, detail="검수 항목을 찾지 못했습니다.") from exc
        raise
    return item.model_dump()


@app.post("/api/answer-key")
async def upload_answer_key(req: AnswerKeyRequest) -> JSONResponse:
    normalized = {}
    for key, value in req.answer_key.items():
        normalized[str(key)] = str(value).upper()
    set_answer_key(settings=settings, answer_key=normalized, version=req.version)
    return JSONResponse({"ok": True, "version": req.version, "questions": len(normalized)})


@app.get("/api/answer-key")
async def read_answer_key() -> dict:
    version, answer_key = get_answer_key(settings)
    return {"version": version, "answer_key": answer_key}


@app.get("/api/export/csv")
async def export_csv() -> FileResponse:
    try:
        csv_path = export_results_csv(settings)
    except ValueError as exc:
        if str(exc) == "no_results":
            raise HTTPException(status_code=404, detail="내보낼 결과가 없습니다.") from exc
        raise
    return FileResponse(path=csv_path, filename=csv_path.name, media_type="text/csv")


@app.get("/review", response_class=HTMLResponse)
async def review_page(request: Request) -> HTMLResponse:
    pending = list_review_items(settings, status="pending")
    rows = []
    for item in pending:
        image_name = Path(item.image_path).name if item.image_path else None
        rows.append(
            {
                "review_id": item.review_id,
                "sheet_id": item.sheet_id,
                "question_no": item.question_no,
                "local_selected": item.local_selected or "",
                "local_confidence": round(item.local_confidence, 3),
                "reason": item.reason,
                "image_url": f"/review-assets/{image_name}" if image_name else None,
            }
        )
    return templates.TemplateResponse(
        request=request,
        name="review.html",
        context={"rows": rows, "choices": list(settings.omr_choices)},
    )


@app.get("/result/{sheet_id}", response_class=HTMLResponse)
async def result_page(request: Request, sheet_id: str) -> HTMLResponse:
    sheet = get_sheet_result(settings, sheet_id)
    if sheet is None:
        raise HTTPException(status_code=404, detail="결과를 찾지 못했습니다.")
    context = build_result_page_context(settings, sheet)
    context["request"] = request
    return templates.TemplateResponse(name="result.html", context=context)


@app.get("/result", response_class=HTMLResponse)
async def latest_result_page(request: Request) -> HTMLResponse:
    rows = list_sheet_results(settings)
    if not rows:
        return HTMLResponse(
            content="<html><body style='font-family:sans-serif;padding:24px;'>"
            "아직 결과가 없습니다. 먼저 홈 화면(/)에서 시험지를 업로드하세요."
            "</body></html>",
            status_code=404,
        )
    latest = sorted(rows, key=lambda x: x.processed_at)[-1]
    context = build_result_page_context(settings, latest)
    context["request"] = request
    return templates.TemplateResponse(name="result.html", context=context)


def datetime_run_id() -> str:
    return uuid.uuid4().hex[:12]
