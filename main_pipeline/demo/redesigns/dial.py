"""SUARA FM: the demo as a valve-era radio tuner. The singer's range is the lit band on a
Hz dial and the needle rests on their median note; songs with a melody range become stations.
Runs the original demo's mock pipeline, so the band, scores and songs are labelled fixtures.

    main_pipeline/.venv/bin/python -m streamlit run main_pipeline/demo/redesigns/dial.py
"""
from __future__ import annotations

import streamlit as st

import shared
from shared import Analysis, Song, esc
from suara.contracts import PipelineError

st.set_page_config(page_title="SUARA FM", page_icon="📻", layout="wide")

FONTS = shared.font_css(("Dial", "bigshoulders-var.woff2", "700 800", "normal"),
                        ("Panel", "barlowsemicond-400.woff2", "400", "normal"),
                        ("Panel", "barlowsemicond-500.woff2", "500", "normal"),
                        ("Panel", "barlowsemicond-600.woff2", "600", "normal"))

CSS = """
:root {
  --walnut: #24160d; --walnut-hi: #33200f; --ink: #1d140c; --glass: #f6d58c; --glass-hi: #fbe8bd;
  --label: #efe2c6; --label-2: #cdb892; --rule: #4b3221; --needle: #c8281e; --amber: #ffb43c;
  --live: #5fcf7e; --brass: #c9ad7a;
}
html, body, .stApp { background: var(--walnut) !important; color: var(--label); }
.stApp, .stApp p, .stApp label, .stApp button { font-family: 'Panel', 'Arial Narrow', sans-serif; }
::selection { background: var(--amber); color: var(--ink); }
[data-testid="stMainBlockContainer"] { max-width: 1320px; padding-left: 2.5rem; padding-right: 2.5rem; }
* { scrollbar-color: var(--rule) var(--walnut); }
:focus-visible { outline: 2px solid var(--amber) !important; outline-offset: 3px; }

.fm-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 2rem;
  padding: 2.4rem 0 1.4rem; border-bottom: 1px solid var(--rule); margin-bottom: 1.6rem; }
.fm-mark { font-family: 'Dial', Impact, sans-serif; font-weight: 800; font-size: 4.6rem; line-height: .82;
  letter-spacing: .01em; color: var(--label); margin: 0; }
.fm-mark span { color: var(--amber); }
.fm-tag { font-size: 1.25rem; color: var(--label-2); margin: .55rem 0 0; max-width: 34ch; line-height: 1.3; }
.fm-lamps { display: flex; flex-wrap: wrap; gap: .7rem 1.6rem; }
.fm-lamp { white-space: nowrap; }
.fm-lamp { display: flex; align-items: center; gap: .6rem; font-weight: 600; font-size: .95rem;
  letter-spacing: .14em; text-transform: uppercase; color: var(--label-2); }
.fm-lamp i { width: 14px; height: 14px; border-radius: 50%; background: #4a3322; box-shadow: inset 0 1px 2px rgba(0,0,0,.6); }
.fm-lamp.on i { background: var(--amber); box-shadow: none; }
.fm-lamp.live i { background: var(--live); box-shadow: none; }
.fm-lamp.on, .fm-lamp.live { color: var(--label); }

.fm-dial { border-radius: 14px; padding: 14px; background: linear-gradient(180deg, #4a3020, #2b1a0f);
  box-shadow: 0 18px 40px -18px rgba(0,0,0,.8); }
.fm-dial svg { display: block; width: 100%; height: auto; border-radius: 6px; }
.fm-dial svg.compact { display: none; }
.fm-needle { animation: sweep 1.2s cubic-bezier(.16,1,.3,1) both; }
@keyframes sweep { from { transform: translateX(var(--from)); } to { transform: none; } }
.fm-caption { color: var(--label-2); font-size: 1.05rem; margin: .8rem 0 0; }
.fm-caption b { color: var(--amber); font-weight: 600; }

.fm-panel-label { font-weight: 600; font-size: .85rem; letter-spacing: .16em; text-transform: uppercase;
  color: var(--label-2); margin: 1.8rem 0 .55rem; }
.fm-panel-label span { text-transform: none; letter-spacing: 0; font-weight: 500; font-size: 1rem; margin-left: .6rem; }
[data-testid="stFileUploaderDropzone"] { background: #170e07 !important; border: 1px solid var(--rule) !important;
  border-radius: 10px !important; box-shadow: inset 0 2px 8px rgba(0,0,0,.55); padding: 1rem 1.1rem !important; }
[data-testid="stFileUploaderDropzoneInstructions"] span { color: var(--label) !important; }
[data-testid="stFileChip"] { background: #2b1b10 !important; border: 1px solid var(--rule) !important; color: var(--label) !important; }
[data-testid="stFileChip"] * { color: var(--label) !important; }
[data-testid="stFileChip"] svg, [data-testid="stBaseButton-borderlessIcon"] { color: var(--label-2) !important; }
[data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"] { background: var(--brass) !important;
  color: var(--ink) !important; border: 0 !important; border-radius: 6px !important; font-weight: 600; }
[data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"] * { color: var(--ink) !important; }
[data-testid="stFileUploaderFile"] { background: transparent !important; }
[data-testid="stFileUploader"] [data-testid="stWidgetLabel"] { display: none; }

[data-testid="stButtonGroup"] { gap: .55rem !important; }
[data-testid="stButtonGroup"] button { font-family: 'Dial', Impact, sans-serif !important; font-weight: 800;
  font-size: 1.5rem; min-width: 3.2rem; height: 3.6rem; border-radius: 6px !important; color: var(--label) !important;
  background: #3f2a1b !important; border: 1px solid #5c412c !important;
  box-shadow: 0 3px 8px -3px rgba(0,0,0,.6); transition: background-color .15s ease-out; }
[data-testid="stButtonGroup"] button:hover { background: #4d3423 !important; }
[data-testid="stButtonGroup"] button p { font-family: inherit !important; font-size: 1.5rem !important; }
[data-testid="stButtonGroup"] button[aria-checked="true"] p { color: var(--ink) !important; }
[data-testid="stButtonGroup"] button[aria-checked="true"] { color: var(--ink) !important;
  background: var(--glass) !important; border-color: var(--glass) !important; }

[data-testid="stBaseButton-primary"] { width: 100%; height: 3.6rem; border-radius: 999px !important;
  background: var(--needle) !important; border: 0 !important;
  box-shadow: 0 10px 22px -10px rgba(0,0,0,.75); transition: transform .12s ease-out, background-color .12s ease-out; }
[data-testid="stBaseButton-primary"] p { font-family: 'Dial', Impact, sans-serif !important; font-weight: 800;
  font-size: 1.6rem !important; letter-spacing: .08em; text-transform: uppercase; color: #fff4e2; }
[data-testid="stBaseButton-primary"]:hover { background: #d9352a !important; }
[data-testid="stBaseButton-primary"]:active { transform: translateY(1px); }
[data-testid="stBaseButton-primary"]:disabled { background: #5a3b2a !important; box-shadow: none; opacity: 1; }
[data-testid="stBaseButton-primary"]:disabled p { color: #a68d6c; }

.fm-h2 { font-family: 'Dial', Impact, sans-serif; font-weight: 800; font-size: 2.4rem; color: var(--label);
  margin: 3.2rem 0 .3rem; letter-spacing: .01em; }
.fm-sub { color: var(--label-2); font-size: 1.1rem; margin: 0 0 1.2rem; }
.fm-presets { list-style: none; margin: 0; padding: 0; border-top: 1px solid var(--rule); }
.fm-preset { display: grid; grid-template-columns: 4.2rem minmax(0, 1fr) 9rem 13rem; gap: 1.4rem; align-items: center;
  padding: 1.15rem 0; border-bottom: 1px solid var(--rule); }
.fm-key { font-family: 'Dial', Impact, sans-serif; font-weight: 800; font-size: 2rem; text-align: center;
  height: 3.6rem; line-height: 3.6rem; border-radius: 6px; color: var(--ink);
  background: var(--glass); box-shadow: 0 3px 8px -3px rgba(0,0,0,.6); }
.fm-preset h3 { font-family: 'Dial', Impact, sans-serif; font-weight: 700; font-size: 1.8rem; line-height: 1.05;
  margin: 0; color: var(--label); letter-spacing: .01em; }
.fm-preset h3 span { color: var(--label-2); font-size: 1.1rem; margin-right: .6rem; letter-spacing: .1em; }
.fm-preset p { margin: .3rem 0 0; color: var(--label-2); font-size: 1.05rem; line-height: 1.35; max-width: 62ch; }
.fm-span { font-family: 'Dial', Impact, sans-serif; font-weight: 700; font-size: 1.6rem; color: var(--label);
  font-variant-numeric: tabular-nums; }
.fm-span small { display: block; font-family: 'Panel', sans-serif; font-size: .9rem; font-weight: 500; color: var(--label-2); }
.fm-meter { display: flex; align-items: center; gap: .9rem; }
.fm-meter ol { display: flex; gap: 3px; list-style: none; margin: 0; padding: 0; }
.fm-meter li { width: 9px; height: 26px; border-radius: 2px; background: #3d281a; }
.fm-meter li.lit { background: var(--amber); }
.fm-meter li.lit:nth-child(n+9) { background: #ffd27a; }
.fm-meter b { font-family: 'Dial', Impact, sans-serif; font-weight: 800; font-size: 1.9rem; color: var(--label);
  font-variant-numeric: tabular-nums; }

.fm-tone { display: grid; grid-template-columns: 15rem minmax(0, 1fr); gap: 2rem; align-items: end; margin-top: 3rem;
  padding: 1.4rem 0; border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule); }
.fm-tone dt { font-weight: 600; font-size: .85rem; letter-spacing: .16em; text-transform: uppercase; color: var(--label-2); }
.fm-tone dd { margin: .3rem 0 0; font-family: 'Dial', Impact, sans-serif; font-size: 2.4rem; font-weight: 700; color: var(--label); }
.fm-tone p { margin: .4rem 0 0; color: var(--label-2); font-size: .95rem; }
.fm-eq { display: flex; align-items: flex-end; gap: 6px; height: 92px; margin-top: .6rem; }
.fm-eq span { flex: 1; background: linear-gradient(180deg, var(--amber), #b8741c); border-radius: 2px 2px 0 0; min-height: 3px; }

.fm-note { margin: 2.2rem 0 0; color: var(--label-2); font-size: 1rem; line-height: 1.45; max-width: 80ch; }
.fm-note b { color: var(--label); font-weight: 600; }
.fm-alert { margin-top: 1.4rem; padding: 1.1rem 1.3rem; border-radius: 10px; background: #3a120d; border: 1px solid #7a2a20; }
.fm-alert h3 { font-family: 'Dial', Impact, sans-serif; font-size: 1.7rem; margin: 0; color: #ffd9cf; }
.fm-alert p { margin: .3rem 0 0; color: #f0c3b8; font-size: 1.05rem; }
[data-testid="stExpander"] details { border: 1px solid var(--rule) !important; border-radius: 10px; background: #1d1209; }
[data-testid="stExpander"] summary p, [data-testid="stExpander"] p { color: var(--label-2) !important; }
@media (max-width: 760px) {
  [data-testid="stMainBlockContainer"] { padding-left: 1rem; padding-right: 1rem; }
  .fm-head { flex-direction: column; align-items: flex-start; gap: 1rem; padding-top: 1.6rem; }
  .fm-mark { font-size: 3.4rem; }
  .fm-dial svg.wide { display: none; }
  .fm-dial svg.compact { display: block; }
  .fm-dial { padding: 8px; }
  .fm-preset { grid-template-columns: 3.2rem minmax(0, 1fr); row-gap: .6rem; }
  .fm-span, .fm-meter { grid-column: 2; }
  .fm-tone { grid-template-columns: 1fr; }
}
@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
"""

