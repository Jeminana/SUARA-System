from typing import Sequence

from suara.contracts import Recommendation, SongFeatures, VoiceProfile
from suara.errors import validate_top_k
from suara.mocks import mock_implementation


@mock_implementation
def recommend_songs(voice_profile: VoiceProfile, song_catalog: Sequence[SongFeatures],
                    top_k: int = 5) -> list[Recommendation]:
    """Lexical ID order with fixture scores 0.9, 0.8, ..., 0.5; no suitability rule."""
    validate_top_k(top_k)
    voice_profile.validate()
    for song in song_catalog:
        song.validate()
    return [Recommendation(
        song_id=song.song_id, title=song.title, artist=song.artist,
        score=round(0.9 - index * 0.1, 1), scoring_version="mock-fixed-v1", mode="mock",
        explanation="Synthetic demonstration rank in ascending song_id order; fixed fixture score. "
                    "No pitch/timbre suitability was measured or evaluated; melody ranges are not verified by this ranker.",
    ) for index, song in enumerate(sorted(song_catalog, key=lambda song: song.song_id)[:top_k])]
