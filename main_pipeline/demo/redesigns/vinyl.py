"""Suara Records: the demo in the logo's world. A tuning dial in the logo's colours shows the
singer's range as a lavender band, with the logo record spinning behind the page as decoration.
Runs the original demo's mock pipeline, so the range, scores and songs are labelled fixtures.

    main_pipeline/.venv/bin/python -m streamlit run main_pipeline/demo/redesigns/vinyl.py
"""
from __future__ import annotations

import re

import streamlit as st

import shared
from shared import Analysis, Scale, Song, esc
from suara.contracts import PipelineError

st.set_page_config(page_title="Suara", page_icon="💿", layout="wide")

FONTS = shared.font_css(("Label", "cormorant-var.woff2", "500 600", "normal"),
                        ("Label", "cormorant-italic-var.woff2", "500 600", "italic"),
                        ("Sleeve", "jost-var.woff2", "400 500", "normal"))
MARK = re.sub(r"<metadata.*?</metadata>", "", (shared.HERE / "assets" / "suara-mark-no-label.svg").read_text(), flags=re.S)

CSS = """
:root {
  --deep: #400b15; --burgundy: #6e1728; --groove: #7a323b; --purple: #6f3e9d; --lavender: #cab1e8;
  --cream: #fbf0e4; --cream-2: #f3e2cf; --ink: #3a0a13; --ink-2: #6e3a44; --on-deep-2: #e2c9cf;
}
html, body, .stApp { background: var(--deep) !important; color: var(--cream); }
.stApp p, .stApp label, .stApp button, .stApp li { font-family: 'Sleeve', 'Futura', sans-serif; }
::selection { background: var(--lavender); color: var(--deep); }
:focus-visible { outline: 2px solid var(--lavender) !important; outline-offset: 3px; }
* { scrollbar-color: var(--groove) var(--deep); }
[data-testid="stMainBlockContainer"] { max-width: 1280px; padding-left: 2.5rem; padding-right: 2.5rem; }

.sr-head { display: flex; align-items: center; gap: 1.1rem; padding: 2.2rem 0 1rem; }
.sr-head svg { width: 64px; height: 64px; flex: none; }
.stApp .sr-word { font-family: 'Label', Georgia, serif !important; font-weight: 600; font-size: 3.4rem; line-height: 1; color: var(--cream);
  margin: 0 0 .3rem; letter-spacing: .01em; }
.stApp .sr-head p { margin: 0 0 0 auto; font-family: 'Label', Georgia, serif; font-style: italic; font-weight: 500;
  font-size: 1.45rem; color: var(--on-deep-2); max-width: 30ch; text-align: right; line-height: 1.35; }

/* The logo record spins behind the page as decoration: under the content, never clickable. */
[data-testid="stMain"] { position: relative; z-index: 0; }
.sr-spin { position: fixed; z-index: -1; pointer-events: none; width: min(120vh, 66vw); aspect-ratio: 1;
  left: calc(min(120vh, 66vw) * -.34); top: 50%; translate: 0 -50%; opacity: .42; animation: sr-spin 60s linear infinite; }
.sr-spin svg { display: block; width: 100%; height: 100%; }
@keyframes sr-spin { to { rotate: 360deg; } }

.sr-dial { border-radius: 14px; padding: 12px; background: var(--burgundy);
  box-shadow: 0 26px 50px -26px rgba(0,0,0,.85); }
.sr-dial svg { display: block; width: 100%; height: auto; border-radius: 6px; }
.sr-dial text { font-variant-numeric: lining-nums; }
.sr-dial svg.compact { display: none; }
.sr-needle { animation: sr-sweep 1.2s cubic-bezier(.16,1,.3,1) both; }
@keyframes sr-sweep { from { transform: translateX(var(--from)); } to { transform: none; } }
.stApp .sr-caption { color: var(--on-deep-2); font-size: 1.02rem; line-height: 1.45; margin: .9rem 0 0; }
.sr-caption b { color: var(--lavender); font-weight: 500; }

.stApp .sr-side h2 { font-family: 'Label', Georgia, serif; font-weight: 600; font-size: 2.6rem; line-height: 1.05;
  color: var(--cream); margin: 3.2rem 0 .6rem; }
.stApp .sr-side h2 em { color: var(--lavender); font-style: italic; font-weight: 500; }
.stApp .sr-side p { color: var(--on-deep-2); font-size: 1.08rem; line-height: 1.5; margin: 0 0 1.8rem; max-width: 40ch; }
.stApp .sr-side .sr-step, .stApp .sr-step { font-family: 'Label', Georgia, serif; font-style: italic; font-weight: 600; font-size: 1.35rem;
  color: var(--cream); margin: 1.4rem 0 .5rem; }
.sr-step span { color: var(--lavender); margin-right: .5rem; }

[data-testid="stFileUploader"] [data-testid="stWidgetLabel"] { display: none; }
[data-testid="stFileUploaderDropzone"] { background: rgba(251,240,228,.06) !important; border: 1px dashed var(--groove) !important;
  border-radius: 999px !important; padding: .8rem 1rem !important; }
[data-testid="stFileUploaderDropzoneInstructions"] span { color: var(--on-deep-2) !important; }
[data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"] { background: var(--cream) !important;
  border: 0 !important; border-radius: 999px !important; padding: .4rem 1.1rem !important; }
[data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"] * { color: var(--deep) !important; font-weight: 500; }
[data-testid="stFileChip"] { background: var(--burgundy) !important; border: 0 !important; border-radius: 999px !important; }
[data-testid="stFileChip"] * { color: var(--cream) !important; }
[data-testid="stBaseButton-borderlessIcon"] { color: var(--on-deep-2) !important; }

[data-testid="stButtonGroup"] [role="radiogroup"] { gap: .5rem; }
[data-testid="stButtonGroup"] button { width: 3.1rem; height: 3.1rem; border-radius: 50% !important; padding: 0 !important;
  background: transparent !important; border: 1.5px solid var(--groove) !important; color: var(--cream) !important;
  transition: background-color .2s ease-out, border-color .2s ease-out; }
[data-testid="stButtonGroup"] button p { font-family: 'Label', Georgia, serif !important; font-weight: 600; font-size: 1.35rem !important; font-variant-numeric: lining-nums; }
[data-testid="stButtonGroup"] button:hover { border-color: var(--lavender) !important; }
[data-testid="stButtonGroup"] button[aria-checked="true"] { background: var(--purple) !important; border-color: var(--lavender) !important; }

[data-testid="stBaseButton-primary"] { height: 3.6rem; margin-top: 1.6rem; border-radius: 999px !important; border: 0 !important;
  background: var(--lavender) !important; box-shadow: 0 10px 26px -12px rgba(0,0,0,.7); transition: transform .15s ease-out, background-color .15s ease-out; }
[data-testid="stBaseButton-primary"] p { font-family: 'Label', Georgia, serif !important; font-style: italic; font-weight: 600;
  font-size: 1.55rem !important; color: var(--deep); }
[data-testid="stBaseButton-primary"]:hover { background: #d8c3f0 !important; transform: translateY(-1px); }
[data-testid="stBaseButton-primary"]:disabled { background: rgba(202,177,232,.25) !important; box-shadow: none; }
[data-testid="stBaseButton-primary"]:disabled p { color: var(--on-deep-2); }

.sr-sleeve { margin-top: 3.4rem; background: var(--cream); color: var(--ink); border-radius: 6px;
  padding: 3rem 3.2rem 2.6rem; box-shadow: 0 30px 60px -30px rgba(0,0,0,.75);
  display: grid; grid-template-columns: minmax(0, 1.7fr) minmax(0, 1fr); gap: 3.2rem; }
.stApp .sr-sleeve h2 { font-family: 'Label', Georgia, serif !important; font-weight: 600; font-size: 2.4rem; margin: 0 0 .2rem; color: var(--ink); }
.stApp .sr-sleeve h2 em { font-weight: 500; color: var(--purple); }
.sr-sleeve .lede { color: var(--ink-2); font-size: 1.02rem; margin: 0 0 1.4rem; }
.sr-tracks { list-style: none; margin: 0; padding: 0; }
.sr-track { display: grid; grid-template-columns: 2.6rem minmax(0, 1fr) auto; gap: 1rem; align-items: baseline;
  padding: 1rem 0; border-top: 1px solid #e3cdb9; }
.sr-track:last-child { border-bottom: 1px solid #e3cdb9; }
.sr-track .no { font-family: 'Label', Georgia, serif; font-style: italic; font-weight: 600; font-size: 1.7rem; color: var(--purple); }
.stApp .sr-track h3 { font-family: 'Label', Georgia, serif !important; font-weight: 600; font-size: 1.75rem; line-height: 1.1; margin: 0; color: var(--ink); }
.sr-track h3 small { white-space: nowrap; font-family: 'Sleeve', sans-serif; font-weight: 500; font-size: .85rem; letter-spacing: .12em;
  color: var(--ink-2); margin-left: .6rem; vertical-align: middle; }
.sr-track p { margin: .35rem 0 0; color: var(--ink-2); font-size: 1rem; line-height: 1.45; max-width: 58ch; }
.sr-fit { text-align: right; }
.sr-fit b { display: block; font-family: 'Label', Georgia, serif; font-weight: 600; font-size: 2rem; color: var(--ink);
  font-variant-numeric: lining-nums tabular-nums; }
.sr-fit span { font-size: .85rem; color: var(--ink-2); }
.stApp .sr-notes h3 { font-family: 'Label', Georgia, serif !important; font-style: italic; font-weight: 600; font-size: 1.6rem; margin: 0 0 .6rem; padding: 0 !important; color: var(--ink); }
.sr-more { grid-column: 1 / -1; color: var(--ink-2); font-size: .92rem; }
.sr-more summary { cursor: pointer; color: var(--ink); font-family: 'Sleeve', sans-serif; font-weight: 500; list-style: none;
  display: inline-flex; align-items: center; gap: .5rem; }
.sr-more summary::-webkit-details-marker { display: none; }
.sr-more summary::before { content: ""; width: .5rem; height: .5rem; border-right: 1.5px solid var(--purple); border-bottom: 1.5px solid var(--purple);
  transform: rotate(-45deg); transition: transform .2s ease-out; }
.sr-more[open] summary::before { transform: rotate(45deg); }
.sr-more li { font-family: 'Sleeve', sans-serif; }
.sr-more ul { margin: .5rem 0 0; padding-left: 1.2rem; }
.sr-notes dl { margin: 0; }
.sr-notes div { padding: .8rem 0; border-top: 1px solid #e3cdb9; }
.sr-notes dt { font-size: .82rem; letter-spacing: .14em; text-transform: uppercase; color: var(--ink-2); }
.sr-notes dd { margin: .2rem 0 0; font-family: 'Label', Georgia, serif; font-weight: 600; font-size: 1.9rem; color: var(--ink);
  font-variant-numeric: lining-nums; }
.sr-notes dd small { font-family: 'Sleeve', sans-serif; font-weight: 400; font-size: .95rem; color: var(--ink-2); margin-left: .4rem; }
.sr-notes svg { display: block; width: 100%; height: 56px; margin-top: .4rem; }
.sr-fine { grid-column: 1 / -1; margin: 0; padding-top: 1.2rem; border-top: 1px solid #e3cdb9; font-size: .92rem;
  line-height: 1.5; color: var(--ink-2); max-width: 95ch; }
.sr-fine b { color: var(--ink); font-weight: 500; }
.sr-alert { margin-top: 2rem; padding: 1.4rem 1.6rem; border-radius: 6px; background: var(--cream); color: var(--ink); }
.stApp .sr-alert h3 { font-family: 'Label', Georgia, serif !important; font-weight: 600; font-size: 1.8rem; margin: 0; }
.sr-alert p { margin: .3rem 0 0; color: var(--ink-2); }
[data-testid="stExpander"] details { border: 1px solid var(--groove) !important; border-radius: 6px; }
[data-testid="stExpander"] p { color: var(--on-deep-2) !important; }
@media (max-width: 760px) {
  [data-testid="stMainBlockContainer"] { padding-left: 1rem; padding-right: 1rem; }
  .sr-head p { display: none; }
  .sr-spin { width: 130vw; left: -55vw; top: 40vh; opacity: .12; }
  .sr-dial { margin-top: 1rem; padding: 8px; }
  .sr-dial svg.medium { display: none; }
  .sr-dial svg.compact { display: block; }
  .sr-sleeve { grid-template-columns: 1fr; padding: 2rem 1.3rem; gap: 2rem; }
  .sr-track { grid-template-columns: 2rem minmax(0, 1fr); }
  .sr-fit { grid-column: 2; text-align: left; }
  .stApp .sr-side h2 { margin-top: 1.6rem; }
}
@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
"""

