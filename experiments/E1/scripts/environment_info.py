#!/usr/bin/env python3
"""Write system and Python environment information to JSON."""

from __future__ import annotations

import importlib.metadata
import argparse
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ("numpy", "scipy", "pandas", "matplotlib", "librosa", "soundfile", "crepe", "tensorflow")
TOOLS = ("python3", "pip3", "brew", "git", "ffmpeg", "sox")
INTERPRETERS = ("python3", "python3.12", "python3.13")


def command_output(*args: str) -> str | None:
    try:
        result = subprocess.run(args, check=True, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="JSON report path (defaults to outputs/environment_info.json)")
    args = parser.parse_args()
    output = args.output or ROOT / "outputs" / "environment_info.json"
    os_version = command_output("sw_vers", "-productVersion") if sys.platform == "darwin" else None
    hardware_report = command_output("system_profiler", "SPHardwareDataType") if sys.platform == "darwin" else None
    graphics_report = command_output("system_profiler", "SPDisplaysDataType") if sys.platform == "darwin" else None
    hardware_lines = (hardware_report or "").splitlines()
    hardware_values = {}
    for line in hardware_lines:
        if ":" in line:
            label, value = line.strip().split(":", 1)
            hardware_values[label] = value.strip()
    memory_text = hardware_values.get("Memory")
    memory_bytes = None
    if memory_text and "GB" in memory_text:
        try:
            memory_bytes = int(float(memory_text.split()[0]) * 1024**3)
        except ValueError:
            pass

    packages = {}
    for package in PACKAGES:
        try:
            packages[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            packages[package] = None

    python_installations = {}
    for command in INTERPRETERS:
        executable = shutil.which(command)
        if executable:
            python_installations[command] = {
                "executable": executable,
                "version": command_output(executable, "--version"),
                "pip": command_output(executable, "-m", "pip", "--version"),
            }

    report = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "os": {"system": platform.system(), "release": platform.release(), "version": os_version, "platform": platform.platform()},
        "hardware": {
            "model_name": hardware_values.get("Model Name"),
            "architecture": platform.machine(),
            "processor": hardware_values.get("Processor Name") or platform.processor() or command_output("sysctl", "-n", "machdep.cpu.brand_string"),
            "physical_cores": hardware_values.get("Total Number of Cores"),
            "logical_cpu_count": __import__("os").cpu_count(),
            "memory_bytes": memory_bytes,
            "memory_note": hardware_values.get("Memory"),
            "graphics_devices": graphics_report,
        },
        "python": {"executable": sys.executable, "version": platform.python_version(), "implementation": platform.python_implementation()},
        "python_installations": python_installations,
        "pip": command_output(sys.executable, "-m", "pip", "--version"),
        "tools": {name: shutil.which(name) for name in TOOLS},
        "packages": packages,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(output)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
