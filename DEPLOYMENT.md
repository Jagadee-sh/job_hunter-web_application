# Deployment Guide for JobHunter AI

## Local Development

### Quick Start
1. Copy environment variables: `cp .env.example .env`
2. Set your OpenAI API key in `.env`
3. Run the start script:
   - Windows: `start.bat`
   - Linux/Mac: `./start.sh`

### Manual Setup
1. Create virtual environment: `python -m venv .venv`
2. Activate it: `.venv\Scripts\activate` (Windows) or `source .venv/bin/activate` (Linux/Mac)
3. Install dependencies: `pip install -e ".[dev]"`
4. Start backend: `uvicorn backend.main:app --port 8000 --loop asyncio`
5. In another terminal, start frontend: `cd frontend && npm install && npm run dev`

## Docker Deployment

### Build and Run Locally
```bash
docker build -t jobhunter-ai .
docker run -p 8000:8000 --env-file .env jobhunter-ai
```

### Docker Compose
```bash
docker-compose up --build
```

## Render Deployment

### Prerequisites
- GitHub account with the project pushed
- Render account (free tier available)
- OpenAI API key

### Step-by-Step Deployment

1. **Push to GitHub**
   ```bash
   git add .
   git commit -m "Ready for Render deployment"
   git push origin main
   ```

2. **Create Render Service**
   - Go to [render.com](https://render.com)
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Render will detect the `render.yaml` configuration automatically

3. **Configure Environment Variables**
   - In Render dashboard, go to your service settings
   - Add `OPENAI_API_KEY` with your actual API key
   - Other variables are pre-configured in `render.yaml`

4. **Deploy**
   - Click "Deploy" 
   - Render will build using the Dockerfile
   - Wait for deployment to complete (typically 2-5 minutes)

5. **Access Your App**
   - Render will provide a URL like `https://jobhunter-ai.onrender.com`
   - The app serves both frontend and backend from the same URL

### Render Configuration Details

The `render.yaml` file includes:
- **Runtime**: Docker
- **Plan**: Free tier
- **Region**: Oregon
- **Environment Variables**: Pre-configured for SQLite
- **Port**: 8000

### Production Considerations

**Database Upgrade** (Recommended for production):
- In Render dashboard, add a PostgreSQL database
- Update `DATABASE_URL` to: `postgresql+asyncpg://user:password@host:port/database`
- The app supports both SQLite and PostgreSQL

**Performance**:
- Free tier has limitations (spins down after inactivity)
- Consider upgrading to paid tier for production use
- Add Redis for Celery task queue if needed

**Security**:
- Never commit `.env` file
- Use Render's environment variable management
- Keep your OpenAI API key secure

## Troubleshooting

### Build Failures
- Check Dockerfile syntax
- Ensure all dependencies are in `pyproject.toml`
- Verify frontend builds successfully locally

### Runtime Errors
- Check Render logs for detailed error messages
- Verify environment variables are set correctly
- Ensure database initialization works

### Database Issues
- SQLite works for development but has limitations
- PostgreSQL recommended for production
- Check database connection string format

## Monitoring

### Health Check
- `GET /health` - Returns `{"status": "ok"}`
- `GET /api` - Returns API status information

### Logs
- Render provides real-time logs in dashboard
- Check for application errors and warnings
- Monitor API usage and performance

## Scaling

For high-traffic deployments:
1. Upgrade to paid Render plan
2. Add load balancer
3. Use PostgreSQL instead of SQLite
4. Add Redis for caching and task queue
5. Consider separate frontend/backend services
