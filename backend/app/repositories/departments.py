"""All database access for the `departments` table (read-only).

Same rules as the other repositories: it is the only place that calls supabase for this table,
it returns Pydantic models, and it raises domain errors, never HTTP errors.
"""
from ..schemas.department import DepartmentOut
from ..supabase_client import admin

TABLE = "departments"


def list_departments() -> list[DepartmentOut]:
    rows = admin().table(TABLE).select("*").order("name").execute().data
    return [DepartmentOut.model_validate(row) for row in rows]
