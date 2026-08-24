# Canonical employee-helpdesk knowledge

Git is the canonical store. Weaviate is a derived index rebuilt from these
Markdown files. The Dify dataset name will be `employee-helpdesk`.

Citation URLs are `{CITATION_REPO_BASE}{filename}` (see `.env.example`).
Example: `vpn-access.md` becomes
`https://github.com/denbon05/helpdesk/blob/main/knowledge_base/vpn-access.md`
when `CITATION_REPO_BASE` is that GitHub prefix. Do not invent another URL
scheme.

This directory holds trusted synthetic English pages only. Do not put
secrets, real people, or real credentials here.
