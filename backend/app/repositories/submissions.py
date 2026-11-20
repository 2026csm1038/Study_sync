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


def clear_storage_path(submission_id: str) -> bool:
    """Clear the temporary Storage path after its file has been deleted."""
    rows = (
        _table()
        .update({"storage_path": None})
        .eq("id", str(submission_id))
        .execute()
        .data
    )
    return bool(rows)


def decide(
    submission_id: str,
    *,
    status: SubmissionStatus,
    reviewed_by: str,
    drive_file_id: str | None = None,
    rejection_reason: str | None = None,
    course_id: str | None = None,
) -> SubmissionRow | None:
    """Approve or reject a request that is STILL pending.

    The `status = 'pending'` condition is part of the update itself, so if two admins decide at the same
    moment only one update matches. Returns None when nothing matched (already decided).
    Approving a new-course request passes the `course_id` of the course that was just created.
    Raises DuplicateSubmission if the approved paper would clash with one already published."""
    changes = {
        "status": status,
        "reviewed_by": reviewed_by,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "drive_file_id": drive_file_id,
        "rejection_reason": rejection_reason,
    }
    if course_id:
        changes["course_id"] = str(course_id)
    try:
        rows = (
            _table()
            .update(changes)
            .eq("id", str(submission_id))
            .eq("status", "pending")
            .execute()
            .data
        )
    except APIError as exc:
        if exc.json().get("code") == UNIQUE_VIOLATION:
            raise DuplicateSubmission() from exc
        raise
    return SubmissionRow.model_validate(rows[0]) if rows else None


def list_pending_new_course(course_code: str) -> list[SubmissionRow]:
    """Pending requests that asked for a not-yet-existing course (course_id is empty for these)."""
    rows = _table().select("*").eq("status", "pending").limit(500).execute().data
    wanted = course_code.strip().upper()
    return [
        row for row in (SubmissionRow.model_validate(r) for r in rows)
        if row.course_id is None and row.new_course and row.new_course.code.upper() == wanted
    ]


# ---- soft deletion of a published resource ------------------------------------------

def soft_delete(submission_id: str, *, deleted_by: str, reason: str | None) -> SubmissionRow | None:
    """Hide an approved resource. Nothing is erased: the row and its Drive file stay so it can be restored.
    The `status = 'approved'` condition is part of the update, so it only matches a live, published resource."""
    rows = (
        _table()
        .update({
            "status": "deleted",
            "deleted_at": datetime.now(timezone.utc).isoformat(),
            "deleted_by": deleted_by,
            "deletion_reason": reason,
        })
        .eq("id", str(submission_id))
        .eq("status", "approved")
        .execute()
        .data
    )
    return SubmissionRow.model_validate(rows[0]) if rows else None


def restore(submission_id: str) -> SubmissionRow | None:
    """Bring a soft-deleted resource back. Raises DuplicateSubmission if a replacement was uploaded meanwhile."""
    try:
        rows = (
            _table()
            .update({"status": "approved", "deleted_at": None, "deleted_by": None, "deletion_reason": None})
            .eq("id", str(submission_id))
            .eq("status", "deleted")
            .execute()
            .data
        )
    except APIError as exc:
        if exc.json().get("code") == UNIQUE_VIOLATION:
            raise DuplicateSubmission() from exc
        raise
    return SubmissionRow.model_validate(rows[0]) if rows else None


def delete_row(submission_id: str) -> None:
    _table().delete().eq("id", str(submission_id)).execute()
