"""Orchestrate PR fetch → LLM → GitHub review, DB-backed settings, comment PATCH reuse."""

from __future__ import annotations

import time
import traceback
import requests
from sqlmodel import Session, select

from config import (
    MAX_DIFF_CHARS,
    MAX_TREE_APPENDIX_CHARS,
    PRIOR_COMMENT_SNIPPET_CHARS,
    RepoConfig,
    geckode_sync_login_allowlist,
)
from diff_parser import build_position_map, filter_diff
from gemini import format_commits, review_pr
from github_api import (
    get_authenticated_user_login,
    get_pr_commits,
    get_pr_diff,
    get_pr_head_sha,
    get_pull_request_review_comment,
    get_recursive_tree_paths,
    get_repo_file,
    list_pull_comments_for_review_merged,
    list_pull_request_review_comments_all,
    map_pull_comment_ids_to_thread_ids,
    patch_pull_request_comment,
    post_pr_comment,
    post_pr_review,
    pull_review_comment_anchor_line,
    resolve_pull_request_review_thread,
)
from repo_tree import build_tree_appendix
from models import PRCommentSnapshot, ConnectedRepo, standards_from_json
from review_dimensions import (
    DEFAULT_REVIEW_DIMENSIONS,
    merge_dimensions,
    parse_dimensions_json,
)
from review_instructions import parse_review_trigger


_FOLLOWUP_ONLY_TRIGGERS = (
    "only resolve",
    "resolve only",
    "don't add new",
    "do not add new",
    "no new comments",
    "no new inline",
    "only close",
    "stop adding",
    "do not add issues",
    "dont add new",
    "no new feedback",
)


def _augment_extra_instructions(extra: str | None) -> str:
    """If the user asked for resolve-only / no-new-comments, append a strict instruction block."""
    base = (extra or "").strip()
    low = base.lower()
    if not any(t in low for t in _FOLLOWUP_ONLY_TRIGGERS):
        return base or "(none)"
    print("[review] strict follow-up keywords detected — appending resolve-first instructions", flush=True)
    suffix = (
        "\n\n## User override (strict)\n"
        "- Prioritize listing **resolve_comment_ids** for prior threads that look fixed in this diff.\n"
        "- Prefer **empty** `inline` and **empty** `general_notes` unless there is a regression or merge blocker.\n"
        "- Do not add stylistic nits or new topics while closing threads.\n"
    )
    return (base + suffix).strip() if base else suffix.strip()


