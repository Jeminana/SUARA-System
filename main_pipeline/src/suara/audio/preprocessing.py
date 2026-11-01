"""Bounded little-endian PCM WAV loading and peak-preserving preprocessing."""
from __future__ import annotations

import math
import struct
from pathlib import Path
from typing import BinaryIO

import numpy as np

from suara.contracts import AudioData, DEFAULT_SAMPLE_RATE, PipelineError
from suara.errors import failure

MIN_DURATION_S = 0.5
MAX_DURATION_S = 60.0
SILENCE_RMS = 1e-5


def _invalid(message: str) -> PipelineError:
    return failure("invalid_audio", "preprocessing", message)


def _unsupported(message: str) -> PipelineError:
    return failure("unsupported_audio", "preprocessing", message)


def _read_pcm(stream: BinaryIO) -> tuple[bytes, int, int, int]:
    """Inspect RIFF/chunk bounds and duration before allocating the sample data."""
    file_size = stream.seek(0, 2)
    stream.seek(0)
    header = stream.read(12)
    if len(header) != 12:
        raise _invalid("WAV header is truncated.")
    if header[:4] in (b"RIFX", b"RF64"):
        raise _unsupported("Only little-endian RIFF WAV is supported.")
    if header[:4] != b"RIFF" or header[8:] != b"WAVE":
        raise _invalid("File content is not a RIFF WAV recording.")
    riff_end = 8 + struct.unpack_from("<I", header, 4)[0]
    if riff_end < 12 or riff_end != file_size:
        raise _invalid("WAV container size does not match the file.")
    fmt: bytes | None = None
    fmt_size = 0
    data_location: tuple[int, int] | None = None
    while stream.tell() < riff_end:
        if riff_end - stream.tell() < 8:
            raise _invalid("WAV chunk header is truncated.")
        chunk_id, size = struct.unpack("<4sI", stream.read(8))
        start = stream.tell()
        end = start + size
        # Some PCM writers omit padding after the final odd-sized data chunk.
        padded_end = end + (size % 2 if end < riff_end else 0)
        if end > riff_end or padded_end > riff_end:
            raise _invalid("WAV chunk extends beyond the container.")
        if chunk_id == b"fmt ":
            if fmt is not None or size < 16:
                raise _invalid("WAV format chunk is invalid or duplicated.")
            fmt_size = size
            fmt = stream.read(min(size, 40))
        elif chunk_id == b"data":
            if data_location is not None:
                raise _invalid("Multiple WAV data chunks are not supported.")
            data_location = (start, size)
        stream.seek(padded_end)
    if fmt is None or data_location is None:
        raise _invalid("WAV requires format and data chunks.")
    tag, channels, rate, byte_rate, block_align, bits = struct.unpack_from("<HHIIHH", fmt)
    if fmt_size != 16:
        if fmt_size < 18 or 18 + struct.unpack_from("<H", fmt, 16)[0] > fmt_size:
            raise _invalid("WAV format extension length is inconsistent.")
    if tag == 0xFFFE:  # WAVE_FORMAT_EXTENSIBLE with an integer PCM subtype
        pcm_guid = bytes.fromhex("0100000000001000800000aa00389b71")
        if len(fmt) < 40 or struct.unpack_from("<H", fmt, 16)[0] < 22:
            raise _invalid("Extensible WAV format is truncated.")
        valid_bits = struct.unpack_from("<H", fmt, 18)[0]
        if fmt[24:40] != pcm_guid or valid_bits != bits:
            raise _unsupported("Extensible WAV must use full-width integer PCM.")
    elif tag != 1:
        raise _unsupported("Only uncompressed integer PCM WAV is supported; float/compressed WAV is unsupported.")
    if channels not in (1, 2) or bits not in (8, 16, 24, 32):
        raise _unsupported("WAV must have one or two channels and 8/16/24/32-bit PCM samples.")
    if rate == 0:
        raise _invalid("WAV sample rate must be positive.")
    if not 8000 <= rate <= 192000:
        raise _unsupported("WAV source rate must be between 8000 and 192000 Hz.")
    width = bits // 8
    if block_align != channels * width or byte_rate != rate * block_align:
        raise _invalid("WAV frame alignment or byte rate is inconsistent.")
    offset, size = data_location
    if size == 0 or size % block_align:
        raise _invalid("WAV data is empty or contains incomplete frames.")
    frames = size // block_align
    duration = frames / rate
    if duration < MIN_DURATION_S:
        raise failure("audio_too_short", "preprocessing", "Recording must be at least 0.5 seconds.")
    if duration > MAX_DURATION_S:
        raise failure("audio_too_long", "preprocessing", "Recording must be at most 60 seconds.")
    stream.seek(offset)
    raw = stream.read(size)
    if len(raw) != size:
        raise _invalid("WAV sample data is truncated.")
    return raw, rate, channels, width


