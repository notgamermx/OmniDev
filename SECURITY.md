<!-- coderabbit-ai-generated:v1 -->

# Security

OmniDev is a development tool for trusted users of a local workspace. Engine tokens authorize workspace-wide access. Do not expose an unauthenticated engine to a network.

## Report a vulnerability

Use GitHub private vulnerability reporting when available on this repository. Otherwise ask the maintainer for a private reporting channel without posting exploit details or secrets publicly. Include the affected version, prerequisites, reproduction, and impact. No response-time guarantee is currently published.

## Execution boundaries

Agent terminal commands require Docker and fail closed without it. Containers have no network and bounded resources. File tools protect pre-existing verification inputs. These restrictions do not make untrusted projects or container runtimes risk-free. Keep provider credentials and personal secrets outside project roots.

External harness installation and execution are approved host operations with full OS account and network access. Manual file editing is trusted. Repository files and tool results are untrusted data; they do not grant execution permissions. Review source changes before committing them.

Remote access requires an API token, HTTPS reverse proxy and explicit allowed origins. Back up engine data and project files before upgrades. Installed Windows Docker isolation and package signing require independent platform verification; see the Windows guide.
