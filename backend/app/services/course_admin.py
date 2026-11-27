"""Business rules for the admin's Manage Courses page.

Plain add / edit go straight through routers/courses.py -> repositories/courses.py. What lives here
is what needs more than one table:

  * list_for_admin  the courses plus how many papers hang off each one
  * delete          refuses while papers are attached, so nothing is orphaned
"""
from uuid import UUID

from ..exceptions import Conflict
from ..repositories import courses, submissions
from ..schemas.course import CourseAdminOut


def _admin_view(course, counts: dict[str, int]) -> CourseAdminOut:
    published, pending, removed = counts.get("approved", 0), counts.get("pending", 0), counts.get("deleted", 0)
    return CourseAdminOut(
        **course.model_dump(),
        resource_count=published,
        pending_count=pending,
        removed_count=removed,
        can_delete=published + pending + removed == 0,
    )


def list_for_admin(**filters) -> list[CourseAdminOut]:
    rows = courses.list_courses(include_inactive=True, **filters)
    counts = submissions.count_by_course()
    return [_admin_view(c, counts.get(str(c.id), {})) for c in rows]


def delete(course_id: UUID) -> None:
    """Delete a course for good. Rejected uploads are cleared with it; anything else blocks the delete."""
    courses.get_course(course_id)  # 404 if it does not exist
    counts = submissions.count_by_course(str(course_id)).get(str(course_id), {})
    attached = counts.get("approved", 0) + counts.get("pending", 0)
    if attached:
        raise Conflict(
            f"This course still has {attached} published or pending paper(s). "
            "Deactivate it instead of deleting it, or remove those papers first."
        )
    if counts.get("deleted", 0):
        raise Conflict(
            f"This course has {counts['deleted']} removed paper(s) that can still be restored. "
            "Delete them permanently from Resource Reports first, or deactivate the course."
        )
    submissions.delete_rejected_for_course(str(course_id))
    courses.delete_course(course_id)
