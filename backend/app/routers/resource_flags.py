"""Community resource reports and admin moderation."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..deps import CurrentUser, get_current_user, require_admin
from ..exceptions import Conflict, NotFound
from ..repositories import courses, submissions
from ..supabase_client import admin
from ..services import google_drive

router = APIRouter(prefix="/api/resource-flags", tags=["resource flags"])
# How much one report counts towards a resource's priority. A report from a professor / faculty
# member counts for more, so flagged resources they care about reach the top of the admin's list.
FLAG_WEIGHT = {"student": 1, "professor": 5, "admin": 5}
DEFAULT_WEIGHT = 1


def weight_for(role: str | None) -> int:
    return FLAG_WEIGHT.get(role or "", DEFAULT_WEIGHT)


REASONS = {"incorrect_content", "duplicate", "poor_quality", "inappropriate", "other"}


class FlagCreate(BaseModel):
    reason: Literal["incorrect_content", "duplicate", "poor_quality", "inappropriate", "other"]
    details: str | None = Field(default=None, max_length=1000)


class FlagStatusUpdate(BaseModel):
    status: Literal["resolved", "dismissed"]


@router.post("/{resource_id}", status_code=201)
def flag_resource(resource_id: UUID, body: FlagCreate, user: CurrentUser = Depends(get_current_user)):
    db = admin()
    resource = (db.table("resource_submissions").select("id,status")
                .eq("id", str(resource_id)).eq("status", "approved").limit(1).execute().data)
    if not resource:
        raise NotFound("Resource not found.")
    existing = (db.table("resource_flags").select("id")
                .eq("resource_id", str(resource_id)).eq("reporter_id", user.id).limit(1).execute().data)
    if existing:
        raise Conflict("You have already reported this resource.")
    row = db.table("resource_flags").insert({
        "resource_id": str(resource_id), "reporter_id": user.id,
        "reason": body.reason, "details": (body.details or "").strip() or None,
        "status": "open",
    }).execute().data[0]
    return {"id": row["id"], "status": row["status"], "message": "Resource reported. Thank you for helping keep StudySync reliable."}


@router.get("", dependencies=[Depends(require_admin)])
def list_flags(status: Literal["open", "resolved", "dismissed"] | None = None):
    query = admin().table("resource_flags").select(
        "id,resource_id,reporter_id,reason,details,status,created_at,resource_submissions(original_filename,course_id,exam_year,exam_type,status,deletion_reason)"
    ).order("created_at", desc=True)
    if status:
        query = query.eq("status", status)
    flags = query.execute().data or []
    reporter_ids = list({str(f["reporter_id"]) for f in flags if f.get("reporter_id")})
    names = {}
    if reporter_ids:
        people = admin().table("profiles").select("id,full_name,email,role").in_("id", reporter_ids).execute().data or []
        names = {str(p["id"]): p for p in people}
    result = []
    for flag in flags:
        resource = flag.pop("resource_submissions", None) or {}
        flag["resource"] = resource
        flag["reporter"] = names.get(str(flag["reporter_id"]), {})
        flag["weight"] = weight_for(flag["reporter"].get("role"))
        result.append(flag)
    return result


@router.patch("/{flag_id}")
def update_flag(flag_id: UUID, body: FlagStatusUpdate, _admin: CurrentUser = Depends(require_admin)):
    rows = (admin().table("resource_flags").update({"status": body.status})
            .eq("id", str(flag_id)).execute().data or [])
    if not rows:
        raise NotFound("Report not found.")
    return rows[0]


class RemoveRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


def _resource_row(resource_id: UUID) -> dict:
    rows = (admin().table("resource_submissions").select("id,status,drive_file_id")
            .eq("id", str(resource_id)).limit(1).execute().data or [])
    if not rows:
        raise NotFound("Resource not found.")
    return rows[0]


@router.get("/resources/removed", dependencies=[Depends(require_admin)])
def list_removed_resources():
    """Soft-deleted resources, newest removal first, so an admin can restore them."""
    rows = [r for r in submissions.list_by_status("deleted", 200)]
    codes = courses.get_many([r.course_id for r in rows if r.course_id])
    return [
        {
            "id": r.id, "original_filename": r.original_filename, "exam_year": r.exam_year,
            "exam_type": r.exam_type, "deleted_at": r.deleted_at, "deletion_reason": r.deletion_reason,
            "course_code": codes[r.course_id].course_code if r.course_id in codes else None,
        }
        for r in rows
    ]


@router.delete("/resources/{resource_id}")
def remove_flagged_resource(
    resource_id: UUID, body: RemoveRequest | None = None, current: CurrentUser = Depends(require_admin)
):
    """SOFT delete: the resource disappears for students (search, filters, view, flagging) but its row
    and Drive file are kept, so it can be restored. Its open reports are marked resolved."""
    _resource_row(resource_id)
    reason = ((body.reason if body else None) or "").strip() or None
    removed = submissions.soft_delete(str(resource_id), deleted_by=current.id, reason=reason)
    if removed is None:
        raise Conflict("This resource is not published, so it can't be removed.")
    (admin().table("resource_flags").update({"status": "resolved"})
     .eq("resource_id", str(resource_id)).eq("status", "open").execute())
    return {"id": str(resource_id), "status": "deleted"}


@router.post("/resources/{resource_id}/restore")
def restore_resource(resource_id: UUID, _admin: CurrentUser = Depends(require_admin)):
    _resource_row(resource_id)
    try:
        restored = submissions.restore(str(resource_id))
    except submissions.DuplicateSubmission as exc:
        raise Conflict("A replacement for this paper has been published since, so it can't be restored.") from exc
    if restored is None:
        raise Conflict("This resource is not in the removed list.")
    return {"id": str(resource_id), "status": "approved"}


@router.delete("/resources/{resource_id}/permanent", status_code=204)
def permanently_delete_resource(resource_id: UUID, _admin: CurrentUser = Depends(require_admin)):
    """Final removal, only for a resource that was soft-deleted first: erases the Drive file and the row."""
    row = _resource_row(resource_id)
    if row["status"] != "deleted":
        raise Conflict("Remove the resource first; only removed resources can be deleted permanently.")
    if row.get("drive_file_id"):
        google_drive.delete_file_from_shared_drive(row["drive_file_id"])
    admin().table("resource_flags").delete().eq("resource_id", str(resource_id)).execute()
    submissions.delete_row(str(resource_id))
    return None
