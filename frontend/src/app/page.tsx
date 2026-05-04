import Link from "next/link";
import { redirect } from "next/navigation";
import { GitPullRequestArrow, MessageSquareCode, ShieldCheck, Sparkles } from "lucide-react";

import { auth } from "@/lib/auth";
import { GeckodeLogo } from "@/components/geckode-logo";
import { SignInButton } from "@/components/sign-in-button";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default async function LandingPage() {
  const session = await auth();
  if (session) {
    redirect("/dashboard");
  }

  return (
    <div className="relative min-h-screen overflow-hidden">
      <div className="geckode-grid-bg absolute inset-0 -z-10" />

      <header className="container flex items-center justify-between py-6">
        <Link href="/" aria-label="Geckode home">
          <GeckodeLogo />
        </Link>
        <nav className="flex items-center gap-2">
          <Button variant="ghost" asChild>
            <Link href="#features">Features</Link>
          </Button>
          <SignInButton size="default" label="Sign in" variant="outline" />
        </nav>
      </header>

      <main className="container">
        <section className="mx-auto flex max-w-3xl flex-col items-center pb-24 pt-20 text-center sm:pt-28">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-border/70 bg-card/40 px-3 py-1 text-xs text-muted-foreground backdrop-blur">
            <Sparkles className="h-3.5 w-3.5 text-primary" />
            AI code reviews, configured per repo
          </div>
          <h1 className="text-balance text-4xl font-semibold tracking-tight sm:text-6xl">
            Code reviews that actually
            <span className="ml-2 bg-gradient-to-r from-primary to-amber-300 bg-clip-text text-transparent">
              read your diff
            </span>
            .
          </h1>
          <p className="mt-6 max-w-2xl text-balance text-lg text-muted-foreground">
            Geckode reviews every pull request against your team&apos;s standards,
            language, and strictness. Connect a repo with one click — no
            webhooks, no YAML, no <code className="rounded bg-card px-1.5 py-0.5 text-sm">/review</code> commands to memorize.
          </p>
          <div className="mt-10 flex flex-col items-center gap-3 sm:flex-row">
            <SignInButton callbackUrl="/dashboard" />
            <Button variant="ghost" size="lg" asChild>
              <Link href="#features">See how it works</Link>
            </Button>
          </div>
          <p className="mt-4 text-xs text-muted-foreground">
            Free for personal repos. We never store your source — only review
            settings.
          </p>
        </section>

        <section id="features" className="mx-auto grid max-w-5xl gap-4 pb-24 sm:grid-cols-3">
          <FeatureCard
            icon={<GitPullRequestArrow className="h-5 w-5" />}
            title="One‑click connect"
            body="Pick a repo from your GitHub list and we wire up the webhook for you. No URLs to copy."
          />
          <FeatureCard
            icon={<MessageSquareCode className="h-5 w-5" />}
            title="Manual reviews"
            body="Trigger a fresh review on any PR with optional extra instructions, right from the dashboard."
          />
          <FeatureCard
            icon={<ShieldCheck className="h-5 w-5" />}
            title="Your standards, your rules"
            body="Set primary language, strictness, and team standards per repo. We respect them every review."
          />
        </section>
      </main>

      <footer className="border-t border-border/60 py-8">
        <div className="container flex flex-col items-center justify-between gap-2 text-xs text-muted-foreground sm:flex-row">
          <span>© {new Date().getFullYear()} Geckode</span>
          <span>Built with Next.js · Hosted on Vercel</span>
        </div>
      </footer>
    </div>
  );
}

function FeatureCard({
  icon,
  title,
  body,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <Card className="bg-card/60 backdrop-blur transition-colors hover:bg-card">
      <CardContent className="flex flex-col gap-3 p-6">
        <span className="inline-flex h-9 w-9 items-center justify-center rounded-md bg-primary/10 text-primary ring-1 ring-inset ring-primary/30">
          {icon}
        </span>
        <h3 className="text-base font-semibold">{title}</h3>
        <p className="text-sm text-muted-foreground">{body}</p>
      </CardContent>
    </Card>
  );
}
