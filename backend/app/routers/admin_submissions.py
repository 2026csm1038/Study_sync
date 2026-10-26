"""Admin approval flow (Page 6: Manage Request). Every route here is admin-only.

    GET  /api/admin/submissions?status=pending   the students' requests (pending | approved | rejected)
    GET  /api/admin/submissions/{id}/file        preview the PDF held in temporary storage
    POST /api/admin/submissions/{id}/approve     copy it to the shared Google Drive and publish it
    POST /api/admin/submissions/{id}/reject      reject it with a reason the student can see

The rules live in services/review.py.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from ..deps import CurrentUser, require_admin
from ..schemas.review import RejectRequest, ReviewItem
from ..schemas.submission import SubmissionStatus
from ..services import review

router = APIRouter(prefix="/api/admin/submissions", tags=["admin: approval"])


@router.get("", response_model=list[ReviewItem])
def list_requests(
    status: SubmissionStatus = "pending",
    limit: int = Query(default=100, ge=1, le=200),
    _admin: CurrentUser = Depends(require_admin),
):
    return review.list_requests(status, limit)


@router.get("/{submission_id}/file")
def preview_file(submission_id: UUID, _admin: CurrentUser = Depends(require_admin)):
    content, filename = review.preview(str(submission_id))
    safe_name = filename.replace('"', "").replace("\r", "").replace("\n", "")
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{safe_name}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/{submission_id}/approve", response_model=ReviewItem)
def approve(submission_id: UUID, admin: CurrentUser = Depends(require_admin)):
    return review.approve(admin, str(submission_id))


@router.post("/{submission_id}/reject", response_model=ReviewItem)
def reject(submission_id: UUID, body: RejectRequest, admin: CurrentUser = Depends(require_admin)):
    return review.reject(admin, str(submission_id), body.reason)
