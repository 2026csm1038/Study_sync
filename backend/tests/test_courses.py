"""Tests for /api/courses. They also show what the Pydantic schemas protect you from."""
import pytest
from postgrest.exceptions import APIError

from .conftest import ADMIN, DEPT_CSE, DEPT_MATH, STUDENT, as_user

NEW_COURSE = {"course_code": " cse305 ", "course_name": "  Computer Networks ", "department_id": DEPT_CSE, "semester": 5}


def codes(response):
    return [c["course_code"] for c in response.json()]


# ------------------------------------------------------------------ reading ---

def test_requires_login(env):
    assert env.client.get("/api/courses").status_code == 401


def test_list_shows_only_active_courses_sorted(env):
    r = env.client.get("/api/courses", headers=as_user(env, STUDENT))
    assert r.status_code == 200 and codes(r) == ["CSE201", "CSE202", "MAT201"]


def test_response_never_leaks_unlisted_columns(env):
    row = env.client.get("/api/courses", headers=as_user(env, STUDENT)).json()[0]
    assert "internal_note" not in row  # the schema is a whitelist, not a pass-through


def test_filters(env):
    h = as_user(env, STUDENT)
    assert codes(env.client.get(f"/api/courses?department_id={DEPT_MATH}", headers=h)) == ["MAT201"]
    assert codes(env.client.get("/api/courses?semester=3", headers=h)) == ["CSE201", "CSE202"]
    assert codes(env.client.get("/api/courses?q=operating", headers=h)) == ["CSE202"]
    assert codes(env.client.get("/api/courses?q=mat2", headers=h)) == ["MAT201"]


@pytest.mark.parametrize("query", ["semester=0", "semester=13", "department_id=not-a-uuid"])
def test_bad_filters_are_rejected(env, query):
    assert env.client.get(f"/api/courses?{query}", headers=as_user(env, STUDENT)).status_code == 422


def test_inactive_courses_are_admin_only(env):
    assert env.client.get("/api/courses?include_inactive=true", headers=as_user(env, STUDENT)).status_code == 403
    r = env.client.get("/api/courses?include_inactive=true", headers=as_user(env, ADMIN))
    assert r.status_code == 200 and "CSE999" in codes(r)


def test_get_one_and_404(env):
    h = as_user(env, STUDENT)
    course_id = env.db["courses"][0]["id"]
    assert env.client.get(f"/api/courses/{course_id}", headers=h).json()["course_code"] == "CSE201"
    assert env.client.get("/api/courses/33333333-3333-4333-8333-333333333333", headers=h).status_code == 404


# ----------------------------------------------------------------- creating ---

def test_student_cannot_create(env):
    assert env.client.post("/api/courses", json=NEW_COURSE, headers=as_user(env, STUDENT)).status_code == 403


def test_admin_creates_course_with_cleaned_input(env):
    r = env.client.post("/api/courses", json=NEW_COURSE, headers=as_user(env, ADMIN))
    assert r.status_code == 201
    body = r.json()
    assert body["course_code"] == "CSE305" and body["course_name"] == "Computer Networks"  # trimmed + upper-cased
    assert body["is_active"] is True and body["id"]


@pytest.mark.parametrize("change", [
    {"semester": 0}, {"semester": 13}, {"course_code": "A"}, {"course_code": "CSE 305!"},
    {"course_name": ""}, {"department_id": "nope"},
])
def test_create_validation(env, change):
    r = env.client.post("/api/courses", json={**NEW_COURSE, **change}, headers=as_user(env, ADMIN))
    assert r.status_code == 422


def test_create_missing_field(env):
    body = {k: v for k, v in NEW_COURSE.items() if k != "semester"}
    assert env.client.post("/api/courses", json=body, headers=as_user(env, ADMIN)).status_code == 422


def test_duplicate_code_and_unknown_department(env):
    h = as_user(env, ADMIN)
    env.state.fail_next = APIError({"code": "23505", "message": "duplicate key"})
    r = env.client.post("/api/courses", json=NEW_COURSE, headers=h)
    assert r.status_code == 409 and "already exists" in r.json()["detail"]

    env.state.fail_next = APIError({"code": "23503", "message": "foreign key"})
    r = env.client.post("/api/courses", json=NEW_COURSE, headers=h)
    assert r.status_code == 400 and "department" in r.json()["detail"]


# ----------------------------------------------------------------- updating ---

def test_update_changes_only_sent_fields(env):
    course = env.db["courses"][0]
    r = env.client.patch(f"/api/courses/{course['id']}", json={"semester": 4, "is_active": False}, headers=as_user(env, ADMIN))
    assert r.status_code == 200
    body = r.json()
    assert body["semester"] == 4 and body["is_active"] is False
    assert body["course_name"] == "Data Structures and Algorithms"  # untouched
    assert course["updated_at"] is not None                          # timestamp refreshed


def test_update_rules(env):
    course_id = env.db["courses"][0]["id"]
    admin = as_user(env, ADMIN)
    assert env.client.patch(f"/api/courses/{course_id}", json={}, headers=admin).status_code == 422
    assert env.client.patch(f"/api/courses/{course_id}", json={"semester": 99}, headers=admin).status_code == 422
    assert env.client.patch("/api/courses/33333333-3333-4333-8333-333333333333", json={"semester": 2}, headers=admin).status_code == 404
    assert env.client.patch(f"/api/courses/{course_id}", json={"semester": 2}, headers=as_user(env, STUDENT)).status_code == 403


# ----------------------------------------------------------------- deleting ---

def test_delete(env):
    course_id = env.db["courses"][0]["id"]
    assert env.client.delete(f"/api/courses/{course_id}", headers=as_user(env, STUDENT)).status_code == 403
    assert env.client.delete(f"/api/courses/{course_id}", headers=as_user(env, ADMIN)).status_code == 204
    assert all(c["id"] != course_id for c in env.db["courses"])
    assert env.client.delete(f"/api/courses/{course_id}", headers=as_user(env, ADMIN)).status_code == 404


def test_cannot_delete_course_that_still_has_resources(env):
    env.state.fail_next = APIError({"code": "23503", "message": "foreign key"})
    r = env.client.delete(f"/api/courses/{env.db['courses'][0]['id']}", headers=as_user(env, ADMIN))
    assert r.status_code == 409 and "Deactivate" in r.json()["detail"]
