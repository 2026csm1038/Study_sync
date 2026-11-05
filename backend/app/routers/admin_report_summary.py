"""Report numbers for the admin (sidebar badge and dashboard alert). Admin-only.

    GET /api/admin/reports/summary

A resource "needs attention" when the weights of its OPEN flags add up to ATTENTION_THRESHOLD or more.
A professor's flag counts 5 and a student's counts 1 (see FLAG_WEIGHT in routers/resource_flags.py),
so five student flags, or one professor flag, is enough.
"""
from collections import defaultdict

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..deps import CurrentUser, require_admin
from ..supabase_client import admin
from .resource_flags import weight_for

ATTENTION_THRESHOLD = 5  # same cut-off as the "High" priority on the Resource Reports page

router = APIRouter(prefix="/api/admin/reports", tags=["admin: reports"])


class ReportSummary(BaseModel):
    open_flags: int          # open flags in total
    flagged_resources: int   # resources with at least one open flag
    needs_attention: int     # resources whose open flags weigh ATTENTION_THRESHOLD or more
    threshold: int


@router.get("/summary", response_model=ReportSummary)
def report_summary(_admin: CurrentUser = Depends(require_admin)):
    flags = (
        admin().table("resource_flags").select("resource_id,reporter_id")
        .eq("status", "open").execute().data or []
    )
    reporter_ids = list({str(f["reporter_id"]) for f in flags if f.get("reporter_id")})
    roles: dict[str, str | None] = {}
    if reporter_ids:
        rows = admin().table("profiles").select("id,role").in_("id", reporter_ids).execute().data or []
        roles = {str(row["id"]): row.get("role") for row in rows}

    score: dict[str, int] = defaultdict(int)
    for flag in flags:
        score[str(flag["resource_id"])] += weight_for(roles.get(str(flag.get("reporter_id"))))

    return ReportSummary(
        open_flags=len(flags),
        flagged_resources=len(score),
        needs_attention=sum(1 for total in score.values() if total >= ATTENTION_THRESHOLD),
        threshold=ATTENTION_THRESHOLD,
    )
