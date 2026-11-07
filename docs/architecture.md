# Architecture

OmniDev is a local-first modular monolith. Interfaces and the future CLI communicate with the FastAPI API layer. API routes delegate application logic to services, which use SQLAlchemy sessions and models to access SQLite. OpenCode and model providers will be integrated through independent adapters in later phases.

Phase 1 includes the API, configuration, logging, exception foundation, database models, migrations, and health/system endpoints. It does not implement agents, external model calls, terminal execution, or file-editing tools.

Future API namespaces are reserved conceptually for `/api/v1/projects`, `/api/v1/agents`, `/api/v1/models`, `/api/v1/providers`, `/api/v1/opencode`, `/api/v1/tasks`, `/api/v1/terminal`, `/api/v1/memory`, and `/api/v1/settings`. They will be registered when their features are designed; Phase 1 intentionally has no empty placeholder routes.
