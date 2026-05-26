from __future__ import annotations


def explain_mark_issue(
    fill_scores: list[float],
    confidence: float,
    mark_min_fill: float,
    confidence_threshold: float,
) -> str:
    if not fill_scores:
        return "버블 후보를 찾지 못했습니다. 시험지 기울어짐, 영역 누락, 해상도 저하 가능성이 있습니다."

    sorted_scores = sorted(fill_scores, reverse=True)
    top = sorted_scores[0]
    second = sorted_scores[1] if len(sorted_scores) > 1 else 0.0

    if top < mark_min_fill:
        return "마킹 농도가 낮아(연필 약함/지움 흔적) 확정이 어렵습니다."

    if top > 0 and (second / top) > 0.9:
        return "복수 선택 가능성이 있습니다. 상위 두 선택지 농도가 매우 유사합니다."

    if confidence < confidence_threshold:
        return "선택지 간 구분 여유가 작아 확신도가 낮습니다."

    return "판독 점검이 필요합니다."


def explain_ocr_issue(field_name: str, confidence: float | None) -> str:
    if confidence is None:
        return f"{field_name} 인식 결과가 비어 있습니다. 입력 영역 확인이 필요합니다."
    if confidence < 40:
        return f"{field_name} OCR 신뢰도가 낮습니다(저해상도/글자 겹침 가능성)."
    return f"{field_name} 검토가 필요합니다."

