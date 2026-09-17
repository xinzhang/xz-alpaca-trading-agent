import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AlphaDesk Console",
  description: "Live view of the multi-agent trading pipeline",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
