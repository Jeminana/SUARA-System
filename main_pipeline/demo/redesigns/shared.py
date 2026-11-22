"""Shared analysis and view data for the demo redesigns; each design only draws.

The analysis is exactly the original demo's: the mock pipeline with its synthetic pitch and
timbre, the fictional mock catalog and the fixed-score mock ranking. Nothing here is measured
from the recording except preprocessing, and every design says so.
"""
from __future__ import annotations

import base64
import html
import math
import tempfile
from dataclasses import dataclass
from pathlib import Path
from functools import lru_cache

from suara.mocks.catalog import mock_song_catalog
from suara.pipeline import run_pipeline
from suara.recommender import hz_to_midi, note_name

HERE = Path(__file__).resolve().parent
FONTS = HERE / "fonts"
DEFAULT_SPAN = (43, 67)   # G2-G4 in MIDI: the axis when nothing on screen has a pitch range

esc = html.escape


@dataclass(frozen=True)
class Song:
    song_id: str
    title: str
    artist: str
    low_hz: float | None          # the mock catalog has no melody ranges
    high_hz: float | None
    rank: int | None = None
    score: float | None = None
    reason: str | None = None

    @property
    def has_range(self) -> bool:
        return self.low_hz is not None and self.high_hz is not None

    @property
    def span(self) -> str:
        if not self.has_range:
            return "no melody range"
        return f"{note_name(hz_to_midi(self.low_hz))}–{note_name(hz_to_midi(self.high_hz))}"

    @property
    def name(self) -> str:
        """Title without a "Pilot song N:" style prefix."""
        return self.title.split(": ", 1)[-1]

    @property
    def code(self) -> str:
        """Short catalog number, e.g. 001 for mock-001."""
        return self.song_id.split("-")[-1]


@dataclass(frozen=True)
class Voice:
    low_hz: float
    high_hz: float
    median_hz: float
    voiced_ratio: float

    @property
    def span(self) -> str:
        return f"{note_name(hz_to_midi(self.low_hz))}–{note_name(hz_to_midi(self.high_hz))}"

    @property
    def median_note(self) -> str:
        return note_name(hz_to_midi(self.median_hz))


@dataclass(frozen=True)
class Analysis:
    voice: Voice | None          # None when no voiced pitch was found
    songs: list[Song]            # the whole catalog, recommended songs first in rank order
    caveat: str                  # an explanation every recommendation shares, shown once
    pitch_measured: bool
    timbre_measured: bool
    centroid_hz: float | None
    mfcc: list[float]
    warnings: list[str]
    seconds: float | None

    @property
    def recommended(self) -> list[Song]:
        return [s for s in self.songs if s.rank is not None]


def catalog_songs() -> list[Song]:
    return [Song(s.song_id, s.title, s.artist, s.melody_min_pitch_hz, s.melody_max_pitch_hz)
            for s in mock_song_catalog()]


