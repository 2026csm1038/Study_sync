"""Pydantic models for the Admin Dashboard (Page 5).

    ActivityOut   one line of the Recent Activity list
    DashboardOut  everything the dashboard shows, in one response
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ActivityKind = Literal["uploaded", "approved", "rejected", "course_added"]


class ActivityOut(BaseModel):
    id: str
    kind: ActivityKind
    text: str
    actor: str | None = None  # who did it: the student who uploaded, or the admin who decided
    at: datetime


class DashboardOut(BaseModel):
    total_students: int
    total_courses: int
    total_resources: int  # approved papers, all types together
    resources_by_type: dict[str, int]  # approved papers per exam type (Midsem, Endsem, Lab Test, Tutorials)
    recent_activity: list[ActivityOut]  # newest first
