"""Local Streamlit presentation for the SUARA mock pipeline."""

from html import escape
from pathlib import Path
import tempfile

import streamlit as st

from suara.contracts import PipelineError, PipelineResult
from suara.pipeline import run_pipeline


ANALYSIS_MODE = "mock"
MOCK_DISCLOSURE = (
    "Synthetic demonstration. Vocal values and song rankings are not "
    "measured from the uploaded recording."
)
MARK = """
<svg viewBox="0 0 36 36" fill="none" aria-hidden="true">
  <path d="M7 15v6M12.5 10v16M18 5v26M23.5 10v16M29 15v6"
        stroke="currentColor" stroke-width="2.6" stroke-linecap="round"/>
</svg>
"""
NOTE = """
<svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
  <path d="M9 17V6l11-2v11M9 17a3 2 0 1 1-6 0 3 2 0 0 1 6 0Zm11-2a3 2 0 1 1-6 0 3 2 0 0 1 6 0Z"
        stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
</svg>
"""


def render_intro() -> None:
    st.html(f"""
        <header class="suara-header">
          <div class="suara-brand">
            <span class="suara-mark">{MARK}</span>
            <div><strong>SUARA</strong><span>Your Voice. Your Sound.</span></div>
          </div>
          <span class="suara-badge">Capstone Prototype</span>
        </header>
        <section class="suara-hero">
          <div class="suara-hero-copy">
            <h1>Your voice deserves<br class="suara-desktop-break"> the right song.</h1>
            <p>Discover music that fits your observed singing range.</p>
          </div>
          <svg class="suara-wave" viewBox="0 0 560 300" fill="none"
               preserveAspectRatio="xMidYMid slice" aria-hidden="true">
            <defs>
              <linearGradient id="suara-wave-ink">
                <stop stop-color="#53D5AB" stop-opacity="0"/>
                <stop offset=".57" stop-color="#53D5AB" stop-opacity=".55"/>
                <stop offset=".82" stop-color="#7DE6C5"/>
                <stop offset="1" stop-color="#53D5AB" stop-opacity=".12"/>
              </linearGradient>
              <path id="suara-wave-curve"
                    d="M0 175C115 175 121 105 192 128S269 241 324 158 367 57 411 141 468 209 560 111"/>
            </defs>
            <g stroke="url(#suara-wave-ink)" stroke-width="1.2">
              <use href="#suara-wave-curve" transform="translate(0 -52)" opacity=".22"/>
              <use href="#suara-wave-curve" transform="translate(0 -39)" opacity=".36"/>
              <use href="#suara-wave-curve" transform="translate(0 -26)" opacity=".52"/>
              <use href="#suara-wave-curve" transform="translate(0 -13)" opacity=".72"/>
              <use href="#suara-wave-curve"/>
              <use href="#suara-wave-curve" transform="translate(0 13)" opacity=".72"/>
              <use href="#suara-wave-curve" transform="translate(0 26)" opacity=".52"/>
              <use href="#suara-wave-curve" transform="translate(0 39)" opacity=".36"/>
              <use href="#suara-wave-curve" transform="translate(0 52)" opacity=".22"/>
            </g>
          </svg>
        </section>
    """)


def clear_analysis() -> None:
    st.session_state.pop("analysis_result", None)


def analyze_recording(recording: bytes, top_k: int) -> PipelineResult:
    # A private directory owns the upload even if writing or analysis fails.
    with tempfile.TemporaryDirectory(prefix="suara-") as directory:
        audio_path = Path(directory) / "recording.wav"
        audio_path.write_bytes(recording)
        return run_pipeline(audio_path=audio_path, mode=ANALYSIS_MODE, top_k=top_k)


def render_upload() -> PipelineResult | None:
    with st.container(key="suara_upload", border=True):
        st.header("Start with your voice", anchor=False)
        st.markdown("Sing for **10–30 seconds**. Choose a quiet spot and record a short phrase.")
        uploaded_file = st.file_uploader(
            "Upload your singing recording",
            type=["wav"],
            key="suara_recording",
            on_change=clear_analysis,
        )
        st.caption("Integer PCM WAV · Mono or stereo · 8–192 kHz · 0.5–60 seconds")
        top_k = st.slider(
            "Number of recommendations", 1, 5, 5,
            key="suara_top_k", on_change=clear_analysis,
        )
        if st.button("Analyze My Voice", type="primary", width="stretch"):
            clear_analysis()
            if uploaded_file is None:
                st.warning("Please upload a WAV file first.")
            else:
                try:
                    with st.spinner("Analyzing your recording…", show_time=True):
                        st.session_state.analysis_result = analyze_recording(
                            uploaded_file.getvalue(), top_k,
                        )
                except PipelineError as error:
                    st.error(f"Analysis failed: {error.error.message}")
                    st.caption(f"Error code: {error.error.code} · Stage: {error.error.stage}")
                except OSError:
                    st.error("The app could not prepare or remove the temporary recording.")

        result = st.session_state.get("analysis_result")
        if result is not None:
            st.success("Analysis complete.")
            with st.expander("Preview your uploaded recording"):
                st.audio(uploaded_file.getvalue(), format="audio/wav")
        return result


