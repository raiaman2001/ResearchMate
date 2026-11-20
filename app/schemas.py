"""Pydantic schemas: LLM se reliable structured output."""
from pydantic import BaseModel, Field


class Plan(BaseModel):
    sub_questions: list[str] = Field(
        min_length=1, max_length=6,
        description="3-4 alag, chhote, search-able sub-questions")


class Finding(BaseModel):
    claim: str = Field(description="Ek chhota factual claim, page me jo likha hai usi par based")
    source_url: str = Field(description="Wahi URL jahan se ye claim mila (exactly copy karo)")


class Findings(BaseModel):
    findings: list[Finding]
    gaps: str = Field(default="", description="Kya nahi mil paya (khali chhodo agar sab mil gaya)")


class ResearchNotes(BaseModel):
    sub_question: str
    findings: list[Finding]
    gaps: str = ""
    dropped: int = 0     # unverified source wale findings jo hata diye gaye
    stance: str | None = None    # debate mode: "pro" / "con"


# ---------- Stage 4 ----------
from typing import Literal  # noqa: E402


class Conflict(BaseModel):
    topic: str = Field(description="Kis topic/metric par conflict hai")
    claim_ids_a: list[int] = Field(description="Ek side ke finding numbers (F ke baad wala number)")
    claim_ids_b: list[int] = Field(description="Doosri side ke finding numbers")
    explanation: str = Field(description="Ek line me: kya clash ho raha hai")


class ConflictReport(BaseModel):
    conflicts: list[Conflict] = Field(default_factory=list)


class ClaimCheck(BaseModel):
    verdict: Literal["supported", "partial", "unsupported"]
    evidence_quote: str = Field(
        default="", description="Source se EXACT copy kiya hua chhota hissa jo claim ko support karta hai")
    reason: str = Field(description="Ek line ka karan")


# ---------- Stage 5 ----------
class DebatePlan(BaseModel):
    pro: list[str] = Field(min_length=1, max_length=3, description="PRO side ke liye search-able angles")
    con: list[str] = Field(min_length=1, max_length=3, description="CON side ke liye search-able angles")


class Triple(BaseModel):
    subject: str
    subject_type: str = "other"
    relation: str
    object: str
    object_type: str = "other"
    finding_id: int = Field(description="Finding ka F-number jisse ye relation nikla")


class TripleBatch(BaseModel):
    triples: list[Triple] = Field(default_factory=list)
