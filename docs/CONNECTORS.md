<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:2ea63e5dda18fb4ebbc4f56aaf5a573d2600daff7f8b9b4718e615999955a207 -->

# Models, providers and harnesses

## Built-in model setup

Provider management and fallback routing run inside the OmniDev engine. No separate FreeLLMAPI installation or gateway process is required.

1. Open **Models & keys**, choose a provider and save your key. Cloudflare also needs an account ID. Blank key input preserves a saved key.
2. Available models load for configured providers. Refresh the catalog when needed, or enter an exact model ID if discovery is unavailable.
3. In **Chat** or **Agents**, select a configured provider and model. Unconfigured cloud providers appear only in setup. Ollama remains a local option; its service and model must be installed separately.
4. Optionally add models to the built-in router, set their fallback order, and choose **Automatic routing** in Chat. Routing becomes available when at least one enabled route has a configured provider.

OpenRouter's free filter uses catalog input/output pricing. Other providers' free-tier availability depends on your account and quotas. OmniDev includes no shared cloud key or unlimited quota.

The router tries enabled, configured routes in saved order. Rate limits place a route on a 30-second cooldown; other provider errors use a 5-second cooldown. Cooldowns reset on restart. After a stream emits an event, a failure is reported without switching providers mid-response. Tool actions are not automatically retried by the router.

### CLI setup

Create a private JSON file outside Git containing `{"api_key":"YOUR_PROVIDER_KEY"}`:

```text
omnidev models setup --provider groq --file credentials.json
omnidev models list --provider groq
omnidev chat --provider groq --model YOUR_CHOSEN_MODEL "Hello"
```

For optional automatic routing, save a private pool file:

```json
{"routes":[{"provider":"groq","model":"YOUR_CHOSEN_MODEL","enabled":true}]}
```

```text
omnidev models save-pool --file pool.json
omnidev models pool
omnidev chat --interactive
```

Remove local credential input files when no longer needed. Keys are encrypted in the engine home with a locally generated key. Existing environment keys continue to work. List responses do not return secrets. Back up the complete engine home to preserve decryptability. OS account access can expose both encrypted values and their decryption key.

## Optional gateways

Use **Connectors** for an existing OpenAI-compatible gateway such as FreeLLMAPI or LM Studio. Supply its API base URL including `/v1`, required key and default model. Remote URLs require HTTPS; HTTP is accepted on loopback. These connections are optional.

Example private gateway file:

```json
{"name":"Local gateway","base_url":"http://127.0.0.1:3001/v1","model":"auto","api_key":"YOUR_GATEWAY_KEY"}
```

```text
omnidev connectors save providers custom_local --file connection.json
omnidev connectors models providers custom_local
omnidev chat --provider custom_local --model auto "Hello"
omnidev connectors list
omnidev connectors delete providers custom_local
```

## Trusted external harnesses

A harness connector runs an installed noninteractive command and captures its output and exit code. Supply the executable and argument array from the harness's own documentation, with `{prompt}` in an argument. Use its own terminal to complete login first. Interactive protocols and streaming terminals are not adapted by this connector.

```json
{"name":"My harness","command":"python","args":["C:/Tools/my_harness.py","--prompt","{prompt}"],"install_command":[]}
```

Use a full executable path when it is not on PATH. The optional install command is a JSON array such as `["npm","install","--global","YOUR_SELECTED_PACKAGE"]`. Prerequisites must already be installed. On Windows, prefer native executables or `node`/`python` entrypoints; batch shims reject shell metacharacters in arguments.

Enable **Connection → Allow terminal and external harness execution**, or `TERMINAL_ENABLED=true`. This enables the routes; every harness install and run additionally requires approval. The UI shows the exact command and host-permission warning. Approval applies to one request and is not saved.

Harnesses run with your OS account and network access, including access outside the project root. Agent shell tools use Docker instead. Arguments are passed without constructing a shell command. Harness runs use a working directory under `PROJECT_ROOT`, time out after at most 120 seconds and retain up to `COMMAND_OUTPUT_BYTES` of output.

```text
omnidev connectors save harnesses my-harness --file harness.json
omnidev connectors install harnesses my-harness --approve-host-execution
omnidev connectors run harnesses my-harness --approve-host-execution --path . --prompt "Create and test a calculator"
```

Both `POST /api/v1/connectors/harnesses/{id}/install` and `/run` require `"approve_host_execution": true`. Missing approval returns HTTP 403 before launching a process. The run body also accepts `prompt`, `path`, and `timeout`. Engine-token holders are trusted users; agent tools cannot grant this approval.

## Appearance and chat behavior

**Settings** saves theme, blue or graphite accent, density, font, motion, response style and default chat mode on the current device. Reduced motion disables transitions and entry animations. Ask, Plan and Code supply different system instructions without granting execution permission. Use **Activity** or an explicitly approved harness to change files through an agent.

Thread search filters saved conversations. Create folder creates a workspace directory. Attach text includes up to 200 KB in the next model prompt. There is no profile section.


<!-- /coderabbit-ai-generated:v1 -->