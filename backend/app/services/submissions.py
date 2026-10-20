"""Business logic for a student's PDF upload.

    1. check the file itself       (PDF, not empty, at most 2 MB)
    2. check the course            (exists and is active)
    3. check for a duplicate       (same course + year + exam type, or the very same file)
         -> yes: reject with a reason, nothing is stored
    4. put the PDF in the private `pending-uploads` bucket
    5. save the metadata row as 'pending' (an admin reviews it later)
         -> if saving fails, the uploaded file is removed again
"""
import hashlib
import re
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from pypdf import PdfReader

from ..deps import CurrentUser
from ..exceptions import BadRequest, Conflict, PayloadTooLarge, UnsupportedMediaType
from ..repositories import courses, submissions
from ..schemas.course import CourseOut
from ..schemas.submission import SubmissionCreate, SubmissionInsert, SubmissionOut, SubmissionRow
from . import storage

MAX_BYTES = 2 * 1024 * 1024  # keep in sync with the bucket limit in submissions_setup.sql and the UI


def read_pdf(file: UploadFile) -> bytes:
    """Read the upload and make sure it really is a small, readable PDF."""
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
    except Exception:
        raise UnsupportedMediaType("This PDF can't be read. It may be damaged or password-protected.")
    return content


def _safe_filename(raw: str | None) -> str:
    name = Path((raw or "paper.pdf").replace("\\", "/")).name
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip() or "paper.pdf"
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name[:255]


def _label(course: CourseOut, exam_type: str, exam_year: int) -> str:
    return f"{course.course_code} · {exam_type} {exam_year}"


def _duplicate_reason(course: CourseOut, data: SubmissionCreate, sha256: str) -> str | None:
    """The reason to reject this upload, or None if it is not a duplicate."""
    same_paper = submissions.find_live_by_metadata(str(data.course_id), data.exam_year, data.exam_type)
    if same_paper:
        label = _label(course, data.exam_type, data.exam_year)
        if same_paper.status == "approved":
            return f"A paper for {label} is already available on StudySync."
        return f"A paper for {label} has already been submitted and is waiting for admin review."

    same_file = submissions.find_live_by_hash(sha256)
    if same_file:
        return (
            "This exact PDF has already been submitted for a different course, year or exam type. "
            "Check the details and try again."
        )
    return None


def submit_paper(user: CurrentUser, data: SubmissionCreate, file: UploadFile) -> SubmissionOut:
    content = read_pdf(file)

    course = courses.get_course(data.course_id)  # 404 if it does not exist
    if not course.is_active:
        raise BadRequest("This course is not accepting uploads.")

    sha256 = hashlib.sha256(content).hexdigest()

    reason = _duplicate_reason(course, data, sha256)
    if reason:
        raise Conflict(reason)

    path = f"{user.id}/{uuid4()}.pdf"
    storage.upload_pdf(path, content)

    try:
        row = submissions.create(
            SubmissionInsert(
                course_id=data.course_id,
                exam_year=data.exam_year,
                exam_type=data.exam_type,
                tags=data.tags,
                original_filename=_safe_filename(file.filename),
                storage_path=path,
                file_size_bytes=len(content),
                file_sha256=sha256,
                uploaded_by=user.id,
            )
        )
    except submissions.DuplicateSubmission:
        # two students submitted the same paper at the same moment; the database let only one through
        storage.delete_file(path)
        raise Conflict(
            _duplicate_reason(course, data, sha256)
            or "This paper was just submitted by someone else."
        )
    except Exception:
        storage.delete_file(path)
        raise

    return to_out(row)


def to_out(row: SubmissionRow) -> SubmissionOut:
    return SubmissionOut(**row.model_dump(include=set(SubmissionOut.model_fields)))