def sync_geckode_snapshots_from_github(
    owner: str,
    repo: str,
    pr_number: int,
    session: Session,
    repo_full_name: str,
) -> int:
    """Upsert PRCommentSnapshot rows from existing pull review comments by GITHUB_TOKEN's user.

    Runs before each review so prior-thread ids are known even when snapshots were never
    stored locally (historic PRs, failed refresh, other clones).
    """
    allow = geckode_sync_login_allowlist()
    if allow is not None:
        if not allow:
            print(
                "[db] skip snapshot import: GECKODE_SYNC_LOGINS is set but empty (no logins to match)",
                flush=True,
            )
            return 0
        allowed: frozenset[str] = allow
        match_desc = f"GECKODE_SYNC_LOGINS ({', '.join(sorted(allow))})"
    else:
        token_login = get_authenticated_user_login()
        if not token_login:
            print("[db] skip snapshot import: could not resolve token login via GET /user", flush=True)
            return 0
        allowed = frozenset({token_login.lower()})
        match_desc = f"token user {token_login!r}"

    try:
        raw = list_pull_request_review_comments_all(owner, repo, pr_number)
    except Exception as e:
        print(f"[github] snapshot import list comments: {e}", flush=True)
        return 0

    best: dict[tuple[str, int], int] = {}
    skipped_reply = 0
    skipped_other = 0
    for c in raw:
        user = c.get("user") or {}
        login = (user.get("login") or "").lower()
        if login not in allowed:
            skipped_other += 1
            continue
        if c.get("in_reply_to_id") is not None:
            skipped_reply += 1
            continue
        path = c.get("path")
        if not path or not isinstance(path, str):
            continue
        line = pull_review_comment_anchor_line(c)
        if line is None:
            continue
        cid = c.get("id")
        if cid is None:
            continue
        icid = int(cid)
        key = (str(path), int(line))
        prev = best.get(key)
        if prev is None or icid > prev:
            best[key] = icid

    changed = 0
    for (path, line), github_comment_id in best.items():
        stmt = select(PRCommentSnapshot).where(
            PRCommentSnapshot.repo_full_name == repo_full_name,
            PRCommentSnapshot.pr_number == pr_number,
            PRCommentSnapshot.path == path,
            PRCommentSnapshot.line == line,
        )
        row = session.exec(stmt).first()
        if row:
            if int(row.github_comment_id) != github_comment_id:
                row.github_comment_id = github_comment_id
                session.add(row)
                changed += 1
        else:
            session.add(
                PRCommentSnapshot(
                    repo_full_name=repo_full_name,
                    pr_number=pr_number,
                    path=path,
                    line=line,
                    github_comment_id=github_comment_id,
                )
            )
            changed += 1
    session.commit()
    if best:
        print(
            f"[db] snapshot import: {len(best)} anchor(s) ({changed} row(s) new/updated), "
            f"match={match_desc}, skipped {skipped_other} non-matching / {skipped_reply} replies",
            flush=True,
        )
    elif raw:
        print(
            f"[db] snapshot import: 0 anchors for {match_desc} "
            f"({len(raw)} PR comment(s) on GitHub — add login to GECKODE_SYNC_LOGINS or fix token)",
            flush=True,
        )
    return changed


def _build_tree_appendix_block(owner: str, repo: str, head_sha: str) -> str:
    try:
        paths = get_recursive_tree_paths(owner, repo, head_sha)
        return build_tree_appendix(paths, max_chars=MAX_TREE_APPENDIX_CHARS)
    except Exception as e:
        print(f"[github] recursive tree: {e}", flush=True)
        return "(not available — tree fetch failed)"


def _build_prior_threads_block(
    session: Session | None,
    owner: str,
    repo: str,
    repo_full_name: str,
    pr_number: int,
) -> tuple[str, set[int]]:
    """Markdown-ish lines for the LLM + valid GitHub comment ids for this PR."""
    if session is None:
        return "(none — first review or no stored threads)", set()
    snaps = list(
        session.exec(
            select(PRCommentSnapshot).where(
                PRCommentSnapshot.repo_full_name == repo_full_name,
                PRCommentSnapshot.pr_number == pr_number,
            )
        ).all()
    )
    if not snaps:
        return "(none — first review or no stored threads)", set()
    lines: list[str] = []
    valid_ids: set[int] = set()
    for snap in snaps:
        valid_ids.add(int(snap.github_comment_id))
        snippet = ""
        try:
            c = get_pull_request_review_comment(owner, repo, int(snap.github_comment_id))
            body = (c.get("body") or "").strip().replace("\r\n", "\n")
            snippet = body[:PRIOR_COMMENT_SNIPPET_CHARS]
            if len(body) > PRIOR_COMMENT_SNIPPET_CHARS:
                snippet += "…"
        except Exception as e:
            print(f"[github] GET pulls/comments/{snap.github_comment_id}: {e}", flush=True)
            snippet = "(could not fetch body)"
        lines.append(f"- id={snap.github_comment_id} path={snap.path}:{snap.line} excerpt: {snippet}")
    return "\n".join(lines), valid_ids


def load_merged_repo_config(
    session: Session | None,
    owner: str,
    repo: str,
    head_sha: str,
    yml_text: str | None,
) -> RepoConfig:
    """Dashboard settings override `.reviewer.yml` when the repo is connected."""
    base = RepoConfig.from_yaml(yml_text)
    full_name = f"{owner}/{repo}"
    if session is None:
        return base
    row = session.exec(select(ConnectedRepo).where(ConnectedRepo.full_name == full_name)).first()
    if not row:
        return base
    # Connected repos use dashboard settings (empty standards means none, not YAML fallback).
    return RepoConfig(
        language=row.language,
        standards=standards_from_json(row.standards_json),
        strictness=row.strictness,
    )


