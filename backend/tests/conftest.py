"""Shared test setup: an in-memory fake of Supabase, so tests need no keys or network."""
from types import SimpleNamespace as NS
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import supabase_client
from app.main import app
from app.routers import auth as auth_mod

STUDENT = {"id": "u1", "email": "v@x.com", "full_name": "Vanshika", "entry_number": "2026CSM1038", "role": "student"}
ADMIN = {"id": "u2", "email": "a@x.com", "full_name": "Admin", "entry_number": None, "role": "admin"}

DEPT_CSE = "11111111-1111-4111-8111-111111111111"
DEPT_MATH = "22222222-2222-4222-8222-222222222222"


class FakeQuery:
    """Just enough of  table(...).select/insert/update/delete(...).eq/or_/order/limit(...).execute()."""

    def __init__(self, rows, state):
        self.rows, self.state = rows, state
        self.mode, self.payload, self.filters, self.search, self.order_by = "select", None, [], None, None

    def select(self, *_a, **_k):
        return self

    def insert(self, payload):
        self.mode, self.payload = "insert", payload
        return self

    def update(self, payload):
        self.mode, self.payload = "update", payload
        return self

    def delete(self):
        self.mode = "delete"
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def or_(self, expression):  # "course_code.ilike.%x%,course_name.ilike.%x%"
        self.search = expression
        return self

    def order(self, column, **_k):
        self.order_by = column
        return self

    def limit(self, _n):
        return self

    def execute(self):
        if self.state.fail_next and self.mode in ("insert", "update", "delete"):  # only writes fail
            error, self.state.fail_next = self.state.fail_next, None
            raise error
        if self.mode == "insert":
            row = {"id": str(uuid4()), "created_at": None, "updated_at": None, **self.payload}
            self.rows.append(row)
            return NS(data=[row])

        matched = [r for r in self.rows if all(r.get(c) == v for c, v in self.filters)]
        if self.search:
            term = self.search.split("%")[1].lower()
            matched = [r for r in matched if term in str(r.get("course_code", "")).lower()
                       or term in str(r.get("course_name", "")).lower()]
        if self.mode == "update":
            for r in matched:
                r.update(self.payload)
        elif self.mode == "delete":
            for r in matched:
                self.rows.remove(r)
        if self.order_by:
            matched = sorted(matched, key=lambda r: r[self.order_by])
        return NS(data=[dict(r) for r in matched])


def make_course(code, name, dept=DEPT_CSE, semester=3, active=True):
    return {"id": str(uuid4()), "course_code": code, "course_name": name, "department_id": dept,
            "semester": semester, "description": None, "is_active": active,
            "created_at": "2026-10-01T10:00:00+00:00", "updated_at": None,
            "internal_note": "never expose this column"}  # a column the API must NOT leak


def make_session(user=STUDENT):
    u = NS(id=user["id"], email=user["email"], identities=[object()])
    return NS(access_token="AT", refresh_token="RT", expires_in=3600, user=u)


@pytest.fixture
def env(monkeypatch):
    db = {
        "profiles": [dict(STUDENT), dict(ADMIN)],
        "courses": [
            make_course("CSE201", "Data Structures and Algorithms"),
            make_course("CSE202", "Operating Systems"),
            make_course("MAT201", "Linear Algebra", dept=DEPT_MATH, semester=2),
            make_course("CSE999", "Retired Course", active=False),
        ],
    }
    state = NS(fail_next=None)
    admin, anon = MagicMock(), MagicMock()
    admin.table.side_effect = lambda name: FakeQuery(db[name], state)
    anon.auth.sign_in_with_password.return_value = NS(session=make_session())
    settings = NS(supabase_configured=True, supabase_admin_configured=True, frontend_url="http://localhost:5173")

    monkeypatch.setattr(supabase_client, "supabase_admin", admin)
    monkeypatch.setattr(supabase_client, "new_anon_client", lambda: anon)
    monkeypatch.setattr(auth_mod, "settings", settings)
    return NS(admin=admin, anon=anon, db=db, state=state, client=TestClient(app))


def as_user(env, user):
    """Headers that make the next request look like it comes from `user`."""
    env.admin.auth.get_user.return_value = NS(user=NS(id=user["id"], email=user["email"]))
    return {"Authorization": "Bearer tok"}
