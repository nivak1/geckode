import { auth } from "@/lib/auth";

const GITHUB_API = "https://api.github.com";

export type GitHubRepo = {
  id: number;
  full_name: string;
  name: string;
  owner: { login: string; avatar_url: string };
  private: boolean;
  description: string | null;
  default_branch: string;
  pushed_at: string;
  html_url: string;
  stargazers_count: number;
  language: string | null;
};

export type GitHubPullRequest = {
  id: number;
  number: number;
  title: string;
  state: "open" | "closed";
  draft: boolean;
  user: { login: string; avatar_url: string };
  created_at: string;
  updated_at: string;
  html_url: string;
  base: { ref: string };
  head: { ref: string };
  comments: number;
  additions?: number;
  deletions?: number;
  changed_files?: number;
};

export class GitHubError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function gh<T>(path: string, token?: string): Promise<T> {
  const accessToken = token ?? (await auth())?.accessToken;
  if (!accessToken) throw new GitHubError("Not authenticated", 401);

  const res = await fetch(`${GITHUB_API}${path}`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "geckode-frontend",
    },
    cache: "no-store",
  });

  if (!res.ok) {
    let message = res.statusText;
    try {
      const data = (await res.json()) as { message?: string };
      if (data?.message) message = data.message;
    } catch {
      // swallow
    }
    throw new GitHubError(message, res.status);
  }
  return (await res.json()) as T;
}

/** Matches `github_api.list_user_repositories`: max 20 pages × 100 = 2000 repos. */
const MAX_REPO_PAGES = 20;

export const github = {
  async listUserRepos(): Promise<GitHubRepo[]> {
    const out: GitHubRepo[] = [];
    for (let page = 1; page <= MAX_REPO_PAGES; page++) {
      const batch = await gh<GitHubRepo[]>(
        `/user/repos?per_page=100&page=${page}&sort=updated&affiliation=owner,collaborator,organization_member`,
      );
      out.push(...batch);
      if (batch.length < 100) break;
    }
    return out;
  },
  getRepo: (owner: string, repo: string) =>
    gh<GitHubRepo>(`/repos/${owner}/${repo}`),
  listOpenPulls: (owner: string, repo: string) =>
    gh<GitHubPullRequest[]>(
      `/repos/${owner}/${repo}/pulls?state=open&per_page=50&sort=updated&direction=desc`,
    ),
  getPull: (owner: string, repo: string, number: number) =>
    gh<GitHubPullRequest>(`/repos/${owner}/${repo}/pulls/${number}`),
};
