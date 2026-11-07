<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:ad22e0125003580332e7d6a5ecb9c0d716e94a6d85a084837301ed2465653a49 -->

# Architecture

React runs in a browser or a Tauri webview. The CLI and both graphical interfaces call one versioned FastAPI API. Services implement agent execution, provider adapters, context, memory, project metadata and scoped tools. SQLAlchemy and Alembic persist state in SQLite. The release wheel includes the CLI, web assets and migrations.

The server owns model credentials and the project root. Terminal execution is explicitly enabled. Instance tokens authorize trusted clients to a shared workspace. There is no per-user isolation inside an engine. Conversation IDs select persisted chat and session memory. Agent tasks run in the same engine, expose persisted step logs, and verify completion when a verification command is supplied.


<!-- /coderabbit-ai-generated:v1 -->