def run_review_for_comment_body(
    owner: str,
    repo: str,
    pr_number: int,
    comment_body: str,
    *,
    session: Session | None = None,
) -> None:
    """Entry point from webhook after `/review` matched."""
    _, extra_instructions = parse_review_trigger(comment_body)
    run_review(
        owner,
        repo,
        pr_number,
        extra_instructions=extra_instructions,
        session=session,
    )


def run_review(
    owner: str,
    repo: str,
    pr_number: int,
    *,
    extra_instructions: str | None = None,
    session: Session | None = None,
    review_dimensions_override: dict[str, str] | None = None,
) -> None:
    commits = get_pr_commits(owner, repo, pr_number)
    raw_diff = get_pr_diff(owner, repo, pr_number)
    head_sha = get_pr_head_sha(owner, repo, pr_number)

    if not raw_diff.strip():
        post_pr_comment(owner, repo, pr_number, "🤖 The diff is empty — nothing to review.")
        return

    yml_text = get_repo_file(owner, repo, ".reviewer.yml", ref=head_sha)
    repo_config = load_merged_repo_config(session, owner, repo, head_sha, yml_text)

    full_name = f"{owner}/{repo}"
    dimensions = dict(DEFAULT_REVIEW_DIMENSIONS)
    if session is not None:
        crow = session.exec(
            select(ConnectedRepo).where(ConnectedRepo.full_name == full_name)
        ).first()
        if crow:
            dimensions = parse_dimensions_json(crow.review_dimensions_json)
    dimensions = merge_dimensions(dimensions, review_dimensions_override)

    filtered_diff, skipped = filter_diff(raw_diff, MAX_DIFF_CHARS)
    if not filtered_diff.strip():
        post_pr_comment(
            owner,
            repo,
            pr_number,
            "🤖 Nothing to review — all changed files are generated/vendored or excluded.",
        )
        return

    print(
        f"[diff] raw={len(raw_diff)}c filtered={len(filtered_diff)}c skipped={len(skipped)}",
        flush=True,
    )

    positions = build_position_map(raw_diff)

    if all(dimensions[k] == "off" for k in ("security", "performance", "maintainability")):
        post_pr_comment(
            owner,
            repo,
            pr_number,
            "🤖 Review skipped — all council dimensions are set to \"Don't check\". "
            "Enable Security, Performance, or Maintainability in repo settings or the review dialog.",
        )
        return

    if session is not None:
        sync_geckode_snapshots_from_github(owner, repo, pr_number, session, full_name)

    print(f"[gemini] asking {len(filtered_diff)} chars...", flush=True)
    tree_block = _build_tree_appendix_block(owner, repo, head_sha)
    prior_block, valid_prior_ids = _build_prior_threads_block(
        session, owner, repo, full_name, pr_number
    )
    llm = review_pr(
        format_commits(commits),
        filtered_diff,
        repo_config,
        extra_instructions=_augment_extra_instructions(extra_instructions),
        use_council=True,
        dimensions=dimensions,
        tree_appendix=tree_block,
        prior_threads_block=prior_block,
        prior_snapshot_count=len(valid_prior_ids),
    )
    raw_comments = llm.inline
    general_notes = llm.general_notes
    raw_resolve_ids = llm.resolve_comment_ids
    print(
        f"[gemini] inline={len(raw_comments)} notes={len(general_notes)} "
        f"resolve_ids_raw={len(raw_resolve_ids)}",
        flush=True,
    )

    patched_ids: list[int] = []
    flagged_pairs: set[tuple[str, int]] = set()
    dropped_pairs: set[tuple[str, int]] = set()

    inline: list[dict] = []
    dropped: list[str] = []
    for c in raw_comments:
        path = c["file"]
        line_val = c["line"]
        body = c["comment"]
        try:
            line_int = int(line_val)
        except (TypeError, ValueError):
            dropped.append(f"{path}:{line_val} (non-numeric line)")
            continue
        file_map = positions.get(path)
        if not file_map:
            dropped.append(f"{path}:{line_int} (file not in diff)")
            dropped_pairs.add((path, line_int))
            continue
        pos = file_map.get(line_int)
        if pos is None:
            dropped.append(f"{path}:{line_int} (line not in diff)")
            dropped_pairs.add((path, line_int))
            continue

        flagged_pairs.add((path, line_int))

        snap = None
        if session is not None:
            snap = session.exec(
                select(PRCommentSnapshot).where(
                    PRCommentSnapshot.repo_full_name == full_name,
                    PRCommentSnapshot.pr_number == pr_number,
                    PRCommentSnapshot.path == path,
                    PRCommentSnapshot.line == line_int,
                )
            ).first()
        if snap:
            try:
                patch_pull_request_comment(owner, repo, snap.github_comment_id, body)
                patched_ids.append(snap.github_comment_id)
                print(f"[github] patched comment {snap.github_comment_id} on {path}:{line_int}", flush=True)
            except requests.HTTPError as e:
                print(f"[github] patch failed, will post new: {e}", flush=True)
                inline.append({"path": path, "position": pos, "body": body})
        else:
            inline.append({"path": path, "position": pos, "body": body})

    patched_set = set(patched_ids)
    for rid in raw_resolve_ids:
        if rid not in valid_prior_ids:
            print(f"[resolve] ignore model id={rid}: not in Geckode snapshots for this PR", flush=True)
        elif rid in patched_set:
            print(
                f"[resolve] ignore model id={rid}: same line updated via PATCH this run",
                flush=True,
            )
    filtered_resolve_ids = [
        rid
        for rid in raw_resolve_ids
        if rid in valid_prior_ids and rid not in patched_set
    ]
    resolved_model = _resolve_threads_by_comment_ids(
        session,
        owner,
        repo,
        pr_number,
        full_name,
        filtered_resolve_ids,
        extra_valid_ids=valid_prior_ids,
    )
    resolved_heuristic = _resolve_cleared_review_threads_heuristic(
        session,
        owner,
        repo,
        pr_number,
        full_name,
        flagged_pairs,
        dropped_pairs,
    )

    summary = _build_summary(
        inline,
        skipped,
        dropped,
        patched_count=len(patched_ids),
        resolved_threads=resolved_model + resolved_heuristic,
        general_notes=general_notes,
    )

    if not inline:
        post_pr_comment(owner, repo, pr_number, summary)
        print("[ok] posted summary comment (no new inline)", flush=True)
        # Refresh snapshots from patches only — nothing new to store.
        return

    try:
        posted = post_pr_review(owner, repo, pr_number, head_sha, summary, inline)
        print(f"[ok] review posted: {posted.get('html_url')}", flush=True)
        review_id = posted.get("id")
        if session is not None and review_id is not None:
            _refresh_comment_snapshots(
                session,
                owner,
                repo,
                pr_number,
                full_name,
                int(review_id),
                expected_inline=len(inline),
            )
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 422:
            print(
                "[fallback] review rejected, posting as regular comment "
                "(inline snapshots not refreshed — resolve-by-id may miss until next inline review)",
                flush=True,
            )
            body_lines = [summary, ""]
            for c in inline:
                body_lines.append(f"**`{c['path']}` (position {c['position']})**")
                body_lines.append(c["body"])
                body_lines.append("")
            post_pr_comment(owner, repo, pr_number, "\n".join(body_lines))
        else:
            raise


