"""Department list (read-only). Any logged-in user. Used by the Department filter on Page 3.

    GET /api/departments
"""
from fastapi import APIRouter, Depends

from ..deps import CurrentUser, get_current_user
from ..repositories import departments
from ..schemas.department import DepartmentOut

router = APIRouter(prefix="/api/departments", tags=["departments"])


@router.get("", response_model=list[DepartmentOut])
def list_departments(_user: CurrentUser = Depends(get_current_user)):
    return departments.list_departments()
