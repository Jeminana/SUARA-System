# SUARA System

Repository for the SUARA main pipeline and its nine experiments. The main pipeline is a placeholder until its design is ready; each experiment can be developed and pushed independently.

## Repository layout

- `main_pipeline/` — shared end-to-end pipeline (not implemented yet)
- `experiments/E1/` through `experiments/E9/` — experiment-specific workspaces
- `experiments/E6/` — E6 voice embedding implementation
- `SUARA_E*_Report.docx` — experiment reports

Active experiments are E1 (pitch detection), E3 (song analysis), and E6 (voice embedding). Keep experiment code and notes in that experiment's folder.

## Working together

Each contributor should work on a separate branch and push it to this repository, then open a pull request to `main` for integration. Do not commit recordings, embeddings, model downloads, virtual environments, or generated outputs; follow the E6 privacy and ignore rules in `experiments/E6/`.

To push, each contributor needs write access to the GitHub repository. A branch can be pushed with `git push -u origin <branch-name>`.