def _decode(raw: bytes, width: int, channels: int) -> np.ndarray:
    if width == 1:
        samples = (np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128) / 128
    elif width == 3:
        octets = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        integers = octets[:, 0] | (octets[:, 1] << 8) | (octets[:, 2] << 16)
        integers = (integers ^ 0x800000) - 0x800000
        samples = integers.astype(np.float64) / 2**23
    else:
        samples = np.frombuffer(raw, dtype=f"<i{width}").astype(np.float64) / 2**(width * 8 - 1)
    return samples.reshape(-1, channels)


def preprocess_audio(audio_path: str | Path, *,
                     target_sample_rate: int = DEFAULT_SAMPLE_RATE) -> AudioData:
    if type(target_sample_rate) is not int or not 8000 <= target_sample_rate <= 48000:
        raise failure("invalid_configuration", "configuration", "Target sample rate must be an integer from 8000 to 48000 Hz.")
    try:
        path = Path(audio_path)
        if not path.exists():
            raise failure("audio_not_found", "preprocessing", "Local audio file was not found.")
        if not path.is_file():
            raise _invalid("Audio input must be a local regular file.")
        if path.suffix.lower() != ".wav":
            raise _unsupported("Only local .wav files are supported.")
        with path.open("rb") as stream:
            raw, source_rate, channels, width = _read_pcm(stream)
    except PipelineError:
        raise
    except (OSError, ValueError, TypeError, struct.error) as exc:
        raise _invalid("Local WAV could not be read or decoded.") from exc

    source = _decode(raw, width, channels)
    if not np.isfinite(source).all() or np.any(np.abs(source) > 1):
        raise _invalid("WAV contains invalid sample values.")
    warnings: list[str] = []
    clipped = int(np.count_nonzero(np.abs(source) >= 0.999))
    if clipped:
        warnings.append(f"Source clipping warning: {clipped} channel samples have absolute amplitude >=0.999.")
    mono = source.mean(axis=1)
    if channels == 2:
        warnings.append("Stereo converted to mono by arithmetic channel averaging; gain preserved.")
    if source_rate != target_sample_rate:
        # Avoid SciPy startup cost when the recording already has the target rate.
        import scipy
        from scipy.signal import resample_poly

        divisor = math.gcd(source_rate, target_sample_rate)
        mono = resample_poly(mono, target_sample_rate // divisor, source_rate // divisor,
                             window=("kaiser", 5.0), padtype="constant")
        expected = max(1, round(len(source) * target_sample_rate / source_rate))
        mono = mono[:expected] if len(mono) >= expected else np.pad(mono, (0, expected - len(mono)))
        warnings.append(f"Resampled {source_rate} to {target_sample_rate} Hz using scipy {scipy.__version__} "
                        "resample_poly, Kaiser beta=5.0, constant-zero padding; output rounded to nearest frame.")
    if not np.isfinite(mono).all():
        raise _invalid("Preprocessing produced nonfinite samples.")
    overshoots = int(np.count_nonzero(np.abs(mono) > 1))
    if overshoots:
        mono = np.clip(mono, -1, 1)
        warnings.append(f"Resampling overshoot: clamped {overshoots} samples to [-1,1].")
    if float(np.sqrt(np.mean(mono * mono))) <= SILENCE_RMS:
        raise failure("silent_audio", "preprocessing", "Recording is below the silence floor (RMS <=1e-5 full scale).")
    return AudioData(waveform=mono.tolist(), sample_rate=target_sample_rate,
                     duration_s=len(mono) / target_sample_rate, warnings=warnings)
