"use server";

import { revalidatePath } from "next/cache";
import { geckode, GeckodeError } from "@/lib/geckode";

export type ActionResult = { ok: true } | { ok: false; error: string };

export async function connectRepoAction(
  fullName: string,
): Promise<ActionResult> {
  if (!fullName || !fullName.includes("/")) {
    return { ok: false, error: "Pick a repository first." };
  }
  try {
    await geckode.connectRepo(fullName);
    revalidatePath("/dashboard");
    return { ok: true };
  } catch (e) {
    const error =
      e instanceof GeckodeError ? e.message : "Could not connect repo.";
    return { ok: false, error };
  }
}