def _resolve_threads_by_comment_ids(
    session: Session | None,
    owner: str,
    repo: str,
    pr_number: int,
    repo_full_name: str,
    comment_ids: list[int],
    *,
    extra_valid_ids: set[int],
) -> int:
    """Resolve threads the model listed in resolve_comment_ids (validated)."""
    if session is None or not comment_ids:
        return 0
    seen_req: set[int] = set()
    resolved = 0
    try:
        cmap = map_pull_comment_ids_to_thread_ids(owner, repo, pr_number)
    except Exception as e:
        print(f"[github] review thread map (graphql): {e}", flush=True)
        return 0
    seen_thread_ids: set[str] = set()
    for rid in comment_ids:
        if rid in seen_req:
            print(f"[resolve] skip duplicate model resolve id={rid}", flush=True)
            continue
        seen_req.add(rid)
        if rid not in extra_valid_ids:
            print(
                f"[resolve] skip model id={rid}: not in Geckode snapshot list for this PR",
                flush=True,
            )
            continue
        stmt = select(PRCommentSnapshot).where(
            PRCommentSnapshot.repo_full_name == repo_full_name,
            PRCommentSnapshot.pr_number == pr_number,
            PRCommentSnapshot.github_comment_id == rid,
        )
        snap = session.exec(stmt).first()
        if not snap:
            print(f"[resolve] skip model id={rid}: no matching snapshot row", flush=True)
            continue
        tid = cmap.get(rid)
        if not tid:
            print(
                f"[resolve] skip model id={rid}: no GraphQL thread id ({snap.path}:{snap.line})",
                flush=True,
            )
            continue
        try:
            if tid not in seen_thread_ids:
                resolve_pull_request_review_thread(tid)
                seen_thread_ids.add(tid)
            session.delete(snap)
            resolved += 1
            print(f"[resolve] model-listed github_comment_id={rid} thread resolved", flush=True)
        except Exception as e:
            print(f"[resolve] resolveReviewThread failed id={rid}: {e}", flush=True)
    session.commit()
    return resolved


