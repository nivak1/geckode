import type { ReviewDimensions } from "@/lib/geckode";

/** Council dimensions: intro (settings + trigger dialog). No implementation details. */
export const COUNCIL_DIMENSIONS_INTRO = [
  "Higher intensity for a lens takes more time and produces a more thorough review for that area.",
  "Don’t check — skip that lens entirely. Low — fewer findings, only clearer issues. Normal — balanced. High — deeper pass; the run takes longer.",
].join(" ");

/** Shorter blurb for modal / tight layouts. */
export const COUNCIL_DIMENSIONS_INTRO_COMPACT =
  "Higher = longer, more thorough for that lens. Don’t check skips it. Low / Normal / High = how deep to go.";

/** One line per lens (label key → description). */
export const COUNCIL_LENS_DESCRIPTION: Record<keyof ReviewDimensions, string> = {
  security:
    "Injection, auth, secrets, unsafe patterns, and similar risks in the changed code.",
  performance:
    "Speed, scalability, allocations, I/O, and obvious inefficiencies in the diff.",
  maintainability:
    "Readability and long-term change cost: naming, structure, duplication, error handling, and testability — not the same as Security or Performance above.",
};

export const COUNCIL_LENS_LABEL: Record<keyof ReviewDimensions, string> = {
  security: "Security",
  performance: "Performance",
  maintainability: "Maintainability",
};
