"""Pydantic models for courses. One model per job:

    CourseCreate  what the browser sends to add a course         (POST)
    CourseUpdate  what it sends to change one; every field optional (PATCH)
    CourseOut     what the API sends back; also validates the database row

Copy this file's shape for every new table (resources, upload_requests, ...).
"""
import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

COURSE_CODE_RE = re.compile(r"^[A-Z0-9\-]{3,30}$")


def _clean_code(value: str) -> str:
    value = value.strip().upper()
    if not COURSE_CODE_RE.match(value):
        raise ValueError("Course code may only contain letters, digits and hyphens, e.g. CSE201.")
    return value


def _clean_text(value: str | None) -> str | None:
    return value.strip() if isinstance(value, str) else value


class CourseCreate(BaseModel):
    course_code: str = Field(min_length=3, max_length=30)
    course_name: str = Field(min_length=2, max_length=150)
    department_id: UUID
    semester: int = Field(ge=1, le=12)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool = True

    @field_validator("course_code")
    @classmethod
    def _code(cls, v: str) -> str:
        return _clean_code(v)

    @field_validator("course_name", "description", mode="before")
    @classmethod
    def _text(cls, v):
        return _clean_text(v)


class CourseUpdate(BaseModel):
    course_code: str | None = Field(default=None, min_length=3, max_length=30)
    course_name: str | None = Field(default=None, min_length=2, max_length=150)
    department_id: UUID | None = None
    semester: int | None = Field(default=None, ge=1, le=12)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None

    @field_validator("course_code")
    @classmethod
    def _code(cls, v: str | None) -> str | None:
        return _clean_code(v) if v is not None else v

    @field_validator("course_name", "description", mode="before")
    @classmethod
    def _text(cls, v):
        return _clean_text(v)

    @model_validator(mode="after")
    def _at_least_one_field(self):
        if not self.model_fields_set:
            raise ValueError("Send at least one field to update.")
        return self


class CourseOut(BaseModel):
    id: UUID
    course_code: str
    course_name: str
    department_id: UUID
    semester: int
    description: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