LOGO = shared.DialTheme(glass=("#fffaf4", "#fbf0e4", "#ead3bd"), ink="#3a0a13", ink_dim="#a77f86", hz_ink="#6e3a44",
                        label="#6e1728", band_glow="#cab1e8", band_fill="#e8dcf7", needle="#6f3e9d",
                        display="Label", display_weight=600, text="Sleeve", text_weight=500)


def dial(songs: list[Song], analysis: Analysis | None) -> str:
    svgs = "".join(shared.dial_svg(songs, analysis, layout, LOGO, "sr-needle") for layout in ("medium", "compact"))
    if analysis and analysis.voice:
        caption = ("<b>Mock pitch:</b> the lavender band and needle are a fixed demo range and median, not measured "
                   "from your recording." if not analysis.pitch_measured else
                   f"The lavender band is the range you sang; the needle marks your typical note.")
    else:
        caption = "Drop the needle on a recording to light up your range."
    return f'<div class="sr-dial">{svgs}</div><p class="sr-caption">{caption}</p>'


def sleeve(analysis: Analysis) -> str:
    voice = analysis.voice
    if not analysis.recommended:
        return ('<div class="sr-alert"><h3>The needle found no melody</h3><p>The recording had no sung pitch, so no track '
                'can be matched. Sing a few seconds of steady notes and drop the needle again.</p></div>')
    tracks = "".join(
        f'<li class="sr-track"><span class="no">{s.rank}</span><div><h3>{esc(s.name)}<small>{esc(s.code)} · {esc(s.span)}</small></h3>'
        f'<p>{esc(s.reason or s.artist)}</p></div><div class="sr-fit"><b>{s.score:.2f}</b>'
        f'<span>{"fit" if s.reason else "demo score"}</span></div></li>'
        for s in analysis.recommended)
    tag = lambda measured: "" if measured else " · mock"
    notes = []
    if voice:
        notes += [f'<div><dt>Your range{tag(analysis.pitch_measured)}</dt><dd>{esc(voice.span)}'
                  f'<small>{voice.low_hz:.0f}–{voice.high_hz:.0f} Hz</small></dd></div>',
                  f'<div><dt>Typical note{tag(analysis.pitch_measured)}</dt><dd>{esc(voice.median_note)}'
                  f'<small>median, {voice.median_hz:.0f} Hz</small></dd></div>']
        if analysis.pitch_measured:
            notes.append(f'<div><dt>Sung</dt><dd>{voice.voiced_ratio:.0%}<small>of the recording</small></dd></div>')
    if analysis.centroid_hz and not analysis.timbre_measured:
        notes.append(f'<div><dt>Brightness · mock</dt><dd>{analysis.centroid_hz:,.0f} Hz<small>spectral centroid</small></dd></div>')
    elif analysis.centroid_hz:
        coeffs = analysis.mfcc[1:]
        peak = max(abs(c) for c in coeffs) or 1.0
        pts = " ".join(f"{i * 300 / (len(coeffs) - 1):.1f},{28 - c / peak * 24:.1f}" for i, c in enumerate(coeffs))
        notes += [f'<div><dt>Brightness · measured</dt><dd>{analysis.centroid_hz:,.0f} Hz<small>spectral centroid</small></dd></div>',
                  f'<div><dt>Timbre shape · MFCC 2–20</dt>'
                  f'<svg viewBox="0 0 300 56" preserveAspectRatio="none" role="img" aria-label="MFCC coefficients 2 to 20, relative">'
                  f'<polyline points="{pts}" fill="none" stroke="#6f3e9d" stroke-width="2"/></svg></div>']
    mock = ("<b>Everything on this sleeve is a demo fixture.</b> The range, tone and the five fictional songs come from "
            "the mock pipeline, not from your recording. " if not analysis.pitch_measured else "")
    seconds = f" Pressed in {analysis.seconds:.2f} s." if analysis.seconds is not None else ""
    warnings = ("" if not analysis.warnings else '<details class="sr-more"><summary>Analysis notes</summary><ul>'
                + "".join(f"<li>{esc(w)}</li>" for w in analysis.warnings) + "</ul></details>")
    return (f'<section class="sr-sleeve"><div><h2>Side A · <em>your tracklist</em></h2>'
            f'<p class="lede">{esc(analysis.caveat or "Ranked by the demo recommender.")}</p>'
            f'<ol class="sr-tracks">{tracks}</ol></div>'
            f'<aside class="sr-notes"><h3>Liner notes</h3><dl>{"".join(notes)}</dl></aside>'
            f'<p class="sr-fine">{mock}Timbre is not used for ranking.{seconds}</p>'
            f'{warnings}</section>')


