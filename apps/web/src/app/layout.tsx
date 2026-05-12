import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL("https://divorse.ai"),
  title: "divorse.ai | Connecticut Divorce Prep",
  description:
    "A mobile-first frontend for a Connecticut divorce prep assistant with citation-backed answers and clear product guardrails.",
  openGraph: {
    title: "divorse.ai | Connecticut Divorce Prep",
    description:
      "A mobile-first frontend for grounded Connecticut divorce research and hearing prep.",
    url: "https://divorse.ai",
    siteName: "divorse.ai",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "divorse.ai | Connecticut Divorce Prep",
    description:
      "Mobile-first product frontend for grounded Connecticut divorce research and preparation.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-slate-950 text-slate-50">
        {children}
      </body>
    </html>
  );
}
