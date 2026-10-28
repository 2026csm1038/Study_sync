from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .config import settings
from .exceptions import AppError
from .supabase_client import supabase
from .routers import auth as auth_router
from .routers import courses as courses_router
from .routers import drive as drive_router
from .routers import submissions as submissions_router
from .routers import resources as resources_router
from .routers import resource_filters as resource_filters_router
from .routers import departments as departments_router
from .routers import admin_submissions as admin_submissions_router
from .routers import admin_dashboard as admin_dashboard_router

app = FastAPI(
    title="StudySync API",
    version="0.1.0",
    description="Backend API for the StudySync academic resource portal.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(AppError)
def handle_app_error(_request: Request, exc: AppError):
    # NotFound -> 404, Conflict -> 409, ... raised anywhere in repositories or routers
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

app.include_router(auth_router.router)
app.include_router(courses_router.router)
app.include_router(drive_router.router)
app.include_router(submissions_router.router)
app.include_router(resources_router.router)
app.include_router(resource_filters_router.router)
app.include_router(departments_router.router)
app.include_router(admin_submissions_router.router)
app.include_router(admin_dashboard_router.router)

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "studysync-api",
        "supabase_configured": settings.supabase_configured,
        "supabase_client_initialized": supabase is not None,
        "database_tables_used": True,
    }
@app.get("/", include_in_schema=False)
def root():
    return {"message": "StudySync API is running. See /docs"}

@app.get("/api")
def api_root():
    return {"message": "StudySync API is running."}
