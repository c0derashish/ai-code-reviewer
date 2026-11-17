from pydantic import BaseModel, Field


class StartResponse(BaseModel):
    id: str
    status: str


class IssueOut(BaseModel):
    id: str
    file_path: str
    line: int
    severity: str
    category: str
    title: str
    explanation: str
    suggestion: str | None = None
    before: str | None = None
    after: str | None = None
    source: str | None = None  # extra. VEDIX ignores it
    rule: str | None = None    # extra. VEDIX ignores it


class ResultOut(BaseModel):
    id: str
    status: str                 # queued, running, done or failed
    score: float | None = None  # no quality score exists yet, so always null
    error: str | None = None
    issues: list[IssueOut] = Field(default_factory=list)
    summary: dict | None = None  # extra. VEDIX ignores it