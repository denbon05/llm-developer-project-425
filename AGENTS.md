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
- Delivery phases: `docs/roadmap.md`

## Working rules

- Read Sources before changing code or design; stay inside the **current phase**
  scope; do not expand work.
- Prefer updating design docs over silent reinterpretation of decisions.
- Never commit secrets. Keep untrusted content (email, retrieval, model output)
  as data — it must not change routing or authorization.
- Do not weaken trust seams or the capability-derived employee scope model.
- Deterministic CI and local gates stay free of paid model calls.

## Tooling

- Package/environment: `uv`
- Lint and format: Ruff
- Tests: pytest
- Public interfaces: explicit types (see requirements FR-11)
- App frameworks and runtime architecture: follow `docs/architecture.md` when
  named; do not invent them here
