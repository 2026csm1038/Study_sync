"""All database access for the `resource_submissions` table.

Same rules as the other repositories: this is the only place that talks to this table,
it takes and returns Pydantic models, and it raises domain errors, never HTTP errors.
"""
from postgrest.exceptions import APIError

from datetime import datetime, timezone

from ..schemas.submission import SubmissionInsert, SubmissionRow, SubmissionStatus
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


# ---- used by the admin review flow ------------------------------------------------

def get_by_id(submission_id: str) -> SubmissionRow | None:
    rows = _table().select("*").eq("id", str(submission_id)).limit(1).execute().data
    return SubmissionRow.model_validate(rows[0]) if rows else None


def list_by_status(status: SubmissionStatus, limit: int = 100) -> list[SubmissionRow]:
    """Waiting requests come oldest first (first come, first reviewed); history comes newest first."""
    newest_first = status != "pending"
    rows = (
        _table()
        .select("*")
        .eq("status", status)
        .order("created_at", desc=newest_first)
        .limit(limit)
        .execute()
        .data
    )
    return [SubmissionRow.model_validate(row) for row in rows]


def decide(
    submission_id: str,
    *,
    status: SubmissionStatus,
    reviewed_by: str,
    drive_file_id: str | None = None,
    rejection_reason: str | None = None,
) -> SubmissionRow | None:
    """Approve or reject a request that is STILL pending.

    The `status = 'pending'` condition is part of the update itself, so if two admins decide at the
    same moment only one update matches. Returns None when nothing matched (already decided)."""
    changes = {
        "status": status,
        "reviewed_by": reviewed_by,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "drive_file_id": drive_file_id,
        "rejection_reason": rejection_reason,
    }
    rows = (
        _table()
        .update(changes)
        .eq("id", str(submission_id))
        .eq("status", "pending")
        .execute()
        .data
    )
    return SubmissionRow.model_validate(rows[0]) if rows else None
