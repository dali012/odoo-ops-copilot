import config from "@/config";

export const tiers = [
  {
    title: "Community",
    subtitle: "Self-host the full open-source edition",
    priceLabel: "Free",
    ctaText: "Get it on GitHub",
    ctaLink: config.githubUrl,
    featured: true,
    features: [
      "Full AGPL-3.0 source",
      "All analytics + write-back tools",
      "Runs on your own Odoo 18 + Postgres",
      "Golden-question eval harness",
      "Bring your own Anthropic API key",
      "Community support via GitHub issues",
    ],
  },
  {
    title: "Commercial",
    subtitle: "For teams who can't adopt AGPL terms",
    priceLabel: "Custom",
    ctaText: "Contact us",
    ctaLink: config.contactUrl,
    features: [
      "Commercial license (no AGPL copyleft)",
      "Priority support & onboarding",
      "Deployment & integration help",
      "Influence on the roadmap",
      "Everything in Community",
    ],
  },
];
