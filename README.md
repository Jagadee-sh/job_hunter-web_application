# JobHunter AI

JobHunter AI is an async Python platform for discovering, scoring, tailoring, preparing, and tracking job applications with explicit human approval before submission.

## Quick start

### Option 1: Automated Start (Recommended)

**Windows:**
```powershell
start.bat
```

**Linux/Mac:**
```bash
chmod +x start.sh
./start.sh
```

### Option 2: Manual Start

**Backend:**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn backend.main:app --port 8000 --loop asyncio
```

**Frontend (in a second terminal):**
```powershell
cd frontend
npm install
npm run dev
```

The development backend uses a local SQLite database by default. On first startup it creates `jobhunter.db` and seeds three demo roles, so the app is immediately usable without PostgreSQL, Redis, or an AI key. The API exposes OpenAPI documentation at `http://127.0.0.1:8000/docs` and a health check at `http://127.0.0.1:8000/health`.

Open `http://127.0.0.1:5173` for the development frontend, or `http://127.0.0.1:8000` for the production build (frontend served by backend).

## Environment Configuration

Copy `.env.example` to `.env` and configure your settings:

```bash
cp .env.example .env
```

Required environment variables:
- `OPENAI_API_KEY`: Your OpenAI API key for AI features
- `DATABASE_URL`: Database connection string (default: SQLite)

## Production Deployment

### Docker

Build and run with Docker:

```bash
docker build -t jobhunter-ai .
docker run -p 8000:8000 --env-file .env jobhunter-ai
```

### Render Deployment

1. Push your code to GitHub
2. Create a new web service on Render
3. Connect your GitHub repository
4. Render will automatically detect the `render.yaml` configuration
5. Set your `OPENAI_API_KEY` in the Render environment variables
6. Deploy!

The `render.yaml` file is pre-configured for automatic deployment with:
- Docker runtime
- SQLite database (upgrade to PostgreSQL for production)
- Automatic environment variable configuration

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
