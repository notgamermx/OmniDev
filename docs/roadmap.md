<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:c8d2c42ec121369c39715c67d5e0761fa6730c9ac0e95fa0873ea951efd7a368 -->

# Implementation scope

The v1 application spans the requested eight phases: Python/FastAPI/SQLite foundation; multi-provider streaming; bounded planning/tool agent loop; scoped filesystem, Git and permissioned terminal tools with completion verification; persistent session/project memory and preferences; a React/Tauri workbench; CLI and browser interfaces sharing the engine; and wheel/Linux desktop packaging with authentication and recovery.

Cloud models need configured credentials; local models need a running provider. Desktop binaries are built on their target OS. Shared access is to a trusted engine using an instance token, not a multi-tenant user authorization service. Platform installers and provider plan terms depend on external systems.


<!-- /coderabbit-ai-generated:v1 -->