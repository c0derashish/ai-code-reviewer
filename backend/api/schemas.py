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


class RepositoryRequest(BaseModel):
    url: str = Field(max_length=300)


class RepositoryStatusOut(BaseModel):
    id: str
    status: str                       # queued, running, done or failed
    project_name: str | None = None
    file_count: int | None = None
    skipped_count: int | None = None
    error: str | None = None
    licence: dict | None = None       # what GitHub says: status, spdx_id, name
    storage: str | None = None        # "full" or "link_only", known when the fetch is done
    storage_reason: str | None = None


class RepoFileOut(BaseModel):
    path: str
    language: str                     # Monaco language id, "plaintext" if unknown
    content: str


class RepositoryFilesOut(BaseModel):
    project_name: str
    files: list[RepoFileOut]


class RegisterRequest(BaseModel):
    name: str = Field(max_length=200)
    email: str = Field(max_length=400)
    password: str = Field(max_length=1000)


class LoginRequest(BaseModel):
    email: str = Field(max_length=400)
    password: str = Field(max_length=1000)


class DeleteAccountRequest(BaseModel):
    password: str = Field(max_length=1000)


class UserOut(BaseModel):
    id: str
    name: str
    email: str


class HistoryItemOut(BaseModel):
    id: str
    project_id: str
    project_name: str
    source: str                        # "upload" or "github"
    repo_url: str | None = None
    created_at: str                    # UTC, like 2026-11-20T10:00:00Z
    scope: str
    primary_language: str | None = None
    files: int
    files_analyzed: int
    loc: int                           # code lines of the analysed files
    issue_count: int
    rule_issue_count: int              # without the AI findings
    severity_counts: dict
    storage: str                       # "full" or "link_only"
    storage_reason: str | None = None
    licence: dict | None = None
    status: str = "done"


class HistoryDetailOut(HistoryItemOut):
    issues: list[IssueOut] = Field(default_factory=list)
    issues_stored: bool = True         # false when only the link is stored
    summary: dict | None = None


class AnalyticsOut(BaseModel):
    totals: dict
    severity: dict
    languages: list[dict]
    trend: list[dict]
    projects: list[dict]
    truncated: bool = False