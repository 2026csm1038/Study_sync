"""Community resource reports and admin moderation."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..deps import CurrentUser, get_current_user, require_admin
from ..exceptions import Conflict, NotFound
from ..supabase_client import admin
from ..services.google_drive import delete_file_from_shared_drive

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
        "id,resource_id,reporter_id,reason,details,status,created_at,resource_submissions(original_filename,course_id,exam_year,exam_type)"
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


@router.delete("/resources/{resource_id}", status_code=204)
def remove_flagged_resource(resource_id: UUID, _admin: CurrentUser = Depends(require_admin)):
    db = admin()
    rows = (db.table("resource_submissions").select("id,drive_file_id")
            .eq("id", str(resource_id)).limit(1).execute().data or [])
    if not rows:
        raise NotFound("Resource not found.")
    file_id = rows[0].get("drive_file_id")
    if file_id:
        delete_file_from_shared_drive(file_id)
    db.table("resource_flags").delete().eq("resource_id", str(resource_id)).execute()
    db.table("resource_submissions").delete().eq("id", str(resource_id)).execute()
    return None
