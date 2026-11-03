"""Direct student PDF upload to Google Drive and resource metadata persistence."""
import hashlib
import re
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from pypdf import PdfReader

from ..deps import CurrentUser
from ..exceptions import BadRequest, Conflict, PayloadTooLarge, UnsupportedMediaType
from ..repositories import courses, departments, submissions
from ..schemas.course import CourseOut
from ..schemas.department import DepartmentOut
from ..schemas.submission import SubmissionCreate, SubmissionInsert, SubmissionOut, SubmissionRow
from . import catalog, google_drive

MAX_BYTES = 2 * 1024 * 1024  # keep in sync with the student upload UI


def read_pdf(file: UploadFile) -> bytes:
    """Read and validate a small, non-empty, readable PDF before sending it to Drive."""
    content = file.file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise PayloadTooLarge("The file is larger than 2 MB.")
    if not content:
        raise BadRequest("The PDF is empty.")

    name = (file.filename or "").lower()
    looks_like_pdf = content.startswith(b"%PDF-") and (
        file.content_type in ("application/pdf", "application/x-pdf") or name.endswith(".pdf")
    )
    if not looks_like_pdf:
        raise UnsupportedMediaType("Only PDF files are allowed.")
    try:
        if len(PdfReader(BytesIO(content)).pages) < 1:
            raise ValueError("no pages")
    except Exception as exc:
        raise UnsupportedMediaType("This PDF can't be read. It may be damaged or password-protected.") from exc
    return content


def _safe_filename(raw: str | None) -> str:
    name = Path((raw or "paper.pdf").replace("\\", "/")).name
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip() or "paper.pdf"
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name[:255]


def _label(course: CourseOut, exam_type: str, exam_year: int) -> str:
    return f"{course.course_code} · {exam_type} {exam_year}"


def _duplicate_reason(
    course: CourseOut | None,
    exam_type: str,
    exam_year: int,
    sha256: str,
) -> str | None:
    """Why this upload is a duplicate, or None if it is fine."""
    # Midsem and Endsem: only one paper per course, year and exam type. A brand-new course
    # has no papers yet, so there is nothing to compare with.
    if course is not None and exam_type in ("Midsem", "Endsem"):
        if submissions.find_live_by_metadata(str(course.id), exam_year, exam_type):
            label = _label(course, exam_type, exam_year)
            return f"A paper for {label} is already available on StudySync."

    # Any exam type: the exact same PDF can't be uploaded twice, whatever details it comes with.
    if submissions.find_live_by_hash(sha256):
        return "This exact PDF has already been uploaded to StudySync."

    return None


def _undo_catalog(course: CourseOut | None, created_course: bool, dept: DepartmentOut | None) -> None:
    """Remove a course/department that this upload created, if the upload then failed.
    Best effort: if somebody else has started using them meanwhile, the delete is refused and they stay."""
    try:
        if created_course and course:
            courses.delete_course(course.id)
        if dept:
            departments.delete(dept.id)
    except Exception:
        pass


def submit_paper(user: CurrentUser, data: SubmissionCreate, file: UploadFile) -> SubmissionOut:
    content = read_pdf(file)

    # An existing course (picked, or typed with a code that already exists). Nothing is created yet:
    # we only create a new course/department once the PDF has passed every check and is on Drive,
    # so a rejected or failed upload leaves no stray courses behind.
    course = courses.get_course(data.course_id) if data.course_id else courses.find_by_code(data.course_code)
    if course is not None and not course.is_active:
        raise BadRequest("This course is not accepting uploads.")

    sha256 = hashlib.sha256(content).hexdigest()
    reason = _duplicate_reason(course, data.exam_type, data.exam_year, sha256)
    if reason:
        raise Conflict(reason)

    filename = _safe_filename(file.filename)
    label_course = course.course_code if course else data.course_code
    drive_name = f"{label_course} · {data.exam_type} {data.exam_year} - {filename}"
    uploaded = google_drive.upload_pdf_bytes_to_shared_drive(content, drive_name)
    drive_file_id = uploaded["file_id"]

    created_course, new_dept = False, None
    try:
        if course is None:
            course, created_course, new_dept = catalog.get_or_create_course(
                code=data.course_code,
                name=data.course_name,
                department=data.department,
                semester=data.semester,
            )
            if not course.is_active:
                raise BadRequest("This course is not accepting uploads.")
        row = submissions.create(SubmissionInsert(
            course_id=course.id,
            exam_year=data.exam_year,
            exam_type=data.exam_type,
            tags=data.tags,
            original_filename=filename,
            storage_path=None,
            file_size_bytes=len(content),
            file_sha256=sha256,
            uploaded_by=user.id,
            status="approved",
            drive_file_id=drive_file_id,
        ))
    except submissions.DuplicateSubmission as exc:
        google_drive.delete_file_from_shared_drive(drive_file_id)
        _undo_catalog(course, created_course, new_dept)
        raise Conflict(_duplicate_reason(course, data.exam_type, data.exam_year, sha256) or
                       "This paper was just uploaded by someone else.") from exc
    except Exception:
        # Compensate for a successful Drive upload if saving the details fails.
        google_drive.delete_file_from_shared_drive(drive_file_id)
        _undo_catalog(course, created_course, new_dept)
        raise

    return to_out(row)


def to_out(row: SubmissionRow) -> SubmissionOut:
    return SubmissionOut(**row.model_dump(include=set(SubmissionOut.model_fields)))
