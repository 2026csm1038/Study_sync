"""Tests for the student filter API (GET /api/resources) and GET /api/departments. Supabase is faked."""
from types import SimpleNamespace as NS
from uuid import uuid4

import pytest

from .conftest import DEPT_CSE, DEPT_MATH, STUDENT, FakeQuery, as_user


class ResourceFakeQuery(FakeQuery):
    """The shared fake only understands course search in or_(); this one also matches file name and tags,
    and pages with limit(...) / range(...)."""

    window = None

    def limit(self, n):
        self.window = (0, n - 1)
        return self

    def range(self, start, end):
        self.window = (start, end)
        return self

    def execute(self):
        search, self.search = self.search, None
        result = super().execute()
        rows = result.data
        if search:
            term = search.split("%")[1].lower()
            rows = [
                r for r in rows
                if term in str(r.get("original_filename") or "").lower() or term in str(r.get("tags") or "").lower()
            ]
        if self.window:
            rows = rows[self.window[0]: self.window[1] + 1]
        return NS(data=rows)


def make_resource(course, year, exam, name, *, tags=None, drive="drive-1", status="approved", n=0):
    return {
        "id": str(uuid4()), "course_id": course["id"], "exam_year": year, "exam_type": exam,
        "tags": tags, "original_filename": name, "drive_file_id": drive, "status": status,
        "created_at": f"2026-10-{10 + n:02d}T10:00:00+00:00",
        "storage_path": "secret/path.pdf", "file_sha256": "secret-hash", "uploaded_by": "u1",  # must never be returned
    }


@pytest.fixture
def renv(env):
    """env + departments, a few papers, and a table fake that understands file-name/tag search."""
    cse201, cse202, mat201 = env.db["courses"][0], env.db["courses"][1], env.db["courses"][2]  # sem 3, sem 3, sem 2
    env.db["departments"] = [
        {"id": DEPT_MATH, "name": "Mathematics", "code": "MAT"},
        {"id": DEPT_CSE, "name": "Computer Science and Engineering", "code": "CSE"},
    ]
    env.db["resource_submissions"] = [
        make_resource(cse201, 2025, "Midsem", "DSA_Midsem_2025.pdf", tags="Trees, Graphs", drive="d1", n=1),
        make_resource(cse201, 2024, "Endsem", "DSA_Endsem_2024.pdf", drive="d2", n=2),
        make_resource(cse202, 2025, "Midsem", "OS_Midsem_2025.pdf", tags="Scheduling", drive="d3", n=3),
        make_resource(mat201, 2025, "Tutorials", "LinAlg_Tutorial_1.pdf", drive="d4", n=4),
        # these three must never show up:
        make_resource(cse201, 2023, "Midsem", "Pending.pdf", status="pending", drive=None, n=5),
        make_resource(cse202, 2022, "Endsem", "Rejected.pdf", status="rejected", drive="d6", n=6),
        make_resource(cse201, 2021, "Endsem", "NoFile.pdf", status="approved", drive=None, n=7),
    ]
    env.admin.table.side_effect = lambda name: ResourceFakeQuery(env.db[name], env.state)
    env.cse201, env.cse202, env.mat201 = cse201, cse202, mat201
    return env


def get(env, **params):
    return env.client.get("/api/resources", params=params, headers=as_user(env, STUDENT))


def titles(response):
    assert response.status_code == 200, response.text
    return {item["title"] for item in response.json()}


# ---------------------------------------------------------------- access ---

def test_login_is_required(renv):
    assert renv.client.get("/api/resources").status_code == 401
    assert renv.client.get("/api/departments").status_code == 401


# ------------------------------------------------------------ what shows ---

def test_without_filters_only_approved_papers_with_a_drive_file_are_returned(renv):
    assert titles(get(renv)) == {
        "DSA_Midsem_2025.pdf", "DSA_Endsem_2024.pdf", "OS_Midsem_2025.pdf", "LinAlg_Tutorial_1.pdf",
    }


def test_response_has_the_search_page_fields_and_leaks_nothing_else(renv):
    r = get(renv, exam_year=2025, exam_type="Midsem", course_id=renv.cse201["id"])
    [item] = r.json()
    assert set(item) == {
        "id", "title", "resource_type", "course_code", "course_name", "semester",
        "academic_year", "exam_type", "tags", "google_drive_url",
    }
    assert item["title"] == "DSA_Midsem_2025.pdf" and item["course_code"] == "CSE201"
    assert item["course_name"] == "Data Structures and Algorithms" and item["semester"] == 3
    assert item["academic_year"] == 2025 and item["exam_type"] == item["resource_type"] == "Midsem"
    assert item["tags"] == "Trees, Graphs"
    assert item["google_drive_url"] == "https://drive.google.com/file/d/d1/view"


# --------------------------------------------------------------- filters ---

