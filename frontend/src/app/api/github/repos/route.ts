import { NextResponse } from "next/server";
import { github, GitHubError } from "@/lib/github";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const repos = await github.listUserRepos();
    return NextResponse.json(
      repos.map((r) => ({ full_name: r.full_name, private: r.private })),
    );
  } catch (e) {
    const status = e instanceof GitHubError ? e.status : 500;
    const message = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: message }, { status });
  }
}
