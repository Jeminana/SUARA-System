# Configuration

`e1_synthetic_tones.json` is the reproducible Phase 4A synthetic tone specification. It selects C2, E2, and G2; C3, E3, and G3; C4, E4, and G4; and C5, E5, and C6. These notes sample low, middle, and high registers with broad octave coverage, include the C2/C6 boundaries, and use familiar major-triad intervals through most of the range. Their frequencies follow equal temperament with A4=440 Hz.

The set intentionally provides broad register and pitch-class coverage rather than exhaustive pitch coverage. No random component or seed is used. The configuration records the frequency values and synthesis parameters used by `scripts/generate_e1_synthetic.py`. No separate original E1 specification document was present in the project when this set was prepared; selection therefore follows the stated shared C2–C6 region and project 16 kHz/10 ms conventions.
