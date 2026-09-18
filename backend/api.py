from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.db import get_session, initialize_database
from backend.hunter_service import hunter_service
from backend.logging_config import configure_logging
from backend.live_jobs import LiveJobSourceError, search_arbeitnow, search_ats_boards
from backend.automation import ATSApplicationAutomation
from backend.resume import ResumeEngine
from backend.schemas import (
    ApplicationCreate,
    ApplicationPrepareRequest,
    ApplicationPrepareResponse,
    BatchApplicationRequest,
    BatchApplicationResponse,
    ApplicationResponse,
    HuntRequest,
    HuntResponse,
    JobResponse,
    JobSearchRequest,
    LiveHuntStartRequest,
    LiveJobSearchRequest,
    PreparedJob,
    ReportResponse,
    ResumeTailorRequest,
    ScoreResponse,
)
from backend.services import JobService

router = APIRouter()
ats_automation = ATSApplicationAutomation()
application_activity: list[dict[str, object]] = []
submitted_job_urls: set[str] = set()


@router.post("/profile/resume")
async def upload_resume(resume: UploadFile = File(...)) -> dict[str, str]:
    """Store a candidate's base DOCX resume for truthful, job-specific tailoring."""
    filename = Path(resume.filename or "resume.docx").name
    if Path(filename).suffix.lower() != ".docx":
        raise HTTPException(status_code=415, detail="Upload a DOCX resume so JobHunter can tailor it safely.")

    content = await resume.read()
    if not content or len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Resume must be a non-empty DOCX file smaller than 10 MB.")

    upload_dir = Path(".uploads")
    upload_dir.mkdir(exist_ok=True)
    stored_path = upload_dir / f"{uuid4()}-{filename}"
    stored_path.write_bytes(content)
    return {"resume_path": str(stored_path), "file_name": filename}


@router.post("/integrations/naukri/launch")
async def launch_naukri_browser() -> dict[str, Any]:
    """Open persistent browser for manual Naukri login/session handling."""
    return await hunter_service.naukri.open()


@router.get("/integrations/naukri/session")
async def get_naukri_session() -> dict[str, Any]:
    """Check whether the persistent browser is open and user is logged in."""
    return await hunter_service.naukri.check_login_status()


@router.post("/integrations/naukri/close")
async def close_naukri_browser() -> dict[str, Any]:
    """Close the persistent browser session."""
    return await hunter_service.naukri.close()


@router.post("/hunt/start")
async def start_autonomous_hunt(request: LiveHuntStartRequest) -> dict[str, Any]:
    """Start autonomous live job discovery, resume tailoring, and applying in background."""
    candidate_profile = {
        "name": request.name,
        "email": request.email,
        "phone": request.phone,
        "resume_path": request.resume_path,
        "target_roles": request.target_roles,
        "locations": request.locations,
    }
    return await hunter_service.start_hunt(
        target_roles=request.target_roles,
        locations=request.locations,
        candidate_profile=candidate_profile,
        auto_apply=request.auto_apply,
        sources=request.sources,
        max_jobs=request.max_jobs,
    )


@router.post("/hunt/stop")
async def stop_autonomous_hunt() -> dict[str, Any]:
    """Gracefully stop active job hunter."""
    return await hunter_service.stop_hunt()


@router.get("/hunt/status")
async def get_hunt_status() -> dict[str, Any]:
    """Get active stats, recent activity log, and current step."""
    return hunter_service.get_status()


