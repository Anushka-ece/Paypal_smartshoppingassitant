import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PennyPilot | Family money, made clearer",
  description: "Family budgets and allowance management dashboard.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
