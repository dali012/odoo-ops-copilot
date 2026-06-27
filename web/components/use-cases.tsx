"use client";
import React, { useState } from "react";
import { Container } from "./container";
import { Badge } from "./badge";
import { SectionHeading } from "./seciton-heading";
import { SubHeading } from "./subheading";
import {
  DevopsIcon,
  PhoneIcon,
  TruckIcon,
  DatabaseIcon,
  WalletIcon,
  GraphIcon,
} from "@/icons/card-icons";
import { Scale } from "./scale";
import { motion } from "motion/react";

export const UseCases = () => {
  const useCases = [
    {
      title: "Demand forecasting",
      description:
        "Seasonal exponential-smoothing forecasts per product category, returned with the sales history behind every number.",
      icon: <GraphIcon className="text-brand size-6" />,
    },
    {
      title: "Stockout & inventory risk",
      description:
        "Rank products by days-of-stock and urgency before they run out, using real sales velocity and reorder points.",
      icon: <TruckIcon className="text-brand size-6" />,
    },
    {
      title: "Margin & pricing",
      description:
        "Gross margin by product or category, plus read-only discount and price-change simulations that never touch Odoo.",
      icon: <WalletIcon className="text-brand size-6" />,
    },
    {
      title: "Customer segmentation",
      description:
        "RFM segments — champions, loyal, at-risk, lost — to target the right audience before drafting a campaign.",
      icon: <PhoneIcon className="text-brand size-6" />,
    },
    {
      title: "Guarded SQL analytics",
      description:
        "Free-form questions become a single read-only SELECT over allowlisted Odoo tables — capped, timed out, never a write.",
      icon: <DatabaseIcon className="text-brand size-6" />,
    },
    {
      title: "Approved write-backs",
      description:
        "Purchase orders, reorder rules, price updates, and campaigns — drafted by the agent, executed only on human approval.",
      icon: <DevopsIcon className="text-brand size-6" />,
    },
  ];
  const [activeUseCase, setActiveUseCase] = useState<number | null>(null);
  return (
    <Container className="border-divide relative overflow-hidden border-x px-4 md:px-8">
      <div className="relative flex flex-col items-center py-20">
        <Badge text="Use Cases" />
        <SectionHeading className="mt-4">
          One copilot, across your operations
        </SectionHeading>

        <SubHeading as="p" className="mx-auto mt-6 max-w-lg">
          From forecasting to approved write-backs — every answer is grounded in
          your live Odoo data, never invented.
        </SubHeading>

        <div className="mt-12 grid grid-cols-1 gap-10 md:grid-cols-2 lg:grid-cols-3">
          {useCases.map((useCase, index) => (
            <div
              onMouseEnter={() => setActiveUseCase(index)}
              key={useCase.title}
              className="relative"
            >
              {activeUseCase === index && (
                <motion.div
                  layoutId="scale"
                  className="absolute inset-0 z-0"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 0.5 }}
                  exit={{ opacity: 0 }}
                >
                  <Scale />
                </motion.div>
              )}
              <div className="relative z-10 rounded-lg bg-gray-50 p-4 transition duration-200 hover:bg-transparent md:p-5 dark:bg-neutral-800">
                <div className="flex items-center gap-2">{useCase.icon}</div>
                <h3 className="mt-4 mb-2 text-lg font-medium">
                  {useCase.title}
                </h3>
                <p className="text-gray-600">{useCase.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </Container>
  );
};
