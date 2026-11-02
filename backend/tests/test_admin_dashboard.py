"""Tests for direct PDF uploads to Google Drive."""
from io import BytesIO

import pytest
from postgrest.exceptions import APIError
from pypdf import PdfWriter

from .conftest import ADMIN, STUDENT, as_user


def make_pdf(title="paper"):
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_metadata({"/Title": title})
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def upload(env, *, user=STUDENT, course=0, year="2025", exam="Midsem", tags="Trees, Graphs",
           content=None, filename="paper.pdf", content_type="application/pdf", **overrides):
    form = {"course_id": env.db["courses"][course]["id"], "exam_year": year, "exam_type": exam, "tags": tags}
    form.update(overrides)
    form = {k: v for k, v in form.items() if v is not None}
    return env.client.post(
        "/api/submissions", data=form,
        files={"file": (filename, content if content is not None else make_pdf(), content_type)},
        headers=as_user(env, user),
    )


def test_upload_is_published_directly_to_google_drive(env):
    response = upload(env)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "approved"
    assert body["exam_type"] == "Midsem" and body["exam_year"] == 2025
    assert body["tags"] == "Trees, Graphs" and body["original_filename"] == "paper.pdf"
    assert "storage_path" not in body and "file_sha256" not in body and "drive_file_id" not in body

    [row] = env.db["resource_submissions"]
    assert row["uploaded_by"] == STUDENT["id"]
    assert row["status"] == "approved" and row["drive_file_id"] == "DRIVE-1"
    assert row["storage_path"] is None and len(row["file_sha256"]) == 64
    env.drive_upload.assert_called_once()
    content, drive_filename = env.drive_upload.call_args.args
    assert content.startswith(b"%PDF-")
    assert drive_filename == "CSE201 · Midsem 2025 - paper.pdf"


def test_admins_may_upload_too(env):
    assert upload(env, user=ADMIN).status_code == 201


def test_blank_tags_and_filename_are_normalized(env):
    response = upload(env, tags="   ", filename="../../etc/My Paper")
    assert response.status_code == 201
    assert response.json()["tags"] is None
    assert response.json()["original_filename"] == "My Paper.pdf"


def test_same_metadata_duplicate_is_rejected_before_drive_upload(env):
    assert upload(env).status_code == 201
    response = upload(env, content=make_pdf("different"))
    assert response.status_code == 409
    assert "already available on StudySync" in response.json()["detail"]
    assert len(env.db["resource_submissions"]) == 1
    assert env.drive_upload.call_count == 1


def test_exact_same_pdf_duplicate_is_rejected(env):
    pdf = make_pdf("same")
    assert upload(env, content=pdf).status_code == 201
    response = upload(env, content=pdf, exam="Endsem")
    assert response.status_code == 409
    assert "exact PDF" in response.json()["detail"]
    assert env.drive_upload.call_count == 1


def test_tutorials_and_lab_tests_allow_multiple_resources(env):
    assert upload(env, exam="Tutorials").status_code == 201
    assert upload(env, exam="Tutorials", content=make_pdf("another")).status_code == 201


def test_rejected_historical_resource_does_not_block_upload(env):
    assert upload(env).status_code == 201
    env.db["resource_submissions"][0]["status"] = "rejected"
    assert upload(env, content=make_pdf("replacement")).status_code == 201


def test_database_failure_deletes_orphaned_drive_file(env):
    env.state.fail_next = APIError({"code": "XX000", "message": "database unavailable"})
    with pytest.raises(APIError):
        upload(env)
    env.drive_delete.assert_called_once_with("DRIVE-1")
    assert env.db["resource_submissions"] == []


@pytest.mark.parametrize("kwargs, code", [
    ({"content": b"just text", "filename": "notes.pdf"}, 415),
    ({"content": b"%PDF-1.4 not a readable pdf"}, 415),
    ({"filename": "paper.txt", "content_type": "text/plain"}, 415),
    ({"content": b""}, 400),
    ({"content": make_pdf() + b"0" * (2 * 1024 * 1024)}, 413),
])
def test_invalid_files_never_reach_google_drive(env, kwargs, code):
    assert upload(env, **kwargs).status_code == code
    assert env.db["resource_submissions"] == []
    env.drive_upload.assert_not_called()


def test_login_is_required(env):
    response = env.client.post("/api/submissions", data={}, files={"file": ("a.pdf", make_pdf(), "application/pdf")})
    assert response.status_code == 401


def test_invalid_details_are_rejected_before_drive_upload(env):
    response = upload(env, exam="Quiz")
    assert response.status_code == 422
    env.drive_upload.assert_not_called()


def test_unknown_or_inactive_course(env):
    assert upload(env, course_id="99999999-9999-4999-8999-999999999999").status_code == 404
    assert upload(env, course=3).status_code == 400
    env.drive_upload.assert_not_called()


def test_mine_lists_published_resources_without_internal_fields(env):
    upload(env, user=STUDENT)
    upload(env, user=ADMIN, year="2024", content=make_pdf("admin upload"))
    response = env.client.get("/api/submissions/mine", headers=as_user(env, STUDENT))
    assert response.status_code == 200
    [only] = response.json()
    assert only["exam_year"] == 2025 and only["status"] == "approved"
    assert "storage_path" not in only and "file_sha256" not in only and "uploaded_by" not in only
    assert env.client.get("/api/submissions/mine").status_code == 401