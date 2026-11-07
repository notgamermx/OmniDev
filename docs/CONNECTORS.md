<!-- coderabbit-ai-generated:v1 -->

# Model gateways and harness connectors

## FreeLLMAPI

Install and start [FreeLLMAPI](https://github.com/tashfeenahmed/freellmapi) separately using its official Windows installer or deployment instructions. Add the provider keys you want in its dashboard and create a unified key there. Its [API documentation](https://github.com/tashfeenahmed/freellmapi/blob/main/docs/en/api/01-rest-api.md) defines the OpenAI-compatible `/v1/chat/completions` and `/v1/models` interfaces used here.

In OmniDev **Connectors → Model connection**, select FreeLLMAPI and save:

- ID: `custom_freellmapi`
- API base URL: `http://127.0.0.1:3001/v1` (or your actual server URL)
- API key: the gateway's unified key
- Model: `auto`, a catalog model ID, or a documented routing strategy such as `auto:fast`

Choose that connection in Chat or Agents. **Discover models** / **Models** loads the live gateway catalog. Streaming, retry handling, and the agent execution loop use the existing shared adapter. Free quotas and provider availability are controlled by your gateway and provider accounts.

Any OpenAI-compatible chat server can use the same form: LM Studio, llama.cpp, a proxy or your own gateway. Use the base URL including `/v1`, without `/chat/completions`. Remote connections require HTTPS; HTTP is allowed on loopback. Native provider adapters remain available through `.env`.

## CLI model connection

Save this JSON to a local private file outside your Git checkout:

```json
{"name":"FreeLLMAPI","base_url":"http://127.0.0.1:3001/v1","model":"auto","api_key":"YOUR_UNIFIED_KEY"}
```

```text
omnidev connectors save providers custom_freellmapi --file connection.json
omnidev connectors models providers custom_freellmapi
omnidev chat --provider custom_freellmapi --model auto "Hello"
omnidev connectors list
omnidev connectors delete providers custom_freellmapi
```

Saved connector definitions are encrypted using a locally generated Fernet key in the engine home. OS account permissions protect the key. List responses never return API keys. Blank key input preserves an existing key; delete the connection to remove it. Back up the complete engine home to preserve decryptability. These protections do not defend against someone with access to your OS account.

## Bring your own harness

A harness connector launches an installed noninteractive command and captures its output and exit code. It is a command adapter, not an implementation of every harness's interactive protocol. Supply the exact executable and argument array documented by your harness. Include `{prompt}` in an argument. Arguments are passed directly without assembling a shell command.

For example, a custom Python harness could be:

```json
{"name":"My harness","command":"python","args":["C:/Tools/my_harness.py","--prompt","{prompt}"],"install_command":[]}
```

Use a full executable path when it is not on PATH. You can register any installed harness that supports a noninteractive task argument, including a locally installed coding CLI. OmniDev does not modify its configuration or bypass its login flow. Use its own terminal to log in first.

The optional **install command** is a JSON argument array such as `["npm", "install", "--global", "YOUR_SELECTED_PACKAGE"]`; enter the actual command from the harness's official instructions. **Install** runs it only when you click it. Node/npm, Python or other prerequisites must already be installed. Installations and harnesses have the permissions of your OS account; they are not sandboxed by the working directory.

Enable **Connection → Allow terminal and external harness execution** for this engine session, or set `TERMINAL_ENABLED=true` in the engine `.env`. The default remains off. This controls the terminal, shell tool and harness routes together. Runs use a directory inside `PROJECT_ROOT`, retain up to 1 MB of output and time out after 120 seconds. A timed-out install can be retried manually using the harness's official terminal instructions. On Windows, prefer native `.exe` or `node`/`python` entrypoints: batch shims reject shell metacharacters in arguments to prevent expansion of prompts by cmd.exe.

```text
omnidev connectors save harnesses my-harness --file harness.json
omnidev connectors install harnesses my-harness
omnidev connectors run harnesses my-harness --path . --prompt "Create and test a calculator"
```

Harness results are shown in Connectors or the CLI. Built-in OmniDev agents use the separate Tasks view for persisted step history and verification. Harness permission prompts, streaming interactive terminals and protocol-specific monitoring remain the responsibility of the selected harness.

## Personalization

Settings saves theme (light/dark/system), accent, density, font, motion, response style and default chat mode on the current device. Chat modes Ask, Plan and Code supply different system instructions; they do not grant execution permissions. Use Tasks or an explicitly run harness for development that changes files. Thread search filters saved conversations, Create folder creates a real workspace directory, and Attach text includes the file in the next model prompt (up to 200 KB). There is no profile section.
