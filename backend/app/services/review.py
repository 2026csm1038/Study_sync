"""Business logic for the admin approval flow.

    list     the requests students made, newest/oldest first, with course and uploader details
    preview  the PDF still held in temporary Supabase Storage
    approve  copy that PDF into the shared Google Drive, mark the request 'approved' and store the
             Drive file id (this is what makes it appear in students' Search), then delete the temp copy
    reject   mark it 'rejected' with a reason the student can see, then delete the temp copy

Both decisions only work on a request that is still 'pending', and the database update itself checks
that, so two admins can never decide the same request twice.
"""
from ..deps import CurrentUser
from ..exceptions import Conflict, NotFound
from ..repositories import courses, profiles, submissions
from ..schemas.review import ReviewItem
from ..schemas.submission import SubmissionRow, SubmissionStatus
from . import google_drive, storage


def _items(rows: list[SubmissionRow]) -> list[ReviewItem]:
    course_by_id = courses.get_many([r.course_id for r in rows])
    user_by_id = profiles.get_many([r.uploaded_by for r in rows])
    items = []
    for r in rows:
        course, user = course_by_id.get(r.course_id), user_by_id.get(r.uploaded_by)
        items.append(
            ReviewItem(
                **r.model_dump(include={
                    "id", "status", "course_id", "exam_year", "exam_type", "tags",
                    "original_filename", "file_size_bytes", "created_at", "reviewed_at", "rejection_reason",
                }),
                course_code=course.course_code if course else None,
                course_name=course.course_name if course else None,
                uploaded_by_name=user.full_name if user else None,
                uploaded_by_entry_number=user.entry_number if user else None,
            )
        )
    return items


def _get(submission_id: str) -> SubmissionRow:
    row = submissions.get_by_id(submission_id)
    if row is None:
        raise NotFound("Request not found.")
    return row


def _get_pending(submission_id: str) -> SubmissionRow:
    row = _get(submission_id)
    if row.status != "pending":
        raise Conflict(f"This request was already {row.status}.")
    return row


def list_requests(status: SubmissionStatus, limit: int) -> list[ReviewItem]:
    return _items(submissions.list_by_status(status, limit))


def preview(submission_id: str) -> tuple[bytes, str]:
    row = _get_pending(submission_id)
    return storage.download_pdf(row.storage_path), row.original_filename


def approve(admin: CurrentUser, submission_id: str) -> ReviewItem:
    row = _get_pending(submission_id)
    content = storage.download_pdf(row.storage_path)

    course = courses.get_many([row.course_id]).get(row.course_id)
    label = f"{course.course_code} {row.exam_type} {row.exam_year}" if course else f"{row.exam_type} {row.exam_year}"

    # 1. copy to Google Drive. If this fails the request simply stays pending and can be retried.
    uploaded = google_drive.upload_pdf_bytes_to_shared_drive(content, f"{label} - {row.original_filename}")
    drive_file_id = uploaded["file_id"]

    # 2. record the approval (and the Drive file id students' Search needs)
    try:
        updated = submissions.decide(
            submission_id, status="approved", reviewed_by=admin.id, drive_file_id=drive_file_id
        )
    except Exception:
        google_drive.delete_file_from_shared_drive(drive_file_id)
        raise
    if updated is None:  # another admin decided in the meantime
        google_drive.delete_file_from_shared_drive(drive_file_id)
        raise Conflict("Another admin has already reviewed this request.")

    # 3. the temporary copy is no longer needed
    storage.delete_file(row.storage_path)
    return _items([updated])[0]


def reject(admin: CurrentUser, submission_id: str, reason: str) -> ReviewItem:
    row = _get_pending(submission_id)
    updated = submissions.decide(
        submission_id, status="rejected", reviewed_by=admin.id, rejection_reason=reason
    )
    if updated is None:
        raise Conflict("Another admin has already reviewed this request.")
    storage.delete_file(row.storage_path)
    return _items([updated])[0]
