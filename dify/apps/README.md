# dify/apps

Secret-free Dify App DSL exports (FR-9: author in Studio, then export).

| File | Purpose |
| --- | --- |
| `email_helpdesk.yml` | Gateway-facing Workflow: User Input start, blocking `/v1/workflows/run`. Knowledge Retrieval (Weighted Score, dataset `employee-helpdesk`); live Yandex on the answer LLM and classifiers (intent SML then ticket/KB graph; categorizer SML). Merge-gate uses a **fake** of the Start/End contract (no paid models). |
| `escalate_stale.yml` | Schedule Trigger (cron every minute) → HTTP `POST http://ticketing:8080/v1/tickets/escalate-stale` → parse `count` / `tickets` → IF `count` > 0, HTTP `POST http://email-gateway:8080/v1/emails/send` with `{subject, tickets}`. App env `ESCALATION_SECONDS` (30) is `older_than_seconds`. Ticketing HTTP retry: 3 × 100ms; send retry off. No digest LLM; the gateway formats the operator mail. No User Input start. Cutoff rules stay in ticketing. |

No provider credentials in these files. App key lives in gitignored `.env`
(`DIFY_EMAIL_HELPDESK_API_KEY`), created via Studio **API Access**.
