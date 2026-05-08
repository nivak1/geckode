"""Thin wrappers around the GitHub REST endpoints we use."""

import base64
from typing import Any

import requests

from config import GITHUB_API, GITHUB_TOKEN

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"

_API_VERSION = "2022-11-28"
_USER_AGENT = "geckode-bot"

_cached_api_login: str | None = None


def get_authenticated_user_login(*, access_token: str | None = None) -> str:
    """Login for the token used by api_headers (GITHUB_TOKEN or bearer). Cached per process."""
    global _cached_api_login
    if _cached_api_login is not None:
        return _cached_api_login
    tok = access_token if access_token is not None else GITHUB_TOKEN
    if not tok:
        return ""
    try:
        r = requests.get(f"{GITHUB_API}/user", headers=api_headers(access_token), timeout=30)
        r.raise_for_status()
        login = (r.json() or {}).get("login")
        if isinstance(login, str) and login.strip():
            _cached_api_login = login.strip()
            return _cached_api_login
    except Exception as e:
        print(f"[github] GET /user for snapshot sync: {e}", flush=True)
    return ""


def pull_review_comment_anchor_line(comment: dict[str, Any]) -> int | None:
    """Line number for snapshot/PATCH matching (REST fields vary by comment shape)."""
    for key in ("line", "original_line", "start_line"):
        v = comment.get(key)
        if v is None:
            continue
        try:
            return int(v)
        except (TypeError, ValueError):
            continue
    return None


def format_github_api_error(response: requests.Response | None) -> str:
    """Human-readable message from GitHub JSON error bodies (422 validation, etc.)."""
    if response is None:
        return "GitHub request failed with no response"
    try:
        data = response.json()
    except Exception:
        text = (response.text or "").strip()
        return text[:1200] if text else f"HTTP {response.status_code}"

    msg = data.get("message") or ""
    errs = data.get("errors") or []
    pieces: list[str] = [msg] if msg else []
    for e in errs:
        if isinstance(e, dict):
            field = e.get("field") or ""
            em = e.get("message") or ""
            code = e.get("code") or ""
            line = f"{field}: {em}".strip(": ").strip() if field else em
            if not line:
                line = code or str(e)
            pieces.append(line)
        else:
            pieces.append(str(e))
    out = " — ".join(p for p in pieces if p)
    return out or str(data)


def api_headers(access_token: str | None = None) -> dict[str, str]:
    """Authorization header uses `access_token`, or falls back to `GITHUB_TOKEN`."""
    tok = access_token if access_token is not None else GITHUB_TOKEN
    if not tok:
        raise RuntimeError("GitHub token is not configured (GITHUB_TOKEN or OAuth token).")
    return {
        "Authorization": f"Bearer {tok}",
        "X-GitHub-Api-Version": _API_VERSION,
        "User-Agent": _USER_AGENT,
        "Accept": "application/vnd.github+json",
    }


def get_pr_diff(owner: str, repo: str, pr_number: int, *, access_token: str | None = None) -> str:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = {**api_headers(access_token), "Accept": "application/vnd.github.diff"}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.text


def get_pr_commits(owner: str, repo: str, pr_number: int, *, access_token: str | None = None) -> list[dict]:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/commits"
    r = requests.get(url, headers=api_headers(access_token), timeout=30)
    r.raise_for_status()
    return r.json()


def get_pr_head_sha(owner: str, repo: str, pr_number: int, *, access_token: str | None = None) -> str:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}"
    r = requests.get(url, headers=api_headers(access_token), timeout=30)
    r.raise_for_status()
    return r.json()["head"]["sha"]


