# Odoo Ops Copilot — marketing site

The public landing page for [Odoo Ops Copilot](../). It is separate from the
product: the chat app lives in [`../frontend`](../frontend), and this site's
CTAs link out to the demo/app.

Built on a Next.js 15 + Tailwind v4 template (Inter Display + DM Mono, brand
`#f17463`, light/dark via `next-themes`).

## Develop

```bash
npm install
npm run dev      # http://localhost:3000
npm run build
```

## Configure

Set these in `.env.local` when deploying:

- `NEXT_PUBLIC_APP_URL` — where the chat app / demo is hosted (the "Try the demo" CTA target). Defaults to the GitHub repo.
- `NEXT_PUBLIC_WEBSITE_URL` — canonical site URL for SEO / Open Graph tags.

## Where content lives

- Site name + links: `config/index.ts`
- Section copy: the components in `components/` (Hero, UseCases, Benefits, Proof, Security, Pricing, FAQs, CTA, HowItWorks, AgenticIntelligence)
- Pricing tiers: `constants/pricing.tsx`
- FAQs: `constants/faqs.ts`
- Theme tokens + fonts: `app/globals.css` and `fonts/`
