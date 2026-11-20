"""Tests for the student Upload PDF endpoints. Supabase (database + storage) is faked."""
from io import BytesIO

import pytest
from postgrest.exceptions import APIError
from pypdf import PdfWriter

from .conftest import ADMIN, DEPT_CSE, STUDENT, as_user


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


def typed(course_code="CSE301", course_name="Compilers", department="Computer Science and Engineering",
          semester="5"):
    """Form fields for a course the student typed instead of picking from the list."""
    return dict(course_id=None, course_code=course_code, course_name=course_name,
                department=department, semester=semester)


# ------------------------------------------------------------- success ---

def test_upload_goes_straight_to_drive_and_is_published(env):
    r = upload(env)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "approved" and body["exam_type"] == "Midsem" and body["exam_year"] == 2025
    assert body["tags"] == "Trees, Graphs" and body["original_filename"] == "paper.pdf"
    assert "storage_path" not in body and "file_sha256" not in body   # internals stay internal

    [row] = env.db["resource_submissions"]
    assert row["uploaded_by"] == STUDENT["id"] and row["status"] == "approved"
    assert row["drive_file_id"] == "DRIVE-1" and len(row["file_sha256"]) == 64
    content, drive_name = env.drive_upload.call_args.args
    assert content.startswith(b"%PDF-") and drive_name.startswith("CSE201 · Midsem 2025")


def test_blank_tags_become_none_and_filename_is_cleaned(env):
    r = upload(env, tags="   ", filename="../../etc/My Paper")
    assert r.status_code == 201
    assert r.json()["tags"] is None and r.json()["original_filename"] == "My Paper.pdf"


def test_admins_may_upload_too(env):
    assert upload(env, user=ADMIN).status_code == 201


# ---------------------------------------------------------- duplicates ---

def test_same_midsem_paper_is_rejected_with_a_reason(env):
    assert upload(env).status_code == 201
    r = upload(env, content=make_pdf("different file"))          # same course + year + exam type
    assert r.status_code == 409
    assert "CSE201 · Midsem 2025" in r.json()["detail"] and "already available" in r.json()["detail"]
    assert len(env.db["resource_submissions"]) == 1
    assert env.drive_upload.call_count == 1                      # nothing new went to Drive


def test_same_endsem_paper_is_rejected_too(env):
    assert upload(env, exam="Endsem").status_code == 201
    assert upload(env, exam="Endsem", content=make_pdf("other")).status_code == 409


def test_tutorials_and_lab_tests_may_repeat(env):
    for exam in ("Tutorials", "Lab Test"):
        assert upload(env, exam=exam, content=make_pdf(f"{exam} 1")).status_code == 201
        assert upload(env, exam=exam, content=make_pdf(f"{exam} 2")).status_code == 201


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
    r = upload(env, content=pdf, exam="Tutorials")
    assert r.status_code == 409 and "exact PDF" in r.json()["detail"]
    assert len(env.db["resource_submissions"]) == 1


def test_simultaneous_duplicate_is_caught_by_the_database_and_the_drive_file_is_removed(env):
    env.state.fail_next = APIError({"code": "23505", "message": "duplicate key"})
    r = upload(env)
    assert r.status_code == 409
    assert env.db["resource_submissions"] == []
    env.drive_delete.assert_called_once_with("DRIVE-1")


def test_other_database_failures_also_remove_the_drive_file(env):
    env.state.fail_next = APIError({"code": "XX000", "message": "boom"})
    with pytest.raises(APIError):
        upload(env)
    env.drive_delete.assert_called_once_with("DRIVE-1")


def test_drive_failure_saves_nothing(env):
    env.drive_upload.side_effect = Exception("Drive is down")
    with pytest.raises(Exception):
        upload(env)
    assert env.db["resource_submissions"] == []


# ------------------------------------------ automatic course/department ---

def test_new_course_is_NOT_created_it_becomes_a_pending_request(env):
    r = upload(env, **typed())
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "pending" and body["course_id"] is None
    assert body["new_course"]["code"] == "CSE301"
    assert not [c for c in env.db["courses"] if c["course_code"] == "CSE301"]   # nothing created yet
    assert len(env.db["departments"]) == 2
    env.drive_upload.assert_not_called()                                         # nothing on Drive yet
    [row] = env.db["resource_submissions"]
    assert row["status"] == "pending" and row["drive_file_id"] is None
    assert row["storage_path"] in env.files                                      # parked in temporary storage


def test_new_department_is_not_created_either(env):
    r = upload(env, **typed(course_code="PHY101", course_name="Mechanics", department="Physics"))
    assert r.status_code == 201, r.text
    assert len(env.db["departments"]) == 2
    assert r.json()["new_course"]["department"] == "Physics"


def test_second_request_for_the_same_new_paper_is_rejected(env):
    assert upload(env, **typed()).status_code == 201
    r = upload(env, content=make_pdf("other"), **typed())
    assert r.status_code == 409 and "waiting for admin approval" in r.json()["detail"]


def test_pending_request_is_cleaned_up_if_saving_it_fails(env):
    env.state.fail_next = APIError({"code": "XX000", "message": "boom"})
    with pytest.raises(APIError):
        upload(env, **typed())
    assert env.files == {} and env.db["resource_submissions"] == []


def test_typing_an_existing_course_code_reuses_that_course(env):
    r = upload(env, **typed(course_code="cse201", course_name="Whatever", department="Chemistry"))
    assert r.status_code == 201, r.text
    assert len([c for c in env.db["courses"] if c["course_code"] == "CSE201"]) == 1
    assert len(env.db["departments"]) == 2                       # Chemistry was NOT created
    assert env.db["resource_submissions"][0]["course_id"] == env.db["courses"][0]["id"]


def test_typed_existing_course_still_gets_the_duplicate_check(env):
    assert upload(env).status_code == 201
    r = upload(env, content=make_pdf("x"), **typed(course_code="CSE201"))
    assert r.status_code == 409


def test_nothing_is_created_when_the_upload_is_rejected(env):
    r = upload(env, content=b"not a pdf", **typed(department="Physics"))
    assert r.status_code == 415
    assert len(env.db["courses"]) == 4 and len(env.db["departments"]) == 2


@pytest.mark.parametrize("missing", ["course_code", "course_name", "department", "semester"])
def test_typed_course_needs_every_field(env, missing):
    assert upload(env, **{**typed(), missing: None}).status_code == 422


def test_typed_inactive_course_is_refused(env):
    assert upload(env, **typed(course_code="CSE999")).status_code == 400


def test_bad_typed_course_code_is_422(env):
    assert upload(env, **typed(course_code="no spaces!")).status_code == 422


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
    assert env.db["resource_submissions"] == [] and env.drive_upload.call_count == 0


@pytest.mark.parametrize("overrides", [
    {"exam": "Quiz"}, {"exam": None}, {"year": "1999"}, {"year": "2999"}, {"year": "abc"},
    {"year": None}, {"course_id": "not-a-uuid"}, {"course_id": None},   # no course at all
])
def test_bad_details_are_422(env, overrides):
    assert upload(env, **overrides).status_code == 422
    assert env.drive_upload.call_count == 0


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
    assert only["exam_year"] == 2025 and only["status"] == "approved"
    assert "storage_path" not in only and "file_sha256" not in only and "uploaded_by" not in only
    assert env.client.get("/api/submissions/mine").status_code == 401