def get_recursive_tree_paths(
    owner: str,
    repo: str,
    ref_sha: str,
    *,
    access_token: str | None = None,
) -> list[str]:
    """Return blob paths for ref from GitHub recursive tree API (may be partial if truncated)."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/commits/{ref_sha}"
    r = requests.get(url, headers=api_headers(access_token), timeout=30)
    r.raise_for_status()
    data = r.json()
    tree_sha = (data.get("commit") or {}).get("tree", {}).get("sha")
    if not tree_sha:
        raise RuntimeError("Commit response missing tree sha")
    url_t = f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{tree_sha}"
    r2 = requests.get(
        url_t,
        headers=api_headers(access_token),
        params={"recursive": "1"},
        timeout=120,
    )
    r2.raise_for_status()
    tdata = r2.json()
    if tdata.get("truncated"):
        print("[github] git tree response truncated — path list may be incomplete", flush=True)
    out: list[str] = []
    for item in tdata.get("tree", []) or []:
        if item.get("type") != "blob":
            continue
        p = item.get("path")
        if isinstance(p, str):
            out.append(p)
    return out


def get_pull_request_review_comment(
    owner: str,
    repo: str,
    comment_id: int,
    *,
    access_token: str | None = None,
) -> dict[str, Any]:
    """GET /repos/{owner}/{repo}/pulls/comments/{comment_id}"""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/comments/{comment_id}"
    r = requests.get(url, headers=api_headers(access_token), timeout=30)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, dict) else {}


def get_repo_file(
    owner: str,
    repo: str,
    path: str,
    ref: str | None = None,
    *,
    access_token: str | None = None,
) -> str | None:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
    params = {"ref": ref} if ref else None
    r = requests.get(url, headers=api_headers(access_token), params=params, timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    data = r.json()
    if data.get("encoding") != "base64" or "content" not in data:
        return None
    return base64.b64decode(data["content"]).decode("utf-8", errors="replace")


def post_pr_comment(
    owner: str,
    repo: str,
    pr_number: int,
    body: str,
    *,
    access_token: str | None = None,
) -> dict[str, Any]:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{pr_number}/comments"
    r = requests.post(url, headers=api_headers(access_token), json={"body": body}, timeout=30)
    r.raise_for_status()
    return r.json()


def list_issue_comments(
    owner: str,
    repo: str,
    pr_number: int,
    *,
    access_token: str | None = None,
) -> list[dict[str, Any]]:
    """PRs use the issues comments endpoint (issue number = PR number)."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{pr_number}/comments"
    out: list[dict[str, Any]] = []
    page = 1
    while True:
        r = requests.get(
            url,
            headers=api_headers(access_token),
            params={"per_page": 100, "page": page},
            timeout=60,
        )
        r.raise_for_status()
        batch = r.json()
        if not isinstance(batch, list) or not batch:
            break
        out.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return out


def delete_issue_comment(
    owner: str,
    repo: str,
    comment_id: int,
    *,
    access_token: str | None = None,
) -> None:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/comments/{comment_id}"
    r = requests.delete(url, headers=api_headers(access_token), timeout=30)
    r.raise_for_status()


def post_pr_review(
    owner: str,
    repo: str,
    pr_number: int,
    commit_id: str,
    summary: str,
    inline_comments: list[dict],
    event: str = "COMMENT",
    *,
    access_token: str | None = None,
) -> dict[str, Any]:
    """POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews.

    Prefer each inline comment as ``path`` + ``body`` + ``line`` + ``side`` (e.g.
    RIGHT). Legacy ``position`` indexing often diverges from GitHub's diff and
    triggers 422 ``Position could not be resolved``.

    If 422 persists: confirm ``commit_id`` matches the PR diff you fetched, audit
    ``diff_parser.build_position_map`` vs GitHub's unified diff, and check rename
    / race between diff + head SHA calls. ``review_service.run_review`` falls
    back to one aggregate PR comment when the review POST still fails.

    Cursor prompt snippet: "Investigate 422 on POST …/pulls/…/reviews — validate
    line/side anchors vs head SHA, diff fetch order, and diff line mapping."
    """
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
    payload = {
        "commit_id": commit_id,
        "event": event,
        "body": summary,
        "comments": inline_comments,
    }
    r = requests.post(url, headers=api_headers(access_token), json=payload, timeout=60)
    if not r.ok:
        print(f"[github] {r.status_code} {r.text[:1000]}", flush=True)
        print(f"[github] payload was: {payload}", flush=True)
    r.raise_for_status()
    return r.json()


