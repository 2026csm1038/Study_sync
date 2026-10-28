"""Business logic for the Admin Dashboard (Page 5): the numbers and the Recent Activity list.

Recent Activity mixes four kinds of events from every user, so an admin also sees what other admins did:
    uploaded       a student submitted a paper (it is waiting for review, or was already decided)
    approved       an admin approved a request
    rejected       an admin rejected a request
    course_added   a new course was created
"""
from typing import get_args

from ..repositories import dashboard as stats
from ..repositories import profiles
from ..schemas.dashboard import ActivityOut, DashboardOut
from ..schemas.submission import ExamType, SubmissionRow

EXAM_TYPES = list(get_args(ExamType))  # Midsem, Endsem, Lab Test, Tutorials


def _title(row: SubmissionRow, codes: dict[str, str]) -> str:
    code = codes.get(row.course_id)
    return f"{code} {row.exam_type} {row.exam_year}" if code else row.original_filename


def _activity(limit: int) -> list[ActivityOut]:
    uploads = stats.latest_submissions(limit)
    decisions = stats.latest_decisions(limit)
    courses = stats.latest_courses(limit)

    codes = stats.course_codes([row.course_id for row in uploads + decisions])
    people = profiles.get_many(
        [row.uploaded_by for row in uploads] + [row.reviewed_by for row in decisions if row.reviewed_by]
    )

    def name(user_id: str | None) -> str | None:
        person = people.get(user_id) if user_id else None
        return person.full_name if person else None

    events: list[ActivityOut] = []
    for row in uploads:
        if row.created_at:
            events.append(ActivityOut(
                id=f"{row.id}:uploaded", kind="uploaded", at=row.created_at,
                text=f"{_title(row, codes)} submitted for review", actor=name(row.uploaded_by),
            ))
    for row in decisions:
        if row.reviewed_at:
            events.append(ActivityOut(
                id=f"{row.id}:{row.status}", kind=row.status, at=row.reviewed_at,
                text=f"{_title(row, codes)} {row.status}", actor=name(row.reviewed_by),
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
