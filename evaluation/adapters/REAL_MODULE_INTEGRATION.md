# Later real-module connection (T10)

The starter intentionally does **not** import real SUARA contracts because actual repo files were not provided. Keep the helpers independent. In the team repository, create contract-aware integration tests that:

- Call the real `analyze_pitch(audio_data: AudioData) -> PitchFeatures` adapter on generated WAVs, after the official preprocessing route.
- Check extracted F0 statistics, voiced ratio, null behavior, metadata/version and typed validation.
- Call real `analyze_timbre(audio_data: AudioData) -> TimbreFeatures`; verify exactly the *contract-specified* MFCC convention (board indicates 20 coefficients c0–c19), finite values, model and processing version.
- Construct `VoiceProfile` and `SongFeatures` using **actual** constructors in `contracts.py`, not the illustrative JSON fields here.
- Call the real ranker (signature from approved contract), and verify stable ordering, scores, reasons and missing-data safeguards.
- Log machine, model versions, processing settings, cold/warm performance and comparison to naive baseline.

If fixtures differ from contract, update only test mapping or approve a versioned contract change; don't silently alter source schemas.
