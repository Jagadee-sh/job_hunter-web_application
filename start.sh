#!/bin/bash

# Start script for JobHunter AI

echo "Starting JobHunter AI..."

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install -e ".[dev]"

# Start backend server
echo "Starting backend server on port 8000..."
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --loop asyncio &
BACKEND_PID=$!

# Wait for backend to start
sleep 5

# Start frontend development server
echo "Starting frontend development server on port 5173..."
cd frontend
npm run dev &
FRONTEND_PID=$!

echo "JobHunter AI is running!"
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo "Press Ctrl+C to stop both servers"

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
