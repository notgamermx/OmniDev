<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:a486ed3755e1b6cb91444c272e45ef96cb51b95960b042652e42a4604c622bc6 -->

# OmniDev on Windows

## Install a packaged build

Windows packages are produced by the **Verify OmniDev → windows-desktop** GitHub Actions job. After pushing this source to your repository, open **Actions → Verify OmniDev → Run workflow**, then download the **OmniDev-Windows** artifact from the successful run. Extract that artifact first.

- Run `OmniDev_*_x64-setup.exe` (the exact name includes the version). The per-user NSIS installer installs the desktop app, Python engine, and CLI. It installs Microsoft WebView2 if needed, which requires internet access. Python, Node and Rust are not required for this installed app.
- Open OmniDev from the Start menu. It starts an authenticated engine on a free loopback port, waits for readiness, and closes that process tree when you exit. A second launch focuses the existing app.
- The standalone `OmniDev-Windows-CLI.zip` contains `omnidev-cli.exe` and its `_internal` folder. Keep them together. Extract to a directory you own; optionally add that directory to your user PATH.

With the desktop app open:

```powershell
.\omnidev-cli.exe health
.\omnidev-cli.exe providers
.\omnidev-cli.exe chat --provider ollama --model llama3.1:8b --interactive
```

The CLI automatically finds the desktop's local connection. To run without the desktop, use `omnidev-cli.exe serve` in one terminal and CLI commands in another. An explicitly supplied `--url`/`--token` or `OMNIDEV_URL`/`OMNIDEV_TOKEN` overrides discovery. When connecting to another engine, supply its token too.

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:6de4a8aef6e825e969f8c0043cc1d6469d31557be029a004a129a6ad88ae1c03 -->

Data, logs, encrypted connections and the SQLite database live in `%USERPROFILE%\.omnidev`. The default workspace is its `projects` folder. Edit `%USERPROFILE%\.omnidev\.env` to set `PROJECT_ROOT=C:/Users/YourName/Projects` or provider keys, then restart the app. Source installs use the repository's `.env` and `projects` folder instead. Back up the home and workspace before upgrading. If startup fails, inspect `desktop-engine.log` in that home.

<!-- /coderabbit-ai-generated:v1 -->

## Run from source now

Install Python **3.12** (with the `py` launcher) and Node.js **24**, then extract or clone the source and open PowerShell in it:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows.ps1
```

This script creates `.venv`, installs Python dependencies, builds the UI and starts the engine. Open **http://127.0.0.1:8000/app/**. Activation is not required. In another PowerShell window:

```powershell
.\.venv\Scripts\omnidev.exe health
.\.venv\Scripts\omnidev.exe chat --provider ollama --model llama3.1:8b --interactive
```

Model access requires your provider key or a running local model. In **Connectors**, add FreeLLMAPI or another compatible endpoint. See [connector instructions](CONNECTORS.md).

## Build the installer yourself

Additionally install Rust and the Windows C++ build tools described in [Tauri's Windows prerequisites](https://v2.tauri.app/start/prerequisites/#windows). From the source root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]" pyinstaller
.\.venv\Scripts\python.exe scripts/windows_bundle.py
.\.venv\Scripts\python.exe scripts/smoke_engine.py dist/windows-engine/omnidev-cli/omnidev-cli.exe
```

The NSIS installer is under `apps/desktop/src-tauri/target/release/bundle/nsis/`; the portable CLI ZIP and wheel are under `dist/`. Packages are unsigned until you configure your own signing in CI. Native Windows validation runs in CI; a build on Linux does not establish Windows runtime compatibility.

## Development source stays small

Python environments, `node_modules`, Rust `target`, bundled Python, model files, build outputs and local data are ignored by Git. Installers include runtime dependencies instead. Harnesses are separate applications: install their prerequisites and authenticate them using their official instructions. OmniDev does not bundle their accounts or model weights.


<!-- /coderabbit-ai-generated:v1 -->