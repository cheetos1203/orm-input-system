from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from app.pipeline.confidence import compute_confidence, should_review


@dataclass
class BubbleRect:
    x: int
    y: int
    w: int
    h: int


@dataclass
class OMRRowResult:
    question_no: int
    selected: str | None
    confidence: float
    fill_scores: list[float]
    needs_review: bool
    row_box: tuple[int, int, int, int]


def _find_bubble_rects(
    binary: np.ndarray,
    min_area: int,
    max_area: int,
) -> list[BubbleRect]:
    contours, _ = cv2.findContours(binary.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    out: list[BubbleRect] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area or area > max_area:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        if w < 8 or h < 8:
            continue
        aspect = w / float(h)
        if 0.7 <= aspect <= 1.3:
            out.append(BubbleRect(x=x, y=y, w=w, h=h))
    return out


def _group_rows(cells: list[BubbleRect], tolerance: int) -> list[list[BubbleRect]]:
    if not cells:
        return []
    cells = sorted(cells, key=lambda c: (c.y, c.x))
    rows: list[list[BubbleRect]] = [[cells[0]]]
    anchors = [cells[0].y]

    for cell in cells[1:]:
        if abs(cell.y - anchors[-1]) <= tolerance:
            rows[-1].append(cell)
            anchors[-1] = int(sum(c.y for c in rows[-1]) / len(rows[-1]))
        else:
            rows.append([cell])
            anchors.append(cell.y)

    for row in rows:
        row.sort(key=lambda c: c.x)
    return rows


def _best_window(row: list[BubbleRect], expected: int) -> list[BubbleRect]:
    if len(row) <= expected:
        return row

    best = row[:expected]
    best_score = float("inf")

    for start in range(0, len(row) - expected + 1):
        window = row[start : start + expected]
        centers = [cell.x + (cell.w / 2.0) for cell in window]
        if len(centers) < 2:
            return window
        spacings = np.diff(centers)
        score = float(np.std(spacings))
        if score < best_score:
            best = window
            best_score = score
    return best


def _fill_ratio(binary: np.ndarray, cell: BubbleRect) -> float:
    roi = binary[cell.y : cell.y + cell.h, cell.x : cell.x + cell.w]
    if roi.size == 0:
        return 0.0
    non_zero = cv2.countNonZero(roi)
    return float(non_zero / roi.size)


def detect_omr_rows(
    binary: np.ndarray,
    choices: str,
    row_group_tolerance: int,
    min_bubble_area: int,
    max_bubble_area: int,
    mark_min_fill: float,
    confidence_threshold: float,
) -> list[OMRRowResult]:
    cells = _find_bubble_rects(binary, min_area=min_bubble_area, max_area=max_bubble_area)
    rows = _group_rows(cells, tolerance=row_group_tolerance)

    results: list[OMRRowResult] = []
    expected = len(choices)
    question_no = 1

    for row in rows:
        if len(row) < 2:
            continue
        row_cells = _best_window(row, expected)
        fill_scores = [_fill_ratio(binary, cell) for cell in row_cells]
        confidence = compute_confidence(fill_scores)
        needs_review = should_review(
            fill_scores=fill_scores,
            confidence=confidence,
            mark_min_fill=mark_min_fill,
            confidence_threshold=confidence_threshold,
        )

        if fill_scores:
            selected_index = int(np.argmax(np.array(fill_scores)))
            selected = choices[selected_index] if selected_index < len(choices) else None
        else:
            selected = None

        min_x = min(cell.x for cell in row_cells)
        min_y = min(cell.y for cell in row_cells)
        max_x = max(cell.x + cell.w for cell in row_cells)
        max_y = max(cell.y + cell.h for cell in row_cells)

        results.append(
            OMRRowResult(
                question_no=question_no,
                selected=selected,
                confidence=confidence,
                fill_scores=fill_scores,
                needs_review=needs_review,
                row_box=(min_x, min_y, max_x, max_y),
            )
        )
        question_no += 1

    return results

