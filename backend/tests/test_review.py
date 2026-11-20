"""Approval flow for uploads that need a NEW course or department, and soft deletion of resources."""
import pytest
from postgrest.exceptions import APIError

from .conftest import ADMIN, STUDENT, as_user
from .test_submissions import typed, upload

NEW_ID = "33333333-3333-4333-8333-333333333333"
GHOST = "00000000-0000-4000-8000-000000000000"


def new_request(env, **kw):
    r = upload(env, **typed(**kw))
    assert r.status_code == 201, r.text
    return r.json()["id"]


def admin_post(env, path, **kw):
    return env.client.post(path, headers=as_user(env, ADMIN), **kw)


def physics(env):
    return new_request(env, course_code="PHY101", course_name="Mechanics", department="Physics")


def no_physics_created(env):
    assert not [c for c in env.db["courses"] if c["course_code"] == "PHY101"]
    assert len(env.db["departments"]) == 2


# ---------------------------------------------------------------- listing ---

def test_admin_sees_the_pending_request_with_the_requested_course(env):
    physics(env)
    [item] = env.client.get("/api/admin/submissions?status=pending", headers=as_user(env, ADMIN)).json()
    assert item["is_new_course"] and item["is_new_department"]
    assert (item["course_code"], item["course_name"], item["department_name"], item["semester"]) == (
        "PHY101", "Mechanics", "Physics", 5)
    assert item["uploaded_by_name"] == "Vanshika"


def test_existing_department_is_not_flagged_as_new(env):
    new_request(env)
    [item] = env.client.get("/api/admin/submissions", headers=as_user(env, ADMIN)).json()
    assert item["is_new_course"] and not item["is_new_department"]


def test_students_cannot_use_the_admin_routes(env):
    sid = new_request(env)
    h = as_user(env, STUDENT)
    assert env.client.get("/api/admin/submissions", headers=h).status_code == 403
    assert env.client.post(f"/api/admin/submissions/{sid}/approve", headers=h).status_code == 403


def test_admin_can_preview_the_temporary_pdf(env):
    sid = new_request(env)
    r = env.client.get(f"/api/admin/submissions/{sid}/file", headers=as_user(env, ADMIN))
    assert r.status_code == 200 and r.content.startswith(b"%PDF-")


# ---------------------------------------------------------------- approve ---

def test_approve_creates_course_and_department_publishes_and_deletes_the_temp_file(env):
    sid = physics(env)
    r = admin_post(env, f"/api/admin/submissions/{sid}/approve")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"

    course = next(c for c in env.db["courses"] if c["course_code"] == "PHY101")
    assert course["course_name"] == "Mechanics" and course["semester"] == 5
    dept = env.db["departments"][-1]
    assert dept["name"] == "Physics" and course["department_id"] == dept["id"]

    [row] = env.db["resource_submissions"]
    assert row["status"] == "approved" and row["course_id"] == course["id"]
    assert row["drive_file_id"] == "DRIVE-1" and row["reviewed_by"] == ADMIN["id"]
    env.drive_upload.assert_called_once()
    assert env.files == {} and row["storage_path"] is None


def test_approved_paper_becomes_searchable(env):
    sid = new_request(env)
    admin_post(env, f"/api/admin/submissions/{sid}/approve")
    r = env.client.get("/api/resources", headers=as_user(env, STUDENT))
    assert r.status_code == 200 and len(r.json()) == 1 and r.json()[0]["course_code"] == "CSE301"


def test_pending_paper_is_not_searchable(env):
    new_request(env)
    r = env.client.get("/api/resources", headers=as_user(env, STUDENT))
    assert r.json() == []


def test_approve_reuses_a_course_created_in_the_meantime(env):
    sid = new_request(env)
    env.db["courses"].append({**env.db["courses"][0], "id": NEW_ID, "course_code": "CSE301"})
    assert admin_post(env, f"/api/admin/submissions/{sid}/approve").status_code == 200
    assert [c["course_code"] for c in env.db["courses"]].count("CSE301") == 1
    assert env.db["resource_submissions"][0]["course_id"] == NEW_ID


def test_failed_drive_upload_leaves_the_request_pending_and_creates_nothing(env):
    sid = physics(env)
    env.drive_upload.side_effect = RuntimeError("drive down")
    with pytest.raises(RuntimeError):
        admin_post(env, f"/api/admin/submissions/{sid}/approve")
    no_physics_created(env)
    row = env.db["resource_submissions"][0]
    assert row["status"] == "pending" and row["storage_path"] in env.files


def _fail_submission_write(env, error):
    """Let the department, course and Drive upload succeed, then make the next database write fail."""
    def upload_then_arm_failure(*_a, **_k):
        env.state.fail_next = error
        return {"file_id": "DRIVE-1", "name": "paper.pdf"}

    env.drive_upload.side_effect = upload_then_arm_failure


def test_failed_save_undoes_drive_course_and_department(env):
    sid = physics(env)
    _fail_submission_write(env, APIError({"code": "XX000", "message": "boom"}))
    with pytest.raises(APIError):
        admin_post(env, f"/api/admin/submissions/{sid}/approve")
    env.drive_delete.assert_called_once_with("DRIVE-1")
    no_physics_created(env)
    assert env.db["resource_submissions"][0]["status"] == "pending"


