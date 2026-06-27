export const faqs = [
  {
    question: "What is Odoo Ops Copilot?",
    answer:
      "An AI operations copilot for a live Odoo ERP. You ask business questions in plain language — forecasts, margins, stockout risk, customer segments — and it answers from your real Odoo data, then drafts operational changes (purchase orders, price updates, campaigns) that only execute after you approve them.",
  },
  {
    question: "Is it open source?",
    answer:
      "Yes. The full project is licensed under AGPL-3.0, so you can read, run, and self-host it. A separate commercial license is available for teams that can't adopt AGPL's network-copyleft terms.",
  },
  {
    question: "How does it write to my Odoo safely?",
    answer:
      "It never writes during normal reasoning. Write-back tools only create a pending proposal; the backend writes to Odoo solely when a human clicks Approve in the UI, and every approved action is recorded with the target Odoo model and record IDs.",
  },
  {
    question: "Can I trust the SQL the agent runs?",
    answer:
      "Analytics run as a single read-only SELECT against an allowlist of Odoo tables, inside a read-only Postgres transaction, with a statement timeout and a hard row cap. Even a prompt-injected query can't write, scan arbitrary tables, or run unbounded. See the threat model in SECURITY.md.",
  },
  {
    question: "How do I know the answers are accurate?",
    answer:
      "A golden-question eval suite runs the real agent against a freshly seeded database — currently 12/12 passing, nightly in CI. The demand forecast is validated by a holdout backtest (about 13% MAPE), so 'forecasting is real' is a measured claim, not a slogan.",
  },
  {
    question: "What does it run on?",
    answer:
      "Odoo Community 18 + PostgreSQL, a FastAPI agent service using the Anthropic Claude Messages API tool-calling loop, and a Next.js chat UI. You bring your own Anthropic API key. The whole stack runs on a single VPS behind Nginx via Docker Compose.",
  },
];
