"""LLM-side: prompt construction, multi-pass council, structured JSON review."""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from google import genai
from google.genai import types

from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_MODEL_FAST,
    GEMINI_MODEL_STRONG,
    GEMINI_MODEL_SYNTHESIS,
    MAX_COUNCIL_SYNTHESIS_CHARS,
    RepoConfig,
)
from review_dimensions import (
    DEFAULT_REVIEW_DIMENSIONS,
    DimensionLevel,
    ReviewDimensions,
    diff_suggests_security_scrutiny,
    estimate_diff_tokens,
)

_client: genai.Client | None = None

_LARGE_DIFF_TOKENS = 5000


@dataclass
class ReviewLLMResult:
    """Parsed model output: inline comments, PR-level notes, and threads to resolve."""

    inline: list[dict] = field(default_factory=list)
    general_notes: list[str] = field(default_factory=list)
    resolve_comment_ids: list[int] = field(default_factory=list)


def _fast_model() -> str:
    return GEMINI_MODEL_FAST or GEMINI_MODEL


def _strong_model() -> str:
    return GEMINI_MODEL_STRONG or GEMINI_MODEL


def _synthesis_model() -> str:
    return GEMINI_MODEL_SYNTHESIS or GEMINI_MODEL


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set.")
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


_BASE_PROMPT = """You are an experienced code reviewer.

## Repo configuration
{repo_config}

## Dimension intensity (this pass)
{intensity_note}

## Extra instructions from the user (may be empty)
{extra_instructions}

## Repository layout (paths at PR head; generated/vendor paths omitted)
{tree_appendix}

## Prior Geckode inline threads (follow-up reviews — each id is a GitHub pull review comment)
{prior_threads}

{prior_followup_block}

## Commit messages
These describe what the developer was trying to accomplish:
{commits}

## Code changes (unified diff)
{diff}

## Your task
Return ONE JSON object with exactly these keys:
- "inline": array of objects, each with "file" (path as in diff b/ side), "line" (new-file line number), "comment" (actionable text).
- "general_notes": array of strings — repo layout, hierarchy, or files that should not exist when you cannot anchor to a single `+` line in the diff (may be empty).
- "resolve_comment_ids": array of integers — see rule below.

Inline rules:
- Each inline item must point to ONE specific changed line; only reference lines starting with `+` in the diff.
- Do not invent line numbers.
- For folder/layout concerns, prefer anchoring to the best related `+` line (e.g. import, config, first line of a touched file); otherwise put the finding in "general_notes".
- On follow-up reviews, omit inline items that are fixed; refine text where still applicable.

Resolve rules ({resolve_policy})

Match strictness to the configured repo level. At "low", flag only correctness bugs (within this dimension's scope).
If there is nothing to say, use "inline": [], "general_notes": [], and "resolve_comment_ids" per policy.
Respond with ONLY the JSON object. No prose, no markdown fences.
"""

_SPECIALIST_PROMPTS = {
    "security": """You are a security-focused reviewer. Flag injection, auth/authz issues, secrets, unsafe deserialization,
cryptographic mistakes, and OWASP-style problems. Ignore pure style unless it affects safety.
Output ONLY the JSON object schema described in the base task (inline, general_notes, resolve_comment_ids).""",
    "performance": """You are a performance-focused reviewer. Flag algorithmic complexity, unnecessary I/O,
memory churn, hot-path allocations, and obvious scalability issues. Ignore formatting.
Output ONLY the JSON object schema from the base task.""",
    "maintainability": """You are a maintainability / best-practices reviewer. Flag unclear naming, missing tests signals,
error handling gaps, API design smells, and duplication. Stay concrete and line-specific.
Output ONLY the JSON object schema from the base task.""",
}

_INTENSITY_NOTES: dict[str, dict[DimensionLevel, str]] = {
    "security": {
        "off": "(skipped)",
        "low": "Intensity: LOW — only flag clear security/correctness risks (injection, auth bypass, secret leaks). Skip minor hardening nits.",
        "normal": "Intensity: NORMAL — standard security review for this diff.",
        "high": "Intensity: HIGH — thorough OWASP-style review; include defense-in-depth and subtle auth/data exposure issues where relevant.",
    },
    "performance": {
        "off": "(skipped)",
        "low": "Intensity: LOW — only flag obvious performance regressions (O(n²) where linear expected, unbounded loops, N+1 queries).",
        "normal": "Intensity: NORMAL — typical performance review.",
        "high": "Intensity: HIGH — deep review of allocations, hot paths, concurrency, and scalability.",
    },
    "maintainability": {
        "off": "(skipped)",
        "low": "Intensity: LOW — only flag confusing names, missing error handling on obvious failure paths, and serious duplication.",
        "normal": "Intensity: NORMAL — standard maintainability review.",
        "high": "Intensity: HIGH — include API clarity, tests gaps signals, and style/consistency where it hurts readability.",
    },
}