AMBER = shared.DialTheme(glass=("#fdedc6", "#f4cf7d", "#d9a24a"), ink="#1d140c", ink_dim="#8a6a3f", hz_ink="#5a3b1c",
                         label="#7a1a12", band_glow="#fffaf0", band_fill="#fffdf6", needle="#c8281e",
                         display="Dial", display_weight=800, text="Panel", text_weight=600)


def dial(songs: list[Song], analysis: Analysis | None) -> str:
    caption = ""
    if analysis and analysis.voice:
        caption = ('<p class="fm-caption"><b>Mock pitch:</b> the lit band and needle are a fixed demo range and median, '
                   'not measured from your recording.</p>' if not analysis.pitch_measured else
                   f'<p class="fm-caption">The lit band is the range you sang and the needle marks your median note. '
                   f'Sung pitch in {analysis.voice.voiced_ratio:.0%} of the recording.</p>')
    svgs = "".join(shared.dial_svg(songs, analysis, layout, AMBER, "fm-needle") for layout in ("wide", "compact"))
    return f'<div class="fm-dial">{svgs}</div>{caption}'


def header(analysis: Analysis | None) -> str:
    def lamp(label: str, measured: bool) -> str:
        return f'<span class="fm-lamp {"live" if measured else "on"}"><i></i>{label} · {"measured" if measured else "mock"}</span>'
    pitch = lamp("Pitch", analysis.pitch_measured if analysis else False)
    timbre = lamp("Timbre", analysis.timbre_measured if analysis else False)
    return (f'<header class="fm-head"><div><h1 class="fm-mark">SUARA <span>FM</span></h1>'
            f'<p class="fm-tag">Tune a singing recording to the songs your voice can carry.</p></div>'
            f'<div class="fm-lamps">{pitch}{timbre}<span class="fm-lamp on"><i></i>Songs · fictional</span></div></header>')


