import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GEO Creator Scout",
  description:
    "AI-assisted Instagram creator discovery for GEO (Generative Engine Optimization) outreach.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
