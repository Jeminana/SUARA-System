"""Generate a public synthetic tone; never read participant recordings."""
import argparse
import math
import struct
import wave
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("main_pipeline/.smoke/tone.wav"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rate = 44100
    # One second, stereo, identical channels, 220 Hz and 25% full-scale amplitude.
    data = b"".join(struct.pack("<hh", value, value) for value in (
        round(8192 * math.sin(2 * math.pi * 220 * index / rate)) for index in range(rate)))
    with wave.open(str(args.output), "wb") as stream:
        stream.setparams((2, 2, rate, 0, "NONE", "not compressed"))
        stream.writeframes(data)
    print(f"Generated synthetic 1-second stereo 44100 Hz PCM16 WAV: {args.output}")


if __name__ == "__main__":
    main()
