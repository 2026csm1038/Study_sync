"""Course endpoints. Read: any logged-in user. Write: admins only (Page 8 / Page 9 of the wireframes).

The router only decides WHO may do WHAT; the database work lives in repositories/courses.py
and the data shapes live in schemas/course.py.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from ..exceptions import NotFound
from ..deps import CurrentUser, get_current_user, require_admin
from ..repositories import courses
from ..services import course_admin
from ..schemas.course import CourseAdminOut, CourseCreate, CourseOut, CourseUpdate

router = APIRouter(prefix="/api/courses", tags=["courses"])


@router.get("", response_model=list[CourseOut])
def list_courses(
    department_id: UUID | None = None,
    semester: int | None = Query(default=None, ge=1, le=12),
    q: str | None = Query(default=None, max_length=100, description="Search course code or name"),
    include_inactive: bool = False,
    user: CurrentUser = Depends(get_current_user),
):
    if include_inactive and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only admins can list inactive courses.")
    return courses.list_courses(
        department_id=department_id,
        semester=semester,
        search=q,
        include_inactive=include_inactive,
    )


@router.get("/admin/overview", response_model=list[CourseAdminOut])
def list_courses_for_admin(
    department_id: UUID | None = None,
    semester: int | None = Query(default=None, ge=1, le=12),
    q: str | None = Query(default=None, max_length=100, description="Search course code or name"),
    _admin: CurrentUser = Depends(require_admin),
):
    """Manage Courses table: every course (inactive too) with its paper counts and whether it can be deleted."""
    return course_admin.list_for_admin(department_id=department_id, semester=semester, search=q)


@router.get("/{course_id}", response_model=CourseOut)
def get_course(course_id: UUID, user: CurrentUser = Depends(get_current_user)):
    course = courses.get_course(course_id)
    if not course.is_active and user.role != "admin":
        raise NotFound("Course not found.")  # an inactive course is invisible to students
    return course


@router.post("", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
def create_course(body: CourseCreate, _admin: CurrentUser = Depends(require_admin)):
    return courses.create_course(body)


@router.patch("/{course_id}", response_model=CourseOut)
def update_course(course_id: UUID, body: CourseUpdate, _admin: CurrentUser = Depends(require_admin)):
    return courses.update_course(course_id, body)


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(course_id: UUID, _admin: CurrentUser = Depends(require_admin)):
    course_admin.delete(course_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
