"""Read-only, student-facing queries on the `resource_submissions` table.

Papers are written by repositories/submissions.py. This file only reads, and it only ever
returns APPROVED papers that already have a Google Drive file, so a student can never see a
pending or rejected paper through it.

Same rules as the other repositories: it is the only place that runs these queries, it returns
Pydantic models, and it raises domain errors, never HTTP errors.
"""
import re
from uuid import UUID

from ..schemas.resource import ResourceOut
from ..supabase_client import admin

TABLE = "resource_submissions"
COLUMNS = "id, course_id, exam_year, exam_type, tags, original_filename, drive_file_id, created_at"


def _clean_text(term: str) -> str:
    """Keep only characters that are safe inside a PostgREST filter string."""
    return re.sub(r"[^A-Za-z0-9 _.-]", " ", term).strip()


def _matching_course_ids(
    *,
    course_id: UUID | None,
    department_id: UUID | None,
    semester: int | None,
) -> list[str]:
    """Ids of the courses that satisfy the course-level filters (course, department, semester)."""
    query = admin().table("courses").select("id")
    if course_id:
        query = query.eq("id", str(course_id))
    if department_id:
        query = query.eq("department_id", str(department_id))
    if semester:
        query = query.eq("semester", semester)
    return [str(row["id"]) for row in query.execute().data]


def _to_out(row: dict, course: dict) -> ResourceOut:
    file_id = row["drive_file_id"].strip()
    return ResourceOut(
        id=str(row["id"]),
        title=row.get("original_filename") or "Untitled resource",
        resource_type=row.get("exam_type") or "Resource",
        course_code=course.get("course_code"),
        course_name=course.get("course_name"),
        semester=course.get("semester"),
        academic_year=row.get("exam_year"),
        exam_type=row.get("exam_type"),
        tags=row.get("tags"),
        google_drive_url=f"https://drive.google.com/file/d/{file_id}/view",
    )


def filter_resources(
    *,
    q: str | None = None,
    course_id: UUID | None = None,
    department_id: UUID | None = None,
    semester: int | None = None,
    exam_year: int | None = None,
    exam_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ResourceOut]:
    """One page of approved papers, newest first, matching every filter that is given (combined with AND).

    Page 1 is offset=0. For the next page, ask again with offset = how many papers the student already has.
    """
    query = admin().table(TABLE).select(COLUMNS).eq("status", "approved")

    # course-level filters are answered by the courses table, then applied as "course is one of these"
    if course_id or department_id or semester:
        course_ids = _matching_course_ids(
            course_id=course_id, department_id=department_id, semester=semester
        )
        if not course_ids:
            return []
        query = query.in_("course_id", course_ids)

    if exam_year:
        query = query.eq("exam_year", exam_year)
    if exam_type:
        query = query.eq("exam_type", exam_type)

    if q is not None:
        term = _clean_text(q)
        if not term:
            return []
        query = query.or_(f"original_filename.ilike.%{term}%,tags.ilike.%{term}%")

    query = query.order("created_at", desc=True)
    # range() is only needed from the second page on; the first page is a plain limit
    query = query.range(offset, offset + limit - 1) if offset else query.limit(limit)
    rows = query.execute().data
    rows = [row for row in rows if (row.get("drive_file_id") or "").strip()]

    # Course names/semesters for the rows we are returning (no PostgREST relationship needed).
    wanted = list({str(row["course_id"]) for row in rows if row.get("course_id")})
    course_by_id: dict[str, dict] = {}
    if wanted:
        course_rows = (
            admin()
            .table("courses")
            .select("id, course_code, course_name, semester")
            .in_("id", wanted)
            .execute()
            .data
        )
        course_by_id = {str(course["id"]): course for course in course_rows}

    return [_to_out(row, course_by_id.get(str(row.get("course_id")), {})) for row in rows]
