<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:f8325b3abfdefdbb7b6428bd43de70860519386df365425d0a7732113098b3cc -->

# OmniDev

A local development environment with a FastAPI/SQLite engine, a React web workbench, a Tauri desktop client, and an installed `omnidev` CLI.

[Download Artifact](https://github.com/notgamermx/OmniDev/actions/runs/42362034188/artifacts/13570233253)

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:f8b76e5890f7dd6b5b5645720aaaaf6372f4032157a44fd3ebf6b8efdd520558 -->

## Windows, gateways and personalization

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:125f8e337df73207f35d58543e1e867ff2620e33f04f45db8666f286d36acc4f -->

For Windows installation, the bundled desktop/CLI build and source startup, see [Windows guide](docs/WINDOWS.md). GitHub Actions produces an MSI installer with a Start menu shortcut and an optional portable CLI ZIP. Install the MSI, then search for OmniDev in Start. Native Windows results must be checked in that workflow.

<!-- /coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:160f930e984d61e821f2872fa47e991822de48edf06f418a425305d010b80566 -->

The workbench uses a minimal layout with no profile section and supports themes, accents, density, fonts and response preferences. **Models** includes provider key setup, live model browsing and a built-in fallback router shared by chat, agents and CLI. **Connectors** remains available for optional external gateways and command harnesses. See the [model and connector guide](docs/CONNECTORS.md).

<!-- /coderabbit-ai-generated:v1 -->

## Start from source

<!-- /coderabbit-ai-generated:v1 -->

Requires Python 3.12 and Node.js 22 or newer.

```bash
python3.12 scripts/setup.py
source .venv/bin/activate
cp .env.example .env
npm ci --prefix apps/desktop/renderer
npm --prefix apps/desktop/renderer run build
omnidev serve
```

Open **http://127.0.0.1:8000/app/**. `serve` applies migrations before startup. The API reference is at `/docs`. Windows activation: `.venv\Scripts\Activate.ps1`.

Set `PROJECT_ROOT` in `.env` to the directory the engine may edit. The default is `projects/`. File and task paths are relative to that directory. This changes the old execution behavior that accepted unrestricted caller paths.

## Connect a model

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:f1bf5598def1a461e7d532ba1174dacd01d8b6ca4d59b2b00d7532b86d858ac6 -->

Choose a provider and enter its model name in Chat or Agents. Built-in provider keys can be set in the engine's ignored `.env`. Connector keys can also be entered in the connection form: they are sent to the engine for encrypted storage and are not persisted in browser storage or returned by list APIs.

<!-- /coderabbit-ai-generated:v1 --> `omnidev providers` shows configuration status. Free tiers and quotas depend on the provider's current terms.

For local Ollama, install Ollama separately, pull a model (`ollama pull llama3.1:8b`), and run its service. The default endpoint is `http://localhost:11434/v1`. For an alternate compatible server:

```dotenv
PROVIDER_URLS={"ollama":"http://localhost:11434/v1"}
```

Chat streams responses; provider adapters retry transient failures and rate limits. Agent failover can be configured with `PROVIDER_FALLBACKS=[{"provider":"groq","model":"your-model"}]`. Every fallback needs its own credentials. Failover can send project context to those configured providers.

## Develop with an agent

1. Create a project and an agent in the workbench.
2. Select the agent's allowed tools. New agents default to read tools. Select `write_file` to edit and `git_commit` to commit.
3. Enable `TERMINAL_ENABLED=true` in `.env` and restart to allow shell commands and test execution. These commands run with the engine process's OS permissions; the engine is intended for trusted users.
4. Create a task with instructions and a verification command, for example `python -m unittest discover`.
5. Follow persisted thoughts, tool output, and verification in Tasks. A failed verification is returned to the agent for repair; completion requires the configured command to succeed. Execution is bounded by the step limit.

Files contains a UTF-8 editor with explicit Save. Terminal runs bounded commands and reports their exit status. It is a command console; shell state does not persist between commands. Conversations are saved on the engine and can be opened by desktop, web, or CLI. Session memory uses the selected conversation ID. Project memories are supplied to agents working on that project. Preferences and project understanding have REST endpoints.

## CLI

```bash
omnidev health
omnidev providers
omnidev chat --provider ollama --model llama3.1:8b --interactive
omnidev chat --session SESSION_ID "Continue our conversation"
omnidev projects create --json '{"name":"My project"}'
omnidev agents create --json '{"name":"Builder","provider":"ollama","model":"llama3.1:8b","tool_names":["think","read_file","list_files","write_file","shell"]}'
omnidev tasks create --json '{"agent_id":1,"title":"Build a calculator","description":"Create it with tests","verification_command":"python -m unittest discover"}'
omnidev tasks run 1 --path .
omnidev tasks get 1
omnidev files .
omnidev read hello.py
omnidev write hello.py --from-file ./local-hello.py
omnidev terminal "python -m unittest discover"
omnidev memory set --session SESSION_ID --key language --value Python
```

Use `omnidev --help` and `omnidev COMMAND --help`. `OMNIDEV_URL` selects another engine; `OMNIDEV_TOKEN` supplies its access token.

## Desktop

The Electron prototype has been replaced with Tauri 2 as requested. Install [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/) including Rust and your platform's native webview libraries.

```bash
npm ci --prefix apps/desktop
npm --prefix apps/desktop run dev
npm --prefix apps/desktop run build
```

Start the engine with `omnidev serve`, then open the desktop app. It uses the same engine and data as the web interface. Connection settings accept an engine URL and token. <!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:88be0668bc902ee91cc97b93e132d04a05b5e31f9549572bc2c3be83bd971569 -->

Linux packaging produces a `.deb` with the desktop UI and uses a separately started Python engine. The Windows release build bundles the engine and CLI and starts its authenticated backend automatically; see the [Windows guide](docs/WINDOWS.md).

<!-- /coderabbit-ai-generated:v1 -->

## Remote access and shared use

An engine is one trusted workspace. Its API token grants full access to that workspace. Shared conversations are shared with all clients authorized to that engine; this is not a separate identity or per-user permission system. The older shared-session service is not exposed as an authorization mechanism.

Before listening outside loopback, set a unique `API_TOKEN` with at least 32 characters. Put a TLS reverse proxy in front of remote engines and explicitly configure `ALLOWED_ORIGINS` for the browser URL. Set `ENVIRONMENT=production`, `DEBUG=false`, and a unique `SECRET_KEY` of at least 32 characters. Provider credentials stay on the engine. The Connection screen retains the API token in session storage only.

## Release and verification

```bash
python scripts/release.py
pip install dist/personal_ai_dev-1.0.0-py3-none-any.whl
omnidev serve
python -m pytest backend/tests -q
```

The release script bundles the web build, CLI, migrations, and engine into the wheel. Installed builds store data under `~/.omnidev`; `OMNIDEV_HOME` overrides it. Back up this directory and `PROJECT_ROOT` before upgrades. A server restart marks interrupted running tasks as failed so they can be reviewed instead of silently replaying tools.

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:5a3659f7843df938552fa1c48ed0b7fde2fbb20240385254447281414f0820ea -->

Python and JavaScript dependencies are independent of model access. Real cloud-provider calls require your credentials; local inference requires a running model service.

<!-- /coderabbit-ai-generated:v1 -->


<!-- /coderabbit-ai-generated:v1 -->
