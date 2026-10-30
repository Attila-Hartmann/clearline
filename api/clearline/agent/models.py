from typing import Literal

from pydantic import BaseModel, Field

Category = Literal["unauthorised_transaction", "card_dispute", "duplicate_charge", "fee_dispute", "atm_cash",
                   "loan_servicing", "account_closure", "service_quality", "data_protection", "other"]
Decision = Literal["uphold", "partial", "reject", "escalate"]


class Screen(BaseModel):
    is_injection: bool
    reason: str


class Triage(BaseModel):
    category: Category
    product: Literal["account", "card", "atm", "transfer", "loan", "branch", "data", "other"]
    is_payment_service: bool
    priority: Literal["low", "normal", "high"]
    vulnerable_signals: bool
    lang: Literal["hu", "en"]
    summary: str


class Extraction(BaseModel):
    customer_id: str | None = None
    card_last4: str | None = None
    transaction_refs: list[str] = Field(default_factory=list)
    amounts_huf: list[int] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    merchant: str | None = None
    customer_request: str = ""


class Assessment(BaseModel):
    decision: Decision
    refund_huf: int = Field(ge=0)
    goodwill_huf: int = Field(ge=0, le=5000)
    rationale: str
    rules_applied: list[str]
    risk_flags: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class Citation(BaseModel):
    marker: int
    chunk_id: str


class Draft(BaseModel):
    subject: str
    body: str
    citations: list[Citation] = Field(default_factory=list)


class ReviewDecision(BaseModel):
    action: Literal["approve", "edit", "reject"]
    body: str | None = None      # edited letter when action == edit
    reason: str | None = None    # required when action == reject
    reviewer: str = "demo-reviewer"
