"""FastAPI app: GitHub webhooks, OAuth, repo settings, and static settings UI."""

from __future__ import annotations

import json
import os
import secrets
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from starlette.middleware.sessions import SessionMiddleware

from bearer_cache import get_cached_bearer_uid, set_cached_bearer_uid
from config import (
    GITHUB_CLIENT_ID,
    GITHUB_CLIENT_SECRET,
    PUBLIC_BASE_URL,
    SESSION_SECRET,
    WEBHOOK_SECRET,
    geckode_access_allowlist,
    require_github_gemini,
)
from db import engine, init_db, session_scope
from delivery_dedupe import should_skip_duplicate
from github_api import (
    create_repository_webhook,
    exchange_oauth_code,
    get_github_user,
    list_user_repositories,
)
from models import ConnectedRepo, ReviewRun, User
from review_dimensions import dimensions_to_json, merge_dimensions, parse_dimensions_json
from review_service import handle_review_error, run_review_for_comment_body
from secrets_storage import decrypt_from_storage, encrypt_for_storage
from webhook_security import verify_github_signature

_oauth_states: dict[str, float] = {}
_STATE_TTL = 600.0


def _cleanup_states() -> None:
    now = time.time()
    dead = [s for s, t in _oauth_states.items() if now - t > _STATE_TTL]
    for s in dead:
        del _oauth_states[s]


def get_session() -> Any:
    with Session(engine) as session:
        yield session


def resolve_webhook_secret(full_name: str, session: Session) -> str | None:
    row = session.exec(select(ConnectedRepo).where(ConnectedRepo.full_name == full_name)).first()
    if row:
        return decrypt_from_storage(row.webhook_secret)
    return WEBHOOK_SECRET


@asynccontextmanager
async def lifespan(app: FastAPI):
    require_github_gemini()
    init_db()
    yield


app = FastAPI(title="Geckode", lifespan=lifespan)

_frontend = os.environ.get("FRONTEND_ORIGIN")
if _frontend:
    _origins = [o.strip() for o in _frontend.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)


@app.get("/")
def root():
    return HTMLResponse(
        "<p>Geckode API — POST webhooks to <code>/webhook</code>. "
        "Open <a href=\"/settings\">/settings</a> after signing in.</p>"
    )


@app.get("/healthz")
def healthz():
    return {"ok": True}


def _bg_review_job(owner: str, repo: str, pr_number: int, comment_body: str) -> None:
    try:
        with session_scope() as session:
            run_review_for_comment_body(owner, repo, pr_number, comment_body, session=session)
    except Exception as e:
        handle_review_error(owner, repo, pr_number, e)


@app.post("/webhook")
async def webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    raw = await request.body()
    sig = request.headers.get("X-Hub-Signature-256")
    delivery = request.headers.get("X-GitHub-Delivery")

    try:
        payload = json.loads(raw.decode("utf-8") if raw else "{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    repo = payload.get("repository") or {}
    full_name = repo.get("full_name")
    if not full_name:
        raise HTTPException(status_code=400, detail="Missing repository")

    secret = resolve_webhook_secret(full_name, session)
    if not secret or not verify_github_signature(raw, sig, secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event = request.headers.get("X-GitHub-Event", "")

    if event == "ping":
        print(f"[ping] webhook connected — {payload.get('zen')}", flush=True)
        return JSONResponse({"ok": True})

    if should_skip_duplicate(delivery):
        print(f"[webhook] duplicate delivery {delivery}, skipping", flush=True)
        return JSONResponse({"ok": True, "deduped": True})

    if event != "issue_comment" or payload.get("action") != "created":
        return JSONResponse({"ok": True})

    issue = payload.get("issue") or {}
    comment = payload.get("comment") or {}
    if "pull_request" not in issue:
        return JSONResponse({"ok": True})
    if (comment.get("user") or {}).get("type") == "Bot":
        return JSONResponse({"ok": True})
    body = (comment.get("body") or "").strip()
    if not body.startswith("/review"):
        return JSONResponse({"ok": True})

    pr_number = issue["number"]
    owner, repo_name = full_name.split("/", 1)
    print(f"\n>>> /review on {full_name}#{pr_number}", flush=True)

    background_tasks.add_task(_bg_review_job, owner, repo_name, pr_number, body)

    return JSONResponse({"ok": True})


# --- OAuth ---


def _redirect_uri() -> str:
    return f"{PUBLIC_BASE_URL}/auth/callback"


@app.get("/auth/github")
def auth_github(request: Request):
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(
            status_code=503,
            detail="GitHub OAuth is not configured (GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET).",
        )
    _cleanup_states()
    state = secrets.token_urlsafe(24)
    _oauth_states[state] = time.time()
    qs = urlencode(
        {
            "client_id": GITHUB_CLIENT_ID,
            "redirect_uri": _redirect_uri(),
            "scope": "repo",
            "state": state,
        }
    )
    return RedirectResponse(f"https://github.com/login/oauth/authorize?{qs}")


@app.get("/auth/callback")
def auth_callback(request: Request, code: str | None = None, state: str | None = None):
    if not code or not state or state not in _oauth_states:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    del _oauth_states[state]
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="OAuth not configured")

    token_payload = exchange_oauth_code(
        code,
        GITHUB_CLIENT_ID,
        GITHUB_CLIENT_SECRET,
        _redirect_uri(),
    )
    access_token = token_payload.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="No access_token from GitHub")

    gh_user = get_github_user(access_token)
    gid = gh_user.get("id")
    login = gh_user.get("login")
    if gid is None or not login:
        raise HTTPException(status_code=400, detail="GitHub user payload incomplete")

    allowed = geckode_access_allowlist()
    if allowed is not None and str(login).strip().lower() not in allowed:
        return _access_denied_oauth_response()

    with session_scope() as s:
        existing = s.exec(select(User).where(User.github_id == int(gid))).first()
        if existing:
            existing.access_token = encrypt_for_storage(access_token)
            existing.login = str(login)
            s.add(existing)
            s.commit()
            uid = existing.id
        else:
            u = User(
                github_id=int(gid),
                login=str(login),
                access_token=encrypt_for_storage(access_token),
            )
            s.add(u)
            s.commit()
            s.refresh(u)
            uid = u.id

    request.session["user_id"] = uid
    return RedirectResponse(url="/settings")


