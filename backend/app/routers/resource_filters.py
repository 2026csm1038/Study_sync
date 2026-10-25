"""Student-facing filter for approved resources (Page 3: Student Search).

    GET /api/resources    approved papers, narrowed by any combination of filters

Every filter is optional and the filters are combined with AND. With none, the newest papers come back.
The router only checks the parameters and who is asking; the query lives in repositories/resources.py.

(Text search by file name or tag alone is still GET /api/resources/search in routers/resources.py.)
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from ..deps import CurrentUser, get_current_user
from ..repositories import resources
from ..schemas.resource import ResourceOut
from ..schemas.submission import FIRST_YEAR, ExamType

router = APIRouter(prefix="/api/resources", tags=["resources"])


@router.get("", response_model=list[ResourceOut])
def filter_resources(
    q: str | None = Query(default=None, max_length=100, description="File name or tag contains this text"),
    course_id: UUID | None = None,
    department_id: UUID | None = None,
    semester: int | None = Query(default=None, ge=1, le=12),
    exam_year: int | None = Query(default=None, ge=FIRST_YEAR, le=2100),
    exam_type: ExamType | None = None,
    content_type: ExamType | None = Query(
        default=None, description="Page 3 'Content Type' dropdown. Same values as exam_type."
    ),
    limit: int = Query(default=50, ge=1, le=100),
    _user: CurrentUser = Depends(get_current_user),
):
    # Content Type and Exam Type both narrow the same column. Two different values can never match one paper.
    wanted = {value for value in (content_type, exam_type) if value}
    if len(wanted) > 1:
        return []

    return resources.filter_resources(
        q=(q or "").strip() or None,  # a blank box means "no text filter"
        course_id=course_id,
        department_id=department_id,
        semester=semester,
        exam_year=exam_year,
        exam_type=wanted.pop() if wanted else None,
        limit=limit,
    )
