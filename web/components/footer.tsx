import Link from "next/link";
import { Button } from "./button";
import { Container } from "./container";
import { Logo } from "./logo";
import { SubHeading } from "./subheading";
import config from "@/config";

export const Footer = () => {
  const resources = [
    { title: "Live demo", href: config.appUrl },
    { title: "GitHub", href: config.githubUrl },
    { title: "Security policy", href: `${config.githubUrl}/blob/main/SECURITY.md` },
    { title: "Changelog", href: `${config.githubUrl}/blob/main/CHANGELOG.md` },
    {
      title: "Contributing",
      href: `${config.githubUrl}/blob/main/CONTRIBUTING.md`,
    },
  ];

  const project = [
    { title: "How it works", href: "#how-it-works" },
    { title: "Use cases", href: "#use-cases" },
    { title: "Security", href: "#security" },
    { title: "Pricing", href: "#pricing" },
  ];

  const legal = [
    { title: "License (AGPL-3.0)", href: `${config.githubUrl}/blob/main/LICENSE` },
    { title: "Threat model", href: `${config.githubUrl}/blob/main/SECURITY.md` },
    { title: "Contributor CLA", href: `${config.githubUrl}/blob/main/CLA.md` },
  ];

  return (
    <Container>
      <div className="grid grid-cols-1 px-4 py-20 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-8">
        <div className="mb-6 sm:col-span-2 md:col-span-4 lg:col-span-3">
          <Logo />
          <SubHeading as="p" className="mt-4 max-w-sm text-left">
            An AI operations copilot for a live Odoo ERP — grounded answers and
            human-approved write-backs.
          </SubHeading>
          <Button
            as={Link}
            href={config.appUrl}
            className="mt-4 mb-8 lg:mb-0"
          >
            Try the demo
          </Button>
        </div>
        <div className="col-span-1 mb-4 flex flex-col gap-2 md:col-span-1 md:mb-0">
          <p className="text-sm font-medium text-gray-600">Resources</p>
          {resources.map((item) => (
            <Link
              href={item.href}
              key={item.title}
              className="text-footer-link my-2 text-sm font-medium"
            >
              {item.title}
            </Link>
          ))}
        </div>
        <div className="col-span-1 mb-4 flex flex-col gap-2 md:col-span-1 md:mb-0">
          <p className="text-sm font-medium text-gray-600">Project</p>
          {project.map((item) => (
            <Link
              href={item.href}
              key={item.title}
              className="text-footer-link my-2 text-sm font-medium"
            >
              {item.title}
            </Link>
          ))}
        </div>
        <div className="col-span-1 mb-4 flex flex-col gap-2 md:col-span-2 md:mb-0">
          <p className="text-sm font-medium text-gray-600">Legal</p>
          {legal.map((item) => (
            <Link
              href={item.href}
              key={item.title}
              className="text-footer-link my-2 text-sm font-medium"
            >
              {item.title}
            </Link>
          ))}
        </div>
      </div>
      <div className="my-4 flex flex-col items-center justify-between px-4 pt-8 md:flex-row">
        <p className="text-footer-link text-sm">
          © {new Date().getFullYear()} Odoo Ops Copilot · AGPL-3.0
        </p>
        <div className="mt-4 flex items-center gap-4 md:mt-0">
          <Link
            href={config.githubUrl}
            className="text-footer-link text-sm transition-colors hover:text-gray-900"
          >
            GitHub
          </Link>
          <Link
            href={config.contactUrl}
            className="text-footer-link text-sm transition-colors hover:text-gray-900"
          >
            Contact
          </Link>
        </div>
      </div>
    </Container>
  );
};
