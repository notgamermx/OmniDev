"""Run on Windows: bundle Python and the CLI, then build a Tauri MSI installer."""

from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    if sys.platform != "win32":
        raise SystemExit(
            "Build Windows installers on Windows (or use the windows-desktop CI job)."
        )
    npm = shutil.which("npm.cmd")
    if not npm:
        raise SystemExit("Install Node.js 24 before building.")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/release.py")], cwd=ROOT, check=True
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onedir",
            "--name",
            "omnidev-cli",
            "--distpath",
            str(ROOT / "dist/windows-engine"),
            "--workpath",
            str(ROOT / "build/pyinstaller"),
            "--specpath",
            str(ROOT / "build"),
            "--paths",
            str(ROOT / "backend"),
            "--collect-all",
            "app",
            "--collect-all",
            "uvicorn",
            "--collect-all",
            "alembic",
            "--collect-all",
            "sqlalchemy",
            "--hidden-import",
            "sqlite3",
            str(ROOT / "scripts/engine_entry.py"),
        ],
        cwd=ROOT,
        check=True,
    )
    binary = ROOT / "dist/windows-engine/omnidev-cli/omnidev-cli.exe"
    subprocess.run([str(binary), "--help"], cwd=ROOT, check=True)
    # Artifact used by CI's native smoke test and usable independently of the GUI.
    shutil.make_archive(str(ROOT / "dist/OmniDev-Windows-CLI"), "zip", binary.parent)
    subprocess.run([npm, "ci", "--prefix", str(ROOT / "apps/desktop")], check=True)
    subprocess.run(
        [
            npm,
            "--prefix",
            str(ROOT / "apps/desktop"),
            "run",
            "tauri",
            "--",
            "build",
            "--config",
            "src-tauri/tauri.windows.conf.json",
        ],
        cwd=ROOT,
        check=True,
    )


if __name__ == "__main__":
    main()
