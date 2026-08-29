# Canonical employee-helpdesk knowledge

Git is the canonical store. Weaviate is a derived index rebuilt from these
Markdown files. The Dify dataset name is `employee-helpdesk`.

Citation URLs are `{CITATION_URL_BASE}{filename}` (see `.env.example`),
built by the email gateway from End `source_filenames`. Example:
`vpn-access.md` becomes
`https://github.com/denbon05/helpdesk/blob/main/knowledge_base/vpn-access.md`
when `CITATION_URL_BASE` is that GitHub prefix. Do not invent another URL
scheme.

This directory holds trusted synthetic English pages only. Do not put
secrets, real people, or real credentials here.
