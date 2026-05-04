import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

import { auth } from "@/lib/auth";
import { AuthSessionProvider } from "@/components/session-provider";
import { Toaster } from "@/components/ui/toaster";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Geckode — AI code reviews on your PRs",
  description:
    "Geckode reviews your GitHub pull requests with team standards, strictness, and per-repo rules. No webhooks. No YAML. Just connect a repo.",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen bg-background font-sans">
        <AuthSessionProvider session={session}>
          {children}
          <Toaster />
        </AuthSessionProvider>
      </body>
    </html>
  );
}
