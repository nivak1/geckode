"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Plus, Loader2, Github, Lock } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/use-toast";
import { connectRepoAction } from "./actions";

type Repo = { full_name: string; private: boolean };

export function ConnectRepoDialog({
  alreadyConnected,
}: {
  alreadyConnected: string[];
}) {
  const router = useRouter();
  const { toast } = useToast();
  const [open, setOpen] = React.useState(false);
  const [repos, setRepos] = React.useState<Repo[] | null>(null);
  const [loadingRepos, setLoadingRepos] = React.useState(false);
  const [filter, setFilter] = React.useState("");
  const [connecting, setConnecting] = React.useState<string | null>(null);
  const connectedSet = React.useMemo(
    () => new Set(alreadyConnected),
    [alreadyConnected],
  );

  React.useEffect(() => {
    if (!open || repos !== null) return;
    setLoadingRepos(true);
    fetch("/api/github/repos")
      .then((r) =>
        r.ok ? (r.json() as Promise<Repo[]>) : Promise.reject(r.statusText),
      )
      .then(setRepos)
      .catch(() => {
        toast({
          variant: "destructive",
          title: "Could not load repos",
          description: "Check that your GitHub access is still valid.",
        });
      })
      .finally(() => setLoadingRepos(false));
  }, [open, repos, toast]);

  const filtered = React.useMemo(() => {
    if (!repos) return [];
    const q = filter.trim().toLowerCase();
    if (!q) return repos;
    return repos.filter((r) => r.full_name.toLowerCase().includes(q));
  }, [repos, filter]);

  async function handleConnect(fullName: string) {
    setConnecting(fullName);
    const result = await connectRepoAction(fullName);
    setConnecting(null);
    if (result.ok) {
      toast({
        title: "Repository connected",
        description: `${fullName} is now reviewed by Geckode.`,
      });
      setOpen(false);
      router.refresh();
    } else {
      toast({
        variant: "destructive",
        title: "Could not connect",
        description: result.error,
      });
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus />
          Connect a repository
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Connect a GitHub repository</DialogTitle>
          <DialogDescription>
            We&apos;ll register a webhook on your behalf. You won&apos;t need to
            copy any URLs.
          </DialogDescription>
        </DialogHeader>

        <Input
          autoFocus
          placeholder="Search owner/repo…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />

        <div className="max-h-80 overflow-y-auto rounded-lg border border-border/70 bg-background/50">
          {loadingRepos ? (
            <div className="flex items-center justify-center gap-2 p-8 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading your repositories…
            </div>
          ) : filtered.length === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">
              No repositories match.
            </div>
          ) : (
            <ul className="divide-y divide-border/70">
              {filtered.slice(0, 100).map((r) => {
                const connected = connectedSet.has(r.full_name);
                const isConnecting = connecting === r.full_name;
                return (
                  <li
                    key={r.full_name}
                    className="flex items-center justify-between gap-3 px-3 py-2.5"
                  >
                    <div className="flex min-w-0 items-center gap-2">
                      <Github className="h-4 w-4 shrink-0 text-muted-foreground" />
                      <span className="truncate text-sm">{r.full_name}</span>
                      {r.private ? (
                        <span className="inline-flex items-center gap-1 rounded bg-muted px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                          <Lock className="h-3 w-3" />
                          private
                        </span>
                      ) : null}
                    </div>
                    <Button
                      size="sm"
                      variant={connected ? "secondary" : "default"}
                      disabled={connected || isConnecting}
                      onClick={() => handleConnect(r.full_name)}
                    >
                      {isConnecting ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : null}
                      {connected
                        ? "Connected"
                        : isConnecting
                          ? "Connecting…"
                          : "Connect"}
                    </Button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Done
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
