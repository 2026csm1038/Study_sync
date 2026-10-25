"""Pydantic model for the student-facing resource list (Page 3: Student Search).

    ResourceOut  one approved paper as the search page shows it.
                 Leaves out storage paths, file hashes, reviewer details and the status column.
"""
from pydantic import BaseModel


class ResourceOut(BaseModel):
    id: str
    title: str
    resource_type: str
    course_code: str | None = None
    course_name: str | None = None
    semester: int | None = None
    academic_year: int | None = None
    exam_type: str | None = None
    tags: str | None = None
    google_drive_url: str
