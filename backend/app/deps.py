from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import supabase_client
from .repositories import profiles
from .schemas.profile import ProfileOut

bearer_scheme = HTTPBearer(auto_error=False)

# The logged-in user, as seen by route functions: id, email, full_name, entry_number, role.
CurrentUser = ProfileOut


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    """Verify the access token sent as `Authorization: Bearer <token>`
    and load the caller's profile (including role) from the database.

    Put this on every route that needs a logged-in user."""
    admin = supabase_client.admin()  # 503 if the service role key is missing

    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated.")

    try:
        user_response = admin.auth.get_user(credentials.credentials)
        user = user_response.user if user_response else None
    except Exception:
        user = None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token.")

    row = profiles.get_by_id(user.id)
    if row is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Profile not found.")

    return CurrentUser(
        id=row.id,
        email=user.email,
        full_name=row.full_name,
        entry_number=row.entry_number,
        role=row.role,
    )


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Use as a dependency on any admin-only route."""
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required.")
    return user