def _resolve_cleared_review_threads_heuristic(
    session: Session | None,
    owner: str,
    repo: str,
    pr_number: int,
    repo_full_name: str,
    flagged_pairs: set[tuple[str, int]],
    dropped_pairs: set[tuple[str, int]],
) -> int:
    """Fallback: resolve when (path,line) no longer flagged and not ambiguously dropped."""
    if session is None:
        return 0
    stmt = select(PRCommentSnapshot).where(
        PRCommentSnapshot.repo_full_name == repo_full_name,
        PRCommentSnapshot.pr_number == pr_number,
    )
    snaps = list(session.exec(stmt).all())
    to_resolve: list[PRCommentSnapshot] = []
    for snap in snaps:
        key = (snap.path, snap.line)
        if key in flagged_pairs:
            print(
                f"[resolve/heuristic] skip comment_id={snap.github_comment_id} "
                f"{snap.path}:{snap.line}: still flagged this review",
                flush=True,
            )
            continue
        if key in dropped_pairs:
            print(
                f"[resolve/heuristic] skip comment_id={snap.github_comment_id} "
                f"{snap.path}:{snap.line}: model mentioned line but diff mapping dropped (ambiguous)",
                flush=True,
            )
            continue
        to_resolve.append(snap)
    if not to_resolve:
        return 0
    try:
        cmap = map_pull_comment_ids_to_thread_ids(owner, repo, pr_number)
    except Exception as e:
        print(f"[github] heuristic thread map (graphql): {e}", flush=True)
        return 0

    seen_thread_ids: set[str] = set()
    resolved = 0
    for snap in to_resolve:
        tid = cmap.get(snap.github_comment_id)
        if not tid:
            print(
                f"[resolve/heuristic] skip comment_id={snap.github_comment_id}: "
                f"no GraphQL thread id ({snap.path}:{snap.line})",
                flush=True,
            )
            continue
        try:
            if tid not in seen_thread_ids:
                resolve_pull_request_review_thread(tid)
                seen_thread_ids.add(tid)
            session.delete(snap)
            resolved += 1
            print(
                f"[resolve/heuristic] resolved thread comment_id={snap.github_comment_id}",
                flush=True,
            )
        except Exception as e:
            print(
                f"[resolve/heuristic] resolveReviewThread failed comment_id={snap.github_comment_id}: {e}",
                flush=True,
            )
    session.commit()
    return resolved


