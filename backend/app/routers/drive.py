"""Admin-only Google Drive connection test and PDF upload endpoints."""
from fastapi import APIRouter, Depends, File, UploadFile, status

from ..deps import CurrentUser, require_admin
from ..services.google_drive import check_shared_drive_access, upload_pdf_to_shared_drive

router = APIRouter(prefix="/api/drive", tags=["Google Drive"])


@router.get("/connection-test")
def connection_test(_admin: CurrentUser = Depends(require_admin)):
    """Confirm the backend service account can access the configured Shared Drive."""
    return {"connected": True, "shared_drive": check_shared_drive_access()}


@router.post("/upload", status_code=status.HTTP_201_CREATED)
def upload_pdf(file: UploadFile = File(...), _admin: CurrentUser = Depends(require_admin)):
    """
    Admin-only integration endpoint. Keep this admin-only until student submission
    and approval routes are implemented.
    """
    return upload_pdf_to_shared_drive(file)
