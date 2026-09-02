# dify/apps

Secret-free Dify App DSL exports (FR-9: author in Studio, then export).

| File | Phase | Purpose |
| --- | --- | --- |
| `email_helpdesk.yml` | 7 | Gateway-facing Workflow: User Input start, blocking `/v1/workflows/run`. Knowledge Retrieval (Weighted Score, dataset `employee-helpdesk`); live Yandex on the answer LLM and classifiers (intent SML then ticket/KB graph; categorizer SML). Merge-gate uses a **fake** of the Start/End contract (no paid models). |
| *(escalate app)* | 8 | Schedule Trigger only; HTTP `POST /v1/tickets/escalate-stale`. Not authored yet. |

No provider credentials in these files. App key lives in gitignored `.env`
(`DIFY_EMAIL_HELPDESK_API_KEY`), created via Studio **API Access**.
