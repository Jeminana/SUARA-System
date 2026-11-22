# SUARA demo redesigns

Two alternative designs for the T13 demo interface (`../app.py`), made for the T11 examiner
demonstration. Both run exactly what `app.py` runs; only the design differs.

| App | Direction | What it draws |
| --- | --- | --- |
| `dial.py` | **SUARA FM**: a walnut radio tuner with a lit amber dial | Your range is the lit band on a Hz dial and the needle sweeps to your median note; songs are listed as numbered presets with a signal meter |
| `vinyl.py` | **Suara Records**: built on the team logo in `logo/` | The same tuning dial in the logo's colours (lavender band, purple needle) beside the controls, with the logo record spinning slowly behind the page as decoration; songs are listed as a sleeve tracklist with liner notes |

Songs with a melody range would be drawn on the dial as stations.
The demo's fictional songs have no melody range, so both designs say so on the diagram and list
the songs below it.

## Run

Install the pipeline and Streamlit as in [../README.md](../README.md), then from the repository root:

```bash
main_pipeline/.venv/bin/python -m streamlit run main_pipeline/demo/redesigns/dial.py
main_pipeline/.venv/bin/python -m streamlit run main_pipeline/demo/redesigns/vinyl.py
```

On Windows use `main_pipeline/.venv/Scripts/python.exe`.

## What they run

`shared.analyze` makes the same call as `app.py`: `run_pipeline(path, mode="mock", top_k=...)`.
That means synthetic pitch (A2–E4) and timbre, the five fictional catalog songs, and the fixed
mock ranking (scores 0.9, 0.8, ... in song ID order). Only WAV preprocessing touches the recording.
Each design labels the mock values where they appear, shows the ranker's explanation once, and
shows pipeline errors with recovery advice and no file paths.

## Files

- `shared.py`: analysis, view data, the pitch scale and the tuning dial both designs draw (with a
  colour theme per design), inlined fonts and error advice. Tested in `main_pipeline/tests/test_demo_shared.py`.
- `fonts/`: the web fonts, inlined into the page at runtime so the demo works offline. All are
  under the SIL Open Font License; the licence for each family is in `fonts/licenses/`
  (Big Shoulders Display and Barlow Semi Condensed for `dial.py`; Cormorant Garamond and Jost for `vinyl.py`).
- `assets/suara-mark-no-label.svg`: the team logo mark from `logo/`, used by `vinyl.py`. The file
  keeps its embedded C2PA provenance; the page strips that metadata only when inlining it. The
  spinning background record is that mark enlarged: it sits behind the content, ignores clicks,
  and stops spinning when the system asks for reduced motion.

## Known limits

- Streamlit's slider was replaced by a five-button control (same 1–5 choice) because its track
  cannot be restyled reliably.
- Diagrams are inline SVG rendered through `st.markdown(unsafe_allow_html=True)`, because
  `st.html` strips SVG. Only escaped catalog and pipeline text is placed in them.
- After editing `shared.py`, restart the Streamlit server; it does not always reload helper modules.