_SYNTHESIS_PROMPT = """You merge specialist code-review findings into one JSON object.

## Repo configuration
{repo_config}

## Repository layout (paths at PR head)
{tree_appendix}

## Prior Geckode inline threads
{prior_threads}

{prior_followup_block}

## Commit summary
{commits}

## Specialist outputs (JSON objects with "inline" / "general_notes" — may overlap)
{specialist_blob}

## Task
Produce ONE JSON object with keys "inline", "general_notes", "resolve_comment_ids":
- "inline": merge and deduplicate by file+line; keep the clearest comment per line.
- "general_notes": merge unique strings (layout / cross-cutting points).
- "resolve_comment_ids": list integer IDs from Prior Geckode inline threads for findings that are fully addressed and should not stay open. Do not list an ID if you keep any inline comment on the same file:line (that line will be PATCHed instead). Only use IDs from the prior section. If several prior issues are clearly fixed, list **all** of their ids.

Rules:
- Preserve line numbers from specialist output; do not invent lines.
- On follow-up reviews: omit resolved inline items; **populate resolve_comment_ids** with every prior id whose feedback is clearly addressed in the current diff. Leaving `resolve_comment_ids` empty is correct only when no prior thread is clearly fixed yet.
- If nothing remains, use empty arrays.
Respond with ONLY the JSON object. No markdown fences.
"""


def format_commits(commits: list[dict]) -> str:
    if not commits:
        return "(none)"
    lines = []
    for c in commits:
        sha = c["sha"][:7]
        subject = c["commit"]["message"].split("\n", 1)[0]
        lines.append(f"- [{sha}] {subject}")
    return "\n".join(lines)


def _normalize_inline_items(raw: list) -> list[dict]:
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        if not all(k in item for k in ("file", "line", "comment")):
            continue
        out.append(
            {
                "file": str(item["file"]),
                "line": item["line"],
                "comment": str(item["comment"]),
            }
        )
    return out


def _parse_review_llm_result(text: str) -> ReviewLLMResult:
    """Parse JSON object (or legacy array) into structured review result."""
    if not (text or "").strip():
        return ReviewLLMResult()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return ReviewLLMResult()
    if isinstance(data, list):
        return ReviewLLMResult(inline=_normalize_inline_items(data))
    if not isinstance(data, dict):
        return ReviewLLMResult()
    inline_raw = data.get("inline")
    if not isinstance(inline_raw, list):
        inline_raw = []
    notes_raw = data.get("general_notes")
    if not isinstance(notes_raw, list):
        notes_raw = []
    notes = [str(x).strip() for x in notes_raw if str(x).strip()]
    rids_raw = data.get("resolve_comment_ids")
    if not isinstance(rids_raw, list):
        rids_raw = []
    rids: list[int] = []
    for x in rids_raw:
        try:
            rids.append(int(x))
        except (TypeError, ValueError):
            continue
    return ReviewLLMResult(
        inline=_normalize_inline_items(inline_raw),
        general_notes=notes,
        resolve_comment_ids=rids,
    )


_RESOLVE_POLICY_SINGLE = (
    "Include an integer in resolve_comment_ids only when that prior thread (matching id) is fully addressed. "
    "Do not list an id if you still leave inline feedback on the same file:line — that updates the thread instead. "
    "Only use ids listed under Prior Geckode inline threads."
)

_RESOLVE_POLICY_PARALLEL_SPECIALIST = (
    'Always use "resolve_comment_ids": [] — the synthesis step merges specialists and assigns resolutions.'
)