def _public_base_url_blocks_github_webhooks() -> str | None:
    """GitHub refuses hook URLs on loopback; return user-facing reason or None if OK."""
    try:
        host = (urlparse(PUBLIC_BASE_URL).hostname or "").lower()
    except Exception:
        return "PUBLIC_BASE_URL is not a valid URL."
    if not host:
        return "PUBLIC_BASE_URL must include a hostname (e.g. https://your-app.ngrok.io)."
    if host in ("localhost", "127.0.0.1", "::1"):
        return (
            "GitHub cannot register webhooks to localhost or 127.0.0.1. "
            "Expose this app with a public HTTPS URL (ngrok, Cloudflare Tunnel, or deploy), "
            "set PUBLIC_BASE_URL to that origin, restart the server, then connect again."
        )
    return None


def _access_denied_oauth_response() -> RedirectResponse | HTMLResponse:
    """Browser OAuth callback when login is not on GECKODE_ALLOWED_LOGINS."""
    fe = (os.environ.get("FRONTEND_ORIGIN") or "").strip()
    if fe:
        first = fe.split(",")[0].strip().rstrip("/")
        return RedirectResponse(f"{first}/?geckode_access=denied", status_code=303)
    return HTMLResponse(
        "<p>Access is limited to selected GitHub accounts. Contact the deployment owner.</p>",
        status_code=403,
    )


def _ensure_user_access(session: Session, uid: int) -> None:
    allowed = geckode_access_allowlist()
    if allowed is None:
        return
    user = session.exec(select(User).where(User.id == uid)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if (user.login or "").strip().lower() not in allowed:
        raise HTTPException(
            status_code=403,
            detail="This deployment only allows selected GitHub accounts.",
        )


def _bearer_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
    if not auth_header:
        return None
    parts = auth_header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


def _resolve_user_via_bearer(token: str, session: Session) -> int:
    """Look up (or upsert) the GitHub user owning this OAuth access token."""
    try:
        gh_user = get_github_user(token)
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="GitHub auth failed") from None
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid GitHub token") from None

    gid = gh_user.get("id")
    login = gh_user.get("login")
    if gid is None or not login:
        raise HTTPException(status_code=401, detail="GitHub user payload incomplete")

    existing = session.exec(select(User).where(User.github_id == int(gid))).first()
    if existing:
        stored_plain = decrypt_from_storage(existing.access_token)
        if stored_plain != token or existing.login != str(login):
            existing.access_token = encrypt_for_storage(token)
            existing.login = str(login)
            session.add(existing)
            session.commit()
        return int(existing.id)  # type: ignore[arg-type]

    u = User(
        github_id=int(gid),
        login=str(login),
        access_token=encrypt_for_storage(token),
    )
    session.add(u)
    session.commit()
    session.refresh(u)
    return int(u.id)  # type: ignore[arg-type]


