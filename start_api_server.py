#!/home/rober/.pyenv/versions/nadia-env/bin/python
"""Simple script to start the API server with proper configuration."""

import os
import sys
import uvicorn

# Ensure proper Python path
project_path = '/home/rober/projects/chatbot_nadia'
if project_path not in sys.path:
    sys.path.insert(0, project_path)

# Set PYTHONPATH environment variable
os.environ['PYTHONPATH'] = project_path

def main():
    """Start the API server."""
    print("🚀 Starting NADIA API Server...")
    print(f"   Project path: {project_path}")
    print(f"   Python path: {sys.path[0]}")
    
    try:
        # Import and verify the app
        from api.server import app
        print("✅ API server app loaded successfully")
        
        # Start the server
        print("🌐 Starting server on http://0.0.0.0:8000")
        print("   Press Ctrl+C to stop")
        
        uvicorn.run(
            "api.server:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            reload_dirs=[project_path],
            log_level="info"
        )
        
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())