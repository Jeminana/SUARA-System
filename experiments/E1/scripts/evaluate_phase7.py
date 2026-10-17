"""Portable core metrics from corrected Phase 7; no I/O or private-data access."""
from __future__ import annotations
import math
import statistics
from typing import Iterable

def number(value: object) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def grid_index(timestamp: object, interval: float = 0.01, origin: float = 0.0,
               tolerance: float = 1e-6) -> int:
    """Return the unique integer grid index, rejecting timestamps off the frozen grid."""
    t = number(timestamp)
    if t is None or interval <= 0:
        raise ValueError(f'invalid timestamp or grid interval: {timestamp!r}')
    index = int(round((t - origin) / interval))
    expected = origin + index * interval
    if index < 0 or abs(t - expected) > tolerance:
        raise ValueError(f'off-grid timestamp {timestamp!r}; nearest index={index}, expected={expected:.12f}')
    return index


def index_rows(source_rows: Iterable[dict[str, str]], timestamp_field: str,
               *, interval: float = 0.01, origin: float = 0.0,
               tolerance: float = 1e-6) -> dict[int, dict[str, str]]:
    """Index rows with integer frames and reject duplicate frame indices."""
    indexed: dict[int, dict[str, str]] = {}
    for row in source_rows:
        k = grid_index(row[timestamp_field], interval, origin, tolerance)
        if k in indexed:
            raise ValueError(f'duplicate grid index {k} ({indexed[k][timestamp_field]!r}, {row[timestamp_field]!r})')
        indexed[k] = row
    return indexed


def require_indices(indexed: dict[int, object], expected: set[int], label: str) -> None:
    actual = set(indexed)
    if actual != expected:
        raise ValueError(f'{label} grid mismatch: missing={sorted(expected-actual)[:10]}, extra={sorted(actual-expected)[:10]}')


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def score(reference: dict[int, dict], prediction: dict[int, dict], detector: str) -> tuple[dict, list[float]]:
    """Apply the unchanged Phase 6 definitions to integer-indexed rows."""
    ref_voiced_frames = [r for r in reference.values() if r['voiced']]
    errors: list[float] = []
    correct = octave = tp = fp = fn = coverage_count = 0
    for k, ref in reference.items():
        pred = prediction.get(k)
        f0 = number(pred.get('f0_hz')) if pred else None
        confidence = number(pred.get('confidence')) if pred else None
        native_flag = pred is not None and str(pred.get('voiced_flag', '')).strip().lower() in ('1', 'true')
        valid_f0 = f0 is not None and f0 > 0
        predicted_voiced = valid_f0 and (native_flag if detector == 'pyin' else confidence is not None and confidence >= 0.5)
        ref_is_voiced = ref['voiced']
        tp += int(ref_is_voiced and predicted_voiced)
        fp += int(not ref_is_voiced and predicted_voiced)
        fn += int(ref_is_voiced and not predicted_voiced)
        if ref_is_voiced and predicted_voiced:
            coverage_count += 1
            cents = 1200 * math.log2(f0 / ref['reference_f0_hz'])
            absolute_cents = abs(cents)
            errors.append(absolute_cents)
            correct += int(absolute_cents <= 50)
            octave += int(abs(absolute_cents - 1200) <= 50)
    voiced_count = len(ref_voiced_frames)
    jointly = len(errors)
    result = {
        'expected_reference_rows': 300,
        'valid_reference_rows': len(reference),
        'reference_coverage': ratio(len(reference), 300),
        'reference_voiced_frames': voiced_count,
        'jointly_voiced_valid_f0_frames': jointly,
        'voiced_estimate_coverage_count': coverage_count,
        'voiced_estimate_coverage': ratio(coverage_count, voiced_count),
        'raw_pitch_accuracy_50c_correct': correct,
        'raw_pitch_accuracy_50c_denominator': voiced_count,
        'raw_pitch_accuracy_within_50_cents': ratio(correct, voiced_count),
        'median_absolute_cents_error': statistics.median(errors) if errors else None,
        'p90_absolute_cents_error': sorted(errors)[math.ceil(0.9 * len(errors)) - 1] if errors else None,
        'octave_errors': octave,
        'octave_error_denominator': voiced_count,
        'octave_error_rate': ratio(octave, voiced_count),
        'voicing_tp': tp,
        'voicing_fp': fp,
        'voicing_fn': fn,
        'voicing_precision': ratio(tp, tp + fp),
        'voicing_recall': ratio(tp, tp + fn),
        'voicing_f1': ratio(2 * tp, 2 * tp + fp + fn),
    }
    return result, errors
