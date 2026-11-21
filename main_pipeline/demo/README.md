# SUARA System · Capstone Prototype

SUARA is a local Streamlit demo for exploring a singing recording, vocal profile, timbre features, and ranked song recommendations. The interface uses the T13 mock pipeline.

> Synthetic demonstration. Vocal values and song rankings are not measured from the uploaded recording.

Ranking scores use a 0–1 scale and do not represent probabilities of vocal suitability. Any measured pitch range in a future integration would describe the uploaded clip only.

## Install and launch

From the repository root, use Python 3.12:

```bash
python3.12 -m venv main_pipeline/.venv
main_pipeline/.venv/bin/python -m pip install -e main_pipeline
main_pipeline/.venv/bin/python -m pip install -r main_pipeline/demo/requirements.txt
main_pipeline/.venv/bin/python -m streamlit run main_pipeline/demo/app.py
```

Open the URL printed by Streamlit, usually http://localhost:8501. On Windows, use `py -3.12` to create the environment and `main_pipeline/.venv/Scripts/python.exe` for the remaining commands.

## Use the demo

1. Upload an integer PCM WAV file. Record 10–30 seconds of singing for the demo. The pipeline accepts mono or stereo audio at 8–192 kHz, 0.5–60 seconds long.
2. Choose 1–5 recommendations and select **Analyze My Voice**.
3. Review the vocal profile and ranked songs. Open **Technical details** for all 20 MFCC coefficients and **Analysis warnings** for pipeline warnings.
4. Open **Preview your uploaded recording** to hear the original WAV after successful analysis. Playback depends on which WAV encodings your browser supports.

Changing the WAV or recommendation count clears the previous result. The pipeline validates malformed or unsupported WAV files, silence, and duration limits. The app displays the pipeline's public error message, code, and stage.

The demo uses a private temporary directory for processing and deletes it when the analysis attempt ends. The uploaded recording remains available in the active browser session for preview. Keep private participant recordings out of Git.

For the separate measured CLI workflow, see the [main pipeline guide](../README.md#real-pipeline-t09).
