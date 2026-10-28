"""Admin Dashboard numbers and recent activity (Page 5). Admin-only.

    GET /api/admin/dashboard    totals, approved papers per exam type, and the newest activity

The rules live in services/dashboard.py.
"""
from fastapi import APIRouter, Depends, Query

from ..deps import CurrentUser, require_admin
from ..schemas.dashboard import DashboardOut
from ..services import dashboard

router = APIRouter(prefix="/api/admin/dashboard", tags=["admin: dashboard"])


@router.get("", response_model=DashboardOut)
def get_dashboard(
    activity_limit: int = Query(default=20, ge=1, le=50),
    _admin: CurrentUser = Depends(require_admin),
):
    return dashboard.build(activity_limit)
