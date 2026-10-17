"""Phase 3 data management utilities. Uses only the Python standard library."""
import argparse
import csv
import random
import sys
import wave
from collections import Counter, defaultdict
from pathlib import Path

SEED = 20261006
SPLITS = {"development", "test"}


def read_manifest(path):
    with Path(path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def split_manifest(source, destination, seed=SEED):
    """Assign complete recording lineages, targeting one third development.

    Existing split values are ignored; each root recording and its derivatives
    are grouped through parent_recording_id (with recursive parent resolution).
    """
    rows = read_manifest(source)
    by_id = {r["recording_id"]: r for r in rows if r.get("recording_id")}

    def root(row):
        seen = set()
        current = row
        while current.get("parent_recording_id"):
            parent = current["parent_recording_id"]
            if parent in seen or parent not in by_id:
                raise ValueError(f"Invalid parent lineage for {row.get('recording_id')}: {parent}")
            seen.add(parent)
            current = by_id[parent]
        return current["recording_id"]

    groups = defaultdict(list)
    for row in rows:
        if row.get("recording_id"):
            groups[root(row)].append(row)
    roots = list(groups)
    random.Random(seed).shuffle(roots)
    target = round(len(roots) / 3)
    # Greedy assignment balances participant/task counts while keeping the
    # development size near target. The seed makes ties reproducible.
    dev_counts, all_counts = Counter(), Counter()
    chosen = set()
    for rid in roots:
        group = groups[rid]
        for r in group:
            for k in ("participant_id", "task"):
                if r.get(k):
                    all_counts[(k, r[k])] += 1
    remaining = list(roots)
    while len(chosen) < target and remaining:
        def cost(rid):
            return sum(dev_counts[(k, r.get(k, ""))] / max(1, all_counts[(k, r.get(k, ""))])
                       for r in groups[rid] for k in ("participant_id", "task") if r.get(k))
        rid = min(remaining, key=cost)
        remaining.remove(rid)
        chosen.add(rid)
        for r in groups[rid]:
            for k in ("participant_id", "task"):
                if r.get(k):
                    dev_counts[(k, r[k])] += 1
    for row in rows:
        if row.get("recording_id"):
            row["split"] = "development" if root(row) in chosen else "test"
    if rows:
        with Path(destination).open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    return len(chosen), len(roots)


def validate_manifest(path, data_root):
    rows = read_manifest(path)
    errors, warnings = [], []
    seen = set()
    by_id = {r.get("recording_id", ""): r for r in rows}
    for i, row in enumerate(rows, 2):
        rid = row.get("recording_id", "").strip()
        label = f"row {i} ({rid or 'no recording_id'})"
        if not rid:
            errors.append(f"{label}: missing recording_id")
        elif rid in seen:
            errors.append(f"{label}: duplicate recording_id")
        seen.add(rid)
        kind = row.get("recording_type", "")
        if kind == "human" and not row.get("consent_status", "").strip():
            errors.append(f"{label}: missing consent_status for human recording")
        if row.get("split") and row["split"] not in SPLITS:
            errors.append(f"{label}: invalid split {row['split']!r}")
        if row.get("exclusion_status", "").lower() in {"excluded", "yes", "true"} and not row.get("exclusion_reason", "").strip():
            errors.append(f"{label}: excluded item needs exclusion_reason")
        for column in ("audio_path", "reference_path"):
            value = row.get(column, "").strip()
            if value:
                p = Path(data_root) / value
                if not p.is_file():
                    errors.append(f"{label}: missing {column}: {value}")
                elif column == "audio_path":
                    try:
                        if p.stat().st_size == 0:
                            errors.append(f"{label}: empty audio: {value}")
                        else:
                            with wave.open(str(p), "rb") as wav:
                                rate, channels, frames = wav.getframerate(), wav.getnchannels(), wav.getnframes()
                                if rate <= 0 or frames <= 0:
                                    errors.append(f"{label}: invalid sample rate or empty WAV: {value}")
                                if row.get("original_sample_rate") and int(row["original_sample_rate"]) != rate and row.get("recording_type") != "working":
                                    warnings.append(f"{label}: declared original sample rate differs from WAV header")
                                if row.get("original_sample_rate") and int(row["original_sample_rate"]) != rate and row.get("recording_type") == "synthetic":
                                    errors.append(f"{label}: declared original sample rate differs from synthetic WAV header")
                                if row.get("working_sample_rate") and int(row["working_sample_rate"]) != rate and row.get("recording_type") == "working":
                                    errors.append(f"{label}: working sample rate differs from WAV header")
                                if row.get("channel_count") and int(row["channel_count"]) != channels:
                                    errors.append(f"{label}: channel_count differs from WAV header")
                                width = wav.getsampwidth()
                                raw = wav.readframes(frames)
                                if width == 2:
                                    vals = [int.from_bytes(raw[j:j+2], "little", signed=True) for j in range(0, len(raw), 2)]
                                    if vals and sum(abs(v) >= 32760 for v in vals) / len(vals) > 0.01:
                                        warnings.append(f"{label}: badly clipped audio (>1% near full scale): {value}")
                    except wave.Error as exc:
                        # Python's wave module does not support IEEE-float WAV
                        # (format code 3); use the already-installed soundfile
                        # reader for those standardized working files.
                        try:
                            import soundfile as sf
                            info = sf.info(str(p))
                            if info.frames <= 0 or info.samplerate <= 0:
                                errors.append(f"{label}: invalid sample rate or empty WAV: {value}")
                            if row.get("original_sample_rate") and int(row["original_sample_rate"]) != info.samplerate and row.get("recording_type") == "synthetic":
                                errors.append(f"{label}: declared original sample rate differs from synthetic WAV header")
                            if row.get("working_sample_rate") and int(row["working_sample_rate"]) != info.samplerate and row.get("recording_type") in {"working", "synthetic"}:
                                errors.append(f"{label}: working sample rate differs from WAV header")
                            if row.get("channel_count") and int(row["channel_count"]) != info.channels:
                                errors.append(f"{label}: channel_count differs from WAV header")
                            audio, _ = sf.read(str(p), dtype="float32", always_2d=True)
                            if audio.size and float((abs(audio) >= 0.99).mean()) > 0.01:
                                warnings.append(f"{label}: badly clipped audio (>1% near full scale): {value}")
                        except (ImportError, RuntimeError, OSError, ValueError) as fallback_exc:
                            errors.append(f"{label}: unreadable WAV {value}: {exc}; soundfile fallback: {fallback_exc}")
                    except (OSError, ValueError) as exc:
                        errors.append(f"{label}: unreadable WAV {value}: {exc}")
        parent = row.get("parent_recording_id", "").strip()
        if parent and parent in by_id and row.get("split") != by_id[parent].get("split"):
            errors.append(f"{label}: derived recording split differs from parent {parent}")
        elif parent and parent not in by_id:
            errors.append(f"{label}: unknown parent_recording_id {parent}")
    return errors, warnings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    split = sub.add_parser("split")
    split.add_argument("manifest")
    split.add_argument("output")
    split.add_argument("--seed", type=int, default=SEED)
    validate = sub.add_parser("validate")
    validate.add_argument("manifest")
    validate.add_argument("--data-root", default="data")
    args = parser.parse_args()
    if args.command == "split":
        dev, total = split_manifest(args.manifest, args.output, args.seed)
        print(f"Assigned {dev}/{total} recording lineages to development; seed={args.seed}")
    else:
        errors, warnings = validate_manifest(args.manifest, args.data_root)
        for message in warnings:
            print("WARNING:", message)
        for message in errors:
            print("ERROR:", message)
        print(f"Validation: {len(errors)} errors, {len(warnings)} warnings")
        return bool(errors)
    return False


if __name__ == "__main__":
    sys.exit(main())
