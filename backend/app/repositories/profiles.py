"""All reads of the `profiles` table. Returns Pydantic ProfileRow objects, never raw dicts."""
from ..schemas.profile import ProfileRow
from ..supabase_client import admin

COLUMNS = "id, email, full_name, entry_number, role, department_id, created_at"


def _first(column: str, value: str) -> ProfileRow | None:
    rows = admin().table("profiles").select(COLUMNS).eq(column, value).limit(1).execute().data
    return ProfileRow.model_validate(rows[0]) if rows else None


def get_by_id(user_id: str) -> ProfileRow | None:
    return _first("id", user_id)


def get_by_entry_number(entry_number: str) -> ProfileRow | None:
    return _first("entry_number", entry_number.upper())


def entry_number_exists(entry_number: str) -> bool:
    return get_by_entry_number(entry_number) is not None
