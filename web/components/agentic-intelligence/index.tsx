"use client";
import React from "react";
import { Container } from "../container";
import { Badge } from "../badge";
import { SubHeading } from "../subheading";
import { SectionHeading } from "../seciton-heading";
import { Card, CardDescription, CardTitle } from "./card";
import {
  BrainIcon,
  FingerprintIcon,
  MouseBoxIcon,
  NativeIcon,
  RealtimeSyncIcon,
  SDKIcon,
} from "@/icons/bento-icons";
import {
  LLMModelSelectorSkeleton,
  NativeToolsIntegrationSkeleton,
  TextToWorkflowBuilderSkeleton,
} from "./skeletons";

type Tab = {
  title: string;
  description: string;
  icon: React.FC<React.SVGProps<SVGSVGElement>>;
  id: string;
};

export const AgenticIntelligence = () => {
  return (
    <Container className="border-divide border-x">
      <div className="flex flex-col items-center py-16">
        <Badge text="Under the hood" />
        <SectionHeading className="mt-4">
          A minimal, inspectable agent
        </SectionHeading>

        <SubHeading as="p" className="mx-auto mt-6 max-w-lg px-2">
          No framework — a small tool-calling loop you can actually read and
          review. The mechanics are the interesting part.
        </SubHeading>
        <div className="border-divide divide-divide mt-16 grid grid-cols-1 divide-y border-y md:grid-cols-2 md:divide-x">
          <Card className="overflow-hidden mask-b-from-80%">
            <div className="flex items-center gap-2">
              <BrainIcon />
              <CardTitle>Claude tool-calling loop</CardTitle>
            </div>
            <CardDescription>
              A minimal Anthropic Messages API loop chooses tools, reads results,
              and recovers from a failed tool call with one bounded retry.
            </CardDescription>
            <LLMModelSelectorSkeleton />
          </Card>
          <Card className="overflow-hidden mask-b-from-80%">
            <div className="flex items-center gap-2">
              <MouseBoxIcon />
              <CardTitle>Streaming trace</CardTitle>
            </div>
            <CardDescription>
              Answers stream token-by-token over SSE next to a live tool-call
              trace — SQL, row counts, and evidence, not a spinner.
            </CardDescription>
            <TextToWorkflowBuilderSkeleton />
          </Card>
        </div>
        <div className="w-full">
          <Card className="relative w-full max-w-none overflow-hidden">
            <div className="pointer-events-none absolute inset-0 h-full w-full bg-[radial-gradient(var(--color-dots)_1px,transparent_1px)] mask-radial-from-10% [background-size:10px_10px]"></div>
            <div className="flex items-center gap-2">
              <NativeIcon />
              <CardTitle>Guarded SQL analytics</CardTitle>
            </div>
            <CardDescription>
              Free-form questions become a single read-only SELECT over
              allowlisted Odoo tables — capped, timed out, and never a write.
            </CardDescription>
            <NativeToolsIntegrationSkeleton />
          </Card>
        </div>
        <div className="grid grid-cols-1 gap-10 md:grid-cols-3">
          <Card>
            <div className="flex items-center gap-2">
              <FingerprintIcon />
              <CardTitle>Human approval</CardTitle>
            </div>
            <CardDescription>
              Every write to Odoo is a pending proposal until a person approves
              it — recorded with the target model and record IDs.
            </CardDescription>
          </Card>
          <Card>
            <div className="flex items-center gap-2">
              <RealtimeSyncIcon />
              <CardTitle>Durable memory</CardTitle>
            </div>
            <CardDescription>
              Chat context persists in Postgres and is restored after a refresh,
              so the conversation survives reloads.
            </CardDescription>
          </Card>
          <Card>
            <div className="flex items-center gap-2">
              <SDKIcon />
              <CardTitle>Eleven write-back tools</CardTitle>
            </div>
            <CardDescription>
              Purchase orders, reorder rules, discounts, price and POS updates,
              campaigns, transfers, inventory adjustments, and more.
            </CardDescription>
          </Card>
        </div>
      </div>
    </Container>
  );
};
