from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from backend.config import get_settings


class Base(DeclarativeBase):
    pass


database_url = get_settings().database_url
if database_url.startswith("sqlite+aiosqlite"):
    engine_options = {"pool_pre_ping": True, "connect_args": {"check_same_thread": False}}
else:
    engine_options = {"pool_pre_ping": True}

engine: AsyncEngine = create_async_engine(database_url, **engine_options)
session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        yield session


async def initialize_database() -> None:
    from backend.models import Job

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        if await session.scalar(select(Job.id).limit(1)) is not None:
            return
        session.add_all(
            [
                Job(
                    id=uuid4(),
                    external_id="northstar-senior-product-designer",
                    source="demo",
                    title="Senior Product Designer",
                    company="Northstar Labs",
                    location="Remote",
                    salary="$145k-$175k",
                    description="Lead product design for a collaborative analytics platform used by growing teams.",
                    application_url="https://example.com/jobs/northstar-senior-product-designer",
                    created_at=datetime.now(UTC),
                ),
                Job(
                    id=uuid4(),
                    external_id="atelier-design-systems-lead",
                    source="demo",
                    title="Design Systems Lead",
                    company="Atelier Works",
                    location="New York, NY",
                    salary="$155k-$190k",
                    description="Own the design system and help product teams ship consistent, accessible experiences.",
                    application_url="https://example.com/jobs/atelier-design-systems-lead",
                    created_at=datetime.now(UTC),
                ),
                Job(
                    id=uuid4(),
                    external_id="meridian-ai-product-designer",
                    source="demo",
                    title="Product Designer, AI",
                    company="Meridian",
                    location="San Francisco, CA",
                    salary="$160k-$205k",
                    description="Design clear, trustworthy workflows for an AI productivity product.",
                    application_url="https://example.com/jobs/meridian-ai-product-designer",
                    created_at=datetime.now(UTC),
                ),
            ]
        )
        await session.commit()
