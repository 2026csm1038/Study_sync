"""Pydantic model for departments. Read-only: the Department filter on Page 3 lists them.

    DepartmentOut  what the API sends back; also validates the database row
"""
from uuid import UUID

from pydantic import BaseModel


class DepartmentOut(BaseModel):
    id: UUID
    name: str
    code: str | None = None