def format_optional(value: float | None, spec: str, unit: str = "") -> str:
    return f"{value:{spec}}{unit}" if value is not None else "Unavailable"


def render_metrics(metrics: list[tuple[str, str]]) -> None:
    cards = "".join(
        f'<div class="suara-metric"><dt>{escape(label)}</dt><dd>{escape(value)}</dd></div>'
        for label, value in metrics
    )
    st.html(f'<dl class="suara-metrics">{cards}</dl>')


def render_profile(result: PipelineResult) -> None:
    profile = result.voice_profile
    pitch = profile.pitch
    status = {"ok": "OK", "warning": "Warning", "no_voiced_pitch": "No voiced pitch"}
    st.header("Your vocal profile", anchor=False)
    st.caption("Observed pitch describes a short clip and does not capture your full vocal range.")
    if profile.status == "no_voiced_pitch":
        st.warning("No voiced pitch was detected. Pitch values are unavailable.")
    render_metrics([
        ("Minimum observed pitch", format_optional(pitch.min_pitch_hz, ".2f", " Hz")),
        ("Maximum observed pitch", format_optional(pitch.max_pitch_hz, ".2f", " Hz")),
        ("Median observed pitch", format_optional(pitch.median_pitch_hz, ".2f", " Hz")),
        ("Voiced ratio", f"{pitch.voiced_ratio:.1%}"),
        ("Pitch confidence", format_optional(pitch.confidence, ".2f")),
        ("Voice profile status", status[profile.status]),
    ])
    if result.processing_time_s is not None:
        st.caption(f"Pipeline processing time · {result.processing_time_s:.2f} seconds")


def render_recommendations(result: PipelineResult) -> None:
    st.header("Recommended songs", anchor=False)
    st.caption("Ranking scores run from 0 to 1 and do not represent probabilities of vocal suitability.")
    if not result.recommendations:
        st.info("No song recommendations are available for this recording.")
        return

    for rank, song in enumerate(result.recommendations, start=1):
        provenance = "Mock ranking" if song.mode == "mock" else "Real ranking"
        st.html(f"""
            <article class="suara-song">
              <span class="suara-rank"><span class="suara-sr-only">Rank </span>{rank:02d}</span>
              <span class="suara-note">{NOTE}</span>
              <div class="suara-song-copy">
                <h3>{escape(song.title)}</h3>
                <p>{escape(song.artist)}</p>
              </div>
              <div class="suara-score">
                <span class="suara-badge">{provenance}</span>
                <label>Score <strong>{song.score:.3f} / 1</strong>
                  <meter min="0" max="1" value="{song.score}"></meter>
                </label>
              </div>
              <p class="suara-explanation">{escape(song.explanation)}</p>
            </article>
        """)


def render_timbre(result: PipelineResult) -> None:
    profile = result.voice_profile
    timbre = profile.timbre
    st.header("Timbre features", anchor=False)
    render_metrics([
        ("Spectral centroid", format_optional(timbre.spectral_centroid_mean_hz, ".2f", " Hz")),
        ("Analysis mode", "Mock · Synthetic" if result.analysis_mode == "mock" else "Real"),
    ])
    with st.expander("Technical details · 20 MFCC coefficients"):
        st.caption(f"Timbre mode: {timbre.mode} · Processing version: {timbre.processing_version}")
        st.dataframe(
            [{"Coefficient": f"c{i}", "Value": value} for i, value in enumerate(timbre.mfcc_mean)],
            width="stretch",
            hide_index=True,
        )
    if profile.warnings:
        with st.expander(f"Analysis warnings ({len(profile.warnings)})"):
            for warning in profile.warnings:
                st.warning(warning)


def main() -> None:
    st.set_page_config(page_title="SUARA System", layout="wide")
    st.html(Path(__file__).with_name("style.css"))
    render_intro()
    result = render_upload()
    if ANALYSIS_MODE == "mock" or (result is not None and result.analysis_mode == "mock"):
        st.warning(MOCK_DISCLOSURE)
    if result is not None:
        render_profile(result)
        render_recommendations(result)
        render_timbre(result)
    st.html("""
        <footer class="suara-footer">
          <strong>SUARA SYSTEM</strong> | Hanyang University ERICA Capstone Design Prototype
        </footer>
    """)


if __name__ == "__main__":
    main()
