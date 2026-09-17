from typing import Any
from uuid import UUID

from fastmcp import FastMCP

from backend.ai import AIService

mcp = FastMCP("JobHunter AI")


@mcp.tool()
async def search_jobs(target_roles: list[str], locations: list[str], skills: list[str]) -> dict[str, Any]:
    """Search configured job-board connectors using normalized preferences."""
    return {"status": "queued", "target_roles": target_roles, "locations": locations, "skills": skills}


@mcp.tool()
async def extract_job(application_url: str) -> dict[str, str]:
    """Extract and normalize a job description from an application URL."""
    return {"application_url": application_url, "status": "ready_for_connector"}


@mcp.tool()
async def score_job(job_description: str, candidate_profile: str) -> dict[str, Any]:
    """Score a job against a candidate profile with structured AI output."""
    return await AIService().complete_json(
        "Return JSON with score from 0 to 100, rationale, and skill_gaps.",
        f"JOB:\n{job_description}\nPROFILE:\n{candidate_profile}",
    )


@mcp.tool()
async def tailor_resume(base_resume_path: str, job_description: str) -> dict[str, str]:
    """Create a truthful tailored resume artifact for a job."""
    return {"base_resume_path": base_resume_path, "job_description": job_description, "status": "queued"}


@mcp.tool()
async def generate_cover_letter(candidate_profile: str, job_description: str) -> str:
    """Generate a concise, truthful cover letter."""
    result = await AIService().complete_json(
        "Return JSON with a single cover_letter string. Never invent candidate facts.",
        f"PROFILE:\n{candidate_profile}\nJOB:\n{job_description}",
    )
    return str(result.get("cover_letter", ""))


@mcp.tool()
async def generate_answers(questions: list[str], candidate_profile: str) -> dict[str, str]:
    """Generate truthful answers for application questions."""
    result = await AIService().complete_json(
        "Return JSON mapping each question to an answer; use an empty string when facts are missing.",
        f"QUESTIONS:\n{questions}\nPROFILE:\n{candidate_profile}",
    )
    return {str(key): str(value) for key, value in result.items()}


@mcp.tool()
async def apply_job(application_id: UUID, approved: bool) -> dict[str, Any]:
    """Prepare or submit an application; submission requires explicit approval."""
    if not approved:
        return {"application_id": str(application_id), "status": "awaiting_user_approval"}
    return {"application_id": str(application_id), "status": "ready_for_browser_submission"}


@mcp.tool()
async def track_application(application_id: UUID, status: str, notes: str = "") -> dict[str, str]:
    """Record an application status update."""
    return {"application_id": str(application_id), "status": status, "notes": notes}


@mcp.tool()
async def generate_report(user_id: UUID, format: str = "json") -> dict[str, Any]:
    """Generate application analytics in JSON, CSV, or HTML format."""
    return {"user_id": str(user_id), "format": format, "metrics": {}}


@mcp.tool()
async def sync_jobs(sources: list[str]) -> dict[str, Any]:
    """Synchronize jobs from supported ATS sources."""
    supported = {"greenhouse", "lever", "ashby", "workday", "smartrecruiters"}
    return {"sources": [source for source in sources if source in supported], "status": "queued"}


if __name__ == "__main__":
    mcp.run()
