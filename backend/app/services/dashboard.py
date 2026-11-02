"""Business logic for the Admin Dashboard."""
from typing import get_args

from ..repositories import dashboard as stats
from ..repositories import profiles
from ..schemas.dashboard import ActivityOut, DashboardOut
from ..schemas.submission import ExamType, SubmissionRow

EXAM_TYPES = list(get_args(ExamType))


def _title(row: SubmissionRow, codes: dict[str, str]) -> str:
    code = codes.get(row.course_id)
    return f"{code} {row.exam_type} {row.exam_year}" if code else row.original_filename


def _activity(limit: int) -> list[ActivityOut]:
    uploads = stats.latest_submissions(limit)
    courses = stats.latest_courses(limit)
    codes = stats.course_codes([row.course_id for row in uploads])
    people = profiles.get_many([row.uploaded_by for row in uploads])

    events: list[ActivityOut] = []
    for row in uploads:
        if row.created_at:
            events.append(ActivityOut(
                id=f"{row.id}:uploaded", kind="uploaded", at=row.created_at,
                text=f"{_title(row, codes)} uploaded and published", 
                actor=(people.get(row.uploaded_by).full_name if people.get(row.uploaded_by) else None),
            ))
    for course in courses:
        if course.created_at:
            events.append(ActivityOut(
                id=f"{course.id}:course_added", kind="course_added", at=course.created_at,
                text=f"New course added: {course.course_code}",
            ))
    events.sort(key=lambda event: event.at, reverse=True)
    return events[:limit]


def build(activity_limit: int = 20) -> DashboardOut:
    by_type = stats.count_approved_by_type(EXAM_TYPES)
    return DashboardOut(
        total_students=stats.count_students(),
        total_courses=stats.count_courses(),
        total_resources=sum(by_type.values()),
        resources_by_type=by_type,
        recent_activity=_activity(activity_limit),
    )
