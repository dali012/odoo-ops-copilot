"use client";
import React from "react";
import { Container } from "./container";
import { Heading } from "./heading";
import { SubHeading } from "./subheading";
import { Button } from "./button";
import { Badge } from "./badge";
import Link from "next/link";
import config from "@/config";

export const Hero = () => {
  return (
    <Container className="border-divide flex flex-col items-center justify-center border-x px-4 pt-10 pb-10 md:pt-32 md:pb-20">
      <Badge text="AI ops copilot for Odoo ERP" />
      <Heading className="mt-4">
        Ask your Odoo ERP anything, <br /> and{" "}
        <span className="text-brand">act on it safely</span>
      </Heading>

      <SubHeading className="mx-auto mt-6 max-w-2xl">
        Odoo Ops Copilot answers natural-language questions against your live Odoo
        data — forecasts, margins, stockout risk, RFM — then drafts purchase
        orders, price changes, and campaigns that only execute after a human
        approves them.
      </SubHeading>

      <div className="mt-6 flex items-center gap-4">
        <Button as={Link} href={config.appUrl}>
          Try the demo
        </Button>
        <Button variant="secondary" as={Link} href={config.githubUrl}>
          View on GitHub
        </Button>
      </div>

      <div className="mt-8 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 font-mono text-xs text-gray-600 dark:text-neutral-400">
        <span>AGPL-3.0 open source</span>
        <span className="hidden sm:inline">·</span>
        <span>12/12 golden-question evals</span>
        <span className="hidden sm:inline">·</span>
        <span>~13% forecast MAPE</span>
        <span className="hidden sm:inline">·</span>
        <span>Human-approved write-backs</span>
      </div>
    </Container>
  );
};