def test_duplicate_at_approval_time_is_a_conflict_and_cleans_up(env):
    sid = physics(env)
    _fail_submission_write(env, APIError({"code": "23505", "message": "dup"}))
    assert admin_post(env, f"/api/admin/submissions/{sid}/approve").status_code == 409
    env.drive_delete.assert_called_once()
    no_physics_created(env)


def test_cannot_decide_twice(env):
    sid = new_request(env)
    assert admin_post(env, f"/api/admin/submissions/{sid}/approve").status_code == 200
    assert admin_post(env, f"/api/admin/submissions/{sid}/approve").status_code == 409
    assert admin_post(env, f"/api/admin/submissions/{sid}/reject", json={"reason": "late"}).status_code == 409


# ----------------------------------------------------------------- reject ---

def test_reject_creates_nothing_deletes_the_temp_file_and_shows_the_reason(env):
    sid = physics(env)
    r = admin_post(env, f"/api/admin/submissions/{sid}/reject", json={"reason": "Not our course"})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    no_physics_created(env)
    env.drive_upload.assert_not_called()
    assert env.files == {}
    mine = env.client.get("/api/submissions/mine", headers=as_user(env, STUDENT)).json()
    assert mine[0]["status"] == "rejected" and mine[0]["rejection_reason"] == "Not our course"


def test_reject_needs_a_reason(env):
    sid = new_request(env)
    assert admin_post(env, f"/api/admin/submissions/{sid}/reject", json={"reason": " "}).status_code == 422


def test_rejected_request_does_not_block_a_new_upload(env):
    sid = new_request(env)
    admin_post(env, f"/api/admin/submissions/{sid}/reject", json={"reason": "Wrong file"})
    assert upload(env, **typed()).status_code == 201


# ------------------------------------------------------------ soft delete ---

def published(env):
    assert upload(env).status_code == 201
    return env.db["resource_submissions"][0]["id"]


def remove(env, rid, **kw):
    return env.client.request("DELETE", f"/api/resource-flags/resources/{rid}", headers=as_user(env, ADMIN), **kw)


def test_soft_delete_hides_the_resource_but_keeps_it(env):
    rid = published(env)
    r = remove(env, rid)
    assert r.status_code == 200 and r.json()["status"] == "deleted"
    [row] = env.db["resource_submissions"]
    assert row["status"] == "deleted" and row["deleted_by"] == ADMIN["id"] and row["deleted_at"]
    env.drive_delete.assert_not_called()                        # the Drive file is kept for restore
    h = as_user(env, STUDENT)
    assert env.client.get("/api/resources", headers=h).json() == []
    assert env.client.get(f"/api/resources/{rid}/view", headers=h).status_code == 404
    flag = env.client.post(f"/api/resource-flags/{rid}", json={"reason": "other"}, headers=h)
    assert flag.status_code == 404


def test_soft_delete_resolves_open_reports(env):
    rid = published(env)
    env.client.post(f"/api/resource-flags/{rid}", json={"reason": "poor_quality"}, headers=as_user(env, STUDENT))
    remove(env, rid)
    assert [f["status"] for f in env.db["resource_flags"]] == ["resolved"]


def test_soft_delete_records_the_reason_and_lists_removed(env):
    rid = published(env)
    remove(env, rid, json={"reason": "Wrong paper"})
    [item] = env.client.get("/api/resource-flags/resources/removed", headers=as_user(env, ADMIN)).json()
    assert item["id"] == rid and item["deletion_reason"] == "Wrong paper" and item["course_code"] == "CSE201"


def test_restore_brings_it_back(env):
    rid = published(env)
    remove(env, rid)
    assert env.client.post(f"/api/resource-flags/resources/{rid}/restore", headers=as_user(env, ADMIN)).status_code == 200
    row = env.db["resource_submissions"][0]
    assert row["status"] == "approved" and row["deleted_at"] is None
    assert env.client.get("/api/resources", headers=as_user(env, STUDENT)).json() != []
    assert env.client.post(f"/api/resource-flags/resources/{rid}/restore", headers=as_user(env, ADMIN)).status_code == 409


def test_cannot_soft_delete_twice_or_unknown(env):
    rid = published(env)
    assert remove(env, rid).status_code == 200
    assert remove(env, rid).status_code == 409
    assert remove(env, GHOST).status_code == 404


def test_permanent_delete_only_after_soft_delete(env):
    rid = published(env)
    h = as_user(env, ADMIN)
    assert env.client.delete(f"/api/resource-flags/resources/{rid}/permanent", headers=h).status_code == 409
    remove(env, rid)
    assert env.client.delete(f"/api/resource-flags/resources/{rid}/permanent", headers=h).status_code == 204
    env.drive_delete.assert_called_once_with("DRIVE-1")
    assert env.db["resource_submissions"] == []


def test_removal_is_admin_only(env):
    rid = published(env)
    h = as_user(env, STUDENT)
    assert env.client.delete(f"/api/resource-flags/resources/{rid}", headers=h).status_code == 403
    assert env.client.post(f"/api/resource-flags/resources/{rid}/restore", headers=h).status_code == 403


def test_a_removed_paper_can_be_uploaded_again(env):
    rid = published(env)
    remove(env, rid)
    assert upload(env, content=None).status_code == 201
