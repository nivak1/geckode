"use server";

import { revalidatePath } from "next/cache";
import { geckode, GeckodeError, type ReviewDimensions } from "@/lib/geckode";

export type SaveSettingsResult =
  | { ok: true }
  | { ok: false; error: string };

export async function saveSettingsAction(
  owner: string,
  repo: string,
  body: {
    language: string;
    strictness: string;
    standards: string[];
    review_dimensions?: Partial<ReviewDimensions>;
  },
): Promise<SaveSettingsResult> {
  try {
    await geckode.saveSettings(owner, repo, body);
    revalidatePath(`/repos/${owner}/${repo}`);
    revalidatePath(`/repos/${owner}/${repo}/settings`);
    revalidatePath(`/dashboard`);
    return { ok: true };
  } catch (e) {
    const error =
      e instanceof GeckodeError ? e.message : "Could not save settings.";
    return { ok: false, error };
  }
}