def patch_pull_request_comment(
    owner: str,
    repo: str,
    comment_id: int,
    body: str,
    *,
    access_token: str | None = None,
) -> dict[str, Any]:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/comments/{comment_id}"
    r = requests.patch(url, headers=api_headers(access_token), json={"body": body}, timeout=30)
    r.raise_for_status()
    return r.json()


def list_pull_request_review_comments_for_review(
    owner: str,
    repo: str,
    pr_number: int,
    review_id: int,
    *,
    access_token: str | None = None,
) -> list[dict[str, Any]]:
    """Comments attached to one review (paginated)."""
    out: list[dict[str, Any]] = []
    page = 1
    url = (
        f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/reviews/"
        f"{review_id}/comments"
    )
    while True:
        r = requests.get(
            url,
            headers=api_headers(access_token),
            params={"per_page": 100, "page": page},
            timeout=60,
        )
        r.raise_for_status()
        batch = r.json()
        if not isinstance(batch, list) or not batch:
            break
        out.extend(batch)
        if len(batch) < 100:
            break
        page += 1
        if page > 20:
            break
    return out


def list_pull_request_review_comments_all(
    owner: str,
    repo: str,
    pr_number: int,
    *,
    access_token: str | None = None,
) -> list[dict[str, Any]]:
    """All pull review comments on the PR (paginated)."""
    out: list[dict[str, Any]] = []
    page = 1
    while True:
        url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/comments"
        r = requests.get(
            url,
            headers=api_headers(access_token),
            params={"per_page": 100, "page": page},
            timeout=60,
        )
        r.raise_for_status()
        batch = r.json()
        if not isinstance(batch, list) or not batch:
            break
        out.extend(batch)
        if len(batch) < 100:
            break
        page += 1
        if page > 50:
            break
    return out


def list_pull_comments_for_review_merged(
    owner: str,
    repo: str,
    pr_number: int,
    review_id: int,
    *,
    access_token: str | None = None,
) -> list[dict[str, Any]]:
    """Comments for `review_id`: nested route plus paginated PR list (dedupe)."""
    rid = int(review_id)
    seen: set[int] = set()
    merged: list[dict[str, Any]] = []

    def _take(seq: list[dict[str, Any]]) -> None:
        for c in seq:
            cid = c.get("id")
            if cid is None:
                continue
            icid = int(cid)
            if icid in seen:
                continue
            seen.add(icid)
            merged.append(c)

    try:
        _take(
            list_pull_request_review_comments_for_review(
                owner, repo, pr_number, rid, access_token=access_token
            )
        )
    except Exception:
        pass
    try:
        for c in list_pull_request_review_comments_all(
            owner, repo, pr_number, access_token=access_token
        ):
            pr_rid = c.get("pull_request_review_id")
            if pr_rid is None:
                continue
            if int(pr_rid) != rid:
                continue
            cid = c.get("id")
            if cid is None:
                continue
            icid = int(cid)
            if icid in seen:
                continue
            seen.add(icid)
            merged.append(c)
    except Exception:
        pass
    return merged


