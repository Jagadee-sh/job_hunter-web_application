from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Job
from backend.repositories import JobRepository
from backend.schemas import JobSearchRequest


class JobService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = JobRepository(session)

    async def search(self, request: JobSearchRequest) -> list[Job]:
        jobs = await self.repository.list_for_user_preferences(request.target_roles, request.locations)
        return list(jobs)

    async def require_job(self, job_id: UUID) -> Job:
        job = await self.repository.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return job
