from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .supabase_client import supabase

app = FastAPI(
    title="StudySync API",
    version="0.1.0",
    description="Backend API for the StudySync academic resource portal.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "studysync-api",
        "supabase_configured": settings.supabase_configured,
        "supabase_client_initialized": supabase is not None,
        "database_tables_used": False,
    }

@app.get("/api")
def api_root():
    return {"message": "StudySync API is running."}
