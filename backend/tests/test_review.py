"""Tests for the admin approval flow (Manage Request). Supabase and Google Drive are faked."""
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services import google_drive

from .conftest import ADMIN, STUDENT, as_user

PDF = b"%PDF-1.4 pretend this is the student's paper"


def make_request(env, *, status="pending", course=0, year=2025, exam="Midsem", name="paper.pdf",
                 user=STUDENT, n=0, **extra):
    row = {
        "id": str(uuid4()), "course_id": env.db["courses"][course]["id"], "exam_year": year, "exam_type": exam,
        "tags": "Trees", "original_filename": name, "storage_path": f"{user['id']}/{uuid4()}.pdf",
        "file_size_bytes": len(PDF), "file_sha256": uuid4().hex * 2, "uploaded_by": user["id"], "status": status,
        "rejection_reason": None, "reviewed_by": None, "reviewed_at": None, "drive_file_id": None,
        "created_at": f"2026-10-{10 + n:02d}T10:00:00+00:00", **extra,
    }
    env.db["resource_submissions"].append(row)
    return row


@pytest.fixture
def renv(env, monkeypatch):
    """env + a fake Google Drive + a temp bucket that holds the student's PDF."""
    env.admin.storage.from_.return_value.download.return_value = PDF
    env.drive_upload = MagicMock(return_value={"file_id": "DRIVE-1", "name": "x.pdf"})
    env.drive_delete = MagicMock()
    monkeypatch.setattr(google_drive, "upload_pdf_bytes_to_shared_drive", env.drive_upload)
    monkeypatch.setattr(google_drive, "delete_file_from_shared_drive", env.drive_delete)
    env.bucket = env.admin.storage.from_.return_value
    return env


def get(env, path, user=ADMIN):
    return env.client.get(path, headers=as_user(env, user))


def post(env, path, body=None, user=ADMIN):
    return env.client.post(path, json=body, headers=as_user(env, user))


# ------------------------------------------------------------- who may ---

@pytest.mark.parametrize("method, path", [
    ("get", "/api/admin/submissions"),
    ("get", f"/api/admin/submissions/{uuid4()}/file"),
    ("post", f"/api/admin/submissions/{uuid4()}/approve"),
    ("post", f"/api/admin/submissions/{uuid4()}/reject"),
])
def test_only_admins_can_use_the_review_endpoints(renv, method, path):
    call = getattr(renv.client, method)
    assert call(path).status_code == 401                                         # not logged in
    assert call(path, headers=as_user(renv, STUDENT)).status_code == 403          # a student
    assert renv.drive_upload.call_count == 0


# ---------------------------------------------------------------- list ---

def test_list_shows_pending_requests_oldest_first_with_course_and_uploader(renv):
    newer = make_request(renv, n=3, name="newer.pdf", exam="Endsem")
    older = make_request(renv, n=1, name="older.pdf")
    make_request(renv, n=2, status="approved", drive_file_id="d")
    r = get(renv, "/api/admin/submissions")
    assert r.status_code == 200
    items = r.json()
    assert [i["id"] for i in items] == [older["id"], newer["id"]]
    first = items[0]
    assert first["course_code"] == "CSE201" and first["course_name"] == "Data Structures and Algorithms"
    assert first["uploaded_by_name"] == STUDENT["full_name"] and first["uploaded_by_entry_number"] == STUDENT["entry_number"]
    assert first["status"] == "pending" and first["exam_year"] == 2025 and first["tags"] == "Trees"
    for secret in ("storage_path", "file_sha256", "uploaded_by", "drive_file_id"):
        assert secret not in first


def test_list_can_show_history(renv):
    make_request(renv, status="approved", drive_file_id="d", n=1)
    rejected = make_request(renv, status="rejected", rejection_reason="Blurry scan", n=2)
    make_request(renv, n=3)
    assert len(get(renv, "/api/admin/submissions?status=approved").json()) == 1
    [only] = get(renv, "/api/admin/submissions?status=rejected").json()
    assert only["id"] == rejected["id"] and only["rejection_reason"] == "Blurry scan"
    assert get(renv, "/api/admin/submissions?status=bogus").status_code == 422


# ------------------------------------------------------------- preview ---

def test_preview_streams_the_temporary_pdf(renv):
    req = make_request(renv, name='my "paper".pdf')
    r = get(renv, f"/api/admin/submissions/{req['id']}/file")
    assert r.status_code == 200 and r.content == PDF
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["cache-control"] == "private, no-store" and r.headers["x-content-type-options"] == "nosniff"
    assert 'filename="my paper.pdf"' in r.headers["content-disposition"]
    renv.admin.storage.from_.assert_called_with("pending-uploads")
    renv.bucket.download.assert_called_with(req["storage_path"])


def test_preview_errors(renv):
    assert get(renv, f"/api/admin/submissions/{uuid4()}/file").status_code == 404
    assert get(renv, "/api/admin/submissions/not-a-uuid/file").status_code == 422
    done = make_request(renv, status="approved", drive_file_id="d")
    assert get(renv, f"/api/admin/submissions/{done['id']}/file").status_code == 409
    waiting = make_request(renv)
    renv.bucket.download.side_effect = Exception("Object not found")
    assert get(renv, f"/api/admin/submissions/{waiting['id']}/file").status_code == 404
    renv.bucket.download.side_effect = Exception("connection reset")
    assert get(renv, f"/api/admin/submissions/{waiting['id']}/file").status_code == 503


# ------------------------------------------------------------- approve ---

