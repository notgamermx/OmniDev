"""Create the project virtual environment and install development dependencies."""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
venv_python = VENV / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
subprocess.run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], check=True)
subprocess.run([str(venv_python), "-m", "pip", "install", "-e", ".[dev]"], cwd=ROOT, check=True)
print(f"Environment ready. Activate it with: {VENV / ('Scripts/Activate.ps1' if sys.platform == 'win32' else 'bin/activate')}")
