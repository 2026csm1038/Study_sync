"""Business logic for the admin approval flow.

    list     the requests students made, newest/oldest first, with course and uploader details
    preview  the PDF still held in temporary Supabase Storage
    approve  copy that PDF into the shared Google Drive, mark the request 'approved' and store the
             Drive file id (this is what makes it appear in students' Search), then delete the temp copy
    reject   mark it 'rejected' with a reason the student can see, then delete the temp copy

A request here always comes from an upload that needs a NEW course and/or department. Nothing is created
until the admin approves: approving creates the department/course, copies the PDF to Drive, publishes
it and deletes the temporary file; rejecting creates nothing and just deletes the temporary file.

Both decisions only work on a request that is still 'pending', and the database update itself checks
that, so two admins can never decide the same request twice.
"""
from ..deps import CurrentUser
from ..exceptions import BadRequest, Conflict, NotFound
from ..repositories import courses, departments, profiles, submissions
from ..schemas.review import ReviewItem
from ..schemas.submission import SubmissionRow, SubmissionStatus
from . import catalog, google_drive, storage
from .submissions import _undo_catalog
import logging

log = logging.getLogger(__name__)


def _items(rows: list[SubmissionRow]) -> list[ReviewItem]:
    course_by_id = courses.get_many([r.course_id for r in rows if r.course_id])
    user_by_id = profiles.get_many([r.uploaded_by for r in rows])
    items = []
    for r in rows:
        course, user = course_by_id.get(r.course_id), user_by_id.get(r.uploaded_by)
        wanted = r.new_course
        extra = {}
        if wanted:
            # Keep the request marker after approval, when course_id has been populated.
            extra = dict(
                course_code=course.course_code if course else wanted.code,
                course_name=course.course_name if course else wanted.name,
                is_new_course=True,
                department_name=wanted.department,
                semester=wanted.semester,
                is_new_department=departments.find_by_name_or_code(wanted.department) is None,
            )
        elif course:
            extra = dict(course_code=course.course_code, course_name=course.course_name, semester=course.semester)
        items.append(
            ReviewItem(
                **r.model_dump(include={
                    "id", "status", "course_id", "exam_year", "exam_type", "tags",
                    "original_filename", "file_size_bytes", "created_at", "reviewed_at", "rejection_reason",
                }),
                uploaded_by_name=user.full_name if user else None,
                uploaded_by_entry_number=user.entry_number if user else None,
                **extra,
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


def _cleanup_temporary_file(submission_id: str, storage_path: str) -> None:
    """Delete the temporary PDF, then clear its path from the database."""
    deleted = storage.delete_file(storage_path)

    if not deleted:
        log.error(
            "Temporary file cleanup failed for submission %s; "
            "storage_path retained: %s",
            submission_id,
            storage_path,
        )
        return

    try:
        cleared = submissions.clear_storage_path(submission_id)

        if not cleared:
            log.error(
                "File was deleted from Storage, but storage_path could not "
                "be cleared for submission %s",
                submission_id,
            )
    except Exception:
        log.exception(
            "File was deleted from Storage, but database path cleanup failed "
            "for submission %s",
            submission_id,
        )


def list_requests(status: SubmissionStatus, limit: int) -> list[ReviewItem]:
    # The Approved tab is a history of approved course requests, not a list of
    # every paper that has been published for existing courses.
    rows = submissions.list_by_status(
        status,
        limit,
        course_requests_only=status == "approved",
    )
    return _items(rows)


def my_activity(admin: CurrentUser) -> list[ReviewItem]:
    """New-course requests that this admin (and only this admin) approved or rejected."""
    return _items([r for r in submissions.list_reviewed_by(admin.id) if r.new_course is not None])


def preview(submission_id: str) -> tuple[bytes, str]:
    row = _get_pending(submission_id)
    if not row.storage_path:
        raise NotFound("The temporary file for this request is no longer available.")
    return storage.download_pdf(row.storage_path), row.original_filename


def approve(admin: CurrentUser, submission_id: str) -> ReviewItem:
    row = _get_pending(submission_id)
    if not row.storage_path:
        raise Conflict("The temporary file for this request is missing, so it can't be approved. Reject it instead.")
    content = storage.download_pdf(row.storage_path)

    # 1. the course (and department) the student asked for. Created only now, on approval.
    course, created_course, new_dept = None, False, None
    if row.course_id:  # an older request for a course that already existed
        course = courses.get_many([row.course_id]).get(row.course_id)
    elif row.new_course:
        wanted = row.new_course
        course, created_course, new_dept = catalog.get_or_create_course(
            code=wanted.code, name=wanted.name, department=wanted.department, semester=wanted.semester,
        )
        if not course.is_active:
            _undo_catalog(course, created_course, new_dept)
            raise BadRequest("That course exists but is not accepting uploads. Reject this request instead.")
    if course is None:
        raise Conflict("This request has no course attached. Reject it instead.")

    # 2. copy to Google Drive. If this fails the request stays pending and can be retried.
    label = f"{course.course_code} · {row.exam_type} {row.exam_year}"
    try:
        uploaded = google_drive.upload_pdf_bytes_to_shared_drive(content, f"{label} - {row.original_filename}")
    except Exception:
        _undo_catalog(course, created_course, new_dept)
        raise
    drive_file_id = uploaded["file_id"]

    # 3. record the approval (and the Drive file id students' Search needs)
    try:
        updated = submissions.decide(
            submission_id, status="approved", reviewed_by=admin.id,
            drive_file_id=drive_file_id, course_id=course.id,
        )
    except submissions.DuplicateSubmission as exc:
        google_drive.delete_file_from_shared_drive(drive_file_id)
        _undo_catalog(course, created_course, new_dept)
        raise Conflict("A paper for this course, year and exam type is already published. Reject this request.") from exc
    except Exception:
        google_drive.delete_file_from_shared_drive(drive_file_id)
        _undo_catalog(course, created_course, new_dept)
        raise
    if updated is None:  # another admin decided in the meantime
        google_drive.delete_file_from_shared_drive(drive_file_id)
        _undo_catalog(course, created_course, new_dept)
        raise Conflict("Another admin has already reviewed this request.")

    # 4. the temporary copy is no longer needed
    _cleanup_temporary_file(submission_id, row.storage_path)
    return _items([updated])[0]


def reject(admin: CurrentUser, submission_id: str, reason: str) -> ReviewItem:
    row = _get_pending(submission_id)
    updated = submissions.decide(
        submission_id, status="rejected", reviewed_by=admin.id, rejection_reason=reason
    )
    if updated is None:
        raise Conflict("Another admin has already reviewed this request.")
    if row.storage_path:  # nothing was created; the temporary file is simply thrown away
        _cleanup_temporary_file(submission_id, row.storage_path)
    return _items([updated])[0]
