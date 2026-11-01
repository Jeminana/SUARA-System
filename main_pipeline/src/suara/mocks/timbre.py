from suara.contracts import AudioData, MFCC_DIM, TimbreFeatures
from suara.mocks import mock_implementation


@mock_implementation
def analyze_timbre(audio_data: AudioData) -> TimbreFeatures:
    """Return a fresh vector of synthetic coefficients on every call."""
    audio_data.validate()
    return TimbreFeatures(
        mfcc_mean=[0.0] * MFCC_DIM, spectral_centroid_mean_hz=1000.0,
        mode="mock", model_version="mock-timbre-v1", processing_version="mock-mfcc-20-v1",
        warnings=["Synthetic timbre fixture; MFCCs and centroid are not measured from the supplied audio."],
    )
