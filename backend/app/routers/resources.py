"""Student-facing search for resources stored in the Shared Google Drive.

The existing submission schema maps to the `resource_submissions` table.
Only approved rows with a `drive_file_id` are returned to students.
"""
import re

from fastapi import APIRouter, Depends, Query
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from ..services.google_drive import download_pdf_from_shared_drive

from ..deps import CurrentUser, get_current_user
from ..supabase_client import admin

router = APIRouter(prefix="/api/resources", tags=["resources"])
TABLE = "resource_submissions"


@router.get("/search")
def search_resources(
    q: str = Query(..., min_length=1, max_length=100, description="Search file name or tags"),
    _user: CurrentUser = Depends(get_current_user),
):
    """Search approved resources by filename/tags and return Google Drive links."""
    term = q.strip()
    if not term:
        return []

    # Keep the search term safe for PostgREST's .or_ filter syntax.
    term = re.sub(r"[^A-Za-z0-9 _.-]", " ", term).strip()
    if not term:
        return []

    rows = (
        admin()
        .table(TABLE)
        .select("id, course_id, exam_year, exam_type, tags, original_filename, drive_file_id, status, created_at")
        .eq("status", "approved")
        .not_.is_("drive_file_id", "null")
        .or_(f"original_filename.ilike.%{term}%,tags.ilike.%{term}%")
        .order("created_at", desc=True)
        .limit(50)
        .execute()
        .data
    )

    # Resolve course labels using the existing courses table. Do not make the
    # search dependent on a PostgREST relationship being configured.
    course_ids = list({str(row["course_id"]) for row in rows if row.get("course_id")})
    course_by_id = {}
    if course_ids:
        course_rows = (
            admin()
            .table("courses")
            .select("id, course_code, course_name, semester")
            .in_("id", course_ids)
            .execute()
            .data
        )
        course_by_id = {str(course["id"]): course for course in course_rows}

    results = []
    for row in rows:
        file_id = (row.get("drive_file_id") or "").strip()
        if not file_id:
            continue

        course = course_by_id.get(str(row.get("course_id")), {})
        results.append({
            "id": row.get("id"),
            "title": row.get("original_filename") or "Untitled resource",
            "resource_type": row.get("exam_type") or "Resource",
            "course_code": course.get("course_code"),
            "course_name": course.get("course_name"),
            "semester": course.get("semester"),
            "academic_year": row.get("exam_year"),
            "exam_type": row.get("exam_type"),
            "tags": row.get("tags"),
            "google_drive_url": f"https://drive.google.com/file/d/{file_id}/view",
        })

    return results


@router.get("/{resource_id}/view")
def view_resource(
    resource_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Serve an approved PDF through the authenticated backend."""

    # Look up the resource using the existing server-side Supabase client.
    response = (
        admin()
        .table(TABLE)
        .select("id, original_filename, drive_file_id, status")
        .eq("id", resource_id)
        .eq("status", "approved")
        .limit(1)
        .execute()
    )

    rows = response.data or []
    if not rows or not rows[0].get("drive_file_id"):
        raise HTTPException(status_code=404, detail="Resource not found.")

    resource = rows[0]

    # Only approved resources are served. The endpoint also requires login.
    pdf_bytes = download_pdf_from_shared_drive(resource["drive_file_id"])

    filename = (resource.get("original_filename") or "resource.pdf")
    filename = filename.replace('"', "").replace("\r", "").replace("\n", "")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )

