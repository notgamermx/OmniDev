<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:500d56ef9df0f417176764209689c16382650ccd5ba0536fd68bb6a8f187ba92 -->

<!-- coderabbit-ai-generated-section:v1:062aaf58160308722e216a944279c39e53111862ef13fe767687ceda310deb97 -->

# API

Run `omnidev serve` and open `/docs` for request/response schemas. API paths start with `/api/v1`. Remote clients send `Authorization: Bearer <API_TOKEN>`.

| Namespace | Purpose |
| --- | --- |
| `/chat/providers/` | Provider catalog and credential status |
| `/chat/completions/`, `/chat/completions/stream` | JSON and SSE chat |
| `/projects/`, `/workspaces/` | Project metadata |
| `/agents/` | Agent definitions and assigned tools |
| `/tasks/` | Tasks, synchronous execution, background run, streaming, cancellation and steps |
| `/sessions` | Persisted conversations shared by clients |
| `/omnimode/run` | Parallel specialist completions followed by an independent reviewer and synthesis |
| `/files`, `/file` | Scoped directory listing and UTF-8 reads/writes |
| `/files/import`, `/file/base64` | Bounded binary imports and authenticated asset previews/downloads |
| `/terminal` | Permissioned bounded command execution |
| `/memory` | Session/project memory, preferences, recall and understanding |
| `/workspace`, `/dashboard` | Workspace capabilities and status |

`POST /tasks/{id}/execute` and `/run` accept `{ "project_root": "." }` relative to the configured root. Task creation accepts `verification_command`. Session memory list/get/delete accept a `session_id` query; writes accept it in the JSON body.


<!-- /coderabbit-ai-generated:v1 -->

## Task lifecycle controls

`POST /tasks/{id}/run` atomically queues pending work. Only one worker can claim it. `POST /tasks/{id}/pause` accepts `{"paused":true}` to pause after the current operation, and `{"paused":false}` to resume the existing worker. Invalid pause/resume states return HTTP 409. `DELETE /tasks/{id}` cancels execution; it does not delete history. Task deletion uses `DELETE /tasks/` with the task ID as the JSON body.

Task detail includes the selected model, planning step count, conservative token-budget reservations and persisted execution steps. State transitions appear as `kind="state"` steps. Interrupted queued/running/verifying/paused tasks fail on restart with an audit event; side effects are not replayed automatically.


<!-- /coderabbit-ai-generated:v1 -->