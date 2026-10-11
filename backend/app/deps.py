from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .supabase_client import supabase_admin

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str | None
    full_name: str
    entry_number: str | None
    role: str  # "student" or "admin"


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    """Verify the Supabase access token sent as `Authorization: Bearer <token>`
    and load the caller's profile (including role) from the database."""
    if supabase_admin is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Server is missing SUPABASE_SERVICE_ROLE_KEY.",
        )
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated.")

    try:
        user_response = supabase_admin.auth.get_user(credentials.credentials)
        user = user_response.user if user_response else None
    except Exception:
        user = None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token.")

    rows = (
        supabase_admin.table("profiles")
        .select("full_name, entry_number, role")
        .eq("id", user.id)
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Profile not found.")

    profile = rows[0]
    return CurrentUser(
        id=user.id,
        email=user.email,
        full_name=profile["full_name"],
        entry_number=profile.get("entry_number"),
        role=profile["role"],
    )


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Use as a dependency on any admin-only route."""
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required.")
    return user
