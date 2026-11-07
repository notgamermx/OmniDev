<!-- coderabbit-ai-generated:v1 -->

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
| `/files`, `/file` | Scoped directory listing and UTF-8 reads/writes |
| `/terminal` | Permissioned bounded command execution |
| `/memory` | Session/project memory, preferences, recall and understanding |
| `/workspace`, `/dashboard` | Workspace capabilities and status |

`POST /tasks/{id}/execute` and `/run` accept `{ "project_root": "." }` relative to the configured root. Task creation accepts `verification_command`. Session memory list/get/delete accept a `session_id` query; writes accept it in the JSON body.


<!-- /coderabbit-ai-generated:v1 -->