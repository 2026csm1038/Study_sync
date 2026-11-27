"""Student profile: GET /api/resource-flags/mine and /mine/received (read-only, own data only)."""
from .conftest import ADMIN, STUDENT, as_user

OTHER = "u9"


def _paper(env, uploader, name, status="approved", tags=None):
    course = env.db["courses"][0]
    row = {"id": f"r-{name}", "course_id": course["id"], "new_course": None, "exam_year": 2025,
           "exam_type": "Midsem", "tags": tags, "original_filename": name, "uploaded_by": uploader,
           "status": status}
    env.db["resource_submissions"].append(row)
    return row["id"]


def _flag(env, rid, reporter, reason="duplicate", details="private words"):
    env.db["resource_flags"].append({"id": f"f-{len(env.db['resource_flags'])}", "resource_id": rid,
                                     "reporter_id": reporter, "reason": reason, "details": details,
                                     "status": "open", "created_at": "2026-11-01T10:00:00+00:00"})


def test_mine_returns_only_my_flags_with_material(env):
    mine, theirs = _paper(env, OTHER, "a.pdf", tags="Trees"), _paper(env, OTHER, "b.pdf")
    _flag(env, mine, STUDENT["id"], "poor_quality", "blurry")
    _flag(env, theirs, OTHER)
    [item] = env.client.get("/api/resource-flags/mine", headers=as_user(env, STUDENT)).json()
    assert item["reason"] == "poor_quality" and item["details"] == "blurry"
    assert item["resource"]["original_filename"] == "a.pdf" and item["resource"]["course_code"] == "CSE201"
    assert item["resource"]["exam_type"] == "Midsem" and item["resource"]["tags"] == "Trees"


def test_mine_includes_removed_materials(env):
    rid = _paper(env, OTHER, "gone.pdf", status="deleted")
    _flag(env, rid, STUDENT["id"])
    [item] = env.client.get("/api/resource-flags/mine", headers=as_user(env, STUDENT)).json()
    assert item["resource"]["status"] == "deleted"


def test_received_groups_by_my_material_and_hides_reporters(env):
    mine, theirs = _paper(env, STUDENT["id"], "mine.pdf"), _paper(env, OTHER, "theirs.pdf")
    _flag(env, mine, OTHER, "duplicate")
    _flag(env, mine, ADMIN["id"], "other")
    _flag(env, theirs, OTHER)
    [item] = env.client.get("/api/resource-flags/mine/received", headers=as_user(env, STUDENT)).json()
    assert item["resource"]["original_filename"] == "mine.pdf" and item["flag_count"] == 2
    assert sorted(item["reasons"]) == ["duplicate", "other"]
    assert "private words" not in str(item) and OTHER not in str(item) and "reporter" not in str(item)


def test_received_empty_when_nothing_uploaded(env):
    assert env.client.get("/api/resource-flags/mine/received", headers=as_user(env, STUDENT)).json() == []


def test_flag_lists_need_login(env):
    assert env.client.get("/api/resource-flags/mine").status_code in (401, 403)
