"use client";

import * as React from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  Loader2,
  Sparkles,
} from "lucide-react";

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
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";
import {
  DEFAULT_REVIEW_DIMENSIONS,
  type ReviewDimensions,
  type ReviewRunPayload,
} from "@/lib/geckode";
import {
  COUNCIL_DIMENSIONS_INTRO_COMPACT,
  COUNCIL_LENS_DESCRIPTION,
  COUNCIL_LENS_LABEL,
} from "@/lib/review-dimensions-copy";
import {
  getReviewRunAction,
  triggerReviewAction,
} from "./actions";

type Phase = "form" | "running" | "done";

function prUrl(owner: string, repo: string, pr: number) {
  return `https://github.com/${owner}/${repo}/pull/${pr}`;
}

export function TriggerReviewDialog({
  owner,
  repo,
  pr,
  title,
  defaultDimensions,
}: {
  owner: string;
  repo: string;
  pr: number;
  title: string;
  defaultDimensions: ReviewDimensions;
}) {
  const { toast } = useToast();
  const [open, setOpen] = React.useState(false);
  const [instructions, setInstructions] = React.useState("");
  const [dims, setDims] = React.useState<ReviewDimensions>(() => ({
    ...DEFAULT_REVIEW_DIMENSIONS,
    ...defaultDimensions,
  }));
  const [submitting, setSubmitting] = React.useState(false);
  const [phase, setPhase] = React.useState<Phase>("form");
  const [runStatus, setRunStatus] = React.useState<string>("queued");
  const [terminalLabel, setTerminalLabel] = React.useState<
    "completed" | "failed"
  >("completed");
  const [statsLines, setStatsLines] = React.useState<string[]>([]);
  const [errorDetail, setErrorDetail] = React.useState<string | null>(null);
  const [fallbackNote, setFallbackNote] = React.useState(false);

  React.useEffect(() => {
    if (open) {
      setDims({ ...DEFAULT_REVIEW_DIMENSIONS, ...defaultDimensions });
    }
  }, [open, defaultDimensions]);

  React.useEffect(() => {
    if (!open) {
      setPhase("form");
      setRunStatus("queued");
      setStatsLines([]);
      setErrorDetail(null);
      setFallbackNote(false);
      setSubmitting(false);
    }
  }, [open]);

  function setDim(key: keyof ReviewDimensions, v: string) {
    if (v === "off" || v === "low" || v === "normal" || v === "high") {
      setDims((d) => ({ ...d, [key]: v }));
    }
  }

  function describeOutcome(payload: ReviewRunPayload) {
    const lines: string[] = [];
    const ip = payload.inline_posted ?? 0;
    const patched = payload.patched_count ?? 0;
    const resolved = payload.resolved_threads ?? 0;
    const notes = payload.general_notes_count ?? 0;
    const skipped = payload.skipped_files_count ?? 0;
    const dropped = payload.dropped_invalid_count ?? 0;

    lines.push(`${ip} new inline comment(s)`);
    lines.push(`${resolved} thread(s) resolved`);
    if (patched > 0) {
      lines.push(`${patched} existing comment(s) updated`);
    }
    if (notes > 0) {
      lines.push(`${notes} repo / layout note(s)`);
    }
    if (skipped > 0) {
      lines.push(`${skipped} file(s) skipped (generated or budget)`);
    }
    if (dropped > 0) {
      lines.push(`${dropped} suggestion(s) dropped (bad line refs)`);
    }
    setFallbackNote(Boolean(payload.used_fallback_comment));
    setStatsLines(lines);
  }

  const runIdRef = React.useRef<number | null>(null);

  React.useEffect(() => {
    if (phase !== "running" || runIdRef.current === null) return;

    let cancelled = false;
    let intervalId = 0;

    async function pollOnce() {
      if (cancelled) return;
      const rid = runIdRef.current;
      if (rid === null) return;
      const res = await getReviewRunAction(rid);
      if (cancelled) return;
      if (!res.ok) {
        window.clearInterval(intervalId);
        setPhase("done");
        setTerminalLabel("failed");
        setErrorDetail(res.error);
        return;
      }
      const st = res.data.status;
      setRunStatus(st);
      if (st === "completed") {
        window.clearInterval(intervalId);
        describeOutcome(res.data);
        setPhase("done");
        setTerminalLabel("completed");
        setErrorDetail(null);
      } else if (st === "failed") {
        window.clearInterval(intervalId);
        setPhase("done");
        setTerminalLabel("failed");
        setErrorDetail(res.data.error_message ?? "Review failed.");
      }
    }

    void pollOnce();
    intervalId = window.setInterval(() => void pollOnce(), 1400);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [phase]);

  async function onSubmit() {
    setSubmitting(true);
    const result = await triggerReviewAction(
      owner,
      repo,
      pr,
      instructions,
      dims,
    );
    setSubmitting(false);
    if (result.ok) {
      runIdRef.current = result.runId;
      setPhase("running");
      setRunStatus("queued");
      setErrorDetail(null);
      setStatsLines([]);
      setFallbackNote(false);
    } else {
      toast({
        variant: "destructive",
        title: "Could not start review",
        description: result.error,
      });
    }
  }

  function closeAndReset() {
    setOpen(false);
    setInstructions("");
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Sparkles className="h-4 w-4" />
          Review
        </Button>
      </DialogTrigger>
      <DialogContent
        className="max-h-[90vh] overflow-y-auto sm:max-w-lg"
        aria-busy={phase === "running"}
      >
        <span className="sr-only" aria-live="polite">
          {phase === "running"
            ? `Review status: ${runStatus}`
            : phase === "done"
              ? terminalLabel === "completed"
                ? "Review finished."
                : "Review failed."
              : ""}
        </span>
        <DialogHeader>
          <DialogTitle>Run review on PR #{pr}</DialogTitle>
          <DialogDescription className="line-clamp-2">{title}</DialogDescription>
        </DialogHeader>

        {phase === "form" ? (
          <>
            <div className="space-y-4">
              <div className="rounded-lg border border-border/70 bg-card/40 p-3">
                <Label className="text-xs uppercase tracking-wide text-muted-foreground">
                  Review focus (this run)
                </Label>
                <p className="mb-1 mt-1 text-xs text-muted-foreground leading-relaxed">
                  Defaults come from repo settings. Adjust here for this PR only.{" "}
                  {COUNCIL_DIMENSIONS_INTRO_COMPACT}
                </p>
                <div className="mt-3 flex flex-col gap-3">
                  {(
                    Object.keys(COUNCIL_LENS_LABEL) as Array<keyof ReviewDimensions>
                  ).map((key) => (
                    <div
                      key={key}
                      className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_180px] sm:items-start sm:gap-3"
                    >
                      <div className="min-w-0">
                        <span className="text-sm font-medium text-foreground">
                          {COUNCIL_LENS_LABEL[key]}
                        </span>
                        <p className="mt-0.5 text-[11px] leading-snug text-muted-foreground">
                          {COUNCIL_LENS_DESCRIPTION[key]}
                        </p>
                      </div>
                      <Select
                        value={dims[key]}
                        onValueChange={(v) => setDim(key, v)}
                      >
                        <SelectTrigger className="h-9 w-full">
                          <SelectValue placeholder="Level" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="off">Don&apos;t check</SelectItem>
                          <SelectItem value="low">Low</SelectItem>
                          <SelectItem value="normal">Normal</SelectItem>
                          <SelectItem value="high">High</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="instructions">Optional extra instructions</Label>
                <Textarea
                  id="instructions"
                  placeholder="e.g. Focus on the auth changes. Skip the docs/ folder."
                  value={instructions}
                  onChange={(e) => setInstructions(e.target.value)}
                  className="min-h-[100px]"
                />
              </div>
            </div>

            <DialogFooter>
              <Button
                variant="ghost"
                onClick={() => setOpen(false)}
                disabled={submitting}
              >
                Cancel
              </Button>
              <Button onClick={onSubmit} disabled={submitting}>
                {submitting ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Sparkles className="h-4 w-4" />
                )}
                {submitting ? "Starting…" : "Start review"}
              </Button>
            </DialogFooter>
          </>
        ) : phase === "running" ? (
          <>
            <div className="space-y-4 py-2">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
                <span>
                  Geckode is reviewing — status:{" "}
                  <span className="font-medium text-foreground">{runStatus}</span>
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                Waiting on the model and GitHub. You can keep this open or check
                the PR on GitHub.
              </p>
              <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                <div className="h-full w-full animate-pulse bg-primary/70" />
              </div>
            </div>
            <DialogFooter className="gap-2 sm:justify-between">
              <Button variant="outline" size="sm" asChild>
                <a
                  href={prUrl(owner, repo, pr)}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <ExternalLink className="h-4 w-4" />
                  Open PR on GitHub
                </a>
              </Button>
              <Button variant="ghost" onClick={() => setOpen(false)}>
                Run in background
              </Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <div className="space-y-3 py-1">
              {terminalLabel === "completed" ? (
                <div className="flex items-start gap-2 text-sm">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  <div>
                    <p className="font-medium text-foreground">Review finished</p>
                    <ul className="mt-2 list-inside list-disc space-y-1 text-muted-foreground">
                      {statsLines.map((line) => (
                        <li key={line}>{line}</li>
                      ))}
                    </ul>
                    {fallbackNote ? (
                      <p className="mt-3 flex gap-2 text-xs text-amber-600 dark:text-amber-400">
                        <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                        GitHub could not place inline comments on the diff; findings
                        were posted as a regular PR comment instead (same content).
                      </p>
                    ) : null}
                  </div>
                </div>
              ) : (
                <div className="flex items-start gap-2 text-sm text-destructive">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  <div>
                    <p className="font-medium">Review failed</p>
                    {errorDetail ? (
                      <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded-md bg-destructive/10 p-2 text-xs font-normal">
                        {errorDetail}
                      </pre>
                    ) : null}
                  </div>
                </div>
              )}
            </div>
            <DialogFooter className="gap-2 sm:justify-end">
              <Button variant="outline" size="sm" asChild>
                <a
                  href={prUrl(owner, repo, pr)}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <ExternalLink className="h-4 w-4" />
                  Open PR on GitHub
                </a>
              </Button>
              <Button onClick={closeAndReset}>Done</Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
