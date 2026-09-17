from celery import Celery  # type: ignore[import-untyped]

from backend.config import get_settings

celery_app = Celery("jobhunter", broker=get_settings().redis_url, backend=get_settings().redis_url)


@celery_app.task(name="jobhunter.sync_jobs")  # type: ignore[untyped-decorator]
def sync_jobs_task(sources: list[str]) -> dict[str, object]:
    return {"sources": sources, "status": "completed"}