def create_repository_webhook(
    owner: str,
    repo: str,
    webhook_url: str,
    secret: str,
    oauth_access_token: str,
) -> dict[str, Any]:
    """Register `issue_comment` webhooks for Geckode."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/hooks"
    payload = {
        "name": "web",
        "active": True,
        "events": ["issue_comment"],
        "config": {
            "url": webhook_url,
            "content_type": "json",
            "secret": secret,
            "insecure_ssl": "0",
        },
    }
    r = requests.post(url, headers=api_headers(oauth_access_token), json=payload, timeout=30)
    if not r.ok:
        raise RuntimeError(format_github_api_error(r))
    return r.json()


def delete_repository_webhook(
    owner: str,
    repo: str,
    hook_id: int,
    oauth_access_token: str,
) -> None:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/hooks/{hook_id}"
    r = requests.delete(url, headers=api_headers(oauth_access_token), timeout=30)
    if r.status_code not in (204, 404):
        r.raise_for_status()


def list_user_repositories(oauth_access_token: str, per_page: int = 100) -> list[dict[str, Any]]:
    """Repositories the authenticated user can access (simplified pagination)."""
    out: list[dict[str, Any]] = []
    page = 1
    while True:
        url = f"{GITHUB_API}/user/repos"
        r = requests.get(
            url,
            headers=api_headers(oauth_access_token),
            params={"per_page": per_page, "page": page, "sort": "updated"},
            timeout=30,
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        out.extend(batch)
        if len(batch) < per_page:
            break
        page += 1
        # Keep in sync with testings/frontend/src/lib/github.ts MAX_REPO_PAGES (20 pages × 100).
        if page > 20:
            break
    return out


def get_github_user(oauth_access_token: str) -> dict[str, Any]:
    r = requests.get(f"{GITHUB_API}/user", headers=api_headers(oauth_access_token), timeout=30)
    r.raise_for_status()
    return r.json()


def github_graphql(
    query: str,
    variables: dict[str, Any] | None = None,
    *,
    access_token: str | None = None,
) -> dict[str, Any]:
    """GitHub GraphQL API (used for review thread resolve — no REST equivalent)."""
    r = requests.post(
        GITHUB_GRAPHQL_URL,
        headers={
            **api_headers(access_token),
            "Content-Type": "application/json",
        },
        json={"query": query, "variables": variables or {}},
        timeout=60,
    )
    r.raise_for_status()
    payload = r.json()
    errs = payload.get("errors")
    if errs:
        msgs: list[str] = []
        for e in errs:
            if isinstance(e, dict):
                msgs.append(e.get("message") or str(e))
            else:
                msgs.append(str(e))
        raise RuntimeError("; ".join(msgs) if msgs else "GraphQL error")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("GraphQL returned no data")
    return data


_REVIEW_THREADS_QUERY = """
query ($owner: String!, $name: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $cursor) {
        pageInfo {
          hasNextPage
          endCursor
        }
        nodes {
          id
          isResolved
          comments(first: 100) {
            nodes {
              databaseId
            }
          }
        }
      }
    }
  }
}
"""


def map_pull_comment_ids_to_thread_ids(
    owner: str,
    repo: str,
    pr_number: int,
    *,
    access_token: str | None = None,
) -> dict[int, str]:
    """Map REST pull review comment id -> GraphQL ReviewThread node id."""
    out: dict[int, str] = {}
    cursor: str | None = None
    while True:
        data = github_graphql(
            _REVIEW_THREADS_QUERY,
            {
                "owner": owner,
                "name": repo,
                "number": pr_number,
                "cursor": cursor,
            },
            access_token=access_token,
        )
        repo_d = (data.get("repository") or {}) if data else {}
        pr_d = repo_d.get("pullRequest") or {}
        rt = pr_d.get("reviewThreads") or {}
        nodes = rt.get("nodes") or []
        for node in nodes:
            tid = node.get("id")
            if not tid:
                continue
            for cn in (node.get("comments") or {}).get("nodes") or []:
                dbid = cn.get("databaseId")
                if dbid is not None:
                    out[int(dbid)] = tid
        page = rt.get("pageInfo") or {}
        if not page.get("hasNextPage"):
            break
        cursor = page.get("endCursor")
        if not cursor:
            break
    return out


_RESOLVE_THREAD_MUTATION = """
mutation ($id: ID!) {
  resolveReviewThread(input: {threadId: $id}) {
    thread {
      isResolved
    }
  }
}
"""


def resolve_pull_request_review_thread(
    thread_node_id: str,
    *,
    access_token: str | None = None,
) -> None:
    """Resolve a PR review conversation thread by GraphQL thread id."""
    github_graphql(
        _RESOLVE_THREAD_MUTATION,
        {"id": thread_node_id},
        access_token=access_token,
    )


def exchange_oauth_code(code: str, client_id: str, client_secret: str, redirect_uri: str) -> dict[str, Any]:
    r = requests.post(
        "https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()
