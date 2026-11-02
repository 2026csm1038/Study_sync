"""Direct student PDF upload to Google Drive and resource metadata persistence."""
import hashlib
import re
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from pypdf import PdfReader

from ..deps import CurrentUser
from ..exceptions import BadRequest, Conflict, PayloadTooLarge, UnsupportedMediaType
from ..repositories import courses, submissions
from ..schemas.course import CourseOut
from ..schemas.submission import SubmissionCreate, SubmissionInsert, SubmissionOut, SubmissionRow
from . import google_drive

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
    course: CourseOut,
    data: SubmissionCreate,
    sha256: str,
) -> str | None:
    """Check duplicate rules based on exam type."""

    # Multiple tutorials and quizzes are allowed for the same course/year.
    if data.exam_type in ("Tutorials", "Quizzes"):
        return None

    # Mid Sem and End Sem: only one upload per course, year and exam type.
    if data.exam_type in ("Mid Sem", "End Sem"):
        existing = submissions.find_live_by_metadata(
            str(data.course_id),
            data.exam_year,
            data.exam_type,
        )

        if existing:
            label = _label(course, data.exam_type, data.exam_year)
            return f"A paper for {label} has already been uploaded."

    return None


def submit_paper(user: CurrentUser, data: SubmissionCreate, file: UploadFile) -> SubmissionOut:
    content = read_pdf(file)
    course = courses.get_course(data.course_id)
    if not course.is_active:
        raise BadRequest("This course is not accepting uploads.")

    sha256 = hashlib.sha256(content).hexdigest()
    reason = _duplicate_reason(course, data, sha256)
    if reason:
        raise Conflict(reason)

    filename = _safe_filename(file.filename)
    drive_name = f"{_label(course, data.exam_type, data.exam_year)} - {filename}"
    uploaded = google_drive.upload_pdf_bytes_to_shared_drive(content, drive_name)
    drive_file_id = uploaded["file_id"]

    try:
        row = submissions.create(SubmissionInsert(
            course_id=data.course_id,
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
        raise Conflict(_duplicate_reason(course, data, sha256) or
                       "This paper was just uploaded by someone else.") from exc
    except Exception:
        # Compensate for a successful Drive upload if metadata persistence fails.
        google_drive.delete_file_from_shared_drive(drive_file_id)
        raise

    return to_out(row)


def to_out(row: SubmissionRow) -> SubmissionOut:
    return SubmissionOut(**row.model_dump(include=set(SubmissionOut.model_fields)))
