from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Mode = Literal["pre_change", "incident"]


# ---------- knowledge ----------
class LNIRecord(BaseModel):
    id: str
    title: str = ""
    date: str = ""
    change_type: str = ""
    vendor: str = ""
    node: str = ""
    node_type: str = ""
    release: str = ""
    mop_id: str = ""
    mop_step: str = ""
    description: str = ""
    symptoms: str = ""
    error_signature: str = ""
    commands: str = ""
    root_cause: str = ""
    resolution: str = ""
    learning: str = ""
    outcome: str = ""
    severity: str = ""
    verified: bool = True
    source: str = "dataset"  # dataset | learning
    verified_by: str = ""
    success_count: int = 0
    related_ids: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_problem(self) -> bool:
        return bool(self.root_cause or self.resolution or self.symptoms)


class MopStep(BaseModel):
    no: int
    text: str


class MopDoc(BaseModel):
    mop_id: str
    title: str = ""
    node_type: str = ""
    vendor: str = ""
    steps: list[MopStep] = Field(default_factory=list)


class LogSnippet(BaseModel):
    id: str
    node: str = ""
    related_ids: list[str] = Field(default_factory=list)
    text: str


class Chunk(BaseModel):
    id: str
    record_id: str
    kind: Literal["lni", "mop", "log"]
    field: str
    text: str
    meta: dict[str, Any] = Field(default_factory=dict)


# ---------- agent ----------
class Fingerprint(BaseModel):
    nodes: list[str] = Field(default_factory=list)
    node_types: list[str] = Field(default_factory=list)
    vendors: list[str] = Field(default_factory=list)
    releases: list[str] = Field(default_factory=list)
    mop_ids: list[str] = Field(default_factory=list)
    mop_steps: list[int] = Field(default_factory=list)
    change_types: list[str] = Field(default_factory=list)
    error_signatures: list[str] = Field(default_factory=list)
    commands: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class Evidence(BaseModel):
    chunk_id: str
    field: str
    text: str
    score: float


class DuplicateRef(BaseModel):
    record_id: str
    confidence: int
    node: str = ""
    date: str = ""


class Match(BaseModel):
    record_id: str
    title: str
    confidence: int
    score: float = 0.0  # unrounded relevance used for ordering
    node: str = ""
    node_type: str = ""
    vendor: str = ""
    release: str = ""
    mop_id: str = ""
    mop_step: str = ""
    date: str = ""
    outcome: str = ""
    severity: str = ""
    root_cause: str = ""
    resolution: str = ""
    learning: str = ""
    verified: bool = True
    source: str = "dataset"
    success_count: int = 0
    reasons: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    duplicates: list[DuplicateRef] = Field(default_factory=list)

    @property
    def all_ids(self) -> list[str]:
        return [self.record_id] + [d.record_id for d in self.duplicates]


class Clarification(BaseModel):
    field: Literal["node", "mop_id", "release"]
    question: str
    options: list[str] = Field(default_factory=list)


class RecItem(BaseModel):
    kind: str  # cause | fix | precheck | pitfall | advice
    text: str
    citations: list[str]
    confidence: int | None = None


class MopStepAdvice(BaseModel):
    no: int
    text: str
    warnings: list[RecItem] = Field(default_factory=list)


class Risk(BaseModel):
    score: int
    level: Literal["Low", "Medium", "High"]
    reasons: list[str] = Field(default_factory=list)


class AgentEvent(BaseModel):
    type: str
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class Recommendation(BaseModel):
    status: Literal["ok", "needs_clarification", "no_match"]
    mode: Mode
    fingerprint: Fingerprint | None = None
    clarification: Clarification | None = None
    summary: str = ""
    items: list[RecItem] = Field(default_factory=list)
    prechecks: list[RecItem] = Field(default_factory=list)
    mop_id: str = ""
    mop_steps: list[MopStepAdvice] = Field(default_factory=list)
    matches: list[Match] = Field(default_factory=list)
    node_history: list[dict[str, Any]] = Field(default_factory=list)
    risk: Risk | None = None
    notification: dict[str, Any] | None = None
    llm_used: bool = False
    dropped_claims: list[str] = Field(default_factory=list)
    trace: list[AgentEvent] = Field(default_factory=list)


# ---------- API requests ----------
class Filters(BaseModel):
    node: str | None = None
    node_type: str | None = None
    vendor: str | None = None
    release: str | None = None
    mop_id: str | None = None

    def as_meta(self) -> dict[str, str]:
        return {k: v for k, v in self.model_dump().items() if v}


class IngestRequest(BaseModel):
    path: str | None = Field(None, description="Folder to ingest (default: data/raw). Ignored when records are given.")
    records: list[dict[str, Any]] | None = Field(None, description="Raw LNI records to add (any column names; mapped via field_map.yaml).")
    reset: bool = Field(True, description="Replace the dataset records (verified learnings are always kept).")


class IngestResponse(BaseModel):
    records: int
    learnings: int
    mops: int
    mop_steps: int
    logs: int
    chunks: int
    tickets: int
    seconds: float


class MatchRequest(BaseModel):
    text: str
    mode: Mode = "incident"
    filters: Filters = Field(default_factory=Filters)
    top_k: int = 5


class MatchResponse(BaseModel):
    fingerprint: Fingerprint
    matches: list[Match]
    no_match: bool
    threshold: int


class RecommendRequest(BaseModel):
    text: str = Field(..., description="Planned LNI description (pre_change) or symptoms / logs / commands (incident).")
    mode: Mode = "incident"
    node: str | None = None
    release: str | None = None
    mop_id: str | None = None
    skip_clarification: bool = False
    use_llm: bool = True
    notify: bool = True
    top_k: int = 5


class FeedbackRequest(BaseModel):
    incident_text: str
    verified_by: str
    matched_ids: list[str] = Field(default_factory=list)
    worked: bool = True
    title: str = ""
    verified_root_cause: str = ""
    verified_fix: str = ""
    learning: str = ""
    node: str = ""
    node_type: str = ""
    vendor: str = ""
    release: str = ""
    mop_id: str = ""
    ticket_id: str | None = None


class FeedbackResponse(BaseModel):
    message: str
    record: LNIRecord | None = None
    confirmed_ids: list[str] = Field(default_factory=list)
    ticket: dict[str, Any] | None = None
