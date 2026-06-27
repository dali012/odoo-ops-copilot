# Security Policy

Odoo Ops Copilot connects a large language model to a live ERP. That is an
inherently sensitive combination, so the system is built around one core
assumption: **the model can be manipulated, and tool/data content can be
hostile.** The guardrails below exist to make that assumption safe.

## Reporting a vulnerability

Please report security issues **privately** — do not open a public GitHub issue.
Contact the maintainer via [dali012.me](https://dali012.me). We aim to
acknowledge reports within a few days. Please include reproduction steps and the
affected version/commit.

| Version | Supported |
| ------- | --------- |
| 0.1.x   | ✅        |

## Threat model

### Assets we protect

- **The live Odoo ERP data** — reading sensitive records, and especially
  *writing* to them.
- **The Anthropic API key** and other deployment secrets.
- **Availability** of the Postgres database backing Odoo.

### Trust boundaries

- **Untrusted: end-user chat input.** Anyone talking to the agent may try to
  make it do something harmful ("ignore your instructions and delete…").
- **Untrusted: data the tools return.** A product name, customer note, or order
  reference fetched from Odoo could itself contain injected instructions
  (indirect prompt injection).
- **Semi-trusted: the LLM.** It is useful but manipulable. **No security control
  in this system depends on the model behaving.** Every guarantee is enforced in
  code or by the database, below the model.

---

### Threat 1 — Prompt injection → malicious SQL

**Scenario:** a user (or injected data) convinces the model to emit
`DROP TABLE`, a multi-statement payload, a write disguised as a read, or a query
that scans the whole database.

**Defenses (defense in depth — each is independent):**

1. **Single statement, `SELECT`-only parser.** `validate_sql`
   ([backend/app/tools.py](backend/app/tools.py)) parses the statement with
   `sqlparse` and rejects anything that isn't exactly one `SELECT`. `DELETE`,
   `UPDATE`, `DROP`, and stacked `…; …` statements are refused before execution.
2. **Table allowlist.** The query's referenced tables are extracted and checked
   against an explicit `ALLOWED_SQL_TABLES` set. Anything outside the known Odoo
   business tables (e.g. `ir_config_parameter`, `res_users`,
   `information_schema`) is rejected.
3. **Read-only transaction.** Even if a malicious statement slipped past the
   parser, it executes on an engine opened with `postgresql_readonly=True` and
   inside `SET LOCAL TRANSACTION READ ONLY`. Postgres itself rejects any write.
   This is the backstop that does **not** rely on parsing being perfect.
4. **Statement timeout.** `SET LOCAL statement_timeout` (5s) caps run-away or
   deliberately expensive queries.
5. **Hard row cap.** Results are wrapped and capped (100 rows) so a query cannot
   exfiltrate or load unbounded data.

**Residual risk:** the allowlist intentionally includes business tables such as
`res_partner`, so a prompt-injected `SELECT` *can* read data within allowlisted
tables (e.g. customer names/emails). The read-only + allowlist design bounds the
blast radius to "read allowlisted business data," not "arbitrary read/write."
For public deployments this is mitigated by `DEMO_MODE` and seeded, non-real data.

### Threat 2 — Prompt injection → unauthorized writes to Odoo

**Scenario:** the model is convinced to create a purchase order, change prices,
cancel orders, or email customers without authorization.

**Defenses:**

- **The agent never writes to Odoo during reasoning.** Write-oriented tools are
  `propose_*` only — they produce a *pending* proposal, they do not mutate Odoo.
- **Human-in-the-loop approval.** A write to Odoo happens **only** when a person
  clicks Approve in the UI, which calls `execute_writeback`
  ([backend/app/writeback.py](backend/app/writeback.py)). Each approved action
  is recorded with the target Odoo model and record IDs (audit trail).
- **Atomic claim.** `execute_writeback` atomically claims a pending action before
  touching Odoo, preventing double-execution from concurrent approvals.
- **Demo lockdown.** With `DEMO_MODE=true` the approve/reject endpoints return
  `403` ([backend/app/main.py](backend/app/main.py)), so a public demo cannot be
  mutated by any visitor, regardless of what the model proposes.

### Threat 3 — Resource exhaustion / denial of service

**Defenses:** SQL statement timeout (5s), row cap (100), and a chat message
length limit (4000 chars, enforced by the request schema in
[backend/app/main.py](backend/app/main.py)).

**Residual risk:** there is **no application-level rate limiting** yet. Deploy
behind a reverse proxy / WAF that enforces request rate limits before exposing
the service publicly. (The reference deployment runs behind Nginx.)

### Threat 4 — Secret exposure

**Defenses:** secrets (`ANTHROPIC_API_KEY`, DB credentials) are read from
environment variables / `.env` (which is git-ignored), never hard-coded.
Required secrets are validated at startup ([backend/app/config.py](backend/app/config.py)).
User-facing errors are generic ("An internal error occurred.") so internal
details and stack traces are not leaked to clients.

## Out of scope

- **Answer correctness / hallucination** is a quality concern, addressed by the
  golden-question eval suite, not by this security policy.
- **Odoo's own security** (authentication, access rights) is the responsibility
  of the Odoo deployment; this project authenticates to Odoo with configured
  credentials and does not bypass Odoo's access controls.

## Reducing exposure when self-hosting

- Set `DEMO_MODE=true` for any publicly reachable deployment that should be
  read-only.
- Use a dedicated, least-privilege Postgres role; the read-only transaction is a
  backstop, not a substitute for least privilege.
- Put a rate-limiting reverse proxy / WAF in front of the service.
- Rotate the Anthropic API key if it is ever exposed.
