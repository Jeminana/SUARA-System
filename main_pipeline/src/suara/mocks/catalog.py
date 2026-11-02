from suara.contracts import SongFeatures


def mock_song_catalog() -> list[SongFeatures]:
    """Five fictional records; no verified or invented melody measurements."""
    return [SongFeatures(
        song_id=f"mock-{index:03d}", title=f"Demo Song {index} (fictional)",
        artist="Mock Artist (fictional)", melody_min_pitch_hz=None, melody_max_pitch_hz=None,
        feature_version="mock-catalog-v1", provenance="mock",
        source_description="Fictional catalog fixture; no recording or verified melody range.",
    ) for index in range(1, 6)]
