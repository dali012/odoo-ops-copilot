"use client";
import React from "react";
import { Container } from "./container";
import { Badge } from "./badge";
import { SectionHeading } from "./seciton-heading";
import { SubHeading } from "./subheading";
import { Button } from "./button";
import Link from "next/link";
import config from "@/config";

const stats = [
  { value: "12 / 12", label: "Golden-question evals passing, nightly in CI" },
  { value: "~13%", label: "Forecast MAPE on a 6-month holdout backtest" },
  { value: "11 / 11", label: "Write-backs verified live against Odoo 18" },
  { value: "100%", label: "Analytics run read-only — SELECT-only, allowlisted" },
];

export const Proof = () => {
  return (
    <Container className="border-divide flex flex-col items-center border-x px-4 py-20 md:px-8">
      <Badge text="Proof" />
      <SectionHeading className="mt-4">Numbers you can reproduce</SectionHeading>
      <SubHeading as="p" className="mx-auto mt-6 max-w-lg">
        Every claim on this page is backed by a test you can run from the repo —
        not a slogan. The eval and write-back suites run against a real Odoo 18
        stack in CI.
      </SubHeading>
      <div className="mt-12 grid w-full grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="rounded-lg bg-gray-50 p-6 dark:bg-neutral-800"
          >
            <div className="text-brand font-mono text-3xl font-medium">
              {stat.value}
            </div>
            <p className="mt-3 text-sm text-gray-600 dark:text-neutral-400">
              {stat.label}
            </p>
          </div>
        ))}
      </div>
      <Button
        as={Link}
        href={`${config.githubUrl}/actions`}
        variant="secondary"
        className="mt-10"
      >
        See the CI runs
      </Button>
    </Container>
  );
};
