<!-- coderabbit-ai-generated:v1 -->

# Changelog

## 1.0.4 — 2026-11-08

- Replace the orbital illustration and sparkle navigation with a geometric logo, line icons and neutral surfaces.
- Remove green/purple theme tints; add restrained interaction motion with reduced-motion support.
- Show configured providers in Chat and automatically load models after setup.
- Normalize engine addresses and explain network, authentication and proxy failures.
- Add Activity history, verification status, permission details, budget reservation display, pause and resume.
- Protect task-service startup races, validate state transitions and interrupt in-flight operations on cancellation.
- Mark interrupted work failed on restart without replaying tools.
- Centralize version synchronization around pyproject.toml, add frontend tests, coverage and dependency-audit CI.
- Remove unused predecessor provider adapters and generated Tauri schemas from Git.

Windows MSI/Docker validation and package signing remain pending for this source version.

## 1.0.3

Atomic task claiming, cancellation cleanup, verification-file write protection, explicit approval for host harness commands, and an installed-Windows Docker verification workflow.
