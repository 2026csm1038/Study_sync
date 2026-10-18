"""Google Drive integration for StudySync's Shared Drive."""
import os
from functools import lru_cache
from pathlib import Path
from io import BytesIO

from fastapi import HTTPException, UploadFile, status
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

DRIVE_SCOPE = ["https://www.googleapis.com/auth/drive"]
SHARED_DRIVE_ID = os.getenv("GOOGLE_SHARED_DRIVE_ID", "").strip()
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()


def _credentials() -> Credentials:
    if not SHARED_DRIVE_ID or not SERVICE_ACCOUNT_FILE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Drive is not configured. Set GOOGLE_SHARED_DRIVE_ID and GOOGLE_SERVICE_ACCOUNT_FILE.",
        )
    path = Path(SERVICE_ACCOUNT_FILE).expanduser()
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google service-account JSON file was not found at the configured path.",
        )
    try:
        return Credentials.from_service_account_file(str(path), scopes=DRIVE_SCOPE)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not load Google service-account credentials.",
        ) from exc


@lru_cache(maxsize=1)
def _drive_service():
    return build("drive", "v3", credentials=_credentials(), cache_discovery=False)


def check_shared_drive_access() -> dict:
    """Verify the configured ID is a Shared Drive accessible to the service account."""
    try:
        drive = _drive_service().drives().get(driveId=SHARED_DRIVE_ID).execute()
        return {"id": drive["id"], "name": drive.get("name", "Shared Drive")}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Cannot access Shared Drive. Check its ID, Drive API enablement, and service-account membership.",
        ) from exc


def upload_pdf_to_shared_drive(file: UploadFile) -> dict:
    """Upload a PDF to the root of the configured Shared Drive."""
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="Only PDF files are accepted.")

    max_bytes = int(os.getenv("MAX_PDF_UPLOAD_MB", "20")) * 1024 * 1024
    content = file.file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"PDF exceeds the {max_bytes // (1024 * 1024)} MB limit.")
    if not content:
        raise HTTPException(status_code=400, detail="The PDF is empty.")
    if not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="The uploaded file does not look like a valid PDF.")

    filename = Path(file.filename or "resource.pdf").name
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"

    media = MediaIoBaseUpload(BytesIO(content), mimetype="application/pdf", resumable=True)
    metadata = {"name": filename, "mimeType": "application/pdf", "parents": [SHARED_DRIVE_ID]}
    try:
        created = _drive_service().files().create(
            body=metadata,
            media_body=media,
            fields="id,name,mimeType,webViewLink",
            supportsAllDrives=True,
        ).execute()
        return {
            "file_id": created["id"],
            "name": created["name"],
            "mime_type": created.get("mimeType", "application/pdf"),
            "web_view_link": created.get("webViewLink"),
        }
    except HttpError as exc:
        raise HTTPException(
            status_code=502,
            detail="Google Drive rejected the upload. Check Shared Drive membership, drive ID, API enablement, and Workspace restrictions.",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Could not upload the PDF to Google Drive.") from exc
