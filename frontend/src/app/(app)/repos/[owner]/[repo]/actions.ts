"use server";

import { revalidatePath } from "next/cache";
import { geckode, GeckodeError, type ReviewDimensions } from "@/lib/geckode";

export type ReviewActionResult =
  | { ok: true }
  | { ok: false; error: string };

export async function triggerReviewAction(
  owner: string,
  repo: string,
  pr_number: number,
  instructions?: string,
  dimensions?: Partial<ReviewDimensions>,
): Promise<ReviewActionResult> {
  try {
    await geckode.triggerReview(owner, repo, pr_number, {
      instructions: instructions?.trim() || undefined,
      dimensions,
    });
    revalidatePath(`/repos/${owner}/${repo}`);
    return { ok: true };
  } catch (e) {
    const error =
      e instanceof GeckodeError
        ? e.message
        : "Could not start the review. Please try again.";
    return { ok: false, error };
  }
}
