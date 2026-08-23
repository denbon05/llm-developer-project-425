# dify/apps

Secret-free Dify App DSL exports (FR-9: author in Studio, then export).

| File | Phase | Purpose |
| --- | --- | --- |
| `email_helpdesk.yml` | 5 (no-model) | Gateway-facing Workflow: User Input start, blocking `/v1/workflows/run`. Committed DSL is the architecture topology with Code/Template stubs (MCP tool nodes, IF/ELSE, stub answer/categorizer/KB, one Variable Aggregator, End `reply_text` / `ticket_id`) — not a Start→End echo. Merge-gate uses a **fake** of this contract. Phase 6 replaces Query KB with Knowledge Retrieval; Phase 7 is live Yandex. Toxicity/hello stay in the gateway. |
| *(escalate app)* | 8 | Schedule Trigger only; HTTP `POST /v1/tickets/escalate-stale`. Not authored yet. |

No provider credentials in these files. App key lives in gitignored `.env`
(`DIFY_EMAIL_HELPDESK_API_KEY`), created via Studio **API Access**.
