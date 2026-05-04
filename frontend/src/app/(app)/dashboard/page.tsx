import Link from "next/link";
import { ArrowRight, GitBranch, Settings } from "lucide-react";

import { auth } from "@/lib/auth";
import { geckode, GeckodeError, type ConnectedRepo } from "@/lib/geckode";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

import { ConnectRepoDialog } from "./connect-repo-dialog";

export const dynamic = "force-dynamic";

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: { geckode_access?: string };
}) {
  const session = await auth();
  let repos: ConnectedRepo[] = [];
  let loadError: string | null = null;
  try {
    repos = await geckode.listConnectedRepos();
  } catch (e) {
    loadError =
      e instanceof GeckodeError
        ? e.message
        : "Could not reach the Geckode API.";
  }

  const accessDenied = searchParams.geckode_access === "denied";

  const greeting = session?.user?.login
    ? `Welcome, @${session.user.login}`
    : "Welcome";

  return (
    <div className="flex flex-col gap-8">
      {accessDenied ? (
        <Card className="border-amber-500/50 bg-amber-500/10">
          <CardContent className="p-4 text-sm text-foreground">
            This deployment only allows selected GitHub accounts. If you think this is a mistake,
            contact the person who runs Geckode for your organization.
          </CardContent>
        </Card>
      ) : null}
      <header className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <p className="text-sm text-muted-foreground">{greeting}</p>
          <h1 className="text-3xl font-semibold tracking-tight">
            Connected repositories
          </h1>
        </div>
        <ConnectRepoDialog
          alreadyConnected={repos.map((r) => r.full_name)}
        />
      </header>

      {loadError ? (
        <Card className="border-destructive/50 bg-destructive/10">
          <CardContent className="p-6 text-sm text-destructive-foreground">
            {loadError}
          </CardContent>
        </Card>
      ) : repos.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {repos.map((r) => (
            <RepoCard key={r.full_name} repo={r} />
          ))}
        </div>
      )}
    </div>
  );
}

function RepoCard({ repo }: { repo: ConnectedRepo }) {
  const [owner, name] = repo.full_name.split("/");
  return (
    <Card className="group transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-lg">
      <CardContent className="flex h-full flex-col gap-4 p-5">
        <div className="flex items-start justify-between">
          <div className="min-w-0">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              {owner}
            </p>
            <Link
              href={`/repos/${owner}/${name}`}
              className="block truncate text-base font-semibold leading-tight hover:text-primary"
            >
              {name}
            </Link>
          </div>
          <Badge variant="success" className="shrink-0">
            Connected
          </Badge>
        </div>

        <div className="flex flex-wrap gap-2 text-xs">
          <Badge variant="muted">
            <GitBranch className="mr-1 h-3 w-3" />
            {repo.language || "auto-detect"}
          </Badge>
          <Badge variant="outline">strictness: {repo.strictness}</Badge>
          <Badge variant="outline">
            {repo.standards.length} standard
            {repo.standards.length === 1 ? "" : "s"}
          </Badge>
        </div>

        <div className="mt-auto flex items-center justify-between pt-2">
          <Button variant="ghost" size="sm" asChild>
            <Link href={`/repos/${owner}/${name}/settings`}>
              <Settings className="h-4 w-4" />
              Settings
            </Link>
          </Button>
          <Button variant="link" size="sm" asChild className="px-0">
            <Link href={`/repos/${owner}/${name}`}>
              View PRs
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function EmptyState() {
  return (
    <Card className="border-dashed bg-card/40">
      <CardContent className="flex flex-col items-center gap-3 p-12 text-center">
        <div className="grid h-12 w-12 place-items-center rounded-full bg-primary/10 text-primary">
          <GitBranch className="h-5 w-5" />
        </div>
        <h2 className="text-lg font-semibold">No repositories connected yet</h2>
        <p className="max-w-md text-sm text-muted-foreground">
          Connect your first repo to start getting AI code reviews on every pull
          request. We&apos;ll register the webhook for you — no setup required.
        </p>
      </CardContent>
    </Card>
  );
}
