import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronLeft } from "lucide-react";

import { geckode, GeckodeError } from "@/lib/geckode";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

import { SettingsForm } from "./settings-form";

export const dynamic = "force-dynamic";

type Params = { params: { owner: string; repo: string } };

export default async function RepoSettingsPage({ params }: Params) {
  const { owner, repo } = params;

  let initial;
  try {
    initial = await geckode.getSettings(owner, repo);
  } catch (e) {
    if (e instanceof GeckodeError && e.status === 404) {
      notFound();
    }
    throw e;
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <div>
        <Button variant="ghost" size="sm" asChild className="-ml-2 mb-2">
          <Link href={`/repos/${owner}/${repo}`}>
            <ChevronLeft className="h-4 w-4" />
            Back to {repo}
          </Link>
        </Button>
        <p className="text-sm text-muted-foreground">{owner}</p>
        <h1 className="text-3xl font-semibold tracking-tight">
          {repo} · settings
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          These review standards apply every time Geckode reviews a PR in this
          repository.
        </p>
      </div>

      <Card>
        <CardContent className="p-6">
          <SettingsForm owner={owner} repo={repo} initial={initial} />
        </CardContent>
      </Card>
    </div>
  );
}
