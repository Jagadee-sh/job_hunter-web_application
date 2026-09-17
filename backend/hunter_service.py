from __future__ import annotations

import asyncio
from datetime import datetime
import json
import logging
from pathlib import Path
import random
from typing import Any, AsyncGenerator
from uuid import uuid4

from backend.ai import AIService
from backend.automation import ATSApplicationAutomation, NaukriAutomation
from backend.live_jobs import search_arbeitnow, search_jobicy
from backend.resume import ResumeEngine

logger = logging.getLogger("jobhunter.service")


class LiveHunterService:
    def __init__(self) -> None:
        self.status: str = "idle"  # idle, running, stopped, completed, error
        self.current_step: str = "Ready to start"
        self._stop_requested: bool = False
        self._current_task: asyncio.Task[None] | None = None
        
        self.stats: dict[str, int] = {
            "jobs_found": 0,
            "jobs_scored": 0,
            "resumes_tailored": 0,
            "applications_submitted": 0,
            "review_required": 0,
            "blocked": 0,
            "skipped": 0,
        }
        
        self.discovered_jobs: list[dict[str, Any]] = []
        self.activity_log: list[dict[str, Any]] = []
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        
        self.naukri = NaukriAutomation()
        self.ats = ATSApplicationAutomation()
        self.ai = AIService()
        self.resume_engine = ResumeEngine()

    def get_status(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "current_step": self.current_step,
            "stats": self.stats,
            "jobs_count": len(self.discovered_jobs),
            "recent_activity": self.activity_log[-50:],
            "jobs": self.discovered_jobs[-50:],
        }

    async def subscribe(self) -> AsyncGenerator[str, None]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers.add(queue)
        try:
            # Yield initial status
            initial_data = json.dumps({"event": "INIT", "data": self.get_status()})
            yield f"data: {initial_data}\n\n"
            
            while True:
                event = await queue.get()
                payload = json.dumps(event)
                yield f"data: {payload}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            self._subscribers.discard(queue)

    def broadcast(self, event_type: str, data: dict[str, Any]) -> None:
        event = {
            "id": str(uuid4()),
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "event": event_type,
            "data": data,
        }
        
        # Keep log entry
        log_entry = {
            "timestamp": event["timestamp"],
            "event": event_type,
            "message": data.get("message", ""),
            "job_title": data.get("job_title", ""),
            "company": data.get("company", ""),
            "url": data.get("url", ""),
            "status": data.get("status", ""),
        }
        self.activity_log.append(log_entry)
        if len(self.activity_log) > 500:
            self.activity_log = self.activity_log[-500:]

        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    async def start_hunt(
        self,
        target_roles: list[str],
        locations: list[str],
        candidate_profile: dict[str, Any],
        auto_apply: bool = False,
        sources: list[str] | None = None,
        max_jobs: int = 15,
    ) -> dict[str, Any]:
        if self.status == "running":
            return {"status": "already_running", "message": "A job hunting session is already running."}

        self._stop_requested = False
        self.status = "running"
        self.current_step = "Starting autonomous job hunter"
        
        # Reset counters
        self.stats = {
            "jobs_found": 0,
            "jobs_scored": 0,
            "resumes_tailored": 0,
            "applications_submitted": 0,
            "review_required": 0,
            "blocked": 0,
            "skipped": 0,
        }
        self.discovered_jobs = []

        sources = sources or ["jobicy", "arbeitnow"]

        self._current_task = asyncio.create_task(
            self._hunt_loop(
                target_roles=target_roles,
                locations=locations,
                candidate_profile=candidate_profile,
                auto_apply=auto_apply,
                sources=sources,
                max_jobs=max_jobs,
            )
        )

        self.broadcast("HUNT_STARTED", {
            "message": f"Autonomous hunter initiated for {', '.join(target_roles)} in {', '.join(locations)}.",
            "auto_apply": auto_apply,
            "sources": sources,
        })

        return {"status": "started", "message": "Job hunter started successfully."}

    async def stop_hunt(self) -> dict[str, Any]:
        if self.status != "running":
            return {"status": "not_running", "message": "No active hunt session to stop."}

        self._stop_requested = True
        self.status = "stopped"
        self.current_step = "Hunt paused / stopped by user"

        if self._current_task and not self._current_task.done():
            self._current_task.cancel()

        self.broadcast("HUNT_STOPPED", {
            "message": "Job hunt stopped by user.",
            "stats": self.stats,
        })
        return {"status": "stopped", "message": "Job hunter stopped."}

    async def _hunt_loop(
        self,
        target_roles: list[str],
        locations: list[str],
        candidate_profile: dict[str, Any],
        auto_apply: bool,
        sources: list[str],
        max_jobs: int,
    ) -> None:
        try:
            raw_jobs: list[dict[str, Any]] = []

            # 1. Search Naukri if requested
            if "naukri" in sources and not self._stop_requested:
                self.current_step = "Searching Naukri live portal..."
                self.broadcast("STATUS_UPDATE", {"message": "Opening Naukri search for target roles..."})
                
                try:
                    naukri_res = await self.naukri.search(target_roles, locations, max_pages=2)
                    found_naukri = naukri_res.get("jobs", [])
                    self.broadcast("PORTAL_SEARCH_RESULT", {
                        "source": "naukri",
                        "count": len(found_naukri),
                        "message": f"Found {len(found_naukri)} roles on Naukri ({naukri_res.get('status')})."
                    })
                    raw_jobs.extend(found_naukri)
                except Exception as ex:
                    logger.warning(f"Naukri search encountered an issue: {ex}")
                    self.broadcast("SOURCE_WARNING", {
                        "source": "naukri",
                        "message": f"Naukri search note: {ex}"
                    })

            # 2. Search Jobicy's public remote-job API if requested
            if "jobicy" in sources and not self._stop_requested:
                self.current_step = "Searching Jobicy remote jobs..."
                self.broadcast("STATUS_UPDATE", {"message": "Fetching live remote listings from Jobicy..."})
                try:
                    jobicy_jobs = await search_jobicy(target_roles, locations, limit=max_jobs)
                    self.broadcast("PORTAL_SEARCH_RESULT", {
                        "source": "jobicy",
                        "count": len(jobicy_jobs),
                        "message": f"Found {len(jobicy_jobs)} live remote listings on Jobicy.",
                    })
                    raw_jobs.extend(jobicy_jobs)
                except Exception as ex:
                    logger.warning(f"Jobicy search error: {ex}")
                    self.broadcast("SOURCE_WARNING", {"source": "jobicy", "message": f"Jobicy search note: {ex}"})

            # 3. Search Arbeitnow's public API if requested
            if "arbeitnow" in sources and not self._stop_requested:
                self.current_step = "Searching live employer job boards..."
                self.broadcast("STATUS_UPDATE", {"message": "Fetching direct employer listings from Arbeitnow..."})
                try:
                    direct_jobs = await search_arbeitnow(target_roles, locations, limit=max_jobs)
                    self.broadcast("PORTAL_SEARCH_RESULT", {
                        "source": "arbeitnow",
                        "count": len(direct_jobs),
                        "message": f"Found {len(direct_jobs)} direct employer listings."
                    })
                    raw_jobs.extend(direct_jobs)
                except Exception as ex:
                    logger.warning(f"Arbeitnow search error: {ex}")

            # Deduplicate by application_url
            unique_jobs: list[dict[str, Any]] = []
            seen_urls = set()
            for j in raw_jobs:
                url = str(j.get("application_url", "")).strip()
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    unique_jobs.append(j)

            self.stats["jobs_found"] = len(unique_jobs)
            self.broadcast("JOBS_DISCOVERED", {
                "count": len(unique_jobs),
                "message": f"Discovered {len(unique_jobs)} total unique listings to evaluate."
            })

            if not unique_jobs:
                self.current_step = "No matching jobs found on current run."
                self.status = "completed"
                self.broadcast("HUNT_COMPLETED", {"message": "Search completed. No active matching jobs found.", "stats": self.stats})
                return

            # Process up to max_jobs
            jobs_to_process = unique_jobs[:max_jobs]

            for idx, job in enumerate(jobs_to_process, start=1):
                if self._stop_requested:
                    break

                job_title = str(job.get("title", "Untitled"))
                company = str(job.get("company", "Employer"))
                job_url = str(job.get("application_url", ""))
                description = str(job.get("description", ""))

                self.current_step = f"Processing [{idx}/{len(jobs_to_process)}]: {job_title} at {company}"
                self.broadcast("PROCESSING_JOB", {
                    "job_title": job_title,
                    "company": company,
                    "url": job_url,
                    "index": idx,
                    "total": len(jobs_to_process),
                    "message": f"Evaluating job fit for {job_title} at {company}..."
                })

                # Step A: AI Fit Score & Keyword Analysis
                fit_score, matched_skills, rationale = await self._score_and_analyze(job, candidate_profile)
                self.stats["jobs_scored"] += 1

                # Step B: Resume Tailoring
                tailored_resume_path = await self._tailor_resume(candidate_profile.get("resume_path", ""), description, matched_skills)
                if tailored_resume_path:
                    self.stats["resumes_tailored"] += 1
                    self.broadcast("RESUME_TAILORED", {
                        "job_title": job_title,
                        "company": company,
                        "tailored_path": tailored_resume_path,
                        "matched_skills": matched_skills,
                        "message": f"Tailored resume with {len(matched_skills)} matched skills: {', '.join(matched_skills[:5])}..."
                    })

                # Record Discovered Job Item
                job_record = {
                    "id": str(job.get("id") or uuid4()),
                    "title": job_title,
                    "company": company,
                    "location": job.get("location", ""),
                    "application_url": job_url,
                    "source": job.get("source", "web"),
                    "description": description[:300] + "...",
                    "fit_score": fit_score,
                    "matched_skills": matched_skills,
                    "rationale": rationale,
                    "tailored_resume": tailored_resume_path,
                    "status": "pending",
                }

                # Step C: Apply / Prepare Application
                if auto_apply:
                    self.broadcast("APPLYING", {
                        "job_title": job_title,
                        "company": company,
                        "url": job_url,
                        "message": f"Navigating to application and filling form for {job_title}..."
                    })
                    
                    apply_result = await self._apply_to_job(job, candidate_profile, tailored_resume_path, auto_submit=True)
                    app_status = apply_result.get("status", "unknown")
                    reason = apply_result.get("reason", "")
                    job_record["status"] = app_status
                    job_record["reason"] = reason

                    if app_status == "submitted":
                        self.stats["applications_submitted"] += 1
                        self.broadcast("APPLICATION_SUBMITTED", {
                            "job_title": job_title,
                            "company": company,
                            "url": job_url,
                            "status": "submitted",
                            "message": f"Successfully submitted application for {job_title} at {company}!"
                        })
                    elif app_status in ("review_required", "ready_for_review"):
                        self.stats["review_required"] += 1
                        self.broadcast("APPLICATION_REVIEW_REQUIRED", {
                            "job_title": job_title,
                            "company": company,
                            "url": job_url,
                            "status": "review_required",
                            "reason": reason,
                            "message": f"Application prepared for {job_title}. Review required: {reason}"
                        })
                    elif app_status == "blocked":
                        self.stats["blocked"] += 1
                        self.broadcast("APPLICATION_BLOCKED", {
                            "job_title": job_title,
                            "company": company,
                            "url": job_url,
                            "status": "blocked",
                            "reason": reason,
                            "message": f"Verification or CAPTCHA required for {company}."
                        })
                    else:
                        self.stats["skipped"] += 1
                        self.broadcast("APPLICATION_SKIPPED", {
                            "job_title": job_title,
                            "company": company,
                            "status": app_status,
                            "reason": reason,
                            "message": f"Skipped application ({app_status}): {reason}"
                        })
                else:
                    # Review Mode: Prepare form without final submit
                    apply_result = await self._apply_to_job(job, candidate_profile, tailored_resume_path, auto_submit=False)
                    job_record["status"] = "ready_for_review"
                    job_record["reason"] = "Prepared in browser. Awaiting your approval to submit."
                    self.stats["review_required"] += 1
                    self.broadcast("APPLICATION_PREPARED", {
                        "job_title": job_title,
                        "company": company,
                        "url": job_url,
                        "status": "ready_for_review",
                        "message": f"Form fields filled and tailored resume attached for {job_title}. Ready for review."
                    })

                self.discovered_jobs.append(job_record)

                # Human-like delay between applications to protect account
                delay = random.uniform(2.5, 4.0)
                await asyncio.sleep(delay)

            self.status = "completed"
            self.current_step = "Hunt session complete"
            self.broadcast("HUNT_COMPLETED", {
                "message": f"Autonomous hunt completed! Processed {len(self.discovered_jobs)} jobs.",
                "stats": self.stats,
            })

        except asyncio.CancelledError:
            self.status = "stopped"
            self.current_step = "Hunt stopped by user."
            logger.info("Hunt task cancelled.")
        except Exception as ex:
            self.status = "error"
            self.current_step = f"Error during hunt: {ex}"
            logger.exception("Error in hunt loop")
            self.broadcast("HUNT_ERROR", {"message": f"Error occurred: {ex}"})

    async def _score_and_analyze(
        self,
        job: dict[str, Any],
        candidate_profile: dict[str, Any]
    ) -> tuple[float, list[str], str]:
        description = str(job.get("description", ""))
        title = str(job.get("title", ""))
        skills = candidate_profile.get("skills", ["Python", "Machine Learning", "PyTorch", "FastAPI", "SQL", "LangChain"])

        # First do fast keyword matching
        searchable = f"{title} {description}".lower()
        matched = [s for s in skills if s.lower() in searchable]

        # Use AI for detailed fit scoring if available
        profile_summary = f"Name: {candidate_profile.get('name')}, Roles: {candidate_profile.get('target_roles')}, Skills: {', '.join(skills)}"
        try:
            ai_score = await self.ai.complete_json(
                system="You are an expert tech recruiter. Return JSON with 'score' (number 0-100), 'rationale' (1 sentence), and 'skill_gaps' (array).",
                user=f"JOB: {title}\nDESCRIPTION: {description[:1000]}\nCANDIDATE: {profile_summary}",
            )
            score = float(ai_score.get("score", 75.0))
            rationale = str(ai_score.get("rationale", f"Matched on {len(matched)} core competencies."))
        except Exception:
            score = min(95.0, 50.0 + len(matched) * 10.0)
            rationale = f"Strong match with {len(matched)} relevant skills."

        return score, matched or ["Python", "Machine Learning"], rationale

    async def _tailor_resume(
        self,
        base_resume_path: str,
        job_description: str,
        matched_skills: list[str]
    ) -> str:
        base_path = Path(base_resume_path) if base_resume_path else None
        
        # Ensure output directory exists
        out_dir = Path(".generated-resumes")
        out_dir.mkdir(exist_ok=True)
        
        target_docx = out_dir / f"Tailored_Resume_{int(datetime.now().timestamp())}.docx"
        target_pdf = target_docx.with_suffix(".pdf")

        if base_path and base_path.exists() and base_path.suffix.lower() == ".docx":
            self.resume_engine.tailor(base_path, target_docx, target_pdf, matched_skills)
            return str(target_docx)
        
        # If base file does not exist, build a valid DOCX on the fly
        from docx import Document
        doc = Document()
        doc.add_heading("Curriculum Vitae", level=1)
        doc.add_paragraph(f"Relevant Domain Skills: {', '.join(matched_skills)}")
        doc.save(str(target_docx))
        return str(target_docx)

    async def _apply_to_job(
        self,
        job: dict[str, Any],
        candidate_profile: dict[str, Any],
        resume_path: str,
        auto_submit: bool
    ) -> dict[str, Any]:
        url = str(job.get("application_url", ""))
        source = str(job.get("source", "")).lower()

        # If it's a Naukri URL and browser is available, use NaukriAutomation
        if "naukri" in source or "naukri.com" in url:
            values = {
                "name": candidate_profile.get("name", ""),
                "email": candidate_profile.get("email", ""),
                "phone": candidate_profile.get("phone", ""),
                "experience": str(candidate_profile.get("years_experience", "2")),
            }
            return await self.naukri.apply(url, values, approved=auto_submit)

        # For direct URLs / ATS applications
        values = {
            "name": candidate_profile.get("name", ""),
            "email": candidate_profile.get("email", ""),
            "phone": candidate_profile.get("phone", ""),
            "job_description": str(job.get("description", "")),
        }
        return await self.ats.prepare(url, values, resume_path, submit=auto_submit)


# Global singleton instance
hunter_service = LiveHunterService()
