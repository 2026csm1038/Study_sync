"""Tests for GET /api/admin/dashboard (Page 5: Admin Dashboard). Supabase is faked."""
from types import SimpleNamespace as NS
from uuid import uuid4

import pytest

from .conftest import ADMIN, STUDENT, FakeQuery, as_user

SECOND_ADMIN = {"id": "u5", "email": "b@x.com", "full_name": "Second Admin", "entry_number": None, "role": "admin"}


class CountingFakeQuery(FakeQuery):
    """Like the shared fake, but also reports how many rows matched (what count='exact' returns)."""

    def execute(self):
        result = super().execute()
        return NS(data=result.data, count=len(result.data))


def make_submission(course, exam, year, status, created, *, uploader="u1", reviewer=None, reviewed=None):
    return {
        "id": str(uuid4()), "course_id": course["id"], "exam_year": year, "exam_type": exam, "tags": None,
        "original_filename": f"{exam}_{year}.pdf", "storage_path": None, "file_size_bytes": 1000,
        "file_sha256": uuid4().hex, "uploaded_by": uploader, "status": status, "rejection_reason": None,
        "reviewed_by": reviewer, "reviewed_at": reviewed, "drive_file_id": "d" if status == "approved" else None,
        "created_at": created,
    }


@pytest.fixture
def denv(env):
    """env + students, two admins, courses with known dates, and requests in every status."""
    env.db["profiles"] += [
        {"id": "u3", "email": "s3@x.com", "full_name": "Niharika", "entry_number": "2026CSM1015", "role": "student"},
        {"id": "u4", "email": "s4@x.com", "full_name": "Student Four", "entry_number": "2026CSM1099", "role": "student"},
        dict(SECOND_ADMIN),
    ]
    cse201, cse202, mat201 = env.db["courses"][0], env.db["courses"][1], env.db["courses"][2]
    cse201["created_at"] = "2026-10-20T09:00:00+00:00"  # the newest course
    env.db["resource_submissions"] = [
        make_submission(cse201, "Midsem", 2025, "approved", "2026-10-10T08:00:00+00:00", reviewer="u2", reviewed="2026-10-12T10:00:00+00:00"),
        make_submission(cse201, "Endsem", 2024, "approved", "2026-10-11T08:00:00+00:00", reviewer="u5", reviewed="2026-10-13T11:00:00+00:00"),
        make_submission(cse202, "Midsem", 2025, "approved", "2026-10-12T08:00:00+00:00", reviewer="u2", reviewed="2026-10-14T10:00:00+00:00"),
        make_submission(mat201, "Tutorials", 2025, "approved", "2026-10-13T08:00:00+00:00", reviewer="u5", reviewed="2026-10-15T10:00:00+00:00"),
        make_submission(cse202, "Endsem", 2023, "rejected", "2026-10-16T08:00:00+00:00", reviewer="u2", reviewed="2026-10-21T10:00:00+00:00"),
        make_submission(cse201, "Lab Test", 2025, "pending", "2026-10-25T12:00:00+00:00"),
    ]
    env.admin.table.side_effect = lambda name: CountingFakeQuery(env.db[name], env.state)
    return env


def dashboard(env, user=ADMIN, **params):
    return env.client.get("/api/admin/dashboard", params=params, headers=as_user(env, user))


# ---------------------------------------------------------------- access ---

def test_login_is_required(denv):
    assert denv.client.get("/api/admin/dashboard").status_code == 401


def test_students_cannot_open_the_dashboard(denv):
    assert dashboard(denv, STUDENT).status_code == 403


# --------------------------------------------------------------- numbers ---

def test_counts(denv):
    body = dashboard(denv).json()
    assert body["total_students"] == 3           # admins are not students
    assert body["total_courses"] == 4            # all courses, including the inactive one
    assert body["resources_by_type"] == {"Midsem": 2, "Endsem": 1, "Lab Test": 0, "Tutorials": 1}
    assert body["total_resources"] == 4          # only approved papers count; pending and rejected do not


def test_an_empty_system_gives_zeros(env):
    env.db["profiles"] = [dict(ADMIN)]
    env.db["courses"].clear()
    env.admin.table.side_effect = lambda name: CountingFakeQuery(env.db[name], env.state)
    body = dashboard(env).json()
    assert body["total_students"] == body["total_courses"] == body["total_resources"] == 0
    assert body["resources_by_type"] == {"Midsem": 0, "Endsem": 0, "Lab Test": 0, "Tutorials": 0}
    assert body["recent_activity"] == []


# -------------------------------------------------------------- activity ---

def test_activity_is_newest_first_and_names_the_events(denv):
    activity = dashboard(denv).json()["recent_activity"]
    assert [(a["kind"], a["text"], a["actor"]) for a in activity[:3]] == [
        ("uploaded", "CSE201 Lab Test 2025 submitted for review", "Vanshika"),
        ("rejected", "CSE202 Endsem 2023 rejected", "Admin"),
        ("course_added", "New course added: CSE201", None),
    ]
    times = [a["at"] for a in activity]
    assert times == sorted(times, reverse=True)


def test_activity_includes_every_kind_of_event_and_other_admins(denv):
    activity = dashboard(denv).json()["recent_activity"]
    assert {a["kind"] for a in activity} == {"uploaded", "approved", "rejected", "course_added"}
    # approvals made by the other admin show up too, with that admin's name
    assert any(a["text"] == "MAT201 Tutorials 2025 approved" and a["actor"] == "Second Admin" for a in activity)
    assert any(a["text"] == "CSE201 Endsem 2024 approved" and a["actor"] == "Second Admin" for a in activity)


def test_every_activity_line_has_its_own_id(denv):
    ids = [a["id"] for a in dashboard(denv).json()["recent_activity"]]
    assert len(ids) == len(set(ids))


def test_activity_limit(denv):
    assert len(dashboard(denv, activity_limit=2).json()["recent_activity"]) == 2


@pytest.mark.parametrize("limit", [0, 51])
def test_activity_limit_is_validated(denv, limit):
    assert dashboard(denv, activity_limit=limit).status_code == 422


# ----------------------------------------------------------------- shape ---

def test_response_has_only_the_dashboard_fields(denv):
    body = dashboard(denv).json()
    assert set(body) == {"total_students", "total_courses", "total_resources", "resources_by_type", "recent_activity"}
    assert set(body["recent_activity"][0]) == {"id", "kind", "text", "actor", "at"}
