import { AgenticIntelligence } from "@/components/agentic-intelligence";
import { Benefits } from "@/components/benefits";
import { CTA } from "@/components/cta";
import { DivideX } from "@/components/divide";
import { FAQs } from "@/components/faqs";
import { Hero } from "@/components/hero";
import { HeroImage } from "@/components/hero-image";
import { HowItWorks } from "@/components/how-it-works";
import { Pricing } from "@/components/pricing";
import { Proof } from "@/components/proof";
import { Security } from "@/components/security";
import { UseCases } from "@/components/use-cases";

import { getSEOTags } from "@/lib/seo";

export const metadata = getSEOTags();

export default function Home() {
  return (
    <main>
      <DivideX />
      <Hero />
      <DivideX />
      <HeroImage />
      <DivideX />
      <div id="how-it-works" className="scroll-mt-24">
        <HowItWorks />
      </div>
      <DivideX />
      <AgenticIntelligence />
      <DivideX />
      <div id="use-cases" className="scroll-mt-24">
        <UseCases />
      </div>
      <DivideX />
      <Benefits />
      <DivideX />
      <Proof />
      <DivideX />
      <div id="pricing" className="scroll-mt-24">
        <Pricing />
      </div>
      <DivideX />
      <div id="security" className="scroll-mt-24">
        <Security />
      </div>
      <DivideX />
      <FAQs />
      <DivideX />
      <CTA />
      <DivideX />
    </main>
  );
}
