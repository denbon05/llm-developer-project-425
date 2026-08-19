# dify/apps

Secret-free Dify App DSL exports (FR-9: author in Studio, then export).

| File | Phase | Purpose |
| --- | --- | --- |
| `email_helpdesk.yml` | 4 echo / 5 full | Gateway-facing Workflow: User Input start, blocking `/v1/workflows/run`. Committed slice is Start→End (no LLM); End emits at least `reply_text`. Gateway merge-gate uses a **fake** of this contract; live echo is opt-in. Phase 5 authors ticket/KB/MCP (toxicity/hello stay in the gateway) and re-exports. |
| *(escalate app)* | 8 | Schedule Trigger only; HTTP `POST /v1/tickets/escalate-stale`. Not authored yet. |

No provider credentials in these files. App key lives in gitignored `.env`
(`DIFY_EMAIL_HELPDESK_API_KEY`), created via Studio **API Access**.