def test_approve_copies_the_pdf_to_google_drive_and_publishes_it(renv):
    req = make_request(renv, name="paper.pdf")
    r = post(renv, f"/api/admin/submissions/{req['id']}/approve")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved" and r.json()["course_code"] == "CSE201"

    # the PDF from temporary storage went to Drive, with a descriptive file name
    renv.drive_upload.assert_called_once_with(PDF, "CSE201 Midsem 2025 - paper.pdf")
    # ... and the row now has everything students' Search needs
    assert req["status"] == "approved" and req["drive_file_id"] == "DRIVE-1"
    assert req["reviewed_by"] == ADMIN["id"] and req["reviewed_at"]
    # the temporary copy is gone
    renv.bucket.remove.assert_called_once_with([req["storage_path"]])


def test_an_approved_paper_shows_up_for_students(renv):
    req = make_request(renv)
    assert get(renv, "/api/resources", user=STUDENT).json() == []                 # pending: invisible
    post(renv, f"/api/admin/submissions/{req['id']}/approve")
    [found] = get(renv, "/api/resources", user=STUDENT).json()                    # approved: visible
    assert found["id"] == req["id"] and found["course_code"] == "CSE201"
    assert found["google_drive_url"] == "https://drive.google.com/file/d/DRIVE-1/view"


@pytest.mark.parametrize("status", ["approved", "rejected"])
def test_cannot_decide_a_request_twice(renv, status):
    req = make_request(renv, status=status, drive_file_id="d" if status == "approved" else None,
                       rejection_reason="no" if status == "rejected" else None)
    r = post(renv, f"/api/admin/submissions/{req['id']}/approve")
    assert r.status_code == 409 and status in r.json()["detail"]
    assert renv.drive_upload.call_count == 0


def test_approve_unknown_request(renv):
    assert post(renv, f"/api/admin/submissions/{uuid4()}/approve").status_code == 404


def test_if_google_drive_fails_the_request_stays_pending_and_keeps_its_file(renv):
    req = make_request(renv)
    renv.drive_upload.side_effect = HTTPException(502, "Could not upload the PDF to Google Drive.")
    r = post(renv, f"/api/admin/submissions/{req['id']}/approve")
    assert r.status_code == 502
    assert req["status"] == "pending" and req["drive_file_id"] is None
    renv.bucket.remove.assert_not_called()


def test_if_the_temp_file_is_missing_nothing_reaches_drive(renv):
    req = make_request(renv)
    renv.bucket.download.side_effect = Exception("Object not found")
    assert post(renv, f"/api/admin/submissions/{req['id']}/approve").status_code == 404
    assert renv.drive_upload.call_count == 0 and req["status"] == "pending"


def test_two_admins_approving_at_once_only_one_wins_and_no_stray_drive_file_is_left(renv):
    req = make_request(renv)

    def other_admin_finishes_first(*_a):
        req.update(status="approved", drive_file_id="THEIRS", reviewed_by="someone-else")
        return {"file_id": "MINE"}

    renv.drive_upload.side_effect = other_admin_finishes_first
    r = post(renv, f"/api/admin/submissions/{req['id']}/approve")
    assert r.status_code == 409
    assert req["drive_file_id"] == "THEIRS"                       # the first decision stands
    renv.drive_delete.assert_called_once_with("MINE")             # our duplicate Drive copy is removed


def test_if_saving_the_approval_fails_the_drive_copy_is_removed(renv):
    from postgrest.exceptions import APIError
    req = make_request(renv)
    renv.state.fail_next = APIError({"code": "XX000", "message": "boom"})
    with pytest.raises(APIError):
        post(renv, f"/api/admin/submissions/{req['id']}/approve")
    renv.drive_delete.assert_called_once_with("DRIVE-1")
    assert req["status"] == "pending"


# -------------------------------------------------------------- reject ---

def test_reject_saves_the_reason_and_removes_the_temp_file(renv):
    req = make_request(renv)
    r = post(renv, f"/api/admin/submissions/{req['id']}/reject", {"reason": "  Scan is unreadable  "})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    assert r.json()["rejection_reason"] == "Scan is unreadable"
    assert req["status"] == "rejected" and req["reviewed_by"] == ADMIN["id"] and req["drive_file_id"] is None
    renv.bucket.remove.assert_called_once_with([req["storage_path"]])
    assert renv.drive_upload.call_count == 0


@pytest.mark.parametrize("body", [None, {}, {"reason": ""}, {"reason": "  "}, {"reason": "no"}, {"reason": "x" * 501}])
def test_reject_needs_a_real_reason(renv, body):
    req = make_request(renv)
    assert post(renv, f"/api/admin/submissions/{req['id']}/reject", body).status_code == 422
    assert req["status"] == "pending"


def test_cannot_reject_what_was_already_decided(renv):
    req = make_request(renv, status="approved", drive_file_id="d")
    assert post(renv, f"/api/admin/submissions/{req['id']}/reject", {"reason": "too late"}).status_code == 409
    assert post(renv, f"/api/admin/submissions/{uuid4()}/reject", {"reason": "who?"}).status_code == 404


def test_the_student_sees_the_rejection_reason_and_can_upload_a_better_copy(renv):
    from .test_submissions import make_pdf, upload
    assert upload(renv).status_code == 201
    [row] = renv.db["resource_submissions"]
    post(renv, f"/api/admin/submissions/{row['id']}/reject", {"reason": "Blurry scan"})

    [mine] = get(renv, "/api/submissions/mine", user=STUDENT).json()
    assert mine["status"] == "rejected" and mine["rejection_reason"] == "Blurry scan"
    assert upload(renv, content=make_pdf("better scan")).status_code == 201