@router.get("/hunt/stream")
async def stream_hunt_events() -> StreamingResponse:
    """Stream real-time Server-Sent Events (SSE) of hunting and application progress."""
    return StreamingResponse(
        hunter_service.subscribe(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/integrations/arbeitnow/search", response_model=list[JobResponse])
async def search_live_jobs(request: LiveJobSearchRequest) -> list[JobResponse]:
    try:
        configured_boards = [item.strip() for item in get_settings().job_board_urls.split(",") if item.strip()]
        board_urls = [str(url) for url in request.board_urls] or configured_boards
        jobs = await search_arbeitnow(request.target_roles, request.locations, request.limit)
        remaining = max(0, request.limit - len(jobs))
        jobs.extend(await search_ats_boards(board_urls, request.target_roles, request.locations, remaining))
    except LiveJobSourceError as error:
        from fastapi import HTTPException

        raise HTTPException(status_code=502, detail=str(error)) from error
    return [JobResponse.model_validate(job) for job in jobs]


@router.post("/applications/prepare", response_model=ApplicationPrepareResponse)
async def prepare_application(request: ApplicationPrepareRequest) -> ApplicationPrepareResponse:
    if str(request.job_url) in submitted_job_urls:
        return ApplicationPrepareResponse(status="skipped", reason="This job was already submitted in the current session.")
    result = await ats_automation.prepare(
        str(request.job_url),
        {"name": request.name, "email": request.email, "phone": request.phone, "job_description": request.job_description},
        request.resume_path,
        request.submit and request.approved,
    )
    if result.get("status") == "submitted":
        submitted_job_urls.add(str(request.job_url))
    activity = {
        "job_url": str(request.job_url),
        "status": str(result.get("status", "unknown")),
        "reason": str(result.get("reason", "")),
        "fields_filled": result.get("fields_filled", []),
        "fields_missing": result.get("fields_missing", []),
    }
    application_activity.append(activity)
    return ApplicationPrepareResponse.model_validate(result)


@router.get("/applications/activity")
async def application_activity_report() -> dict[str, object]:
    counts = {"ready_for_review": 0, "submitted": 0, "blocked": 0, "review_required": 0, "browser_error": 0}
    for item in application_activity:
        status = str(item.get("status", ""))
        if status in counts:
            counts[status] += 1
    return {"counts": counts, "applications": application_activity[-50:]}


@router.post("/applications/batch", response_model=BatchApplicationResponse)
async def apply_batch(request: BatchApplicationRequest) -> BatchApplicationResponse:
    results: list[dict[str, object]] = []
    for job in request.jobs:
        job_url = str(job.get("application_url", ""))
        if not job_url:
            continue
        if job_url in submitted_job_urls:
            results.append({"job_url": job_url, "status": "skipped", "reason": "Already submitted in this session."})
            continue
        result = await ats_automation.prepare(
            job_url,
            {"name": request.name, "email": request.email, "phone": request.phone, "job_description": str(job.get("description", ""))},
            request.resume_path,
            request.approved,
        )
        result_with_job = {"job_url": job_url, **result}
        results.append(result_with_job)
        if result.get("status") == "submitted":
            submitted_job_urls.add(job_url)
        application_activity.append(result_with_job)
    counts = {"submitted": 0, "skipped": 0, "blocked": 0, "review_required": 0}
    for result in results:
        status = str(result.get("status", ""))
        if status in counts:
            counts[status] += 1
    return BatchApplicationResponse(attempted=len(results), **counts, results=results)


@router.post("/jobs/search", response_model=list[JobResponse])
async def search_jobs(
    request: JobSearchRequest, session: AsyncSession = Depends(get_session)
) -> list[JobResponse]:
    return [JobResponse.model_validate(job) for job in await JobService(session).search(request)]


@router.post("/hunt/prepare", response_model=HuntResponse)
async def prepare_hunt(
    request: HuntRequest, session: AsyncSession = Depends(get_session)
) -> HuntResponse:
    jobs = await JobService(session).search(request)
    missing_profile_fields = [
        field
        for field, value in {
            "name": request.name,
            "email": request.email,
            "phone": request.phone,
            "resume_path": request.resume_path,
        }.items()
        if not value
    ]
    prepared: list[PreparedJob] = []
    for job in jobs:
        job_text = f"{job.title} {job.description}".lower()
        matched_skills = [skill for skill in request.skills if skill.lower() in job_text]
        role_match = any(role.lower() in job_text for role in request.target_roles)
        fit_score = min(99.0, 55.0 + (25.0 if role_match else 0.0) + min(20.0, len(matched_skills) * 5.0))
        missing = list(missing_profile_fields)
        if not request.skills:
            missing.append("skills")
        prepared.append(
            PreparedJob(
                job=JobResponse.model_validate(job),
                fit_score=fit_score,
                matched_skills=matched_skills,
                missing_information=missing,
                application_mode="manual_review_required",
            )
        )
    return HuntResponse(
        status="ready_for_review",
        candidate_ready=not missing_profile_fields,
        missing_profile_fields=missing_profile_fields,
        matches=prepared,
        report={
            "jobs_found": len(prepared),
            "jobs_scored": len(prepared),
            "applications_started": 0,
            "applications_completed": 0,
            "applications_failed": 0,
            "applications_skipped": 0,
            "resume_versions_generated": 0,
        },
    )


@router.post("/jobs/score", response_model=ScoreResponse)
async def score_job(request: dict[str, str]) -> ScoreResponse:
    from backend.ai import AIService

    result = await AIService().complete_json(
        "Return JSON with score from 0 to 100, rationale, and skill_gaps.",
        f"JOB:\n{request.get('job_description', '')}\nPROFILE:\n{request.get('candidate_profile', '')}",
    )
    from uuid import UUID

    return ScoreResponse(job_id=UUID(request["job_id"]), score=float(result.get("score", 0)), rationale=str(result.get("rationale", "")), skill_gaps=[str(item) for item in result.get("skill_gaps", [])])


@router.post("/resume/tailor")
async def tailor_resume(request: ResumeTailorRequest) -> dict[str, str]:
    ResumeEngine().tailor(Path(request.base_resume_path), Path(request.output_docx), Path(request.output_pdf), request.keywords)
    return {"docx": request.output_docx, "pdf": request.output_pdf, "status": "generated"}


@router.post("/applications", response_model=ApplicationResponse)
async def create_application(request: ApplicationCreate) -> ApplicationResponse:
    status = "ready_for_submission" if request.approved else "awaiting_user_approval"
    message = "Ready for browser submission after approval." if request.approved else "Prepared, but explicit approval is required before browser submission."
    return ApplicationResponse(application_id=request.job_id, status=status, message=message)


@router.get("/reports", response_model=ReportResponse)
async def report(format: str = "json") -> ReportResponse:
    return ReportResponse(format=format, metrics={"jobs_found": 0, "jobs_scored": 0, "applications_started": 0, "applications_completed": 0, "applications_failed": 0, "applications_skipped": 0, "resume_versions_generated": 0})


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

@router.get("/api")
async def root():
    return {
        "status": "running",
        "app": "JobHunter AI"
    }

def create_app() -> FastAPI:
    configure_logging(get_settings().log_level)
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await initialize_database()
        yield

    application = FastAPI(title="JobHunter AI", version="0.1.0", lifespan=lifespan)
    application.include_router(router)
    
    # Serve frontend static files
    frontend_dist = Path("frontend/dist")
    if frontend_dist.exists():
        application.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
    
    return application


app = create_app()
