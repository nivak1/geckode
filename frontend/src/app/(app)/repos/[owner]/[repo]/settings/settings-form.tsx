"use client";

import * as React from "react";
import { Loader2, Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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
  type RepoSettings,
  type ReviewDimensions,
} from "@/lib/geckode";
import {
  COUNCIL_DIMENSIONS_INTRO,
  COUNCIL_LENS_DESCRIPTION,
  COUNCIL_LENS_LABEL,
} from "@/lib/review-dimensions-copy";
import { saveSettingsAction } from "./actions";

const STRICTNESS_HELP: Record<string, string> = {
  low: "Only flag real bugs and correctness issues.",
  medium: "Also flag clear quality issues.",
  high: "Also flag style nits and minor improvements.",
};

function mergedDims(initial: RepoSettings): ReviewDimensions {
  return {
    ...DEFAULT_REVIEW_DIMENSIONS,
    ...initial.review_dimensions,
  };
}

export function SettingsForm({
  owner,
  repo,
  initial,
}: {
  owner: string;
  repo: string;
  initial: RepoSettings;
}) {
  const { toast } = useToast();
  const [language, setLanguage] = React.useState(initial.language || "");
  const [strictness, setStrictness] = React.useState(
    initial.strictness || "medium",
  );
  const [standards, setStandards] = React.useState(
    (initial.standards || []).join("\n"),
  );
  const [reviewDimensions, setReviewDimensions] = React.useState<ReviewDimensions>(
    () => mergedDims(initial),
  );
  const [saving, setSaving] = React.useState(false);

  const initialDims = React.useMemo(() => mergedDims(initial), [initial]);

  const dirty =
    language.trim() !== (initial.language || "").trim() ||
    strictness !== (initial.strictness || "medium") ||
    standards.trim() !==
      (initial.standards || []).join("\n").trim() ||
    reviewDimensions.security !== initialDims.security ||
    reviewDimensions.performance !== initialDims.performance ||
    reviewDimensions.maintainability !== initialDims.maintainability;

  async function onSave() {
    setSaving(true);
    const cleanedStandards = standards
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    const result = await saveSettingsAction(owner, repo, {
      language: language.trim() || "auto-detect",
      strictness,
      standards: cleanedStandards,
      review_dimensions: reviewDimensions,
    });
    setSaving(false);
    if (result.ok) {
      toast({
        title: "Saved",
        description: "Settings will apply to the next review.",
      });
    } else {
      toast({
        variant: "destructive",
        title: "Could not save",
        description: result.error,
      });
    }
  }

  function setDim(key: keyof ReviewDimensions, v: string) {
    if (v === "off" || v === "low" || v === "normal" || v === "high") {
      setReviewDimensions((d) => ({ ...d, [key]: v }));
    }
  }

  return (
    <form
      className="flex flex-col gap-6"
      onSubmit={(e) => {
        e.preventDefault();
        onSave();
      }}
    >
      <div className="grid gap-2">
        <Label htmlFor="language">Primary language</Label>
        <Input
          id="language"
          placeholder="auto-detect"
          autoComplete="off"
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
        />
        <p className="text-xs text-muted-foreground">
          Used to tune the reviewer&apos;s prompt. Leave blank to auto-detect
          from the diff.
        </p>
      </div>

      <div className="grid gap-2">
        <Label htmlFor="strictness">Strictness</Label>
        <Select value={strictness} onValueChange={setStrictness}>
          <SelectTrigger id="strictness">
            <SelectValue placeholder="medium" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="low">Low</SelectItem>
            <SelectItem value="medium">Medium</SelectItem>
            <SelectItem value="high">High</SelectItem>
          </SelectContent>
        </Select>
        <p className="text-xs text-muted-foreground">
          {STRICTNESS_HELP[strictness] ?? STRICTNESS_HELP.medium}
        </p>
      </div>

      <div className="grid gap-3 rounded-lg border border-border/70 bg-card/40 p-4">
        <div>
          <Label className="text-base">Council dimensions</Label>
          <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
            {COUNCIL_DIMENSIONS_INTRO}
          </p>
        </div>
        {(Object.keys(COUNCIL_LENS_LABEL) as Array<keyof ReviewDimensions>).map((key) => (
          <div
            key={key}
            className="grid gap-2 border-b border-border/60 pb-4 last:border-0 last:pb-0 sm:grid-cols-[minmax(0,1fr)_200px] sm:items-start sm:gap-4"
          >
            <div className="min-w-0">
              <Label htmlFor={`dim-${key}`} className="text-foreground">
                {COUNCIL_LENS_LABEL[key]}
              </Label>
              <p className="mt-1 text-xs text-muted-foreground leading-snug">
                {COUNCIL_LENS_DESCRIPTION[key]}
              </p>
            </div>
            <Select
              value={reviewDimensions[key]}
              onValueChange={(v) => setDim(key, v)}
            >
              <SelectTrigger id={`dim-${key}`} className="w-full sm:mt-0">
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

      <div className="grid gap-2">
        <Label htmlFor="standards">Team standards</Label>
        <Textarea
          id="standards"
          placeholder={"e.g.\nPrefer explicit types\nNo console.log in production\nUse early returns"}
          value={standards}
          onChange={(e) => setStandards(e.target.value)}
          className="min-h-[160px] font-mono text-sm"
        />
        <p className="text-xs text-muted-foreground">
          One rule per line. Applied on every review Geckode runs for this
          repository.
        </p>
      </div>

      <div className="flex items-center justify-end gap-3">
        <p className="mr-auto text-xs text-muted-foreground">
          {dirty ? "Unsaved changes" : "All changes saved"}
        </p>
        <Button type="submit" disabled={!dirty || saving}>
          {saving ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Save className="h-4 w-4" />
          )}
          {saving ? "Saving…" : "Save settings"}
        </Button>
      </div>
    </form>
  );
}
