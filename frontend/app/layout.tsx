import type { Metadata } from "next"
import { GeistSans } from "geist/font/sans"
import { GeistMono } from "geist/font/mono"
import "./globals.css"

export const metadata: Metadata = {
  title: "Odoo Ops Copilot",
  description: "AI-powered operations analytics for Odoo",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html
      lang="en"
      className={`${GeistSans.variable} ${GeistMono.variable}`}
      suppressHydrationWarning
    >
      <body style={{ height: "100vh", overflow: "hidden", fontFamily: "var(--font-geist-sans)" }}>
        {children}
      </body>
    </html>
  )
}
