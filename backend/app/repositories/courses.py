"""All database access for the `courses` table.

Rules for a repository:
  * it is the only place that calls supabase for this table
  * it takes Pydantic models in and returns Pydantic models out (never raw dicts)
  * it raises NotFound / Conflict, never HTTP errors
"""
import re
from datetime import datetime, timezone
from uuid import UUID

from postgrest.exceptions import APIError

from ..exceptions import BadRequest, Conflict, NotFound
from ..schemas.course import CourseCreate, CourseOut, CourseUpdate
from ..supabase_client import admin

TABLE = "courses"

# Postgres error codes
UNIQUE_VIOLATION = "23505"
FOREIGN_KEY_VIOLATION = "23503"


def _table():
    return admin().table(TABLE)


def _translate(exc: APIError, *, action: str):
    """Turn a database error into a domain error with a friendly message."""
    code = exc.json().get("code")
    if code == UNIQUE_VIOLATION:
        return Conflict("A course with this code already exists.")
    if code == FOREIGN_KEY_VIOLATION:
        if action == "delete":
            return Conflict("This course still has resources. Deactivate it instead of deleting it.")
        return BadRequest("That department does not exist.")
    return exc


def list_courses(
    *,
    department_id: UUID | None = None,
    semester: int | None = None,
    search: str | None = None,
    include_inactive: bool = False,
) -> list[CourseOut]:
    query = _table().select("*")
    if not include_inactive:
        query = query.eq("is_active", True)
    if department_id:
        query = query.eq("department_id", str(department_id))
    if semester:
        query = query.eq("semester", semester)
    if search:
        # keep only characters that are safe inside a PostgREST filter string
        term = re.sub(r"[^\w\s\-]", " ", search).strip()
        if term:
            query = query.or_(f"course_code.ilike.%{term}%,course_name.ilike.%{term}%")
    rows = query.order("course_code").execute().data
    return [CourseOut.model_validate(row) for row in rows]


def get_course(course_id: UUID) -> CourseOut:
    rows = _table().select("*").eq("id", str(course_id)).limit(1).execute().data
    if not rows:
        raise NotFound("Course not found.")
    return CourseOut.model_validate(rows[0])


def create_course(data: CourseCreate) -> CourseOut:
    try:
        rows = _table().insert(data.model_dump(mode="json")).execute().data
    except APIError as exc:
        raise _translate(exc, action="create")
    return CourseOut.model_validate(rows[0])


def update_course(course_id: UUID, data: CourseUpdate) -> CourseOut:
    changes = data.model_dump(mode="json", exclude_unset=True)
    changes["updated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        rows = _table().update(changes).eq("id", str(course_id)).execute().data
    except APIError as exc:
        raise _translate(exc, action="update")
    if not rows:
        raise NotFound("Course not found.")
    return CourseOut.model_validate(rows[0])


def delete_course(course_id: UUID) -> None:
    try:
        rows = _table().delete().eq("id", str(course_id)).execute().data
    except APIError as exc:
        raise _translate(exc, action="delete")
    if not rows:
        raise NotFound("Course not found.")


def get_many(course_ids: list[str]) -> dict[str, CourseOut]:
    """Several courses at once, keyed by id (inactive ones included)."""
    if not course_ids:
        return {}
    rows = _table().select("*").in_("id", list(set(course_ids))).execute().data
    return {str(r["id"]): CourseOut.model_validate(r) for r in rows}
