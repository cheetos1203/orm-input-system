from __future__ import annotations


def compute_confidence(fill_scores: list[float]) -> float:
    if not fill_scores:
        return 0.0
    ordered = sorted(fill_scores, reverse=True)
    top = ordered[0]
    second = ordered[1] if len(ordered) > 1 else 0.0
    if top <= 0:
        return 0.0
    margin = top - second
    confidence = margin / top
    return max(0.0, min(1.0, confidence))


def should_review(
    fill_scores: list[float],
    confidence: float,
    mark_min_fill: float,
    confidence_threshold: float,
) -> bool:
    if not fill_scores:
        return True
    top = max(fill_scores)
    if top < mark_min_fill:
        return True
    if confidence < confidence_threshold:
        return True
    return False

