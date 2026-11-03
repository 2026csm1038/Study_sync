"""Pydantic models for published resource uploads."""
import re
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from .course import _clean_code
from pydantic import BaseModel, Field, field_validator, model_validator

ExamType = Literal["Midsem", "Endsem", "Lab Test", "Tutorials"]
SubmissionStatus = Literal["pending", "approved", "rejected"]
FIRST_YEAR = 2000



class SubmissionCreate(BaseModel):
    """What the upload form sends.

    Either pick an existing course (`course_id`), or type a new one (`course_code`, `course_name`,
    `department`, `semester`). A typed course that already exists is simply reused; a new course
    (and new department, if needed) is created automatically when the PDF is saved.
    """
    course_id: UUID | None = None
    course_code: str | None = Field(default=None, max_length=30)
    course_name: str | None = Field(default=None, max_length=150)
    department: str | None = Field(default=None, max_length=100)
    semester: int | None = Field(default=None, ge=1, le=12)
    exam_year: int = Field(ge=FIRST_YEAR)
    exam_type: ExamType
    tags: str | None = Field(default=None, max_length=300)

    @field_validator("exam_year")
    @classmethod
    def _not_in_the_future(cls, v: int) -> int:
        if v > datetime.now(timezone.utc).year:
            raise ValueError("The exam year can't be in the future.")
        return v

    @field_validator("course_code", "course_name", "department", mode="before")
    @classmethod
    def _clean_typed(cls, v):
        if isinstance(v, str):
            v = re.sub(r"\s+", " ", v).strip()
        return v or None

    @field_validator("course_code")
    @classmethod
    def _code(cls, v: str | None) -> str | None:
        return _clean_code(v) if v else v

    @model_validator(mode="after")
    def _course_given(self):
        if self.course_id:
            return self
        missing = [
            label
            for label, value in (
                ("course code", self.course_code),
                ("course name", self.course_name),
                ("department", self.department),
                ("semester", self.semester),
            )
            if not value
        ]
        if missing:
            raise ValueError("Choose a course, or enter its " + ", ".join(missing) + ".")
        return self

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
    storage_path: str | None = None
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
    """Metadata written after the PDF has been uploaded directly to Google Drive."""
    course_id: UUID
    exam_year: int
    exam_type: ExamType
    tags: str | None
    original_filename: str
    storage_path: str | None = None
    file_size_bytes: int
    file_sha256: str
    uploaded_by: str
    status: SubmissionStatus = "approved"
    drive_file_id: str


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
