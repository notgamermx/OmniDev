"""Build the workbench and a wheel containing the engine, CLI, and migrations."""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, default=ROOT / "dist")
args = parser.parse_args()
npm = shutil.which("npm")
if not npm:
    raise SystemExit("Install Node.js and npm before building.")
subprocess.run(
    [npm, "ci", "--prefix", str(ROOT / "apps/desktop/renderer")], check=True
)
subprocess.run(
    [npm, "--prefix", str(ROOT / "apps/desktop/renderer"), "run", "build"], check=True
)
if (ROOT / "backend/app/static").exists():
    shutil.rmtree(ROOT / "backend/app/static")
shutil.copytree(
    ROOT / "apps/desktop/renderer/dist", ROOT / "backend/app/static", dirs_exist_ok=True
)
if (ROOT / "build").exists():
    shutil.rmtree(ROOT / "build")
subprocess.run(
    [
        sys.executable,
        "-m",
        "pip",
        "wheel",
        "--no-deps",
        ".",
        "-w",
        str(args.output.resolve()),
    ],
    cwd=ROOT,
    check=True,
)
