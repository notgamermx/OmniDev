<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:ad22e0125003580332e7d6a5ecb9c0d716e94a6d85a084837301ed2465653a49 -->

# Architecture

React runs in a browser or a Tauri webview. The CLI and both graphical interfaces call one versioned FastAPI API. Services implement agent execution, provider adapters, context, memory, project metadata and scoped tools. SQLAlchemy and Alembic persist state in SQLite. The release wheel includes the CLI, web assets and migrations.

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:7b04c01aa031cc3b1782734dc4044a7f91b1f844e8a4bd70a64251a17441fa8f -->

The server owns model credentials and the project root. Terminal execution is explicitly enabled. Instance tokens authorize trusted clients to a shared workspace. There is no per-user isolation inside an engine. Conversation IDs select persisted chat and session memory. Agent tasks run in the same engine, expose persisted step logs, and verify completion when a verification command is supplied.

## Agent execution ownership and verification

A conditional database update claims a pending task exactly once across engine instances. A failed claim starts no agent loop. Cancellation is persisted and cannot be overwritten by a late completion update. Background coroutine cancellation waits for cleanup, including coroutines cancelled before their first turn.

Agent file tools preserve the task's original verification inputs; direct write-handler calls also protect existing tests and configuration. Explicit human editor saves are separate trusted operations. External command harnesses require approval for each host operation and remain outside the Docker boundary used by agent shell commands.

A future isolated working-copy workflow would let agents edit a separate project copy, run checks there, and present a validated diff for approval before applying it to the main project. The current application does not implement this apply/merge workflow; agents still write unprotected source files in the selected project.


<!-- /coderabbit-ai-generated:v1 -->


<!-- /coderabbit-ai-generated:v1 -->