st.html(f"<style>{FONTS}{shared.CHROME_CSS}{CSS}</style>")
st.markdown(f'<header class="sr-head">{MARK}<h1 class="sr-word">suara</h1>'
            '<p>Sing a few seconds. See which melodies sit inside your range.</p></header>', unsafe_allow_html=True)

st.markdown(f'<div class="sr-spin" aria-hidden="true">{MARK}</div>', unsafe_allow_html=True)
disc, side = st.columns(2, gap="large", vertical_alignment="center")
with side:
    st.html('<div class="sr-side"><h2>Press your voice <em>against the catalogue</em></h2>'
            '<p>The dial is a pitch scale, low notes on the left and high on the right. Your range lights up in lavender '
            'and the needle settles on your typical note.</p>'
            '<p class="sr-step"><span>i.</span>Your recording · WAV, 0.5–60 s</p></div>')
    audio = st.file_uploader("Recording", type=["wav"], label_visibility="collapsed")
    st.html('<p class="sr-step"><span>ii.</span>Tracks to list</p>')
    count = st.segmented_control("Tracks to list", [1, 2, 3, 4, 5], default=5, label_visibility="collapsed") or 5
    play = st.button("Drop the needle", type="primary", disabled=audio is None, width="stretch")

if audio is None:
    st.session_state.pop("sr", None)
elif play:
    try:
        with st.spinner("Pressing…"):
            st.session_state["sr"] = shared.analyze(audio.getvalue(), count)
    except PipelineError as error:
        st.session_state["sr"] = error.error

state = st.session_state.get("sr")
analysis = state if isinstance(state, Analysis) else None
with disc:
    st.markdown(dial(analysis.songs if analysis else shared.catalog_songs(), analysis), unsafe_allow_html=True)

if analysis:
    st.markdown(sleeve(analysis), unsafe_allow_html=True)
elif state is not None:
    st.html(f'<div class="sr-alert"><h3>The record would not play</h3><p>{esc(shared.error_text(state.code))}</p>'
            f'<p>{esc(state.message)} ({esc(state.code)})</p></div>')
