"""Tests for GET /api/admin/reports/summary (notification numbers for the admin). Supabase is faked."""
from .conftest import ADMIN, STUDENT, as_user


def flag(resource, reporter, status="open"):
    return {"resource_id": resource, "reporter_id": reporter, "status": status}


def summary(env, user=ADMIN):
    return env.client.get("/api/admin/reports/summary", headers=as_user(env, user))


def test_login_and_admin_role_are_required(env):
    assert env.client.get("/api/admin/reports/summary").status_code == 401
    assert summary(env, STUDENT).status_code == 403


def test_no_flags_gives_zeros(env):
    env.db["resource_flags"] = []
    assert summary(env).json() == {"open_flags": 0, "flagged_resources": 0, "needs_attention": 0, "threshold": 5}


def test_five_student_flags_or_one_professor_flag_needs_attention(env):
    env.db["profiles"] += [{"id": f"s{i}", "email": None, "full_name": f"S{i}", "entry_number": None, "role": "student"} for i in range(5)]
    env.db["profiles"].append({"id": "p1", "email": None, "full_name": "Prof", "entry_number": None, "role": "professor"})
    env.db["resource_flags"] = (
        [flag("A", f"s{i}") for i in range(5)]   # five students on A -> 5
        + [flag("B", "p1")]                      # one professor on B -> 5
        + [flag("C", "s0"), flag("C", "s1")]     # two students on C -> 2, below the threshold
    )
    assert summary(env).json() == {"open_flags": 8, "flagged_resources": 3, "needs_attention": 2, "threshold": 5}


def test_resolved_and_dismissed_flags_do_not_count(env):
    env.db["profiles"].append({"id": "p1", "email": None, "full_name": "Prof", "entry_number": None, "role": "professor"})
    env.db["resource_flags"] = [flag("A", "p1", "resolved"), flag("B", "p1", "dismissed")]
    assert summary(env).json()["needs_attention"] == 0
    assert summary(env).json()["open_flags"] == 0
