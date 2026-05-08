"use server";

import { revalidatePath } from "next/cache";
import {
  geckode,
  GeckodeError,
  type ReviewDimensions,
  type ReviewRunPayload,
} from "@/lib/geckode";

export type PollReviewRunResult =
  | { ok: true; data: ReviewRunPayload }
  | { ok: false; error: string };

export type ReviewActionResult =
  | { ok: true; runId: number }
  | { ok: false; error: string };

export async function triggerReviewAction(
  owner: string,
  repo: string,
  pr_number: number,
  instructions?: string,
  dimensions?: Partial<ReviewDimensions>,
): Promise<ReviewActionResult> {
  try {
    const res = await geckode.triggerReview(owner, repo, pr_number, {
      instructions: instructions?.trim() || undefined,
      dimensions,
    });
    revalidatePath(`/repos/${owner}/${repo}`);
    return { ok: true, runId: res.run_id };
  } catch (e) {
    const error =
      e instanceof GeckodeError
        ? e.message
        : "Could not start the review. Please try again.";
    return { ok: false, error };
  }
}

export async function getReviewRunAction(
  runId: number,
): Promise<PollReviewRunResult> {
  try {
    const data = await geckode.getReviewRun(runId);
    return { ok: true, data };
  } catch (e) {
    const error =
      e instanceof GeckodeError
        ? e.message
        : "Could not load review status.";
    return { ok: false, error };
  }
}
