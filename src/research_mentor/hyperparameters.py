"""Process-wide tunables.

Edit this file to change scoring, retrieval, timeouts and limits for local debugging.
Environment variables on Settings still override the overlapping operator fields
(provider, database, upload root, demo mode, and the Settings-backed numbers).
"""

from __future__ import annotations

from typing import Final


# --- Check / scoring (product rule; bump SCORING_RULE_VERSION when changed) ---
SCORING_RULE_VERSION: Final = "v1.1"
CHECK_PASS_SCORE: Final = 6.0
MAX_CHECK_ROUNDS: Final = 5
SCORE_WEIGHTS: Final[dict[str, float]] = {
    "research_fit": 0.20,
    "novelty": 0.25,
    "research_value": 0.20,
    "testability_feasibility": 0.20,
    "evidence_support": 0.15,
}
CHECK_DIMENSION_FLOORS: Final[dict[str, float]] = {
    "research_fit": 3.5,
    "novelty": 3.0,
    "research_value": 3.0,
    "testability_feasibility": 3.0,
    "evidence_support": 2.5,
}
CHECK_REVISION_REQUEST_LIMIT: Final = 3

# --- Plan candidates ---
PLAN_CANDIDATE_COUNTS: Final[dict[str, int]] = {"low": 1, "mid": 2, "high": 3}
PLAN_CANDIDATE_MAX: Final = 3
PLAN_CANDIDATE_FOCUS_HINTS: Final[tuple[str, ...]] = (
    "最小可行、风险受控的验证路径",
    "强调研究增量与对照解释的平衡路径",
    "强调高信息增益与关键假设压力测试的路径",
)
if len(PLAN_CANDIDATE_FOCUS_HINTS) != PLAN_CANDIDATE_MAX:
    raise RuntimeError("PLAN_CANDIDATE_FOCUS_HINTS must match PLAN_CANDIDATE_MAX")

# --- Retrieval / context ---
RAG_RELEVANCE_THRESHOLD: Final = 0.3
WORKING_RETRIEVAL_TOP_K: Final = 10
RETRIEVAL_CANDIDATE_LIMIT: Final = 200
OPENALEX_DEFAULT_LIMIT: Final = 10
OPENALEX_PER_PAGE_CAP: Final = 50
OPENALEX_MAX_ATTEMPTS: Final = 3
SEARCH_PLAN_MAX_QUERIES: Final = 4
DOCUMENT_CHUNK_MAX_CHARS: Final = 4000
DOCUMENT_CHUNK_OVERLAP_CHARS: Final = 200
WORKING_CONTEXT_CHARACTER_BUDGET: Final = 12000
COMPACT_SUMMARY_MAX_CHARS: Final = 2000
COMPACT_SUMMARY_BUDGET_DENOMINATOR: Final = 4
EVIDENCE_PANEL_VISIBLE_LIMIT: Final = 12

# --- Text / upload limits ---
IDEA_TEXT_MAX_LENGTH: Final = 19999
PROJECT_TITLE_MAX_LENGTH: Final = 500
DOMAIN_MAX_LENGTH: Final = 200
UPLOAD_MAX_FILE_BYTES: Final = 10 * 1024 * 1024
UPLOAD_MAX_PROJECT_BYTES: Final = 100 * 1024 * 1024
UPLOAD_ALLOWED_MEDIA_TYPES: Final[tuple[str, ...]] = (
    "text/plain",
    "text/markdown",
    "text/x-markdown",
    "application/markdown",
    "application/pdf",
)
UPLOAD_ALLOWED_EXTENSIONS: Final[tuple[str, ...]] = (
    ".txt",
    ".md",
    ".markdown",
    ".pdf",
)

# --- Runtime ---
# mid/high 会并行调用多家 plan_loop；单次仍可能接近 3 分钟。
# run timeout 需覆盖一次慢调用 + 候选内一次重试。
MODEL_REQUEST_TIMEOUT_SECONDS: Final = 240.0
RUN_TIMEOUT_SECONDS: Final = 720.0
RUN_RETRY_LIMIT: Final = 3
SCHEMA_REPAIR_RETRY_LIMIT: Final = 2
RUN_LEASE_SECONDS: Final = 30.0
RUN_LEASE_RENEWAL_SECONDS: Final = 10.0
WORKER_POLL_INTERVAL_SECONDS: Final = 0.25
RETRY_BACKOFF_CAP_SECONDS: Final = 30
SSE_HEARTBEAT_INTERVAL_SECONDS: Final = 15.0
SSE_POLL_INTERVAL_SECONDS: Final = 1.0

SUPPORTED_DOMAINS: Final[tuple[str, ...]] = ("computer_science",)
SUPPORTED_DOMAIN_ALIASES: Final[tuple[str, ...]] = (
    "computer science",
    "cs",
    "计算机科学",
    "计算机",
)


def run_config_snapshot() -> dict[str, object]:
    """Frozen copy attached to each AgentRun for audit and replay."""
    return {
        "scoring_rule_version": SCORING_RULE_VERSION,
        "check_pass_score": CHECK_PASS_SCORE,
        "check_dimension_floors": dict(CHECK_DIMENSION_FLOORS),
        "score_weights": dict(SCORE_WEIGHTS),
        "max_check_rounds": MAX_CHECK_ROUNDS,
        "plan_candidate_counts": dict(PLAN_CANDIDATE_COUNTS),
        "rag_relevance_threshold": RAG_RELEVANCE_THRESHOLD,
        "working_retrieval_top_k": WORKING_RETRIEVAL_TOP_K,
        "retrieval_candidate_limit": RETRIEVAL_CANDIDATE_LIMIT,
        "document_chunk_max_chars": DOCUMENT_CHUNK_MAX_CHARS,
        "document_chunk_overlap_chars": DOCUMENT_CHUNK_OVERLAP_CHARS,
        "working_context_character_budget": WORKING_CONTEXT_CHARACTER_BUDGET,
        "compact_summary_max_chars": COMPACT_SUMMARY_MAX_CHARS,
        "model_request_timeout_seconds": MODEL_REQUEST_TIMEOUT_SECONDS,
        "run_timeout_seconds": RUN_TIMEOUT_SECONDS,
        "run_retry_limit": RUN_RETRY_LIMIT,
        "schema_repair_retry_limit": SCHEMA_REPAIR_RETRY_LIMIT,
        "run_lease_seconds": RUN_LEASE_SECONDS,
        "run_lease_renewal_seconds": RUN_LEASE_RENEWAL_SECONDS,
    }
