# dify/apps

Secret-free Dify App DSL exports (FR-9: author in Studio, then export).

| File | Phase | Purpose |
| --- | --- | --- |
| `email_helpdesk.yml` | 6 | Gateway-facing Workflow: User Input start, blocking `/v1/workflows/run`. Knowledge Retrieval (Weighted Score, dataset `employee-helpdesk`); answer/categorizer remain Code/Template stubs. Merge-gate uses a **fake** of this contract. Phase 7 is live Yandex. Toxicity/hello stay in the gateway. |
| *(escalate app)* | 8 | Schedule Trigger only; HTTP `POST /v1/tickets/escalate-stale`. Not authored yet. |

No provider credentials in these files. App key lives in gitignored `.env`
(`DIFY_EMAIL_HELPDESK_API_KEY`), created via Studio **API Access**.
