"""Pydantic models for the admin approval flow (Page 6: Manage Request).

    ReviewItem     one student request as the admin sees it (who, what, which course, review status)
    RejectRequest  what the admin sends to reject one: the reason the student will see
"""
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from .submission import ExamType, SubmissionStatus


class ReviewItem(BaseModel):
    id: str
    status: SubmissionStatus
    course_id: str
    course_code: str | None = None
    course_name: str | None = None
    exam_year: int
    exam_type: ExamType
    tags: str | None = None
    original_filename: str
    file_size_bytes: int
    uploaded_by_name: str | None = None
    uploaded_by_entry_number: str | None = None
    created_at: datetime | None = None
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None


class RejectRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Give the student a reason (at least 3 characters).")
        return v
