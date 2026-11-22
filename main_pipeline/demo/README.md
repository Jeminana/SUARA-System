
# SUARA Minimal Demo Interface (T13)

## Overview

This is a local Streamlit interface for the SUARA System
capstone prototype.

It allows users to upload a WAV recording, run the existing
SUARA pipeline, and view vocal profile information and
ranked song recommendations.

## Implemented Features

- WAV file upload
- Existing SUARA pipeline integration
- Minimum, maximum and median pitch display
- Voiced ratio and analysis status
- Timbre features (MFCC and spectral centroid)
- Ranked song recommendations
- Song titles, artists, scores and explanations
- Clear mock/synthetic result labels
- User-friendly pipeline error messages
- Temporary audio file cleanup

## Current Limitations

The initial interface uses the mock pipeline.

Pitch and timbre values are synthetic fixtures, not
measurements from the uploaded voice.

Recommendation scores are fixed mock rankings and do
not indicate actual singing suitability.

Real AI integration and recommendation validation are
separate project tasks.

## Requirements

- Python 3.12
- SUARA main pipeline
- Streamlit
- NumPy and SciPy (installed with the pipeline)

## Installation

From the SUARA-System repository root:

```bash
python3.12 -m venv main_pipeline/.venv
main_pipeline/.venv/bin/python -m pip install -e main_pipeline
main_pipeline/.venv/bin/python -m pip install -r main_pipeline/demo/requirements.txt
```

## Running the Interface

From the repository root:

```bash
main_pipeline/.venv/bin/python -m streamlit run main_pipeline/demo/app.py
```

Open the local URL displayed by Streamlit, normally:

http://localhost:8501

## Usage

1. Open the local SUARA interface.
2. Upload a supported WAV recording.
3. Select the number of recommendations (1–5).
4. Click Analyze My Voice.
5. View the vocal profile, timbre features and recommended songs.

## Supported Audio

- WAV files containing supported integer PCM audio
- Mono or stereo
- Source sample rates: 8,000–192,000 Hz
- Duration: 0.5–60 seconds

Not all WAV encodings are supported.

## Error Handling

The interface displays errors returned by the existing
SUARA pipeline.

Examples include:
- Invalid WAV files
- Unsupported audio formats
- Audio that is too short or too long
- Silent recordings
- Pipeline module errors

## Privacy

Uploaded files are temporarily stored for local analysis
and deleted afterward.

Do not commit private participant recordings to GitHub.

## Redesign options

Two alternative designs of this interface, running the same mock pipeline, are in
[redesigns/](redesigns/README.md).

## Scope

T13 implements the minimal local interface only.
It does not modify the existing SUARA integration contracts
or AI algorithms.
