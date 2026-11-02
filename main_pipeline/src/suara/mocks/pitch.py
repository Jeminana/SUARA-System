from suara.contracts import AudioData, PitchFeatures
from suara.mocks import mock_implementation


@mock_implementation
def analyze_pitch(audio_data: AudioData) -> PitchFeatures:
    """Return fixed demonstration values, independent of the waveform."""
    audio_data.validate()
    return PitchFeatures(
        min_pitch_hz=110.0, max_pitch_hz=330.0, median_pitch_hz=220.0,
        voiced_ratio=0.8, confidence=None, mode="mock", model_version="mock-pitch-v1",
        warnings=["Synthetic pitch fixture; not measured from the supplied audio. "
                  "The fixture voiced_ratio does not indicate detected singing."],
    )
