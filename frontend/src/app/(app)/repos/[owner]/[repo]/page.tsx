import Link from "next/link";
import { notFound } from "next/navigation";
import {
  ChevronLeft,
  ExternalLink,
  GitPullRequest,
  MessageSquare,
  Settings,
} from "lucide-react";

import {
  DEFAULT_REVIEW_DIMENSIONS,
  geckode,
  GeckodeError,
} from "@/lib/geckode";
import { github, GitHubError } from "@/lib/github";
import { timeAgo } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

import { TriggerReviewDialog } from "./trigger-review-dialog";

export const dynamic = "force-dynamic";

type Params = { params: { owner: string; repo: string } };

export default async function RepoPage({ params }: Params) {
  const { owner, repo } = params;

  const [settingsResult, ghRepoResult, prsResult] = await Promise.allSettled([
    geckode.getSettings(owner, repo),
    github.getRepo(owner, repo),
    github.listOpenPulls(owner, repo),
  ]);

  if (
    settingsResult.status === "rejected" &&
    settingsResult.reason instanceof GeckodeError &&
    settingsResult.reason.status === 404
  ) {
    notFound();
  }

  const settings =
    settingsResult.status === "fulfilled" ? settingsResult.value : null;
  const ghRepo = ghRepoResult.status === "fulfilled" ? ghRepoResult.value : null;
  const prs = prsResult.status === "fulfilled" ? prsResult.value : [];
  const prError =
    prsResult.status === "rejected"
      ? prsResult.reason instanceof GitHubError
        ? prsResult.reason.message
        : "Could not load pull requests."
      : null;

  return (
    <div className="flex flex-col gap-8">
      <div>
        <Button variant="ghost" size="sm" asChild className="-ml-2 mb-2">
          <Link href="/dashboard">
            <ChevronLeft className="h-4 w-4" />
            All repositories
          </Link>
        </Button>
        <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
          <div>
            <p className="text-sm text-muted-foreground">{owner}</p>
            <h1 className="text-3xl font-semibold tracking-tight">{repo}</h1>
            {ghRepo?.description ? (
              <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
                {ghRepo.description}
              </p>
            ) : null}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {settings ? (
              <>
                <Badge variant="muted">
                  language: {settings.language || "auto-detect"}
                </Badge>
                <Badge variant="muted">strictness: {settings.strictness}</Badge>
              </>
            ) : null}
            <Button variant="outline" size="sm" asChild>
              <Link href={`/repos/${owner}/${repo}/settings`}>
                <Settings className="h-4 w-4" />
                Settings
              </Link>
            </Button>
            {ghRepo ? (
              <Button variant="outline" size="sm" asChild>
                <a
                  href={ghRepo.html_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <ExternalLink className="h-4 w-4" />
                  GitHub
                </a>
              </Button>
            ) : null}
          </div>
        </div>
      </div>

      <section>
        <header className="mb-4 flex items-center gap-2">
          <GitPullRequest className="h-4 w-4 text-muted-foreground" />
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Open pull requests
          </h2>
          <Badge variant="muted" className="ml-1">
            {prs.length}
          </Badge>
        </header>

        {prError ? (
          <Card className="border-destructive/50 bg-destructive/10">
            <CardContent className="p-6 text-sm text-destructive-foreground">
              {prError}
            </CardContent>
          </Card>
        ) : prs.length === 0 ? (
          <Card className="border-dashed bg-card/40">
            <CardContent className="flex flex-col items-center gap-2 p-12 text-center">
              <GitPullRequest className="h-6 w-6 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                No open pull requests right now.
              </p>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <ul className="divide-y divide-border/70">
              {prs.map((pr) => (
                <li
                  key={pr.id}
                  className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:gap-4"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <a
                        href={pr.html_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="truncate text-sm font-medium hover:text-primary"
                      >
                        {pr.title}
                      </a>
                      <Badge variant="muted" className="shrink-0">
                        #{pr.number}
                      </Badge>
                      {pr.draft ? (
                        <Badge variant="secondary" className="shrink-0">
                          draft
                        </Badge>
                      ) : null}
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      <span className="font-medium text-foreground/80">
                        @{pr.user.login}
                      </span>{" "}
                      opened {timeAgo(pr.created_at)} ·{" "}
                      <span className="font-mono text-[11px]">
                        {pr.head.ref} → {pr.base.ref}
                      </span>{" "}
                      · {pr.comments}{" "}
                      <MessageSquare className="-mt-0.5 inline h-3 w-3" />
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Button variant="ghost" size="sm" asChild>
                      <a
                        href={pr.html_url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        Open
                        <ExternalLink className="h-3.5 w-3.5" />
                      </a>
                    </Button>
                    <TriggerReviewDialog
                      owner={owner}
                      repo={repo}
                      pr={pr.number}
                      title={pr.title}
                      defaultDimensions={
                        settings?.review_dimensions ?? DEFAULT_REVIEW_DIMENSIONS
                      }
                    />
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </section>
    </div>
  );
}
