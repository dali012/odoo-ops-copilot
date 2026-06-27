"use client";
import React from "react";
import { Container } from "./container";
import { Badge } from "./badge";
import { SectionHeading } from "./seciton-heading";
import { SubHeading } from "./subheading";
import { DivideX } from "./divide";
import { Button } from "./button";
import { CheckIcon } from "@/icons/card-icons";
import { tiers } from "@/constants/pricing";
import Link from "next/link";

export const Pricing = () => {
  return (
    <section>
      <Container className="border-divide flex flex-col items-center justify-center border-x pt-10 pb-10">
        <Badge text="Pricing" />
        <SectionHeading className="mt-4">
          Open source, commercially friendly
        </SectionHeading>
        <SubHeading as="p" className="mx-auto mt-6 max-w-lg">
          Run the full project yourself under AGPL-3.0, or take a commercial
          license if those terms don&apos;t fit your deployment.
        </SubHeading>
      </Container>
      <DivideX />
      <Container className="border-divide border-x">
        <div className="divide-divide grid grid-cols-1 divide-y md:grid-cols-2 md:divide-x md:divide-y-0">
          {tiers.map((tier) => (
            <div className="p-6 md:p-8" key={tier.title}>
              <h3 className="text-charcoal-700 text-xl font-medium dark:text-neutral-100">
                {tier.title}
              </h3>
              <p className="text-base text-gray-600 dark:text-neutral-400">
                {tier.subtitle}
              </p>
              <span className="mt-6 block text-3xl font-medium dark:text-white">
                {tier.priceLabel}
              </span>
              <Button
                className="mt-6 w-full"
                as={Link}
                href={tier.ctaLink}
                variant={tier.featured ? "brand" : "secondary"}
              >
                {tier.ctaText}
              </Button>
              <div className="mt-6 flex flex-col gap-4">
                {tier.features.map((feature) => (
                  <Step key={feature}>{feature}</Step>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Container>
    </section>
  );
};

const Step = ({ children }: { children: React.ReactNode }) => (
  <div className="text-charcoal-700 flex items-center gap-2 dark:text-neutral-100">
    <CheckIcon className="h-4 w-4 shrink-0" />
    {children}
  </div>
);
