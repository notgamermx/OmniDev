<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:9f718bffc434a40f5e5f293be2929e55252bc8e7b677041053647b2e34484820 -->

<!-- coderabbit-ai-generated-section:v1:a486ed3755e1b6cb91444c272e45ef96cb51b95960b042652e42a4604c622bc6 -->

# OmniDev on Windows

## Install a packaged build

Download `OmniDev-Windows-x64.msi` from [GitHub Releases](https://github.com/notgamermx/OmniDev/releases). Version-tag builds publish the MSI, CLI ZIP and Python wheel after all CI jobs pass. If there is no release yet, the repository owner must publish a version tag first. Development artifacts remain available through successful Actions runs but require GitHub sign-in and expire. Shell execution additionally requires Docker Desktop running Linux containers and the execution image described in the README.

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:adc8f305f3e31c2843608f4d87b137415a978280e9b616e2e5506d6fc1632407 -->

- Open the `.msi` Windows Installer package and follow its installation steps. It installs OmniDev as a normal application, including its engine, dependencies and Start menu shortcut. The build bundles WebView2 installation support; internet access may be required if WebView2 is missing. Users do not need Python, Node or Rust for the installed app.
- Press the Windows key, search **OmniDev**, and open it. The engine starts automatically with the app. A second launch focuses the existing window. Closing the app stops its local engine.
- Uninstall OmniDev using **Settings → Apps → Installed apps**. User data stays in `%USERPROFILE%\.omnidev` (or `OMNIDEV_HOME`), separate from installed program files.
- The optional `OmniDev-Windows-CLI.zip` is for terminal users. Extract it and keep its executable and `_internal` folder together. The desktop installer already contains the engine and CLI.

<!-- /coderabbit-ai-generated:v1 -->

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

Model access requires your provider key or a running local model. <!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:1b6f33e782db832f2965ca7828dc46628f9a26a58af47b21f3a75437f8dea5ac -->

In **Models**, set up providers, browse models and choose your fallback order. No separate model gateway is required.

<!-- /coderabbit-ai-generated:v1 --> See [connector instructions](CONNECTORS.md).

## Build the installer yourself

Additionally install Rust and the Windows C++ build tools described in [Tauri's Windows prerequisites](https://v2.tauri.app/start/prerequisites/#windows). From the source root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]" pyinstaller
.\.venv\Scripts\python.exe scripts/windows_bundle.py
.\.venv\Scripts\python.exe scripts/smoke_engine.py dist/windows-engine/omnidev-cli/omnidev-cli.exe
```

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:af8f4c9ec91e02faed6816b370c9a33667b9137f649d03a60f8744657b2b3d79 -->

The MSI installer is under `apps/desktop/src-tauri/target/release/bundle/msi/`

<!-- /coderabbit-ai-generated:v1 -->; the portable CLI ZIP and wheel are under `dist/`. Packages are unsigned until you configure your own signing in CI. Native Windows validation runs in CI; a build on Linux does not establish Windows runtime compatibility.

## Development source stays small

Python environments, `node_modules`, Rust `target`, bundled Python, model files, build outputs and local data are ignored by Git. Installers include runtime dependencies instead. Harnesses are separate applications: install their prerequisites and authenticate them using their official instructions. OmniDev does not bundle their accounts or model weights.


<!-- /coderabbit-ai-generated:v1 -->