def test_filter_by_exam_type(renv):
    assert titles(get(renv, exam_type="Midsem")) == {"DSA_Midsem_2025.pdf", "OS_Midsem_2025.pdf"}
    assert titles(get(renv, exam_type="Tutorials")) == {"LinAlg_Tutorial_1.pdf"}


def test_content_type_filters_the_same_column_as_exam_type(renv):
    assert titles(get(renv, content_type="Endsem")) == {"DSA_Endsem_2024.pdf"}


def test_two_different_content_and_exam_types_match_nothing(renv):
    assert get(renv, content_type="Endsem", exam_type="Midsem").json() == []
    assert titles(get(renv, content_type="Midsem", exam_type="Midsem")) == {"DSA_Midsem_2025.pdf", "OS_Midsem_2025.pdf"}


def test_filter_by_year(renv):
    assert titles(get(renv, exam_year=2024)) == {"DSA_Endsem_2024.pdf"}
    assert get(renv, exam_year=1999).status_code == 422


def test_filter_by_course(renv):
    assert titles(get(renv, course_id=renv.cse202["id"])) == {"OS_Midsem_2025.pdf"}


def test_filter_by_semester(renv):
    assert titles(get(renv, semester=3)) == {"DSA_Midsem_2025.pdf", "DSA_Endsem_2024.pdf", "OS_Midsem_2025.pdf"}
    assert titles(get(renv, semester=2)) == {"LinAlg_Tutorial_1.pdf"}


def test_filter_by_department(renv):
    assert titles(get(renv, department_id=DEPT_MATH)) == {"LinAlg_Tutorial_1.pdf"}
    assert len(get(renv, department_id=DEPT_CSE).json()) == 3


def test_filters_combine_with_and(renv):
    r = get(renv, department_id=DEPT_CSE, semester=3, exam_year=2025, exam_type="Midsem")
    assert titles(r) == {"DSA_Midsem_2025.pdf", "OS_Midsem_2025.pdf"}
    assert get(renv, department_id=DEPT_MATH, exam_type="Midsem").json() == []


def test_a_filter_that_matches_no_course_returns_an_empty_list(renv):
    assert get(renv, semester=9).json() == []
    assert get(renv, course_id=str(uuid4())).json() == []


# ----------------------------------------------------------- text search ---

def test_q_matches_file_name_and_tags(renv):
    assert titles(get(renv, q="linalg")) == {"LinAlg_Tutorial_1.pdf"}
    assert titles(get(renv, q="graphs")) == {"DSA_Midsem_2025.pdf"}


def test_q_can_be_combined_with_filters(renv):
    assert titles(get(renv, q="midsem", semester=3)) == {"DSA_Midsem_2025.pdf", "OS_Midsem_2025.pdf"}
    assert titles(get(renv, q="midsem", exam_year=2024)) == set()


def test_blank_q_means_no_text_filter_but_symbols_only_matches_nothing(renv):
    assert len(get(renv, q="   ").json()) == 4
    assert get(renv, q="%%%").json() == []


# ---------------------------------------------------------------- paging ---

def test_pages_do_not_overlap_and_together_cover_everything(renv):
    first = get(renv, limit=3).json()
    second = get(renv, limit=3, offset=3).json()
    assert len(first) == 3 and len(second) == 1            # 4 visible papers in total
    assert {r["id"] for r in first}.isdisjoint({r["id"] for r in second})
    assert {r["title"] for r in first + second} == {
        "DSA_Midsem_2025.pdf", "DSA_Endsem_2024.pdf", "OS_Midsem_2025.pdf", "LinAlg_Tutorial_1.pdf",
    }


def test_an_offset_past_the_end_gives_an_empty_page(renv):
    assert get(renv, offset=50).json() == []


def test_paging_works_together_with_filters(renv):
    assert len(get(renv, exam_type="Midsem", limit=1).json()) == 1
    assert len(get(renv, exam_type="Midsem", limit=1, offset=1).json()) == 1
    assert get(renv, exam_type="Midsem", limit=1, offset=2).json() == []


# ------------------------------------------------------------ validation ---

@pytest.mark.parametrize("params", [
    {"exam_type": "Quiz"}, {"content_type": "Solution"}, {"semester": 0}, {"semester": 13},
    {"limit": 0}, {"limit": 101}, {"offset": -1}, {"course_id": "not-a-uuid"}, {"department_id": "nope"},
])
def test_bad_parameters_are_rejected(renv, params):
    assert get(renv, **params).status_code == 422


# ----------------------------------------------------------- departments ---

def test_departments_are_listed_by_name(renv):
    r = renv.client.get("/api/departments", headers=as_user(renv, STUDENT))
    assert r.status_code == 200
    assert [d["name"] for d in r.json()] == ["Computer Science and Engineering", "Mathematics"]
    assert set(r.json()[0]) == {"id", "name", "code"}
