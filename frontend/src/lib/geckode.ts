import { auth } from "@/lib/auth";

const API_URL =
  process.env.NEXT_PUBLIC_GECKODE_API_URL ??
  process.env.GECKODE_API_URL ??
  "http://localhost:8080";

export type DimensionLevel = "off" | "low" | "normal" | "high";

export type ReviewDimensions = {
  security: DimensionLevel;
  performance: DimensionLevel;
  maintainability: DimensionLevel;
};

export const DEFAULT_REVIEW_DIMENSIONS: ReviewDimensions = {
  security: "normal",
  performance: "normal",
  maintainability: "normal",
};

export type ConnectedRepo = {
  full_name: string;
  language: string;
  strictness: "low" | "medium" | "high" | string;
  standards: string[];
  review_dimensions?: ReviewDimensions;
};

export type RepoSettings = ConnectedRepo;

export class GeckodeError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  init: RequestInit & { token?: string } = {},
): Promise<T> {
  const token = init.token ?? (await auth())?.accessToken;
  if (!token) {
    throw new GeckodeError("Not authenticated", 401);
  }

  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }

  if (!res.ok) {
    const detail =
      typeof data === "object" && data && "detail" in data
        ? String((data as { detail: unknown }).detail)
        : res.statusText;
    throw new GeckodeError(detail, res.status);
  }

  return data as T;
}

export const geckode = {
  listConnectedRepos: () => request<ConnectedRepo[]>("/api/repos"),
  connectRepo: (full_name: string) =>
    request<{ ok: true; full_name: string; webhook_id: number | null }>(
      "/api/repos/connect",
      { method: "POST", body: JSON.stringify({ full_name }) },
    ),
  getSettings: (owner: string, repo: string) =>
    request<RepoSettings>(
      `/api/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/settings`,
    ),
  saveSettings: (
    owner: string,
    repo: string,
    body: Partial<{
      language: string;
      strictness: string;
      standards: string[];
      review_dimensions: Partial<ReviewDimensions>;
    }>,
  ) =>
    request<{ ok: true }>(
      `/api/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/settings`,
      { method: "PATCH", body: JSON.stringify(body) },
    ),
  triggerReview: (
    owner: string,
    repo: string,
    pr_number: number,
    options?: {
      instructions?: string;
      dimensions?: Partial<ReviewDimensions>;
    },
  ) =>
    request<{ ok: true; pr_number: number }>(
      `/api/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/pulls/${pr_number}/review`,
      {
        method: "POST",
        body: JSON.stringify({
          instructions: options?.instructions ?? null,
          dimensions: options?.dimensions ?? null,
        }),
      },
    ),
};
