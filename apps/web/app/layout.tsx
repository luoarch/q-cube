import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Q³ — Q-Cube",
  description: "Quantitative Strategy Lab"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
