# Main SUARA pipeline

Day 1 architecture and typed application contracts are available. The runnable
pipeline, preprocessing, mock modules, CLI and full tests are planned for Days 2
and 3; they are not implemented yet.

The current MVP accepts one local singing WAV and will return a structured voice
profile and ranked recommendations. Its first runtime will use real preprocessing
with explicitly synthetic mock analysis and song data. No model or cloud service
is required for the contract layer.

- [MVP scope and repository inspection](../docs/MVP_SCOPE.md)
- [Architecture and planned package layout](../docs/ARCHITECTURE.md)
- [Integration contract and JSON examples](../docs/INTEGRATION_CONTRACT.md)
- [Teammate integration guide](../docs/TEAM_INTEGRATION_GUIDE.md)

Shared source lives in `src/suara/`; experiment code remains in `../experiments/`.
Python 3.12 is the application target. From the repository root in PowerShell:

```powershell
$env:PYTHONPATH = (Resolve-Path main_pipeline/src).Path
python -c "from suara.contracts import SCHEMA_VERSION; print(SCHEMA_VERSION)"
```

This imports the dependency-free schemas. Packaging/install commands and the
`python -m suara.cli --audio ... --mode mock` command are Day 2 work and do not
work yet. Do not install the experiment dependency stacks into this package.