def current_user_id(
    request: Request,
    session: Session = Depends(get_session),
) -> int:
    """Accept either a session-cookie user (legacy UI) or a Bearer GitHub token (Next.js)."""
    bearer = _bearer_token(request)
    if bearer:
        cached = get_cached_bearer_uid(bearer)
        if cached is not None:
            _ensure_user_access(session, cached)
            return cached
        uid = _resolve_user_via_bearer(bearer, session)
        set_cached_bearer_uid(bearer, uid)
        _ensure_user_access(session, uid)
        return uid
    uid = request.session.get("user_id")
    if uid is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    uid_int = int(uid)
    _ensure_user_access(session, uid_int)
    return uid_int


# --- API ---


class ConnectBody(BaseModel):
    full_name: str = Field(..., description="owner/repo")


@app.post("/api/repos/connect")
def api_connect_repo(
    body: ConnectBody,
    session: Session = Depends(get_session),
    uid: int = Depends(current_user_id),
):
    user = session.exec(select(User).where(User.id == uid)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    parts = body.full_name.strip().split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise HTTPException(status_code=400, detail="full_name must be owner/repo")

    owner, repo = parts[0], parts[1]
    hook_url = f"{PUBLIC_BASE_URL}/webhook"
    wh_secret = secrets.token_hex(32)

    existing = session.exec(select(ConnectedRepo).where(ConnectedRepo.full_name == body.full_name)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Repository already connected")

    blocked = _public_base_url_blocks_github_webhooks()
    if blocked:
        raise HTTPException(status_code=400, detail=blocked)

    try:
        oauth_token = decrypt_from_storage(user.access_token)
        if oauth_token is None:
            raise HTTPException(status_code=401, detail="User token missing")
        created = create_repository_webhook(owner, repo, hook_url, wh_secret, oauth_token)
    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"GitHub request failed: {e}") from e
    hid = created.get("id")

    row = ConnectedRepo(
        full_name=body.full_name,
        user_id=uid,
        webhook_id=int(hid) if hid is not None else None,
        webhook_secret=encrypt_for_storage(wh_secret),
    )
    session.add(row)
    session.commit()

    return {"ok": True, "full_name": body.full_name, "webhook_id": hid}


@app.get("/api/repos")
def api_list_repos(
    session: Session = Depends(get_session),
    uid: int = Depends(current_user_id),
):
    rows = session.exec(select(ConnectedRepo).where(ConnectedRepo.user_id == uid)).all()
    return [
        {
            "full_name": r.full_name,
            "language": r.language,
            "strictness": r.strictness,
            "standards": json.loads(r.standards_json or "[]"),
        }
        for r in rows
    ]


@app.get("/api/github/repos")
def api_github_upstream(uid: int = Depends(current_user_id)):
    """Proxy list of repos from GitHub for the connect UI."""
    with session_scope() as s:
        user = s.get(User, uid)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        token = decrypt_from_storage(user.access_token)
        if not token:
            raise HTTPException(status_code=401, detail="User token missing")
    raw = list_user_repositories(token)
    simplified = [
        {"full_name": r.get("full_name"), "private": r.get("private")}
        for r in raw
        if r.get("full_name")
    ]
    return simplified


class RepoSettingsBody(BaseModel):
    language: str | None = None
    strictness: str | None = None
    standards: list[str] | None = None
    review_dimensions: dict[str, str] | None = None


@app.get("/api/repos/{owner}/{repo}/settings")
def api_get_settings(
    owner: str,
    repo: str,
    session: Session = Depends(get_session),
    uid: int = Depends(current_user_id),
):
    full_name = f"{owner}/{repo}"
    row = session.exec(
        select(ConnectedRepo).where(
            ConnectedRepo.full_name == full_name,
            ConnectedRepo.user_id == uid,
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Repo not connected")
    rd = parse_dimensions_json(row.review_dimensions_json)
    return {
        "full_name": row.full_name,
        "language": row.language,
        "strictness": row.strictness,
        "standards": json.loads(row.standards_json or "[]"),
        "review_dimensions": rd,
    }


@app.patch("/api/repos/{owner}/{repo}/settings")
def api_patch_settings(
    owner: str,
    repo: str,
    body: RepoSettingsBody,
    session: Session = Depends(get_session),
    uid: int = Depends(current_user_id),
):
    full_name = f"{owner}/{repo}"
    row = session.exec(
        select(ConnectedRepo).where(
            ConnectedRepo.full_name == full_name,
            ConnectedRepo.user_id == uid,
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Repo not connected")

    if body.language is not None:
        row.language = body.language
    if body.strictness is not None:
        row.strictness = body.strictness
    if body.standards is not None:
        row.standards_json = json.dumps(body.standards)
    if body.review_dimensions is not None:
        merged = merge_dimensions(
            parse_dimensions_json(row.review_dimensions_json),
            body.review_dimensions,
        )
        row.review_dimensions_json = dimensions_to_json(merged)

    session.add(row)
    session.commit()
    return {"ok": True}


class ManualReviewBody(BaseModel):
    instructions: str | None = None
    dimensions: dict[str, str] | None = None


def _bg_manual_review_job(
    owner: str,
    repo: str,
    pr_number: int,
    instructions: str | None,
    dimensions: dict[str, str] | None,
    review_run_id: int,
) -> None:
    try:
        with session_scope() as session:
            from review_service import run_review

            rr = session.get(ReviewRun, review_run_id)
            if rr is not None:
                rr.status = "running"
                session.add(rr)
                session.commit()

            run_review(
                owner,
                repo,
                pr_number,
                extra_instructions=instructions,
                session=session,
                review_dimensions_override=dimensions,
                review_run_id=review_run_id,
            )
    except Exception as e:  # noqa: BLE001
        try:
            with session_scope() as session:
                rr = session.get(ReviewRun, review_run_id)
                if rr is not None:
                    rr.status = "failed"
                    rr.finished_at = datetime.now(timezone.utc)
                    rr.error_message = str(e)[:8000]
                    session.add(rr)
                    session.commit()
        except Exception:
            pass
        handle_review_error(owner, repo, pr_number, e)


@app.get("/api/review-runs/{run_id}")
def api_get_review_run(
    run_id: int,
    session: Session = Depends(get_session),
    uid: int = Depends(current_user_id),
):
    rr = session.get(ReviewRun, run_id)
    if rr is None or rr.user_id != uid:
        raise HTTPException(status_code=404, detail="Review run not found")
    return {
        "id": rr.id,
        "repo_full_name": rr.repo_full_name,
        "pr_number": rr.pr_number,
        "status": rr.status,
        "created_at": rr.created_at.isoformat() if rr.created_at else None,
        "finished_at": rr.finished_at.isoformat() if rr.finished_at else None,
        "error_message": rr.error_message,
        "inline_posted": rr.inline_posted,
        "patched_count": rr.patched_count,
        "resolved_threads": rr.resolved_threads,
        "general_notes_count": rr.general_notes_count,
        "skipped_files_count": rr.skipped_files_count,
        "dropped_invalid_count": rr.dropped_invalid_count,
        "used_fallback_comment": rr.used_fallback_comment,
    }


@app.post("/api/repos/{owner}/{repo}/pulls/{pr_number}/review")
def api_trigger_review(
    owner: str,
    repo: str,
    pr_number: int,
    body: ManualReviewBody,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    uid: int = Depends(current_user_id),
):
    """Manually run a review for a PR — same code path as `/review` comments,
    but without requiring the user to type the magic command."""
    full_name = f"{owner}/{repo}"
    row = session.exec(
        select(ConnectedRepo).where(
            ConnectedRepo.full_name == full_name,
            ConnectedRepo.user_id == uid,
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Repo not connected")

    instructions = (body.instructions or "").strip() or None
    dim_override = body.dimensions if body.dimensions else None
    print(
        f"\n>>> manual review on {full_name}#{pr_number}"
        + (f" (with instructions)" if instructions else ""),
        flush=True,
    )
    review_run = ReviewRun(
        user_id=uid,
        repo_full_name=full_name,
        pr_number=pr_number,
        status="queued",
    )
    session.add(review_run)
    session.commit()
    session.refresh(review_run)
    run_id = int(review_run.id)  # type: ignore[arg-type]
    background_tasks.add_task(
        _bg_manual_review_job,
        owner,
        repo,
        pr_number,
        instructions,
        dim_override,
        run_id,
    )
    return {"ok": True, "pr_number": pr_number, "run_id": run_id}


# --- Static settings UI ---

_static_dir = Path(__file__).resolve().parent / "static"
if _static_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_static_dir)), name="assets")


@app.get("/settings")
def settings_page():
    html_path = Path(__file__).resolve().parent / "static" / "settings.html"
    if not html_path.is_file():
        return HTMLResponse(
            "<p>Create <code>static/settings.html</code> for the dashboard UI.</p>",
            status_code=404,
        )
    return FileResponse(html_path)

