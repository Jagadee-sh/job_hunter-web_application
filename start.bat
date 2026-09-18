@echo off
REM Start script for JobHunter AI (Windows)

echo Starting JobHunter AI...

REM Check if virtual environment exists
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Install dependencies
echo Installing Python dependencies...
pip install -e ".[dev]"

REM Start backend server
echo Starting backend server on port 8000...
start "JobHunter Backend" cmd /k "uvicorn backend.main:app --host 0.0.0.0 --port 8000 --loop asyncio"

REM Wait for backend to start
timeout /t 5 /nobreak

REM Start frontend development server
echo Starting frontend development server on port 5173...
cd frontend
start "JobHunter Frontend" cmd /k "npm run dev"
cd ..

echo JobHunter AI is running!
echo Backend: http://localhost:8000
echo Frontend: http://localhost:5173
echo Press any key to close this window (servers will continue running)
pause
