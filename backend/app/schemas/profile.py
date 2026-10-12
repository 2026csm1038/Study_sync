from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Role = Literal["student", "admin"]


class ProfileRow(BaseModel):
    """A row of the `profiles` table, exactly as stored. Internal: never return this from an endpoint."""

    id: str
    email: str | None = None
    full_name: str
    entry_number: str | None = None
    role: Role
    department_id: str | None = None
    created_at: datetime | None = None


class ProfileOut(BaseModel):
    """What the API sends to the browser: only the fields the app needs."""

    id: str
    email: str | None
    full_name: str
    entry_number: str | None
    role: Role