def _refresh_comment_snapshots(
    session: Session,
    owner: str,
    repo: str,
    pr_number: int,
    repo_full_name: str,
    review_id: int,
    *,
    expected_inline: int = 0,
) -> None:
    """Store path+line → comment id so future reviews can PATCH.

    GitHub can briefly return no comments right after POST; we retry. We merge the
    nested review endpoint with the paginated PR comments list and accept line/
    original_line for snapshot keys.
    """
    comments: list[dict] = []
    for attempt in range(12):
        comments = list_pull_comments_for_review_merged(
            owner, repo, pr_number, review_id
        )
        if comments or attempt >= 11:
            break
        if expected_inline > 0:
            print(
                f"[db] snapshot fetch attempt {attempt + 1}: 0 API comments "
                f"(expected ~{expected_inline}), retrying…",
                flush=True,
            )
            time.sleep(0.35 * (attempt + 1))
    if expected_inline > 0 and not comments:
        print(
            "[db] warning: GitHub returned no comments for this review id — "
            "snapshots not stored (resolve/PATCH will miss until next run)",
            flush=True,
        )

    stored = 0
    for c in comments:
        cid = c.get("id")
        path = c.get("path")
        line = pull_review_comment_anchor_line(c)
        if cid is None or not path or line is None:
            if cid is not None and path and line is None:
                print(
                    f"[db] skip snapshot id={cid} path={path}: no line/original_line in API",
                    flush=True,
                )
            continue
        stmt = select(PRCommentSnapshot).where(
            PRCommentSnapshot.repo_full_name == repo_full_name,
            PRCommentSnapshot.pr_number == pr_number,
            PRCommentSnapshot.path == str(path),
            PRCommentSnapshot.line == int(line),
        )
        row = session.exec(stmt).first()
        if row:
            row.github_comment_id = int(cid)
            session.add(row)
        else:
            session.add(
                PRCommentSnapshot(
                    repo_full_name=repo_full_name,
                    pr_number=pr_number,
                    path=str(path),
                    line=int(line),
                    github_comment_id=int(cid),
                )
            )
        stored += 1
    session.commit()
    print(f"[db] upserted {stored} comment snapshot(s) for {repo_full_name}#{pr_number}", flush=True)


def _build_summary(
    inline: list[dict],
    skipped: list[str],
    dropped: list[str],
    *,
    patched_count: int = 0,
    resolved_threads: int = 0,
    general_notes: list[str] | None = None,
) -> str:
    parts: list[str] = []
    if resolved_threads:
        parts.append(
            f"🤖 Resolved {resolved_threads} prior review thread(s) that look addressed."
        )
    if patched_count:
        parts.append(f"🤖 Updated {patched_count} existing inline comment(s).")
    if inline:
        parts.append(f"🤖 Found {len(inline)} thing(s) worth a look.")
    elif not patched_count and not inline:
        if not resolved_threads:
            parts.append("🤖 Reviewed — nothing to flag.")
    body = " ".join(parts) if parts else "🤖 Reviewed — nothing to flag."
    gn = [x for x in (general_notes or []) if str(x).strip()]
    if gn:
        body += "\n\n**Layout / repo notes** (no diff anchor)\n"
        for i, note in enumerate(gn[:25], 1):
            body += f"{i}. {note}\n"
        if len(gn) > 25:
            body += f"_…and {len(gn) - 25} more_\n"
    notes: list[str] = []
    if skipped:
        notes.append(
            "Skipped: " + ", ".join(skipped[:5]) + ("…" if len(skipped) > 5 else "")
        )
    if dropped:
        notes.append(f"{len(dropped)} suggestion(s) dropped (referenced lines not in diff).")
    if notes:
        body += "\n\n_" + " ".join(notes) + "_"
    return body


def handle_review_error(owner: str, repo: str, pr_number: int, exc: BaseException) -> None:
    """Log and post a generic PR message (no exception strings)."""
    print(f"[error] {type(exc).__name__}: {exc}", flush=True)
    traceback.print_exc()
    try:
        post_pr_comment(
            owner,
            repo,
            pr_number,
            "🤖 Sorry, the review failed. Please try again later; details are in the Geckode logs.",
        )
    except Exception:
        pass
