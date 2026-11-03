"""All database access for the `departments` table.

Same rules as the other repositories: it is the only place that calls supabase for this table,
it returns Pydantic models, and it raises domain errors, never HTTP errors.
"""
import re

from postgrest.exceptions import APIError

from ..exceptions import Conflict
from ..schemas.department import DepartmentOut
from ..supabase_client import admin

TABLE = "departments"
UNIQUE_VIOLATION = "23505"


def list_departments() -> list[DepartmentOut]:
    rows = admin().table(TABLE).select("*").order("name").execute().data
    return [DepartmentOut.model_validate(row) for row in rows]


def find_by_name_or_code(text: str) -> DepartmentOut | None:
    """Match what a student typed against existing departments, ignoring case and extra spaces.
    "cse", "CSE" and "computer  science" style variations all find the same row."""
    wanted = re.sub(r"\s+", " ", text).strip().lower()
    for dept in list_departments():
        if wanted in (dept.name.strip().lower(), (dept.code or "").strip().lower()):
            return dept
    return None


def create(name: str, code: str) -> DepartmentOut:
    try:
        rows = admin().table(TABLE).insert({"name": name, "code": code}).execute().data
    except APIError as exc:
        if exc.json().get("code") == UNIQUE_VIOLATION:
            raise Conflict("A department with this code already exists.")
        raise
    return DepartmentOut.model_validate(rows[0])


def delete(department_id) -> None:
    admin().table(TABLE).delete().eq("id", str(department_id)).execute()
