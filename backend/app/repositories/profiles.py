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


def get_many(user_ids: list[str]) -> dict[str, ProfileRow]:
    """Several profiles at once, keyed by id. Used to show who uploaded what."""
    if not user_ids:
        return {}
    rows = admin().table("profiles").select(COLUMNS).in_("id", list(set(user_ids))).execute().data
    return {str(r["id"]): ProfileRow.model_validate(r) for r in rows}


def make_professor(user_id: str) -> None:
    """Turn a just-created student profile into a professor profile (no entry number).

    Only used when the email did not need confirming, so the profile already exists by the time
    the signup endpoint knows the role. It only ever changes a 'student' row, so it can never
    touch an admin."""
    (
        admin()
        .table("profiles")
        .update({"role": "professor", "entry_number": None})
        .eq("id", user_id)
        .eq("role", "student")
        .execute()
    )
