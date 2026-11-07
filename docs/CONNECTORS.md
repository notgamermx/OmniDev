<!-- coderabbit-ai-generated:v1 -->

# Model gateways and harness connectors

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:53c22a574c726c32467cbfa18c7e5631915e0ad97afecd645add740aac7e15b3 -->

## Built-in providers, models and routing

OmniDev includes its own provider management and model router in the Python engine. No separate FreeLLMAPI installation or gateway process is required.

1. Open **Models** from the sidebar and choose a provider. Built-in adapters cover Gemini, Groq, OpenRouter, Ollama, Mistral, Cloudflare, Cohere, NVIDIA NIM, Cerebras, Hugging Face, DeepInfra, Together, SambaNova and OpenAI.
2. Enter your provider API key and save it. Cloudflare also requires an account ID. Keys are encrypted in the engine home; existing `.env` keys continue to work. Ollama needs a separately running local model service but no cloud key.
3. Click **Load available models**, filter the live catalog, select a model and click **Add to built-in router**. Model IDs can also be entered manually if the provider cannot list them. OpenRouter's optional free filter uses the catalog's input/output pricing; other providers' free-tier availability depends on your account and quotas.
4. Add other models/providers and arrange the fallback order. Enable or disable individual entries.
5. In Chat or Agents choose **OmniDev · built-in router → Automatic**. Alternatively, choose a provider and a specific model from its dropdown. The **Models** refresh button reloads the current catalog. These controls are shared by desktop and web.

The router tries enabled, configured models in your saved order. A rate limit puts that model on a 30-second cooldown; another provider error puts it on a 5-second cooldown. Models on cooldown are skipped. If a stream has already emitted an event, OmniDev reports an interruption instead of splicing in a different response. Cooldowns are in memory and reset at engine restart. There are no bundled cloud keys or unlimited free quotas.

### CLI built-in setup

Create a private JSON file outside Git containing `{"api_key":"YOUR_PROVIDER_KEY"}` and run:

```text
omnidev models setup --provider groq --file credentials.json
omnidev models list --provider groq
```

Put the model IDs you chose into a private pool file:

```json
{"routes":[{"provider":"groq","model":"YOUR_CHOSEN_MODEL","enabled":true}]}
```

```text
omnidev models save-pool --file pool.json
omnidev models pool
omnidev chat --interactive
```

Chat defaults to the built-in router and `auto`. Direct model selection remains available with `--provider PROVIDER --model MODEL`. Remove local credential input files after setup if you do not need them.

## Optional external gateways

Existing custom connections remain supported under **Connectors**. They are optional for users who already run a compatible server, including FreeLLMAPI, LM Studio or another gateway. Enter its API base URL including `/v1`, its key if required and a default model. Remote URLs require HTTPS; HTTP is accepted on loopback. FreeLLMAPI's [API reference](https://github.com/tashfeenahmed/freellmapi/blob/main/docs/en/api/01-rest-api.md) documents its own model names and routing strategies.



<!-- /coderabbit-ai-generated:v1 -->## CLI model connection

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

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:976e54da406d044f9a58998baea20a1809c89ed63a833306bf4faa250d57d513 -->

The optional **install command** is a JSON argument array such as `["npm", "install", "--global", "YOUR_SELECTED_PACKAGE"]`; enter the actual command from the harness's official instructions. **Install** shows the exact saved command and a host-permission warning; it runs only after you confirm. Each **Run harness** also requires confirmation showing the command, arguments and working folder. Approvals apply to one request and are not saved. Node/npm, Python or other prerequisites must already be installed. Installations and harnesses have the permissions of your OS account; they are not sandboxed by the working directory.

<!-- /coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:8f9e39702434f7eba6d918734a48470f45a867486e55bf4a7a0cca8458b0561c -->

Enable **Connection → Allow terminal and external harness execution** for this engine session, or set `TERMINAL_ENABLED=true` in the engine `.env`. The default remains off. This controls the terminal, shell tool and harness routes together. Runs use a directory inside `PROJECT_ROOT`, retain up to `COMMAND_OUTPUT_BYTES` (32,000 bytes by default) of output and time out after 120 seconds. A timed-out install can be retried manually using the harness's official terminal instructions. On Windows, prefer native `.exe` or `node`/`python` entrypoints: batch shims reject shell metacharacters in arguments to prevent expansion of prompts by cmd.exe.

<!-- /coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:f3606f0f876416f3ae0de2d929a9071a56e3b37846fc02b9276db5bdeae27ecf -->

```text
omnidev connectors save harnesses my-harness --file harness.json
omnidev connectors install harnesses my-harness --approve-host-execution
omnidev connectors run harnesses my-harness --approve-host-execution --path . --prompt "Create and test a calculator"
```

<!-- /coderabbit-ai-generated:v1 -->

Harness results are shown in Connectors or the CLI. Built-in OmniDev agents use the separate Tasks view for persisted step history and verification. Harness permission prompts, streaming interactive terminals and protocol-specific monitoring remain the responsibility of the selected harness.

## Personalization

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:47ad97b6ac3865ba196e1ee6c0b3fe08b0fe48cbdcc07281c2dc3e1763b89c4d -->

Settings saves theme (light/dark/system), accent, density, font, motion, response style and default chat mode on the current device. Chat modes Ask, Plan and Code supply different system instructions; they do not grant execution permissions. Use Tasks or an explicitly run harness for development that changes files. Thread search filters saved conversations, Create folder creates a real workspace directory, and Attach text includes the file in the next model prompt (up to 200 KB). There is no profile section.

## Harness API approval

Both `POST /api/v1/connectors/harnesses/{id}/install` and `/run` require `"approve_host_execution": true` in their JSON body, in addition to `TERMINAL_ENABLED=true`. Missing or false approval returns HTTP 403 without launching a process. A run body also includes `prompt`, optional `path`, and optional `timeout` (maximum 120 seconds). This approval authorizes a privileged host operation with the current OS account's permissions, including access outside `PROJECT_ROOT` and network access. Only trusted clients should hold the engine token. Agent tools cannot grant this approval.


<!-- /coderabbit-ai-generated:v1 -->
