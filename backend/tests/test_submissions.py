"""Tests for the student Upload PDF endpoints. Supabase (database + storage) is faked."""
from io import BytesIO

import pytest
from postgrest.exceptions import APIError
from pypdf import PdfWriter

from .conftest import ADMIN, STUDENT, as_user


def make_pdf(title="paper") -> bytes:
    """A tiny but valid one-page PDF. Different titles give different file contents."""
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
        "/api/submissions",
        data=form,
        files={"file": (filename, content if content is not None else make_pdf(), content_type)},
        headers=as_user(env, user),
    )


def stored(env):
    return env.admin.storage.from_.return_value


# ------------------------------------------------------------- success ---

def test_upload_stores_file_privately_and_saves_a_pending_row(env):
    r = upload(env)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "pending" and body["exam_type"] == "Midsem" and body["exam_year"] == 2025
    assert body["tags"] == "Trees, Graphs" and body["original_filename"] == "paper.pdf"
    assert "storage_path" not in body and "file_sha256" not in body   # internals stay internal

    [row] = env.db["resource_submissions"]
    assert row["uploaded_by"] == STUDENT["id"] and row["status"] == "pending"
    assert row["storage_path"].startswith(f"{STUDENT['id']}/") and row["storage_path"].endswith(".pdf")
    assert len(row["file_sha256"]) == 64

    env.admin.storage.from_.assert_called_with("pending-uploads")
    path, content, options = stored(env).upload.call_args.args
    assert path == row["storage_path"] and content.startswith(b"%PDF-")
    assert options["content-type"] == "application/pdf" and options["upsert"] == "false"


def test_blank_tags_become_none_and_filename_is_cleaned(env):
    r = upload(env, tags="   ", filename="../../etc/My Paper")
    assert r.status_code == 201
    assert r.json()["tags"] is None and r.json()["original_filename"] == "My Paper.pdf"


def test_admins_may_upload_too(env):
    assert upload(env, user=ADMIN).status_code == 201


# ---------------------------------------------------------- duplicates ---

def test_same_paper_already_waiting_is_rejected_with_a_reason(env):
    assert upload(env).status_code == 201
    r = upload(env, content=make_pdf("different file"))          # same course + year + exam type
    assert r.status_code == 409
    assert "CSE201 · Midsem 2025" in r.json()["detail"] and "waiting for admin review" in r.json()["detail"]
    assert len(env.db["resource_submissions"]) == 1              # nothing new saved...
    assert stored(env).upload.call_count == 1                    # ...and nothing new uploaded


def test_same_paper_already_approved_is_rejected_with_a_reason(env):
    assert upload(env).status_code == 201
    env.db["resource_submissions"][0]["status"] = "approved"
    r = upload(env, user=ADMIN, content=make_pdf("other"))
    assert r.status_code == 409 and "already available on StudySync" in r.json()["detail"]


def test_a_rejected_paper_does_not_block_a_new_upload(env):
    assert upload(env).status_code == 201
    env.db["resource_submissions"][0].update(status="rejected", rejection_reason="Blurry scan")
    assert upload(env, content=make_pdf("better scan")).status_code == 201


@pytest.mark.parametrize("change", [{"year": "2024"}, {"exam": "Endsem"}, {"course": 1}])
def test_different_metadata_is_not_a_duplicate(env, change):
    assert upload(env).status_code == 201
    assert upload(env, content=make_pdf("another"), **change).status_code == 201


def test_the_same_pdf_under_different_details_is_rejected(env):
    pdf = make_pdf("same bytes")
    assert upload(env, content=pdf).status_code == 201
    r = upload(env, content=pdf, exam="Endsem")
    assert r.status_code == 409 and "exact PDF" in r.json()["detail"]
    assert len(env.db["resource_submissions"]) == 1


def test_simultaneous_duplicate_is_caught_by_the_database_and_the_file_is_removed(env):
    env.state.fail_next = APIError({"code": "23505", "message": "duplicate key"})
    r = upload(env)
    assert r.status_code == 409
    assert env.db["resource_submissions"] == []
    stored(env).remove.assert_called_once()                       # the orphan file is cleaned up
    assert stored(env).remove.call_args.args[0] == [stored(env).upload.call_args.args[0]]


def test_other_database_failures_also_remove_the_uploaded_file(env):
    env.state.fail_next = APIError({"code": "XX000", "message": "boom"})
    with pytest.raises(APIError):
        upload(env)
    stored(env).remove.assert_called_once()


def test_storage_failure_returns_503_and_saves_nothing(env):
    stored(env).upload.side_effect = Exception("Bucket not found")
    r = upload(env)
    assert r.status_code == 503
    assert env.db["resource_submissions"] == []


# ---------------------------------------------------------- bad input ---

def test_login_is_required(env):
    r = env.client.post("/api/submissions", data={}, files={"file": ("a.pdf", make_pdf(), "application/pdf")})
    assert r.status_code == 401


@pytest.mark.parametrize("kwargs, code", [
    ({"content": b"just some text", "filename": "notes.pdf"}, 415),               # not a PDF inside
    ({"content": b"%PDF-1.4 this is not really a pdf"}, 415),                      # header only, unreadable
    ({"filename": "paper.txt", "content_type": "text/plain"}, 415),                # wrong type
    ({"content": b""}, 400),                                                       # empty
    ({"content": make_pdf() + b"0" * (2 * 1024 * 1024)}, 413),                     # over 2 MB
])
def test_bad_files_are_rejected_before_anything_is_stored(env, kwargs, code):
    assert upload(env, **kwargs).status_code == code
    assert env.db["resource_submissions"] == [] and stored(env).upload.call_count == 0


@pytest.mark.parametrize("overrides", [
    {"exam": "Quiz"}, {"exam": None}, {"year": "1999"}, {"year": "2999"}, {"year": "abc"},
    {"year": None}, {"course_id": "not-a-uuid"}, {"course_id": None},
])
def test_bad_details_are_422(env, overrides):
    assert upload(env, **overrides).status_code == 422
    assert stored(env).upload.call_count == 0


def test_missing_file_is_422(env):
    r = env.client.post("/api/submissions", headers=as_user(env, STUDENT),
                        data={"course_id": env.db["courses"][0]["id"], "exam_year": "2025", "exam_type": "Midsem"})
    assert r.status_code == 422


def test_unknown_or_inactive_course(env):
    assert upload(env, course_id="99999999-9999-4999-8999-999999999999").status_code == 404
    assert upload(env, course=3).status_code == 400            # CSE999 is not active


# ---------------------------------------------------------------- mine ---

def test_mine_lists_only_my_submissions_without_internals(env):
    upload(env, user=STUDENT)
    upload(env, user=ADMIN, year="2024", content=make_pdf("admin's"))
    r = env.client.get("/api/submissions/mine", headers=as_user(env, STUDENT))
    assert r.status_code == 200
    [only] = r.json()
    assert only["exam_year"] == 2025 and only["status"] == "pending"
    assert "storage_path" not in only and "file_sha256" not in only and "uploaded_by" not in only
    assert env.client.get("/api/submissions/mine").status_code == 401
