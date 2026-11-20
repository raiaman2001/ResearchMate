"""RunResult + errors (graph aur pipeline dono use karte hain)."""
from dataclasses import dataclass, field

from app.llm import StructuredOutputError


class RunFailed(Exception):
    """Expected failure (jaise koi finding nahi mili): user ko message dikhana hai, traceback nahi."""


@dataclass
class RunResult:
    ok: bool
    topic: str
    report: str = ""                       # final markdown (sab sections ke saath)
    plan: list = field(default_factory=list)
    sources: list = field(default_factory=list)
    trace: list = field(default_factory=list)          # har LLM call (latency, tokens, cost)
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    elapsed: float = 0.0
    cache_hits: int = 0
    failed_questions: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    run_id: int | None = None
    file_path: str | None = None
    error: str | None = None
    # Stage 4
    claim_checks: list = field(default_factory=list)
    source_scores: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)
    confidence_label: str = "Not verified"
    confidence_score: float | None = None
    retries: int = 0
    verify_first: dict = field(default_factory=dict)
    verify_final: dict = field(default_factory=dict)
    limitations: list = field(default_factory=list)
    # Stage 5
    mode: str = "standard"
    events: list = field(default_factory=list)         # activity trace (kya search kiya, kya reject hua...)
    memory_reused: int = 0
    kg_added: int = 0
    debate_stats: dict = field(default_factory=dict)
    # Stage 6
    language: str = "en"
    body: str = field(default="", repr=False)              # final writer output (tags/sections ke bina)
    first_body: str = field(default="", repr=False)        # pehla draft (verifier loop se pehle): eval ke liye
    source_texts: dict = field(default_factory=dict, repr=False)   # {id: (url, text)}: eval judge ke liye


def friendly_error(e):
    if isinstance(e, RunFailed):
        return str(e)
    err_type = type(e).__name__
    err_msg = str(e)
    if "AuthenticationError" in err_type or "API_KEY_INVALID" in err_msg or "INVALID_ARGUMENT" in err_msg and "key" in err_msg.lower():
        return "Invalid API key. Please check your .env file."
    if "RateLimitError" in err_type or "RATE_LIMIT" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "429" in err_msg:
        return f"Rate limit exceeded: {err_msg}"
    if "APIError" in err_type:
        return f"API error: {e}"
    if isinstance(e, StructuredOutputError):
        return f"LLM failed to return structured output: {e}"
    return f"Unexpected error: {e}"
