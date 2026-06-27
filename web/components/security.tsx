import React from "react";
import { Container } from "./container";
import { DivideX } from "./divide";
import { SectionHeading } from "./seciton-heading";
import { SubHeading } from "./subheading";
import { Button } from "./button";
import Link from "next/link";
import config from "@/config";

const guardrails = [
  "SELECT-only, single-statement SQL parser",
  "Allowlisted Odoo tables — nothing else is queryable",
  "Read-only transaction: writes are rejected by Postgres",
  "Statement timeout + hard row cap",
  "Writes to Odoo happen only after human approval",
];

export const Security = () => {
  return (
    <>
      <Container className="border-divide border-x">
        <h2 className="pt-10 pb-5 text-center font-mono text-sm tracking-tight text-neutral-500 uppercase md:pt-20 md:pb-10 dark:text-neutral-400">
          Designed for prompt injection, not surprised by it
        </h2>
      </Container>
      <DivideX />
      <Container className="border-divide grid grid-cols-1 border-x bg-gray-100 px-8 py-12 md:grid-cols-2 dark:bg-neutral-900">
        <div>
          <SectionHeading className="text-left">
            Guardrails that don&apos;t depend on the model
          </SectionHeading>
          <SubHeading as="p" className="mt-4 text-left">
            The agent can be manipulated and tool data can be hostile — so every
            guarantee is enforced in code or by Postgres, below the model. A
            prompt-injected query still can&apos;t write, scan, or escape the
            allowlist.
          </SubHeading>
          <Button
            className="mt-6 mb-8 inline-block w-full md:w-auto"
            as={Link}
            href={`${config.githubUrl}/blob/main/SECURITY.md`}
          >
            Read the threat model
          </Button>
        </div>
        <div className="flex flex-col justify-center gap-3">
          {guardrails.map((item) => (
            <div
              key={item}
              className="shadow-aceternity text-charcoal-700 flex items-center gap-3 rounded-lg bg-white px-4 py-3 text-sm font-medium dark:bg-neutral-950 dark:text-neutral-100"
            >
              <span className="bg-brand/10 text-brand flex size-6 shrink-0 items-center justify-center rounded-md font-mono text-xs">
                ✓
              </span>
              {item}
            </div>
          ))}
        </div>
      </Container>
    </>
  );
};
