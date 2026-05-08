import Link from "next/link";
import { redirect } from "next/navigation";
import {
  GitPullRequestArrow,
  Link2,
  MessageSquare,
  MessageSquareCode,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

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
        <section className="mx-auto flex max-w-3xl flex-col items-center pb-16 pt-20 text-center sm:pt-28">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-border/70 bg-card/40 px-3 py-1 text-xs font-medium tracking-wide text-muted-foreground backdrop-blur">
            <Sparkles className="h-3.5 w-3.5 shrink-0 text-primary" />
            Security · Performance · Maintainability
          </div>
          <h1 className="text-balance text-4xl font-semibold tracking-tight sm:text-6xl">
            Code reviews that actually
            <span className="ml-2 bg-gradient-to-r from-primary to-amber-300 bg-clip-text text-transparent">
              read your diff
            </span>
            .
          </h1>
          <p className="mt-6 max-w-2xl text-balance text-lg text-muted-foreground">
            Geckode runs a multi-lens AI council on every pull request — surfacing
            security risks, performance issues, and maintainability problems before
            merge. Connect a repository in seconds.
          </p>
          <div className="mt-10 flex flex-col items-center gap-3 sm:flex-row">
            <SignInButton callbackUrl="/dashboard" />
            <Button variant="ghost" size="lg" asChild>
              <Link href="#features">See how it works</Link>
            </Button>
          </div>
          <p className="mt-4 text-xs text-muted-foreground">
            We don&apos;t store your source — only review preferences and repo
            settings you configure in Geckode.
          </p>
        </section>

        <section
          aria-labelledby="how-heading"
          className="mx-auto max-w-5xl border-y border-border/60 bg-card/25 px-4 py-14 backdrop-blur sm:px-6"
        >
          <h2
            id="how-heading"
            className="text-center text-sm font-semibold uppercase tracking-wide text-muted-foreground"
          >
            How it works
          </h2>
          <div className="mt-10 grid gap-10 sm:grid-cols-3 sm:gap-8">
            <HowStep
              step={1}
              icon={<Link2 className="h-5 w-5" />}
              title="Connect"
              body="Sign in with GitHub and choose a repository. Geckode registers the webhook — no URLs to paste."
            />
            <HowStep
              step={2}
              icon={<Sparkles className="h-5 w-5" />}
              title="Review"
              body="Open a PR from the dashboard and run a review. The council reads your diff through security, performance, and maintainability lenses."
            />
            <HowStep
              step={3}
              icon={<MessageSquare className="h-5 w-5" />}
              title="Feedback on GitHub"
              body="Comments and summaries land on the pull request where your team already reviews code."
            />
          </div>
        </section>

        <section id="features" className="mx-auto grid max-w-5xl gap-4 pb-24 pt-16 sm:grid-cols-3">
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

function HowStep({
  step,
  icon,
  title,
  body,
}: {
  step: number;
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <div className="flex flex-col items-center text-center sm:items-start sm:text-left">
      <span className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-full bg-primary/12 text-primary ring-1 ring-inset ring-primary/25">
        {icon}
      </span>
      <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        Step {step}
      </span>
      <h3 className="mt-1 text-base font-semibold">{title}</h3>
      <p className="mt-2 text-sm text-muted-foreground">{body}</p>
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