def results(analysis: Analysis) -> str:
    out = []
    picks = analysis.recommended
    if picks:
        out.append(f'<h2 class="fm-h2">On air · {len(picks)} demo station{"s" if len(picks) != 1 else ""}</h2>'
                   f'<p class="fm-sub">{esc(analysis.caveat or "Ranked by the demo recommender.")}</p>'
                   '<ol class="fm-presets">')
        for song in picks:
            lit = round((song.score or 0) * 10)
            cells = "".join(f'<li class="{"lit" if i < lit else ""}"></li>' for i in range(10))
            out.append(f'<li class="fm-preset"><div class="fm-key" aria-hidden="true">{song.rank}</div>'
                       f'<div><h3><span>{esc(song.code)}</span>{esc(song.name)}</h3><p>{esc(song.reason or song.artist)}</p></div>'
                       f'<div class="fm-span">{esc(song.span) if song.has_range else "—"}<small>'
                       f'{"melody range" if song.has_range else "no melody range"}</small></div>'
                       f'<div class="fm-meter" aria-label="Demo score {song.score:.2f} of 1"><ol>{cells}</ol><b>{song.score:.2f}</b></div></li>')
        out.append("</ol>")
    else:
        out.append('<div class="fm-alert"><h3>No signal</h3><p>The recording had no sung pitch, so no station can be matched. '
                   'Record a few seconds of steady singing and tune in again.</p></div>')
    if analysis.mfcc and not analysis.timbre_measured:
        centroid = f"{analysis.centroid_hz:,.0f} Hz" if analysis.centroid_hz else "—"
        out.append(f'<dl class="fm-tone"><div><dt>Tone · brightness</dt><dd>{centroid}</dd></div>'
                   '<p>Mock timbre: a fixed demo value, not measured from your recording. Its 20 MFCC values are all 0, '
                   'so there is no shape to draw. Timbre is not used for ranking.</p></dl>')
    elif analysis.mfcc:
        coeffs = analysis.mfcc[1:]
        peak = max(abs(c) for c in coeffs) or 1.0
        bars = "".join(f'<span style="height:{max(4, abs(c) / peak * 100):.0f}%"></span>' for c in coeffs)
        centroid = f"{analysis.centroid_hz:,.0f} Hz" if analysis.centroid_hz else "—"
        out.append(f'<dl class="fm-tone"><div><dt>Tone · brightness</dt><dd>{centroid}</dd>'
                   f'<p>Spectral centroid, measured. Timbre is shown, not used for ranking.</p></div>'
                   f'<div><dt>Timbre shape · MFCC 2–20, relative size</dt>'
                   f'<div class="fm-eq" role="img" aria-label="Relative size of MFCC coefficients 2 to 20">{bars}</div></div></dl>')
    if analysis.seconds is not None:
        out.append(f'<p class="fm-note">Analysed in {analysis.seconds:.2f} s.</p>')
    return "".join(out)