def _prior_followup_block(prior_snapshot_count: int) -> str:
    if prior_snapshot_count <= 0:
        return ""
    return (
        "## Follow-up requirement\n"
        f"There are **{prior_snapshot_count}** prior Geckode thread id(s) in the list above. "
        "For each one whose issue is **clearly fixed** in the current diff, you **must** add its numeric `id` to `resolve_comment_ids`. "
        "If you are not sure a thread is fully addressed, leave that id out. "
        "If the user asked to stop adding new feedback, keep new `inline` and `general_notes` empty or only for serious regressions.\n"
    )


def _pick_specialist_model(
    kind: str,
    level: DimensionLevel,
    diff_text: str,
) -> str:
    est = estimate_diff_tokens(diff_text)
    sensitive = diff_suggests_security_scrutiny(diff_text)
    large = est >= _LARGE_DIFF_TOKENS

    if kind == "security":
        if level == "low":
            return _fast_model()
        if level == "high":
            return _strong_model()
        # normal
        if sensitive or large:
            return _strong_model()
        return GEMINI_MODEL

    if kind in ("performance", "maintainability"):
        if level == "low":
            return _fast_model()
        if level == "high":
            return _strong_model() if GEMINI_MODEL_STRONG else GEMINI_MODEL
        return GEMINI_MODEL

    return GEMINI_MODEL


def review_pr(
    commits_text: str,
    diff_text: str,
    repo_config: RepoConfig,
    *,
    extra_instructions: str | None = None,
    use_council: bool = True,
    dimensions: ReviewDimensions | None = None,
    tree_appendix: str | None = None,
    prior_threads_block: str | None = None,
    prior_snapshot_count: int = 0,
) -> ReviewLLMResult:
    """Structured review: multi-agent council by default."""
    dims = dimensions if dimensions is not None else DEFAULT_REVIEW_DIMENSIONS
    if use_council:
        return review_pr_council(
            commits_text,
            diff_text,
            repo_config,
            extra_instructions=extra_instructions,
            dimensions=dims,
            tree_appendix=tree_appendix,
            prior_threads_block=prior_threads_block,
            prior_snapshot_count=prior_snapshot_count,
        )
    return _single_review(
        commits_text,
        diff_text,
        repo_config,
        extra_instructions=extra_instructions,
        tree_appendix=tree_appendix,
        prior_threads_block=prior_threads_block,
        prior_snapshot_count=prior_snapshot_count,
    )


def _single_review(
    commits_text: str,
    diff_text: str,
    repo_config: RepoConfig,
    *,
    extra_instructions: str | None = None,
    tree_appendix: str | None = None,
    prior_threads_block: str | None = None,
    prior_snapshot_count: int = 0,
) -> ReviewLLMResult:
    extra = (extra_instructions or "").strip() or "(none)"
    prompt = _BASE_PROMPT.format(
        repo_config=repo_config.as_prompt_section(),
        intensity_note="Intensity: N/A (single pass)",
        extra_instructions=extra,
        tree_appendix=tree_appendix or "(not available)",
        prior_threads=prior_threads_block or "(none — first review or no stored threads)",
        prior_followup_block=_prior_followup_block(prior_snapshot_count),
        resolve_policy=_RESOLVE_POLICY_SINGLE,
        commits=commits_text,
        diff=diff_text,
    )
    client = _get_client()
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    text = (response.text or "").strip()
    return _parse_review_llm_result(text)


