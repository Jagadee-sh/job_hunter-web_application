<<<<<<< HEAD
# JobHunter AI

JobHunter AI is an async Python platform for discovering, scoring, tailoring, preparing, and tracking job applications with explicit human approval before submission.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn backend.main:app --port 8000 --loop asyncio
```

The development backend uses a local SQLite database by default. On first startup it creates `jobhunter.db` and seeds three demo roles, so the app is immediately usable without PostgreSQL, Redis, or an AI key. The API exposes OpenAPI documentation at `http://127.0.0.1:8000/docs` and a health check at `http://127.0.0.1:8000/health`.

Run the dashboard in a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. The dashboard's Search jobs action calls the backend and displays the seeded roles. To use PostgreSQL instead, set `DATABASE_URL` to a PostgreSQL async URL before starting the API.

## Naukri automation

The dashboard's `Naukri search` action opens a visible Chromium browser using the persistent `.browser-profile` directory. Log in to Naukri in that window yourself, complete any CAPTCHA or verification yourself, and then rerun the search. The adapter searches the requested roles and locations across up to five result pages and returns the job links for review. Company-site roles are marked for external review rather than being falsely counted as submitted.

Applications require an explicit approval request through `POST /integrations/naukri/apply`. The adapter fills matching fields, stops when information is missing or the site presents an ambiguous form, and never claims success unless Naukri confirms submission. Do not put Naukri credentials in `.env` or source code.

## Architecture

- `backend/models.py`: SQLAlchemy 2.0 persistence model
- `backend/repositories.py`: persistence access boundary
- `backend/services.py`: application service boundary
- `backend/api.py`: FastAPI transport boundary
- `backend/agents/`: LangGraph orchestration
- `backend/mcp_server.py`: FastMCP tool surface
- `backend/automation/`: Playwright browser adapters
- `backend/resume/`: truthful DOCX/PDF tailoring
- `frontend/`: React dashboard
=======
# job_hunter-web_application
>>>>>>> 9df26f2fb2db1de9933db519bf0999156f370588
