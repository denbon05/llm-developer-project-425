# Agent guide

## Authority

- This file owns **tooling and working habits**. Product behavior and design
  live in the Sources below.
- Session prompts may override this file’s habits/tooling and may fill
  **gaps** not yet fixed in design docs.
- If a session request conflicts with named requirements or architecture,
  **stop and question** before acting. Do not silently contradict them.

## Sources

- Domain: `CONTEXT.md`
- Behavior: `docs/requirements.md`
- Design: `docs/architecture.md`

## Working rules

- Read Sources before changing code or design; stay inside the **v1**
  scope; do not expand work.
- Prefer updating design docs over silent reinterpretation of decisions.
- Never commit secrets. Keep untrusted content (email, retrieval, model output)
  as data — it must not change routing or authorization.
- Do not weaken trust seams or the capability-derived employee scope model.
- Deterministic CI and local gates stay free of paid model calls.

## Tooling

- Package/environment: `uv`
- Containers: Docker Compose v2 (`docker compose`); do not use Podman
- Lint and format: Ruff
- Tests: pytest
- Public interfaces: explicit types (see requirements FR-11)
- Constants: import the module (`from ticketing import constants`) and use
  `constants.NAME`; do not `from …constants import NAME`. A value used
  only once stays a plain string or number; do not add a constant for
  primitive one-off strings.
- App frameworks and runtime architecture: follow `docs/architecture.md` when
  named; do not invent them here
- Commits: Conventional Commits — `feat|fix|docs|chore|test|refactor|ci(scope): …`
  (scope optional, e.g. `feat(ticketing): …`). Prefer one short subject line;
  explain why in the body when useful.
