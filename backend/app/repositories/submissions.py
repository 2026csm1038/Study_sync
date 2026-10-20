"""All database access for the `resource_submissions` table.

Same rules as the other repositories: this is the only place that talks to this table,
it takes and returns Pydantic models, and it raises domain errors, never HTTP errors.
"""
from postgrest.exceptions import APIError

from ..schemas.submission import SubmissionInsert, SubmissionRow
from ..supabase_client import admin

TABLE = "resource_submissions"
UNIQUE_VIOLATION = "23505"

# A "live" submission is one that still counts: waiting for review, or already approved.
# A rejected one does not block somebody uploading a better copy.
LIVE = ["pending", "approved"]


class DuplicateSubmission(Exception):
    """The database refused the insert because an identical live paper/file already exists."""


def _table():
    return admin().table(TABLE)


def find_live_by_metadata(course_id: str, exam_year: int, exam_type: str) -> SubmissionRow | None:
    rows = (
        _table()
        .select("*")
        .eq("course_id", str(course_id))
        .eq("exam_year", exam_year)
        .eq("exam_type", exam_type)
        .in_("status", LIVE)
        .limit(1)
        .execute()
        .data
    )
    return SubmissionRow.model_validate(rows[0]) if rows else None


def find_live_by_hash(file_sha256: str) -> SubmissionRow | None:
    rows = (
        _table()
        .select("*")
        .eq("file_sha256", file_sha256)
        .in_("status", LIVE)
        .limit(1)
        .execute()
        .data
    )
    return SubmissionRow.model_validate(rows[0]) if rows else None


def create(data: SubmissionInsert) -> SubmissionRow:
    try:
        rows = _table().insert(data.model_dump(mode="json")).execute().data
    except APIError as exc:
        if exc.json().get("code") == UNIQUE_VIOLATION:
            raise DuplicateSubmission() from exc
        raise
    return SubmissionRow.model_validate(rows[0])


def list_for_user(user_id: str) -> list[SubmissionRow]:
    rows = (
        _table()
        .select("*")
        .eq("uploaded_by", user_id)
        .order("created_at", desc=True)
        .execute()
        .data
    )
    return [SubmissionRow.model_validate(row) for row in rows]