def analyze(audio: bytes, top_k: int) -> Analysis:
    """Run the original demo's mock pipeline on uploaded WAV bytes; raises PipelineError."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
        handle.write(audio)
        path = Path(handle.name)
    try:
        result = run_pipeline(path, mode="mock", top_k=top_k)
    finally:
        path.unlink(missing_ok=True)

    pitch = result.voice_profile.pitch
    voice = None if pitch.voiced_ratio == 0 else Voice(pitch.min_pitch_hz, pitch.max_pitch_hz,
                                                       pitch.median_pitch_hz, pitch.voiced_ratio)
    explanations = {rec.explanation for rec in result.recommendations}
    shared_note = explanations.pop() if len(explanations) == 1 else ""
    ranked = {rec.song_id: (rank, rec.score, None if shared_note else rec.explanation)
              for rank, rec in enumerate(result.recommendations, 1)}
    songs = [Song(s.song_id, s.title, s.artist, s.low_hz, s.high_hz, *ranked.get(s.song_id, (None, None, None)))
             for s in catalog_songs()]
    songs.sort(key=lambda s: (s.rank is None, s.rank or 0, s.song_id))
    timbre = result.voice_profile.timbre
    return Analysis(voice=voice, songs=songs, caveat=shared_note, pitch_measured=pitch.mode == "real",
                    timbre_measured=timbre.mode == "real", centroid_hz=timbre.spectral_centroid_mean_hz,
                    mfcc=list(timbre.mfcc_mean), warnings=list(result.voice_profile.warnings),
                    seconds=result.processing_time_s)


@dataclass(frozen=True)
class Scale:
    """Log-frequency axis in semitones, padded around everything it must show."""
    low: float
    high: float

    @classmethod
    def around(cls, songs: list[Song], voice: Voice | None, pad: float = 2.0) -> "Scale":
        ranged = [s for s in songs if s.has_range]
        values = [hz_to_midi(s.low_hz) for s in ranged] + [hz_to_midi(s.high_hz) for s in ranged]
        if voice:
            values += [hz_to_midi(voice.low_hz), hz_to_midi(voice.high_hz)]
        if not values:
            return cls(*DEFAULT_SPAN)
        return cls(math.floor(min(values) - pad), math.ceil(max(values) + pad))

    def pos(self, hz: float) -> float:
        """0..1 along the axis."""
        return (hz_to_midi(hz) - self.low) / (self.high - self.low)

    def ticks(self, names: tuple[str, ...] = ("C", "A")) -> list[tuple[float, str, float]]:
        """(position, note name, Hz) for each C and A on the axis."""
        out = []
        for midi in range(math.ceil(self.low), math.floor(self.high) + 1):
            name = note_name(midi)
            if name.rstrip("0123456789-") in names:
                hz = 440.0 * 2 ** ((midi - 69) / 12)
                out.append(((midi - self.low) / (self.high - self.low), name, hz))
        return out


@dataclass(frozen=True)
class DialTheme:
    """Colours and faces for the tuning dial, so each design draws the same instrument in its own world."""
    glass: tuple[str, str, str]   # centre, middle and edge of the lit glass
    ink: str                      # scale, ticks and note names
    ink_dim: str                  # stations not in the current results
    hz_ink: str                   # Hz sub-labels and the empty-dial note
    label: str                    # band and needle captions
    band_glow: str
    band_fill: str
    needle: str
    display: str                  # font family for note names and captions
    display_weight: int
    text: str                     # font family for station labels
    text_weight: int
    display_style: str = "normal"


DIAL_LAYOUTS = {"wide": (1200, 40, 1160), "medium": (640, 26, 614), "compact": (440, 22, 418)}
DIAL_H = 300


def dial_label(songs: list[Song], voice: Voice | None) -> str:
    stations = "; ".join(f"{s.code} {s.name} {s.span}" for s in songs) or "none, the demo songs have no melody range"
    lead = f"Your voice {voice.span}, centre {voice.median_note}. " if voice else "No voice range yet. "
    return f"Tuning dial. {lead}Stations: {stations}."


def dial_svg(songs: list[Song], analysis: Analysis | None, layout: str, theme: DialTheme,
             needle_class: str = "dial-needle") -> str:
    """The tuning dial: a Hz scale, the singer's range as a lit band, the needle on the median note,
    and every song that has a melody range as a station. Returns one <svg class="{layout}">."""
    width, left, right = DIAL_LAYOUTS[layout]
    compact = layout == "compact"
    t = theme
    voice = analysis.voice if analysis else None
    scale = Scale.around(songs, voice)
    x = lambda hz: left + scale.pos(hz) * (right - left)
    rows = sorted((s for s in songs if s.has_range), key=lambda s: s.song_id)
    label_size = {"compact": 19, "medium": 17, "wide": 15}[layout]
    disp = f'font-family="{t.display}" font-weight="{t.display_weight}" font-style="{t.display_style}"'
    gid = layout[0]
    parts = [f'<svg class="{layout}" viewBox="0 0 {width} {DIAL_H}" role="img" aria-label="{esc(dial_label(rows, voice))}">',
             f'<defs><radialGradient id="glass-{gid}" cx="50%" cy="45%" r="75%">'
             f'<stop offset="0" stop-color="{t.glass[0]}"/><stop offset=".6" stop-color="{t.glass[1]}"/>'
             f'<stop offset="1" stop-color="{t.glass[2]}"/></radialGradient>'
             f'<filter id="bloom-{gid}" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="9"/></filter>'
             '</defs>',
             f'<rect width="{width}" height="{DIAL_H}" fill="url(#glass-{gid})"/>']
    if voice:
        x0, x1 = x(voice.low_hz), x(voice.high_hz)
        parts += [f'<rect x="{x0:.1f}" y="14" width="{x1 - x0:.1f}" height="216" fill="{t.band_glow}" opacity=".75" filter="url(#bloom-{gid})"/>',
                  f'<rect x="{x0:.1f}" y="14" width="{x1 - x0:.1f}" height="216" fill="{t.band_fill}" opacity=".55"/>',
                  f'<text x="{x0 + 8:.1f}" y="34" {disp} font-size="{label_size + 2}" letter-spacing=".5" fill="{t.label}">'
                  f'YOUR BAND {esc(voice.span)}{"" if compact else f"  ·  {voice.low_hz:.0f}–{voice.high_hz:.0f} Hz"}</text>']
    for i, song in enumerate(rows):
        y = 70 + i * 30
        x0, x1 = x(song.low_hz), x(song.high_hz)
        ink = t.ink if (analysis is None or song.rank is not None) else t.ink_dim
        parts += [f'<line x1="{x0:.1f}" y1="{y}" x2="{x1:.1f}" y2="{y}" stroke="{ink}" stroke-width="3"/>',
                  f'<line x1="{x0:.1f}" y1="{y - 7}" x2="{x0:.1f}" y2="{y + 7}" stroke="{ink}" stroke-width="2"/>',
                  f'<line x1="{x1:.1f}" y1="{y - 7}" x2="{x1:.1f}" y2="{y + 7}" stroke="{ink}" stroke-width="2"/>']
        if compact:   # code above the start of the line, so it never runs off the glass
            parts.append(f'<text x="{x0:.1f}" y="{y - 9}" font-family="{t.text}" font-weight="{t.text_weight}" '
                         f'font-size="{label_size - 3}" fill="{ink}">{esc(song.code)}</text>')
        else:
            parts.append(f'<text x="{x1 + 10:.1f}" y="{y + 5}" font-family="{t.text}" font-weight="{t.text_weight}" '
                         f'font-size="{label_size}" fill="{ink}">{esc(song.code)}  {esc(song.name)}</text>')
    if not rows:   # the mock catalog carries no melody ranges, so nothing can be placed
        lines = (("The demo songs have no melody range, so no station is placed on the dial",) if layout == "wide"
                 else ("The demo songs have no melody range,", "so no station is placed on the dial"))
        for k, line in enumerate(lines):
            parts.append(f'<text x="{(left + right) / 2:.1f}" y="{132 + k * 26}" text-anchor="middle" font-family="{t.text}" '
                         f'font-weight="{t.text_weight}" font-size="{label_size + 2}" fill="{t.hz_ink}" paint-order="stroke" '
                         f'stroke="{t.band_fill if voice else t.glass[1]}" stroke-width="6" stroke-linejoin="round">{line}</text>')
    parts.append(f'<line x1="{left}" y1="232" x2="{right}" y2="232" stroke="{t.ink}" stroke-width="2"/>')
    for semitone in range(scale.low, scale.high + 1):
        sx = left + (semitone - scale.low) / (scale.high - scale.low) * (right - left)
        parts.append(f'<line x1="{sx:.1f}" y1="232" x2="{sx:.1f}" y2="240" stroke="{t.ink}" stroke-width="1.2"/>')
    for pos, name, hz in scale.ticks(("C", "A") if compact else ("C", "E", "G", "A")):
        sx = left + pos * (right - left)
        parts += [f'<line x1="{sx:.1f}" y1="222" x2="{sx:.1f}" y2="250" stroke="{t.ink}" stroke-width="2.4"/>',
                  f'<text x="{sx:.1f}" y="276" text-anchor="middle" {disp} font-size="24" fill="{t.ink}">{name}</text>']
        if not compact:
            parts.append(f'<text x="{sx:.1f}" y="294" text-anchor="middle" font-family="{t.text}" font-weight="500" '
                         f'font-size="13" fill="{t.hz_ink}">{hz:.0f} Hz</text>')
    if voice:
        needle = x(voice.median_hz)
        anchor, dx = ("end", -10) if needle > (left + right) / 2 else ("start", 10)
        parts += [f'<g class="{needle_class}" style="--from:{left + 6 - needle:.1f}px">',
                  f'<line x1="{needle:.1f}" y1="6" x2="{needle:.1f}" y2="246" stroke="{t.needle}" stroke-width="3.5"/>',
                  f'<rect x="{needle - 7:.1f}" y="2" width="14" height="12" rx="3" fill="{t.needle}"/>',
                  f'<text x="{needle + dx:.1f}" y="214" text-anchor="{anchor}" {disp} font-size="{label_size + 2}" '
                  f'fill="{t.label}">{esc(voice.median_note)} · {voice.median_hz:.0f} Hz</text></g>']
    else:
        parts += [f'<line x1="{left + 6}" y1="6" x2="{left + 6}" y2="246" stroke="{t.needle}" stroke-width="3.5"/>',
                  f'<rect x="{left - 1}" y="2" width="14" height="12" rx="3" fill="{t.needle}"/>',
                  f'<text x="{left + 20}" y="34" {disp} font-size="{label_size + 2}" letter-spacing=".5" fill="{t.label}">'
                  f'{"NO SIGNAL · NO SUNG PITCH" if analysis else "NO SIGNAL · TUNE IN A RECORDING"}</text>']
    parts.append("</svg>")
    return "".join(parts)


@lru_cache(maxsize=None)
def font_css(*faces: tuple[str, ...]) -> str:
    """@font-face rules with the font files inlined, so the demo needs no network.

    Each face is (family, file name in fonts/, weight or weight range, style[, width range]).
    """
    rules = []
    for family, filename, weight, style, *stretch in faces:
        data = base64.b64encode((FONTS / filename).read_bytes()).decode("ascii")
        extra = f"font-stretch:{stretch[0]};" if stretch else ""
        rules.append(f"@font-face{{font-family:'{family}';src:url(data:font/woff2;base64,{data}) format('woff2');"
                     f"font-weight:{weight};font-style:{style};{extra}font-display:block;}}")
    return "\n".join(rules)


# Streamlit chrome that no design wants on a projector: toolbar, deploy button, header bar.
CHROME_CSS = """
[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], #MainMenu, footer { display: none !important; }
[data-testid="stMainBlockContainer"] { padding-top: 0 !important; padding-bottom: 4rem !important; }
[data-testid="stFileUploaderDropzoneInstructions"] small { display: none; }
"""


def error_text(code: str) -> str:
    """Recovery advice per pipeline error code; the pipeline's own message stays alongside."""
    return {
        "audio_too_short": "Record at least half a second of singing and upload it again.",
        "audio_too_long": "Trim the recording to 60 seconds or less.",
        "silent_audio": "The recording is almost silent. Check the microphone level and record again.",
        "unsupported_audio": "Use an uncompressed PCM WAV (8–32-bit integer, mono or stereo).",
        "invalid_audio": "The file is not a readable PCM WAV. Export it again as WAV.",
        "module_failure": "An analysis step failed. Try the recording again.",
    }.get(code, "Check the recording and try again.")
