import type { Metadata } from "next";
import "./globals.css";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { ThemeProvider } from "@/context/theme-provider";
import { inter } from "@/fonts/inter-display/inter";
import { dmMono } from "@/fonts/dm-mono";
import { getSEOTags } from "@/lib/seo";

export const metadata: Metadata = getSEOTags();

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${inter.variable} ${dmMono.variable}`}
    >
      <body className="font-primary h-full bg-white [--pattern-fg:var(--color-charcoal-900)]/10 dark:bg-black dark:[--pattern-fg:var(--color-neutral-100)]/30">
        <ThemeProvider attribute="class" defaultTheme="system">
          <main className="h-full bg-white antialiased dark:bg-black">
            <Navbar />
            {children}
            <Footer />
          </main>
        </ThemeProvider>
      </body>
    </html>
  );
}