st.html(f"<style>{FONTS}{shared.CHROME_CSS}{CSS}</style>")
head_slot, dial_slot = st.empty(), st.empty()

st.html('<p class="fm-panel-label">Input<span>a WAV of you singing, 0.5–60 seconds</span></p>')
left, middle, right = st.columns([5, 4, 3], vertical_alignment="bottom")
with left:
    audio = st.file_uploader("Recording", type=["wav"], label_visibility="collapsed")
with middle:
    st.html('<p class="fm-panel-label" style="margin-top:0">Presets<span>songs to show</span></p>')
    count = st.segmented_control("Songs to show", [1, 2, 3, 4, 5], default=5, label_visibility="collapsed") or 5
with right:
    tune = st.button("Tune in", type="primary", disabled=audio is None, width="stretch")

if audio is None:
    st.session_state.pop("fm", None)
elif tune:
    try:
        with st.spinner("Tuning…"):
            st.session_state["fm"] = shared.analyze(audio.getvalue(), count)
    except PipelineError as error:
        st.session_state["fm"] = error.error

state = st.session_state.get("fm")
analysis = state if isinstance(state, Analysis) else None
songs = analysis.songs if analysis else shared.catalog_songs()
head_slot.html(header(analysis))
dial_slot.markdown(dial(songs, analysis), unsafe_allow_html=True)  # st.html strips SVG

if analysis:
    st.html(results(analysis))
    if analysis.warnings:
        with st.expander("Analysis notes"):
            for warning in analysis.warnings:
                st.write(warning)
elif state is not None:
    st.html(f'<div class="fm-alert"><h3>Could not tune in</h3><p>{esc(shared.error_text(state.code))}</p>'
            f'<p>{esc(state.message)} ({esc(state.code)})</p></div>')
