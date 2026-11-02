"""Reproduce Day 3 tests, CLI transcripts and mock-runtime benchmarks offline.

Run from the repository root with the installed pipeline interpreter. All audio
is synthetic and ignored; evidence logs contain no waveform or participant data.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.metadata
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PIPELINE = ROOT / 'main_pipeline'
sys.path.insert(0, str(PIPELINE / 'tests'))
from helpers import write_wav  # noqa: E402 - reuse the synthetic-only test writer


def peak_memory_mib():
    """OS process lifetime peak working set; includes interpreter/native libraries."""
    if os.name == 'nt':
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD),
                        *[(name, ctypes.c_size_t) for name in (
                            'PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
                            'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
                            'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        query = ctypes.WinDLL('psapi', use_last_error=True).GetProcessMemoryInfo
        query.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        query.restype = wintypes.BOOL
        if query(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            return counters.PeakWorkingSetSize / 1024**2
        return None
    try:
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return peak / (1024**2 if sys.platform == 'darwin' else 1024)
    except ImportError:
        return None


COLD_CODE = '''import json, sys, time
start = time.perf_counter()
from suara.pipeline import run_pipeline
imported = time.perf_counter()
result = run_pipeline(sys.argv[1])
finished = time.perf_counter()
# Read memory only after the timed pipeline work; no fixture helpers imported.
import runpy
helpers = runpy.run_path(sys.argv[2], run_name="day3_memory_helpers")
print(json.dumps({"import_s": imported-start, "first_call_wall_s": finished-imported,
    "processing_time_s": result.processing_time_s,
    "peak_working_set_mib": helpers["peak_memory_mib"]()}))
'''


def experiment_digest():
    """Hash every tracked experiment file without running experiment modules."""
    command = ['git', '-c', f'safe.directory={ROOT.as_posix()}', 'ls-files', '-z', '--',
               'experiments/E1', 'experiments/E3', 'experiments/E6']
    result = subprocess.run(command, cwd=ROOT, capture_output=True, check=True)
    digest = hashlib.sha256()
    count = 0
    for name in sorted(result.stdout.decode().split('\0')):
        if name:
            digest.update(name.encode())
            digest.update((ROOT / name).read_bytes())
            count += 1
    return {'tracked_files': count, 'sha256': digest.hexdigest()}


def summarize(values):
    return {'samples': values, 'median': statistics.median(values),
            'min': min(values), 'max': max(values)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--checks-only', action='store_true',
                        help='Re-run checks and retain previously recorded benchmark samples.')
    args = parser.parse_args()
    if args.repeats < 3:
        parser.error('Use at least three repeats.')
    logs = PIPELINE / 'validation_logs'
    fixtures = PIPELINE / '.smoke' / 'day3'
    logs.mkdir(exist_ok=True)
    fixtures.mkdir(parents=True, exist_ok=True)
    previous = None
    if args.checks_only:
        if not (logs / 'summary.json').exists():
            parser.error('--checks-only requires a previous full validation run.')
        previous = json.loads((logs / 'summary.json').read_text(encoding='utf-8'))
    summary = {'recorded_utc': datetime.now(timezone.utc).isoformat(),
               'environment': {'python': sys.version, 'platform': platform.platform(),
                               'machine': platform.machine(), 'cpu_count': os.cpu_count(),
                               'packages': {name: importlib.metadata.version(name) for name in
                                            ('numpy', 'scipy', 'pip', 'suara-main-pipeline')}},
               'experiments_before': experiment_digest(), 'checks': {}}

    def command(name, argv, expected=0):
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
        record = {'command': argv, 'exit_code': result.returncode, 'expected_exit_code': expected,
                  'stdout': result.stdout, 'stderr': result.stderr}
        (logs / f'{name}.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
        summary['checks'][name] = result.returncode == expected
        print(f'{name}: exit {result.returncode} (expected {expected})', flush=True)
        return result

    tests = command('tests', [sys.executable, '-m', 'unittest', 'discover', '-s', 'main_pipeline/tests', '-v'])
    (logs / 'tests.txt').write_text(tests.stdout + tests.stderr, encoding='utf-8')
    command('dependencies', [sys.executable, '-m', 'pip', 'check'])
    command('imports', [sys.executable, '-c',
        "import sys; import suara; from suara.contracts import SCHEMA_VERSION; "
        "assert not ({'numpy','scipy','torch','tensorflow','librosa','speechbrain'} & sys.modules.keys()); "
        "print('Package and contracts import successfully without audio or AI libraries:', SCHEMA_VERSION)"])

    paths = {}
    for duration in (1, 10, 30, 60):
        for rate, channels in ((16000, 1), (48000, 2)):
            name = f'{duration}s_{rate}hz_{channels}ch'
            paths[name] = write_wav(fixtures / f'{name}.wav', duration=duration, rate=rate, channels=channels)
    silent = write_wav(fixtures / 'silence.wav', amplitude=0)
    short = write_wav(fixtures / 'short.wav', duration=0.1)
    long = write_wav(fixtures / 'long.wav', duration=60+1/16000)
    broken = fixtures / 'broken.wav'
    broken.write_bytes(b'not a WAV')
    unsupported = fixtures / 'unsupported.mp3'
    unsupported.write_bytes(b'synthetic unsupported fixture')
    cli_cases = [('cli_success', ['--audio', str(paths['1s_48000hz_2ch']), '--mode', 'mock'], 0, None),
                 ('cli_top2', ['--audio', str(paths['1s_16000hz_1ch']), '--top-k', '2'], 0, None),
                 ('cli_silence', ['--audio', str(silent)], 2, 'silent_audio'),
                 ('cli_short', ['--audio', str(short)], 2, 'audio_too_short'),
                 ('cli_long', ['--audio', str(long)], 2, 'audio_too_long'),
                 ('cli_corrupt', ['--audio', str(broken)], 2, 'invalid_audio'),
                 ('cli_unsupported', ['--audio', str(unsupported)], 2, 'unsupported_audio'),
                 ('cli_missing', ['--audio', str(fixtures / 'missing.wav')], 2, 'audio_not_found'),
                 ('cli_real', ['--audio', str(paths['1s_16000hz_1ch']), '--mode', 'real'], 2, 'invalid_configuration'),
                 ('cli_bad_arguments', ['--audio', 'synthetic.wav', '--top-k', 'six'], 2, 'invalid_configuration')]
    for name, argv, expected, error in cli_cases:
        result = command(name, [sys.executable, '-m', 'suara.cli', *argv], expected)
        try:
            payload = json.loads(result.stderr if expected else result.stdout)
            assert (result.stdout if expected else result.stderr) == ''
            if error:
                assert payload['code'] == error
            else:
                assert payload['analysis_mode'] == 'mock'
                assert len(payload['recommendations']) == (2 if name == 'cli_top2' else 5)
                assert all(r['mode'] == 'mock' for r in payload['recommendations'])
        except (ValueError, AssertionError, KeyError):
            summary['checks'][name] = False

    command('mock_imports', [sys.executable, '-c',
        "import sys; from suara.pipeline import run_pipeline; run_pipeline(sys.argv[1]); "
        "assert not ({'torch','tensorflow','librosa','speechbrain','crepe','transformers'} & sys.modules.keys()); "
        "print('Mock pipeline completed without AI libraries.')", str(paths['1s_48000hz_2ch'])])

    from suara.pipeline import run_pipeline
    measurements = {}
    for name, path in ([] if args.checks_only else paths.items()):
        cold = []
        for _ in range(args.repeats):
            started = time.perf_counter()
            result = subprocess.run([sys.executable, '-c', COLD_CODE, str(path), str(Path(__file__).resolve())],
                                    cwd=ROOT, capture_output=True, text=True, check=True)
            wall = time.perf_counter() - started
            cold.append(dict(json.loads(result.stdout), process_wall_s=wall))
        run_pipeline(path)  # Untimed warmup for this configuration.
        warm_wall, warm_reported = [], []
        for _ in range(args.repeats):
            started = time.perf_counter()
            result = run_pipeline(path)
            warm_wall.append(time.perf_counter() - started)
            warm_reported.append(result.processing_time_s)
        measurements[name] = {'cold': {key: summarize([row[key] for row in cold]) for key in cold[0]
                                                  if cold[0][key] is not None},
                              'warm_wall_s': summarize(warm_wall),
                              'warm_processing_time_s': summarize(warm_reported)}
        print(f'{name}: warm median {statistics.median(warm_wall):.4f}s', flush=True)
    summary['performance'] = measurements
    summary['performance_method'] = (
        'Three fresh child processes per configuration; parent wall includes process launch, imports, '
        'first pipeline call, memory helper and JSON output/exit. Cold worker times imports and first '
        'pipeline call separately. Same parent process: one warmup/configuration then three calls. '
        'OS peak working set includes interpreter/native libraries and the post-timing memory helper; '
        'it is approximate lifetime process memory, not incremental allocations. OS file caches remain warm. '
        'Synthetic PCM16; 16kHz mono and 48kHz stereo. Fixture generation excluded. '
        'Mock processing only, not AI inference latency.')
    summary['performance_recorded_utc'] = summary['recorded_utc']
    if previous is not None:
        summary['performance'] = previous['performance']
        summary['performance_method'] = previous['performance_method']
        summary['performance_recorded_utc'] = previous.get('performance_recorded_utc', previous['recorded_utc'])
    git = ['git', '-c', f'safe.directory={ROOT.as_posix()}']
    command('diff_check', [*git, 'diff', '--check'])
    command('git_status', [*git, 'status', '--short'])
    command('git_branch', [*git, 'branch', '--show-current'])
    command('experiment_diff', [*git, 'diff', '--exit-code', 'HEAD', '--',
                                'experiments/E1', 'experiments/E3', 'experiments/E6'])
    summary['experiments_after'] = experiment_digest()
    summary['checks']['experiment_hashes_unchanged'] = summary['experiments_before'] == summary['experiments_after']
    summary['all_checks_passed'] = all(summary['checks'].values())
    (logs / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(f"All checks passed: {summary['all_checks_passed']}", flush=True)
    return 0 if summary['all_checks_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
