"""Automatic creation of departments and courses from what a student types on the upload form.

Admins still manage courses (rename, deactivate, delete) from Manage Courses; this only fills the
gaps so an upload is never blocked by a missing course or department.
"""
import re

from ..exceptions import BadRequest, Conflict
from ..repositories import courses, departments
from ..schemas.course import CourseCreate, CourseOut
from ..schemas.department import DepartmentOut

_SMALL_WORDS = {"and", "of", "the", "for", "in", "&"}
CODE_MAX = 20  # departments.code is varchar(20)


def department_code_for(name: str) -> str:
    """A short code for a new department.

    "CSE" stays "CSE". "Computer Science and Engineering" becomes "CSE" (initials, small words
    skipped). A single long word like "Mathematics" becomes "MATH" (first four letters)."""
    cleaned = re.sub(r"[^A-Za-z0-9 &]", " ", name).strip()
    if " " not in cleaned and len(cleaned) <= 6:
        return cleaned.upper()
    words = [w for w in cleaned.split() if w.lower() not in _SMALL_WORDS]
    code = "".join(w[0] for w in words).upper() if len(words) > 1 else cleaned[:4].upper()
    return (code or "DEPT")[:CODE_MAX]


def _tidy_name(name: str) -> str:
    """Keep what was typed, but fix shouting/lowercase: 'computer science' -> 'Computer Science'.
    A short all-caps entry such as 'CSE' is left alone."""
    name = re.sub(r"\s+", " ", name).strip()
    return name if name.isupper() and len(name) <= 6 else name.title() if name.islower() or name.isupper() else name


def get_or_create_department(typed: str) -> tuple[DepartmentOut, bool]:
    """Return (department, created). Matches existing ones by name or code, ignoring case."""
    found = departments.find_by_name_or_code(typed)
    if found:
        return found, False

    name = _tidy_name(typed)
    base = department_code_for(name)
    for attempt in range(1, 20):
        code = base if attempt == 1 else f"{base[: CODE_MAX - 2]}{attempt}"
        try:
            return departments.create(name[:100], code), True
        except Conflict:
            # Someone created a department meanwhile (or the code is taken). If it is the same
            # department, use it; otherwise try the next code.
            found = departments.find_by_name_or_code(typed)
            if found:
                return found, False
    raise BadRequest("Could not create that department. Please pick one from the list.")


def get_or_create_course(
    *, code: str, name: str, department: str, semester: int
) -> tuple[CourseOut, bool, DepartmentOut | None]:
    """Return (course, course_created, department_created_or_None).

    An existing course with this code is reused as it is (its name, department and semester are the
    admin's, not whatever the student typed)."""
    existing = courses.find_by_code(code)
    if existing:
        return existing, False, None

    dept, dept_created = get_or_create_department(department)
    try:
        course = courses.create_course(
            CourseCreate(course_code=code, course_name=name, department_id=dept.id, semester=semester)
        )
    except Conflict:
        # Lost a race with another student uploading the same new course: use theirs.
        existing = courses.find_by_code(code)
        if existing:
            return existing, False, dept if dept_created else None
        raise
    return course, True, dept if dept_created else None
