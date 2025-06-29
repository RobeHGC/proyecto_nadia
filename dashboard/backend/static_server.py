# dashboard/backend/static_server.py
"""Simple static file server for the HITL dashboard."""
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Create FastAPI app for serving dashboard
app = FastAPI(title="NADIA Dashboard Server")

# Get the frontend directory path
frontend_dir = Path(__file__).parent.parent / "frontend"

# Mount static files for /static/ URLs
app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

@app.get("/")
async def dashboard_root():
    """Serve the dashboard index.html"""
    return FileResponse(str(frontend_dir / "index.html"))

@app.get("/app.js")
async def get_app_js():
    """Serve the app.js file"""
    return FileResponse(str(frontend_dir / "app.js"))

@app.get("/styles.css")
async def get_styles_css():
    """Serve the styles.css file"""
    return FileResponse(str(frontend_dir / "styles.css"))

@app.get("/data-analytics.html")
async def get_data_analytics():
    """Serve the data-analytics.html file"""
    return FileResponse(str(frontend_dir / "data-analytics.html"))

@app.get("/data-analytics.js")
async def get_data_analytics_js():
    """Serve the data-analytics.js file"""
    return FileResponse(str(frontend_dir / "data-analytics.js"))

@app.get("/knowledge-management.html")
async def get_knowledge_management():
    """Serve the knowledge-management.html file"""
    return FileResponse(str(frontend_dir / "knowledge-management.html"))

@app.get("/knowledge-management.js")
async def get_knowledge_management_js():
    """Serve the knowledge-management.js file"""
    return FileResponse(str(frontend_dir / "knowledge-management.js"))

@app.get("/index.html")
async def get_index():
    """Serve the index.html file for 'Back to Dashboard' button"""
    return FileResponse(str(frontend_dir / "index.html"))

@app.get("/api/config")
async def get_config():
    """Serve configuration for frontend"""
    return JSONResponse({
        "apiKey": os.getenv("DASHBOARD_API_KEY", "miclavesegura45mil"),
        "apiBase": "http://localhost:8000"
    })

if __name__ == "__main__":
    import uvicorn

    # Start the dashboard server on port 3000
    uvicorn.run(
        "static_server:app",
        host="0.0.0.0",
        port=3000,
        reload=True
    )
