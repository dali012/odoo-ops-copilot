const config = {
  websiteName: "Odoo Ops Copilot — an AI operations copilot for your Odoo ERP",
  websiteUrl: process.env.NEXT_PUBLIC_WEBSITE_URL || "https://dali012.me",
  websiteDescription:
    "Odoo Ops Copilot answers natural-language business questions against a live Odoo ERP, forecasts demand, analyses margin and stockout risk, and drafts human-approved write-backs. Built on FastAPI + Anthropic Claude tool-calling with guarded SQL over Odoo Postgres.",
  // Where the actual chat app / demo lives (set in env when deployed).
  appUrl:
    process.env.NEXT_PUBLIC_APP_URL ||
    "https://github.com/dali012/odoo-ops-copilot",
  githubUrl: "https://github.com/dali012/odoo-ops-copilot",
  contactUrl: "https://dali012.me",
};

export default config;
