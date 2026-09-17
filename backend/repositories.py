from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Job


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_user_preferences(self, roles: list[str], locations: list[str]) -> Sequence[Job]:
        query = select(Job).order_by(Job.created_at.desc()).limit(100)
        if roles:
            query = query.where(Job.title.ilike(f"%{roles[0]}%"))
        if locations:
            query = query.where(Job.location.ilike(f"%{locations[0]}%"))
        return (await self.session.scalars(query)).all()

    async def get(self, job_id: UUID) -> Job | None:
        return await self.session.get(Job, job_id)
