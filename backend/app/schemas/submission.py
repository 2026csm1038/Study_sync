"""Pydantic models for student PDF submissions (the Upload PDF page).

    SubmissionCreate  the form fields the student fills in (sent together with the PDF)
    SubmissionRow     a row of `resource_submissions`, exactly as stored. Internal only.
    SubmissionOut     what the API sends back. Leaves out the storage path and file hash.
"""
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

ExamType = Literal["Midsem", "Endsem", "Lab Test", "Tutorials"]
SubmissionStatus = Literal["pending", "approved", "rejected"]

FIRST_YEAR = 2000


class SubmissionCreate(BaseModel):
    course_id: UUID
    exam_year: int = Field(ge=FIRST_YEAR)
    exam_type: ExamType
    tags: str | None = Field(default=None, max_length=300)

    @field_validator("exam_year")
    @classmethod
    def _not_in_the_future(cls, v: int) -> int:
        if v > datetime.now(timezone.utc).year:
            raise ValueError("The exam year can't be in the future.")
        return v

    @field_validator("tags")
    @classmethod
    def _clean_tags(cls, v: str | None) -> str | None:
        v = v.strip() if v else v
        return v or None


class SubmissionRow(BaseModel):
    id: str
    course_id: str
    exam_year: int
    exam_type: ExamType
    tags: str | None = None
    original_filename: str
    storage_path: str
    file_size_bytes: int
    file_sha256: str
    uploaded_by: str
    status: SubmissionStatus
    rejection_reason: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    drive_file_id: str | None = None
    created_at: datetime | None = None


class SubmissionInsert(BaseModel):
    """Everything written when a new submission is saved (status starts as 'pending')."""

    course_id: UUID
    exam_year: int
    exam_type: ExamType
    tags: str | None
    original_filename: str
    storage_path: str
    file_size_bytes: int
    file_sha256: str
    uploaded_by: str


class SubmissionOut(BaseModel):
    id: str
    course_id: str
    exam_year: int
    exam_type: ExamType
    tags: str | None = None
    original_filename: str
    file_size_bytes: int
    status: SubmissionStatus
    rejection_reason: str | None = None
    created_at: datetime | None = None
