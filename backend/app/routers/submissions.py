"""Student PDF submissions (Page 4: Upload PDF).

    POST /api/submissions        upload a PDF + its details (multipart form)
    GET  /api/submissions/mine   the caller's own submissions and their review status

The router only handles HTTP. The rules live in services/submissions.py.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from ..deps import CurrentUser, get_current_user
from ..repositories import submissions as repo
from ..schemas.submission import ExamType, SubmissionCreate, SubmissionOut
from ..services import submissions as service

router = APIRouter(prefix="/api/submissions", tags=["submissions"])


def submission_details(
    course_id: UUID = Form(...),
    exam_year: int = Form(...),
    exam_type: ExamType = Form(...),
    tags: str | None = Form(default=None),
) -> SubmissionCreate:
    """The text fields of the upload form, checked by the SubmissionCreate model.
    (A multipart request can't be read as one JSON-style model, so each field is a Form field.)"""
    try:
        return SubmissionCreate(course_id=course_id, exam_year=exam_year, exam_type=exam_type, tags=tags)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors(include_url=False, include_context=False))


@router.post("", response_model=SubmissionOut, status_code=status.HTTP_201_CREATED)
def upload_paper(
    details: SubmissionCreate = Depends(submission_details),
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
):
    """Check the details for a duplicate first. A duplicate is rejected with 409 and the reason
    in `detail`; otherwise the PDF is stored privately and the submission starts as 'pending'."""
    return service.submit_paper(user, details, file)


@router.get("/mine", response_model=list[SubmissionOut])
def my_submissions(user: CurrentUser = Depends(get_current_user)):
    return [service.to_out(row) for row in repo.list_for_user(user.id)]
