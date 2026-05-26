from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings
from app.models import SheetResult
from app.storage import get_answer_key, list_sheet_results


DEFAULT_REPORT_CONFIG = {
    "school_name": "",
    "exam_round": "",
    "subject_name": "",
    "academy_avg_total": 0.0,
    "national_avg_total": 0.0,
    "grade_cut": {"1": 85, "2": 79, "3": 70, "4": 60},
    "domains": [
        {
            "name": "독서",
            "max_score": 38,
            "start": 1,
            "end": 17,
            "academy_avg": 0,
            "national_avg": 0,
            "groups": [
                {"label": "독서(독서론)", "start": 1, "end": 4},
                {"label": "독서(인문통합)", "start": 5, "end": 10},
                {"label": "독서(사회)", "start": 11, "end": 17},
            ],
        },
        {
            "name": "문학",
            "max_score": 38,
            "start": 18,
            "end": 34,
            "academy_avg": 0,
            "national_avg": 0,
            "groups": [
                {"label": "문학(고전소설)", "start": 18, "end": 21},
                {"label": "문학(고전시가+수필통합)", "start": 22, "end": 25},
                {"label": "문학(현대소설)", "start": 26, "end": 30},
                {"label": "문학(현대시)", "start": 31, "end": 34},
            ],
        },
        {
            "name": "언어와 매체",
            "max_score": 24,
            "start": 35,
            "end": 45,
            "academy_avg": 0,
            "national_avg": 0,
            "groups": [
                {"label": "언어", "start": 35, "end": 40},
                {"label": "매체", "start": 41, "end": 43},
                {"label": "매체-언어 통합", "start": 44, "end": 45},
            ],
        },
    ],
}


@dataclass
class QuestionView:
    question_no: int
    answer: str
    marked: str
    ox: str


def _read_report_config(settings: Settings) -> dict:
    path = settings.data_dir / "report_config.json"
    if not path.exists():
        return DEFAULT_REPORT_CONFIG
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        base = DEFAULT_REPORT_CONFIG.copy()
        base.update(payload)
        return base
    except Exception:
        return DEFAULT_REPORT_CONFIG


def _mask_name(name: str | None) -> str:
    if not name:
        return "-"
    name = name.strip()
    if len(name) <= 1:
        return name + "*"
    return f"{name[0]}*{name[-1]}"


def _mask_id(student_id: str | None) -> str:
    if not student_id:
        return "****"
    clean = "".join(ch for ch in student_id if ch.isdigit())
    if len(clean) <= 4:
        return "****" + clean
    return "****" + clean[-4:]


def _grade_from_cut(total: float, cut: dict[str, float]) -> str:
    ordered = []
    for k, v in cut.items():
        try:
            ordered.append((int(k), float(v)))
        except Exception:
            continue
    ordered.sort(key=lambda x: x[0])
    for grade, threshold in ordered:
        if total >= threshold:
            return f"{grade}등급"
    return "-"


def _final_marked(sheet: SheetResult, question_no: int) -> str:
    for q in sheet.questions:
        if q.question_no == question_no:
            if q.fallback_selected:
                return q.fallback_selected
            return q.selected or "-"
    return "-"


def build_result_page_context(settings: Settings, sheet: SheetResult) -> dict:
    report_config = _read_report_config(settings)
    _, answer_key = get_answer_key(settings)

    total_score = float(sheet.raw_score or 0.0)
    grade_cut = report_config.get("grade_cut", {})
    grade = _grade_from_cut(total_score, grade_cut)

    domains_view = []
    for domain in report_config.get("domains", []):
        start = int(domain.get("start", 1))
        end = int(domain.get("end", start))
        question_views: list[QuestionView] = []
        correct_count = 0
        for qno in range(start, end + 1):
            answer = str(answer_key.get(str(qno), "-"))
            marked = _final_marked(sheet, qno)
            if answer == "-" or marked == "-":
                ox = "-"
            else:
                ox = "O" if marked == answer else "X"
            if ox == "O":
                correct_count += 1
            question_views.append(QuestionView(question_no=qno, answer=answer, marked=marked, ox=ox))

        group_headers = []
        for grp in domain.get("groups", []):
            g_start = int(grp.get("start", start))
            g_end = int(grp.get("end", g_start))
            colspan = max(1, g_end - g_start + 1)
            group_headers.append({"label": grp.get("label", ""), "colspan": colspan})

        domains_view.append(
            {
                "name": domain.get("name", ""),
                "max_score": float(domain.get("max_score", 0)),
                "academy_avg": float(domain.get("academy_avg", 0)),
                "national_avg": float(domain.get("national_avg", 0)),
                "questions": question_views,
                "group_headers": group_headers,
                "student_score": float(correct_count),
            }
        )

    domain_chart_labels = [f"{d['name']}({int(d['max_score'])})" for d in domains_view]
    domain_chart_student = [d["student_score"] for d in domains_view]
    domain_chart_academy = [d["academy_avg"] for d in domains_view]
    domain_chart_national = [d["national_avg"] for d in domains_view]

    history = _build_history(settings, sheet)
    history_labels = [h["label"] for h in history]
    history_student = [h["student"] for h in history]
    history_academy = [h["academy"] for h in history]
    history_national = [h["national"] for h in history]

    return {
        "sheet_id": sheet.sheet_id,
        "school_name": report_config.get("school_name", ""),
        "student_display": f"{_mask_name(sheet.student_name)}({_mask_id(sheet.student_id)})",
        "exam_round": report_config.get("exam_round", sheet.answer_key_version or ""),
        "subject_name": report_config.get("subject_name", ""),
        "total_score": total_score,
        "grade": grade,
        "academy_rank": "-",
        "academy_avg_total": float(report_config.get("academy_avg_total", 0)),
        "national_avg_total": float(report_config.get("national_avg_total", 0)),
        "grade_cut": {
            "1": float(grade_cut.get("1", 85)),
            "2": float(grade_cut.get("2", 79)),
            "3": float(grade_cut.get("3", 70)),
            "4": float(grade_cut.get("4", 60)),
        },
        "domains": domains_view,
        "domain_chart_labels": domain_chart_labels,
        "domain_chart_student": domain_chart_student,
        "domain_chart_academy": domain_chart_academy,
        "domain_chart_national": domain_chart_national,
        "history_labels": history_labels,
        "history_student": history_student,
        "history_academy": history_academy,
        "history_national": history_national,
    }


def _build_history(settings: Settings, current_sheet: SheetResult) -> list[dict]:
    all_rows = list_sheet_results(settings)
    if not all_rows:
        return []

    report_config = _read_report_config(settings)
    academy_avg = float(report_config.get("academy_avg_total", 0))
    national_avg = float(report_config.get("national_avg_total", 0))

    key_name = (current_sheet.student_name or "").strip()
    key_id = (current_sheet.student_id or "").strip()

    filtered = []
    for row in all_rows:
        if key_id and row.student_id == key_id:
            filtered.append(row)
            continue
        if key_name and row.student_name == key_name:
            filtered.append(row)

    if not filtered:
        filtered = [current_sheet]

    filtered.sort(key=lambda x: x.processed_at)
    out = []
    for idx, row in enumerate(filtered, start=1):
        label = row.answer_key_version or f"{idx}회차"
        out.append(
            {
                "label": label,
                "student": float(row.raw_score or 0),
                "academy": academy_avg,
                "national": national_avg,
            }
        )
    return out


def write_report_config_example(settings: Settings) -> Path:
    path = settings.data_dir / "report_config.example.json"
    if not path.exists():
        path.write_text(json.dumps(DEFAULT_REPORT_CONFIG, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
