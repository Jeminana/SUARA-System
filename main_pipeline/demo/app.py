
from pathlib import Path
import tempfile

import streamlit as st

from suara.contracts import PipelineError
from suara.pipeline import run_pipeline


st.set_page_config(
    page_title="SUARA System",
    page_icon="🎵",
    layout="wide",
)

st.title("🎵 SUARA SYSTEM")
st.subheader("Discover songs suitable for your voice")

st.write(
    "Upload a short singing recording to view your vocal "
    "profile and recommended songs."
)

st.info(
    "Prototype mode: This version uses synthetic mock analysis. "
    "The displayed vocal values and song rankings are not "
    "measured from your recording."
)

uploaded_file = st.file_uploader(
    "Upload your singing recording",
    type=["wav"],
    help="Upload a supported PCM WAV recording between 0.5 and 60 seconds.",
)

top_k = st.slider(
    "Number of recommendations",
    min_value=1,
    max_value=5,
    value=5,
)

if st.button("Analyze My Voice", type="primary"):

    if uploaded_file is None:
        st.warning("Please upload a WAV file first.")

    else:
        temporary_path = None

        try:
            with tempfile.NamedTemporaryFile(
                suffix=".wav",
                delete=False,
            ) as temporary_file:
                temporary_file.write(uploaded_file.getbuffer())
                temporary_path = Path(temporary_file.name)

            with st.spinner("Analyzing your recording..."):
                result = run_pipeline(
                    audio_path=temporary_path,
                    mode="mock",
                    top_k=top_k,
                )

            st.success("Analysis completed!")

            if result.analysis_mode == "mock":
                st.warning(
                    "Synthetic demo results: Pitch values, "
                    "timbre features and recommendation scores "
                    "are not measured from this recording."
                )

            profile = result.voice_profile
            pitch = profile.pitch
            timbre = profile.timbre

            st.header("🎤 Your Vocal Profile")

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric(
                    "Minimum Pitch",
                    f"{pitch.min_pitch_hz:.2f} Hz"
                    if pitch.min_pitch_hz is not None else "N/A",
                )

            with col2:
                st.metric(
                    "Maximum Pitch",
                    f"{pitch.max_pitch_hz:.2f} Hz"
                    if pitch.max_pitch_hz is not None else "N/A",
                )

            with col3:
                st.metric(
                    "Median Pitch",
                    f"{pitch.median_pitch_hz:.2f} Hz"
                    if pitch.median_pitch_hz is not None else "N/A",
                )

            st.write(f"**Voice status:** {profile.status}")
            st.write(f"**Voiced ratio:** {pitch.voiced_ratio:.1%}")

            if pitch.confidence is not None:
                st.write(
                    f"**Pitch confidence:** {pitch.confidence:.2f}"
                )

            st.header("🎼 Timbre Features")

            if timbre.spectral_centroid_mean_hz is not None:
                st.metric(
                    "Spectral Centroid",
                    f"{timbre.spectral_centroid_mean_hz:.2f} Hz",
                )
            else:
                st.write("Spectral centroid: Not available")

            with st.expander("View 20 MFCC coefficients"):
                st.dataframe(
                    [
                        {
                            "Coefficient": f"MFCC {i}",
                            "Value": value,
                        }
                        for i, value in enumerate(timbre.mfcc_mean)
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

            st.header("🎶 Recommended Songs")

            if not result.recommendations:
                st.info(
                    "No song recommendations are available "
                    "for this recording."
                )

            for rank, recommendation in enumerate(
                result.recommendations,
                start=1,
            ):
                with st.container(border=True):
                    st.subheader(
                        f"{rank}. {recommendation.title}"
                    )

                    st.write(
                        f"**Artist:** {recommendation.artist}"
                    )
                    st.write(
                        f"**Match score:** {recommendation.score:.3f}"
                    )
                    st.write(
                        f"**Explanation:** {recommendation.explanation}"
                    )
                    st.caption(
                        f"Analysis mode: {recommendation.mode}"
                    )

            if profile.warnings:
                with st.expander("Analysis warnings"):
                    for warning in profile.warnings:
                        st.warning(warning)

            if result.processing_time_s is not None:
                st.caption(
                    f"Pipeline processing time: "
                    f"{result.processing_time_s:.2f} seconds"
                )

        except PipelineError as error:
            st.error(
                f"Analysis failed: {error.error.message}"
            )
            st.caption(
                f"Error code: {error.error.code} "
                f"| Stage: {error.error.stage}"
            )

        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
