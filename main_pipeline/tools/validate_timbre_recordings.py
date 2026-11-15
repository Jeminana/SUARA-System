"""Local authorized E6 manifest check. Print aggregates, never audio or vectors."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path

from suara.audio.preprocessing import preprocess_audio
from suara.contracts import PipelineDependencies, PipelineError
from suara.mocks.pitch import analyze_pitch
from suara.mocks.recommender import recommend_songs
from suara.pipeline import run_pipeline
from suara.timbre import MODEL_VERSION, PROCESSING_VERSION, analyze_timbre


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--audio-root', type=Path, required=True)
    args = parser.parse_args()
    deps = PipelineDependencies(preprocess_audio=preprocess_audio, analyze_pitch=analyze_pitch,
                                analyze_timbre=analyze_timbre, recommend_songs=recommend_songs)
    passed = skipped = 0
    errors = Counter()
    root = args.audio_root.resolve()
    with args.manifest.open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            if row['consent'].lower() != 'yes' or row['excluded'].lower() != 'false':
                skipped += 1
                continue
            path = (root / row['file_path']).resolve()
            if not path.is_relative_to(root):
                errors['invalid_manifest_path'] += 1
                continue
            try:
                audio = preprocess_audio(path)
                before = audio.to_dict()
                standalone = analyze_timbre(audio)
                result = run_pipeline(path, dependencies=deps)
                result.to_json()
                assert audio.to_dict() == before
                assert standalone == result.voice_profile.timbre
                assert standalone.processing_version == PROCESSING_VERSION
                assert standalone.model_version == MODEL_VERSION
                assert standalone.mode == 'real'
                assert result.analysis_mode == result.voice_profile.pitch.mode == 'mock'
                assert all(rec.mode == 'mock' for rec in result.recommendations)
                passed += 1
            except PipelineError as exc:
                errors[exc.error.code] += 1
            except Exception as exc:
                # No private file names, raw exceptions, vectors, or participant IDs.
                errors[type(exc).__name__] += 1
    print(json.dumps(dict(passed=passed, skipped=skipped, failed=sum(errors.values()),
                          errors=dict(errors), model_version=MODEL_VERSION,
                          processing_version=PROCESSING_VERSION), indent=2))
    return 1 if errors or passed == 0 else 0


if __name__ == '__main__':
    raise SystemExit(main())