def review_pr_council(
    commits_text: str,
    diff_text: str,
    repo_config: RepoConfig,
    *,
    extra_instructions: str | None = None,
    dimensions: ReviewDimensions | None = None,
    tree_appendix: str | None = None,
    prior_threads_block: str | None = None,
    prior_snapshot_count: int = 0,
) -> ReviewLLMResult:
    """Specialist passes (subset by dimension levels), optional synthesis."""
    dims = dimensions if dimensions is not None else DEFAULT_REVIEW_DIMENSIONS
    extra = (extra_instructions or "").strip() or "(none)"
    tree_txt = tree_appendix or "(not available)"
    prior_txt = prior_threads_block or "(none — first review or no stored threads)"
    follow_block = _prior_followup_block(prior_snapshot_count)

    active_kinds = [k for k in ("security", "performance", "maintainability") if dims[k] != "off"]
    if not active_kinds:
        return ReviewLLMResult()

    parallel = len(active_kinds) > 1
    resolve_pol = _RESOLVE_POLICY_PARALLEL_SPECIALIST if parallel else _RESOLVE_POLICY_SINGLE

    specialist_outputs: dict[str, str] = {}

    def run_specialist(kind: str) -> tuple[str, str]:
        level = dims[kind]
        intensity_note = _INTENSITY_NOTES[kind][level]
        base_ctx = _BASE_PROMPT.format(
            repo_config=repo_config.as_prompt_section(),
            intensity_note=intensity_note,
            extra_instructions=extra,
            tree_appendix=tree_txt,
            prior_threads=prior_txt,
            prior_followup_block=follow_block,
            resolve_policy=resolve_pol,
            commits=commits_text,
            diff=diff_text,
        )
        angle = _SPECIALIST_PROMPTS[kind]
        prompt = f"{angle}\n\n{base_ctx}"
        model = _pick_specialist_model(kind, level, diff_text)
        client = _get_client()
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return kind, (response.text or "").strip()

    max_workers = min(3, len(active_kinds))
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(run_specialist, k) for k in active_kinds]
        for fut in as_completed(futures):
            kind, text = fut.result()
            specialist_outputs[kind] = text

    if len(active_kinds) == 1:
        only = specialist_outputs[active_kinds[0]]
        return _parse_review_llm_result(only)

    parts = [
        f"### {kind}\n{txt}"
        for kind, txt in sorted(specialist_outputs.items())
    ]
    blob = "\n\n".join(parts)
    if len(blob) > MAX_COUNCIL_SYNTHESIS_CHARS:
        blob = blob[: MAX_COUNCIL_SYNTHESIS_CHARS // 2] + "\n\n[...specialist output truncated for synthesis budget...]\n"

    synth = _SYNTHESIS_PROMPT.format(
        repo_config=repo_config.as_prompt_section(),
        tree_appendix=tree_txt,
        prior_threads=prior_txt,
        prior_followup_block=follow_block,
        commits=commits_text,
        specialist_blob=blob,
    )
    client = _get_client()
    syn_resp = client.models.generate_content(
        model=_synthesis_model(),
        contents=synth,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return _parse_review_llm_result((syn_resp.text or "").strip())


_FALLBACK_FIXED_PROMPT = """You judge whether each prior finding from an aggregate PR comment has been FULLY addressed in the CURRENT unified diff.

Return ONE JSON object with exactly this shape:
{{ "fixed": [ true or false, ... ] }}

The array MUST have exactly {n} booleans in the same order as the items below.

Rules:
- TRUE only if the current diff clearly shows the issue is resolved (corrected code, removed bad pattern, or the finding is obsolete).
- FALSE if the issue likely remains, you are unsure, or the relevant lines are unchanged.

## Commit summary (context)
{commits}

## Items (same order as output booleans)
{items_block}

## Unified diff
{diff}

Respond with ONLY the JSON object. No markdown fences.
"""


def classify_fallback_items_fixed(
    filtered_diff: str,
    items: list[dict],
    *,
    commits_text: str = "",
    max_diff_chars: int = 48_000,
) -> list[bool] | None:
    """Return whether each parsed fallback item is fixed; None if the model call failed."""
    if not items:
        return []
    n = len(items)
    lines: list[str] = []
    for i, it in enumerate(items):
        excerpt = ((it.get("body") or "").replace("\r\n", "\n"))[:400].replace("\n", " ")
        ln = it.get("line")
        lines.append(f'{i}. `{it.get("path")}` line {ln} — {excerpt}')
    items_block = "\n".join(lines)
    diff_txt = filtered_diff if len(filtered_diff) <= max_diff_chars else (
        filtered_diff[: max_diff_chars // 2]
        + "\n\n[...diff truncated for classify step...]\n\n"
        + filtered_diff[-max_diff_chars // 2 :]
    )
    prompt = _FALLBACK_FIXED_PROMPT.format(
        n=n,
        commits=commits_text or "(none)",
        items_block=items_block,
        diff=diff_txt,
    )
    try:
        client = _get_client()
        resp = client.models.generate_content(
            model=_fast_model(),
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        raw = (resp.text or "").strip()
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        fixed_raw = data.get("fixed")
        if not isinstance(fixed_raw, list):
            return None
        out: list[bool] = []
        for x in fixed_raw[:n]:
            out.append(bool(x))
        while len(out) < n:
            out.append(False)
        return out[:n]
    except Exception:
        return None
