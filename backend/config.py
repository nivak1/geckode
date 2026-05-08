"""Environment, constants, and per-repo configuration."""

import os
from dataclasses import dataclass, field

import yaml
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

GITHUB_API = "https://api.github.com"
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")
# Optional council routing (default to GEMINI_MODEL when unset).
GEMINI_MODEL_FAST = os.environ.get("GEMINI_MODEL_FAST") or None
GEMINI_MODEL_STRONG = os.environ.get("GEMINI_MODEL_STRONG") or None
GEMINI_MODEL_SYNTHESIS = os.environ.get("GEMINI_MODEL_SYNTHESIS") or None

# Webhook verification: required for production webhooks; optional for local dev if unset.
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET")

# SQLite path, or Postgres (e.g. postgresql+psycopg://... from Supabase).
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./geckode.db")

# OAuth (GitHub App or OAuth App)
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET")
# Public URL of this API (e.g. https://geckode.railway.app) — used for OAuth redirect and webhook URL.
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8080").rstrip("/")

# Session signing for OAuth cookie (set in production).
SESSION_SECRET = os.environ.get("SESSION_SECRET", "dev-change-me-in-production")

def _normalize_encryption_key(raw: str | None) -> str:
    """Strip whitespace and optional surrounding quotes (common AWS console paste mistake)."""
    s = (raw or "").strip()
    if len(s) >= 2 and s[0] in "\"'" and s[0] == s[-1]:
        s = s[1:-1].strip()
    return s


# Fernet (url-safe base64) key for encrypting GitHub access tokens and webhook secrets at rest.
# Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY = _normalize_encryption_key(os.environ.get("ENCRYPTION_KEY"))

# How big a diff we'll send to the LLM in one go.
MAX_DIFF_CHARS = 50_000

# Multi-agent council: max specialist outputs combined character estimate (cost guardrail).
MAX_COUNCIL_SYNTHESIS_CHARS = 120_000

# Path-only tree appendix at PR head (token guardrail).
MAX_TREE_APPENDIX_CHARS = int(os.environ.get("MAX_TREE_APPENDIX_CHARS", "10000"))

# First line(s) of prior Geckode inline comments passed to the model for resolve decisions.
PRIOR_COMMENT_SNIPPET_CHARS = 280

def geckode_access_allowlist() -> frozenset[str] | None:
    """If set and non-empty, only these GitHub ``user.login`` values may use the API/UI.

    Comma-separated, case-insensitive. Unset or empty = no restriction (open access).
    """

    raw = (os.environ.get("GECKODE_ALLOWED_LOGINS") or "").strip()
    if not raw:
        return None
    return frozenset(x.strip().lower() for x in raw.split(",") if x.strip())


def geckode_sync_login_allowlist() -> frozenset[str] | None:
    """None = use token user only; non-None = only these logins (lowercase), may be empty set.

    Set env ``GECKODE_SYNC_LOGINS`` to a comma-separated list of GitHub ``user.login`` values
    (e.g. when review comments are posted by a different account than ``GITHUB_TOKEN``).
    """
    raw = (os.environ.get("GECKODE_SYNC_LOGINS") or "").strip()
    if not raw:
        return None
    return frozenset(x.strip().lower() for x in raw.split(",") if x.strip())

# When skipped-file summaries mention these path fragments, append a .gitignore hint.
GITIGNORE_HINT_TRIGGER_SUBSTRINGS = (
    "__pycache__/",
    "node_modules/",
    "vendor/",
    "dist/",
    "build/",
    ".min.js",
    ".min.css",
)

SKIP_FILE_PATTERNS = (
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "Cargo.lock",
    "poetry.lock",
    "Pipfile.lock",
    "composer.lock",
    "Gemfile.lock",
    "go.sum",
    ".min.js",
    ".min.css",
    "node_modules/",
    "vendor/",
    "dist/",
    "build/",
    "__pycache__/",
    ".generated.",
    "_pb2.py",
    "_pb2_grpc.py",
)


def require_github_gemini() -> None:
    """Fail fast when starting the review worker path without credentials."""
    missing = []
    if not GITHUB_TOKEN:
        missing.append("GITHUB_TOKEN")
    if not GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")
    if missing:
        raise SystemExit(
            "Missing " + ", ".join(missing) + ". "
            "Set them in .env locally or via your host's secret manager."
        )


@dataclass
class RepoConfig:
    """Per-repo configuration from `.reviewer.yml` and/or dashboard DB."""

    language: str = "auto-detect"
    standards: list[str] = field(default_factory=list)
    strictness: str = "medium"  # low | medium | high

    @classmethod
    def from_yaml(cls, raw: str | None) -> "RepoConfig":
        if not raw:
            return cls()
        try:
            data = yaml.safe_load(raw) or {}
        except yaml.YAMLError:
            return cls()
        return cls(
            language=str(data.get("language", "auto-detect")),
            standards=list(data.get("standards", []) or []),
            strictness=str(data.get("strictness", "medium")),
        )

    def as_prompt_section(self) -> str:
        lines = [f"Primary language: {self.language}"]
        if self.standards:
            lines.append("Standards to enforce: " + ", ".join(self.standards))
        lines.append(
            f"Strictness: {self.strictness} "
            "(low = only flag real bugs and correctness issues; "
            "medium = also flag clear quality issues; "
            "high = also flag style nits and minor improvements)"
        )
        return "\n".join(lines)
