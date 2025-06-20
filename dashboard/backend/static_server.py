# dashboard/backend/static_server.py
"""Simple static file server for the HITL dashboard."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
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

if __name__ == "__main__":
    import uvicorn

    # Start the dashboard server on port 3000
    uvicorn.run(
        "static_server:app",
        host="0.0.0.0",
        port=3000,
        reload=True
    )
