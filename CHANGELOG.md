# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-06-26

First public release of Odoo Ops Copilot — an AI operations copilot for a live
Odoo Community 18 ERP.

### Added

- **Agent service (FastAPI + Anthropic Messages API):** tool-calling loop that
  answers natural-language business questions and grounds answers in live Odoo
  data, with Postgres-backed durable chat memory.
- **Read-only analytics tools:** `odoo_query`, `sql_analytics`, `search_partners`,
  `forecast_demand` (seasonal exponential smoothing via statsmodels),
  `simulate_discount_impact`, `compare_periods`, `stockout_risk`,
  `inventory_aging`, `margin_analysis`, `supplier_scorecard`, and `customer_rfm`.
- **Human-approved write-back loop:** eleven `propose_*` tools create pending
  actions (purchase orders, reorder rules, discounts, price/POS updates, vendor
  price corrections, inventory adjustments, sale-order cancellations, invoice
  follow-ups, email campaigns, stock transfers). Nothing writes to Odoo until a
  human clicks Approve in the UI.
- **SQL guardrails:** single-statement `SELECT` only, table allowlist, read-only
  transaction, statement timeout, and hard row cap.
- **Schema grounding:** compact Odoo schema/business glossary in the system
  prompt so generated SQL uses real Odoo tables and fields.
- **Next.js 16 chat UI:** SSE streaming, session history, and Approve/Reject
  controls for proposed write-backs.
- **Seeded business dataset:** catalog, 30 months of sales, purchase orders,
  invoices, POS sessions, and draft email campaigns.
- **Eval harness:** 12 golden questions covering all major analytics tools, run
  against the seeded database — currently 100% pass rate.
- **Demo safety:** `DEMO_MODE=true` disables approve/reject endpoints for public
  deployments, plus a scheduled reset script that re-seeds Odoo and wipes chat
  history every 6 hours.
- **Deployment:** single-VPS Docker Compose stack behind an Nginx reverse proxy.

[0.1.0]: https://github.com/dali012/odoo-ops-copilot/releases/tag/v0.1.0
