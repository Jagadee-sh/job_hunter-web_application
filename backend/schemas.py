from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class JobSearchRequest(BaseModel):
    target_roles: list[str] = Field(min_length=1)
    locations: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    preferred_companies: list[str] = Field(default_factory=list)


class CandidateProfile(JobSearchRequest):
    name: str = ""
    email: str = ""
    phone: str = ""
    years_experience: int = Field(default=0, ge=0)
    resume_path: str = ""


class HuntRequest(CandidateProfile):
    sources: list[str] = Field(default_factory=lambda: ["demo"])


class PreparedJob(BaseModel):
    job: JobResponse
    fit_score: float
    matched_skills: list[str]
    missing_information: list[str]
    application_mode: str


class HuntResponse(BaseModel):
    status: str
    candidate_ready: bool
    missing_profile_fields: list[str]
    matches: list[PreparedJob]
    report: dict[str, int]


class NaukriSearchRequest(BaseModel):
    target_roles: list[str] = Field(min_length=1)
    locations: list[str] = Field(default_factory=list)
    max_pages: int = Field(default=5, ge=1, le=20)


class NaukriJob(BaseModel):
    title: str
    company: str
    location: str
    description: str
    application_url: HttpUrl
    source: str = "naukri"


class NaukriSearchResponse(BaseModel):
    status: str
    reason: str | None = None
    jobs: list[NaukriJob]


class NaukriApplyRequest(BaseModel):
    job_url: HttpUrl
    values: dict[str, str] = Field(default_factory=dict)
    approved: bool = False


class NaukriApplyResponse(BaseModel):
    status: str
    reason: str


class LiveJobSearchRequest(BaseModel):
    target_roles: list[str] = Field(min_length=1)
    locations: list[str] = Field(default_factory=list)
    board_urls: list[HttpUrl] = Field(default_factory=list)
    limit: int = Field(default=30, ge=1, le=100)


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    company: str
    location: str
    salary: str | None
    description: str
    application_url: HttpUrl
    source: str


class ScoreResponse(BaseModel):
    job_id: UUID
    score: float
    rationale: str
    skill_gaps: list[str]


class ApplicationCreate(BaseModel):
    user_id: UUID
    job_id: UUID
    approved: bool = False


class ApplicationPrepareRequest(BaseModel):
    job_url: HttpUrl
    job_description: str = ""
    name: str
    email: str
    phone: str
    resume_path: str
    submit: bool = False
    approved: bool = False


class ApplicationPrepareResponse(BaseModel):
    status: str
    reason: str
    fields_filled: list[str] = Field(default_factory=list)
    fields_missing: list[str] = Field(default_factory=list)


class BatchApplicationRequest(BaseModel):
    jobs: list[dict[str, str]] = Field(min_length=1, max_length=30)
    name: str
    email: str
    phone: str
    resume_path: str
    approved: bool = False


class BatchApplicationResponse(BaseModel):
    attempted: int
    submitted: int
    skipped: int
    blocked: int
    review_required: int
    results: list[dict[str, object]]


class ResumeTailorRequest(BaseModel):
    base_resume_path: str
    output_docx: str
    output_pdf: str
    keywords: list[str] = Field(default_factory=list)


class ApplicationResponse(BaseModel):
    application_id: UUID
    status: str
    message: str


class ReportResponse(BaseModel):
    format: str
    metrics: dict[str, int]


class LiveHuntStartRequest(BaseModel):
    target_roles: list[str] = Field(default_factory=lambda: ["ML Engineer", "AI Engineer"])
    locations: list[str] = Field(default_factory=lambda: ["Hyderabad", "Remote"])
    name: str = "Maddi Jagadeesh"
    email: str = "new192975@gmail.com"
    phone: str = "9963475211"
    resume_path: str = ""
    auto_apply: bool = False
    sources: list[str] = Field(default_factory=lambda: ["jobicy", "arbeitnow"])
    max_jobs: int = Field(default=15, ge=1, le=50)
