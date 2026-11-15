# Later real-module connection (T10)

The metric helpers remain independent of AI modules, while the fixture tests and
sample runner load the live SUARA contracts through `scripts/contracts_bridge.py`.
The default source is this checkout's `main_pipeline/src/suara/contracts.py`;
`SUARA_REPO_ROOT` selects another checkout. No reference snapshot is shipped.
The 2026-11-15 review verified all 23 framework tests against the live schema.

T06/T07 supply the merged five-song pilot catalog and loader. Local T04/T05 work
supplies `suara.timbre.analyze_timbre` and mixed-mode tests, but has not been merged.
Real pitch and ranking still need implementation/integration. During T10, add
contract-aware evaluation that:

- Call the real `analyze_pitch(audio_data: AudioData) -> PitchFeatures` adapter on generated WAVs, after the official preprocessing route.
- Check extracted F0 statistics, voiced ratio, null behavior, metadata/version and typed validation.
- Call real `analyze_timbre(audio_data: AudioData) -> TimbreFeatures`; verify exactly the *contract-specified* MFCC convention (board indicates 20 coefficients c0–c19), finite values, model and processing version.
- Construct `VoiceProfile` and `SongFeatures` using **actual** constructors in `contracts.py`, not the illustrative JSON fields here.
- Call the real ranker (signature from approved contract), and verify stable ordering, scores, reasons and missing-data safeguards.
- Log machine, model versions, processing settings, cold/warm performance and comparison to naive baseline.

If fixtures differ from contract, update only test mapping or approve a versioned contract change; don't silently alter source schemas.
