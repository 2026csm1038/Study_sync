"""Read-only statistics for the Admin Dashboard (Page 5).

The dashboard looks across several tables, so this file only counts rows and fetches the newest rows
for the activity list. It never writes. Same rules as the other repositories: it returns Pydantic
models or plain numbers, and it never raises HTTP errors.
"""
from ..schemas.course import CourseOut
from ..schemas.submission import SubmissionRow
from ..supabase_client import admin


def _count(table: str, **equals: str) -> int:
    """How many rows match. The database does the counting, so it stays correct beyond 1000 rows."""
    query = admin().table(table).select("id", count="exact")
    for column, value in equals.items():
        query = query.eq(column, value)
    return query.limit(1).execute().count or 0


def count_students() -> int:
    return _count("profiles", role="student")


def count_courses() -> int:
    return _count("courses")


def count_approved_by_type(exam_types: list[str]) -> dict[str, int]:
    return {t: _count("resource_submissions", status="approved", exam_type=t) for t in exam_types}


def latest_submissions(limit: int) -> list[SubmissionRow]:
    """Newest uploads, whatever their status."""
    rows = (
        admin().table("resource_submissions").select("*")
        .order("created_at", desc=True).limit(limit).execute().data
    )
    return [SubmissionRow.model_validate(row) for row in rows]


def latest_decisions(limit: int) -> list[SubmissionRow]:
    """Newest approvals and rejections, by any admin."""
    rows = (
        admin().table("resource_submissions").select("*")
        .in_("status", ["approved", "rejected"])
        .order("reviewed_at", desc=True).limit(limit).execute().data
    )
    return [SubmissionRow.model_validate(row) for row in rows]


def latest_courses(limit: int) -> list[CourseOut]:
    rows = admin().table("courses").select("*").order("created_at", desc=True).limit(limit).execute().data
    return [CourseOut.model_validate(row) for row in rows]


def course_codes(course_ids: list[str]) -> dict[str, str]:
    """course id -> course code, for the titles in the activity list."""
    if not course_ids:
        return {}
    rows = admin().table("courses").select("id, course_code").in_("id", list(set(course_ids))).execute().data
    return {str(row["id"]): row["course_code"] for row in rows}
