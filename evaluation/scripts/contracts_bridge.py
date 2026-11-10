"""Load the team's exact Python contracts without importing AI dependencies.

Use --repo-root via SUARA_REPO_ROOT for live team source; otherwise load a
snapshot of contracts.py directly pasted by the user on 2026-11-09.
"""
import importlib.util
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

def load_contracts():
    repo = os.environ.get("SUARA_REPO_ROOT")
    if repo:
        path = Path(repo) / "main_pipeline" / "src" / "suara" / "contracts.py"
        if not path.is_file():
            raise FileNotFoundError(f"SUARA_REPO_ROOT did not contain {path}")
    else:
       path = ROOT.parent / "main_pipeline" / "src" / "suara" / "contracts.py"
    name = "t12_suara_contracts"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load contracts: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module, str(path)

def construct_profile(cls, data):
    pitch = cls.PitchFeatures(**data["pitch"])
    timbre = cls.TimbreFeatures(**data["timbre"])
    return cls.VoiceProfile(pitch=pitch, timbre=timbre,
        analysis_mode=data["analysis_mode"], status=data["status"],
        warnings=data["warnings"], schema_version=data["schema_version"])
