"use client";

import * as React from "react";
import { Loader2, Sparkles } from "lucide-react";

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
} from "@/lib/geckode";
import {
  COUNCIL_DIMENSIONS_INTRO_COMPACT,
  COUNCIL_LENS_DESCRIPTION,
  COUNCIL_LENS_LABEL,
} from "@/lib/review-dimensions-copy";
import { triggerReviewAction } from "./actions";

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

  React.useEffect(() => {
    if (open) {
      setDims({ ...DEFAULT_REVIEW_DIMENSIONS, ...defaultDimensions });
    }
  }, [open, defaultDimensions]);

  function setDim(key: keyof ReviewDimensions, v: string) {
    if (v === "off" || v === "low" || v === "normal" || v === "high") {
      setDims((d) => ({ ...d, [key]: v }));
    }
  }

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
      toast({
        title: "Review started",
        description: `Geckode is reviewing PR #${pr}. Comments will appear on GitHub shortly.`,
      });
      setInstructions("");
      setOpen(false);
    } else {
      toast({
        variant: "destructive",
        title: "Could not start review",
        description: result.error,
      });
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Sparkles className="h-4 w-4" />
          Review
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Run review on PR #{pr}</DialogTitle>
          <DialogDescription className="line-clamp-2">{title}</DialogDescription>
        </DialogHeader>

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
              {(Object.keys(COUNCIL_LENS_LABEL) as Array<keyof ReviewDimensions>).map(
                (key) => (
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
                ),
              )}
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
      </DialogContent>
    </Dialog>
  );
}
