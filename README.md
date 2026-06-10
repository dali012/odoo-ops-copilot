# Odoo Ops Copilot

An AI operations copilot for a live Odoo ERP. It answers natural-language business questions, grounds the answer in Odoo data, forecasts demand, and can draft human-approved writebacks such as purchase orders, reorder rules, discounts, POS pricing changes, invoice follow-ups, email campaigns, and stock transfers.

**Live demo:** _coming soon — deploying to VPS_
**Eval pass rate:** 91 % on the golden-question suite (10/11 questions, run against the seeded database)

---

![Odoo Ops Copilot — tool trace visible in right rail](docs/screenshot.png)

---

## What It Does

Ask questions like:

- "Forecast Outerwear demand next month."
- "Which products are slowest-moving over the last 90 days?"
- "Draft a purchase order for out-of-stock Outerwear."
- "Create an email campaign for customers after those items are restocked."
- "Which POS categories drove the most revenue last quarter?"

The agent chooses tools, calls Odoo or Postgres, explains the answer, and only writes to Odoo after a human approves the proposed action in the UI.

## Architecture

```text
Next.js chat UI
  |
  |  POST /chat/stream (SSE)   GET /chat/sessions/:id
  |  POST /writebacks/:id/approve|reject
  v
FastAPI agent service
  |
  |-- Anthropic Messages API tool-calling loop
  |-- Odoo XML-RPC tools for record lookup and approved writes
  |-- Guarded SQL analytics against Odoo Postgres
  |-- Forecasting with pandas + statsmodels
  |-- Postgres-backed chat memory and writeback audit log
  v
Odoo Community 18 + PostgreSQL
  ^
  |
Nginx reverse proxy (port 80/443)
```

## Highlights

- **Human-approved writeback loop:** proposal tools create pending actions; the UI exposes Approve/Reject; only approval writes to Odoo.
- **SQL guardrails:** single-statement `SELECT` only, table allowlist, read-only transaction, PostgreSQL statement timeout, and hard row cap.
- **Schema grounding:** the system prompt includes a compact Odoo schema/business glossary so SQL uses real Odoo tables and fields.
- **Durable chat memory:** same-chat context is stored in the `copilot` Postgres schema and restored after refresh.
- **Eval harness:** golden questions run against the live seeded database and report a pass rate (currently **91 %**).
- **Seeded business dataset:** catalog, 30 months of sales, purchase orders, invoices, POS sessions, and draft email campaigns.
- **Demo safety:** `DEMO_MODE=true` disables the write-back approve/reject endpoints for public deployments. A scheduled reset script re-seeds Odoo and wipes chat history every 6 hours.

## Tool Surface

Read tools:

- `odoo_query` — Odoo record lookup via XML-RPC
- `sql_analytics` — guarded SQL aggregates (SELECT-only, allowlisted tables, row cap)
- `forecast_demand` — category-level monthly demand forecast (pandas + statsmodels)

Approval-gated writeback proposal tools:

- `propose_discount_rule`
- `propose_restock_rule`
- `propose_purchase_order`
- `propose_invoice_reminder`
- `propose_price_update`
- `propose_pos_pricelist`
- `propose_email_campaign`
- `propose_transfer_stock`

## Tech Stack

- **Backend:** FastAPI, Anthropic Messages API, SQLAlchemy, pandas, statsmodels
- **ERP/data:** Odoo Community 18, PostgreSQL 16
- **Frontend:** Next.js 16, React 19, TypeScript, Recharts, react-markdown
- **Infra:** Docker Compose, Nginx
- **Quality:** Jest, Python unittest, golden-question eval harness

## Local Setup

1. Copy env files:

   ```bash
   cp .env.example .env
   cp frontend/.env.example frontend/.env.local
   ```

2. Set `ANTHROPIC_API_KEY` in `.env`.
3. Start all services:

   ```bash
   docker compose up -d db odoo
   ```

4. Open `http://localhost:8069`, create the `odoo_copilot` database, and install:
   - Sales, Inventory, Invoicing, Purchase, Point of Sale, Email Marketing

5. Seed data and start the backend:

   ```bash
   cd backend
   pip install -r requirements.txt
   python -m app.seed
   uvicorn app.main:app --reload --port 8001
   ```

6. Start the frontend:

   ```bash
   cd frontend && npm install && npm run dev
   ```

Open `http://localhost:3000`.

## VPS Deployment

The full stack runs on a single VPS behind Nginx. Copy `.env.example` to `.env`, fill in credentials, then:

1. Build and start everything:

   ```bash
   DEMO_MODE=true docker compose up -d --build
   ```

2. Schedule the demo reset (wipes chat history, re-seeds Odoo every 6 hours):

   ```bash
   chmod +x scripts/reset_demo.sh
   # Add to crontab:
   0 */6 * * * /path/to/scripts/reset_demo.sh >> /var/log/demo_reset.log 2>&1
   ```

## Useful Commands

Backend tests:

```bash
cd backend
python -m unittest test_writeback.py test_sql_guardrails.py test_session_store.py test_eval_harness.py
```

Frontend checks:

```bash
cd frontend
npm run lint && npx jest && npm run build
```

Eval harness (current pass rate: 91 %):

```bash
cd backend
python -m app.eval_harness --fail-under 0.85
```

Run one seed phase:

```bash
cd backend
python -m app.seed --phase pos
```

## Safety Model

The agent can suggest operational changes, but it does not directly write to Odoo during normal reasoning. Writeback tools only create a pending proposal in `copilot.writeback_actions`. The backend writes to Odoo only when the user clicks Approve, and each approved action is recorded with the target Odoo model and record ids.

On public deployments, set `DEMO_MODE=true` to return `403 Forbidden` on all approve/reject calls, so no visitor can mutate the demo Odoo instance.

## License

MIT — see [LICENSE](LICENSE).
