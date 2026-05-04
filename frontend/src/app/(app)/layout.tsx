import Link from "next/link";
import { redirect } from "next/navigation";

import { auth } from "@/lib/auth";
import { GeckodeLogo } from "@/components/geckode-logo";
import { UserMenu } from "@/components/user-menu";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();
  if (!session) {
    redirect("/");
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 border-b border-border/60 bg-background/85 backdrop-blur">
        <div className="container flex h-14 items-center justify-between gap-4">
          <Link
            href="/dashboard"
            aria-label="Geckode dashboard"
            className="transition-opacity hover:opacity-80"
          >
            <GeckodeLogo />
          </Link>
          <UserMenu session={session} />
        </div>
      </header>
      <main className="flex-1">
        <div className="container py-8 md:py-10">{children}</div>
      </main>
    </div>
  );
}
