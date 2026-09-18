# Multi-stage build for frontend and backend
FROM node:18-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Backend stage
FROM python:3.12-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy backend files
COPY pyproject.toml ./
COPY backend/ ./backend/
COPY alembic.ini ./

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir ".[dev]"

# Copy frontend build artifacts
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Create necessary directories
RUN mkdir -p .uploads .generated-resumes .browser-profile

EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite+aiosqlite:///./jobhunter.db
ENV PORT=8000

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port $PORT"]