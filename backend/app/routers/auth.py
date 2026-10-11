from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..config import settings
from ..deps import CurrentUser, get_current_user, require_admin
from ..supabase_client import new_anon_client, supabase_admin

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Same message for every failure, so the API never reveals whether an
# entry number or email is registered.
INVALID_LOGIN = "Invalid entry number / email or password."


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=254, description="Entry number or email")
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int | None = None


class MeResponse(BaseModel):
    id: str
    email: str | None
    full_name: str
    entry_number: str | None
    role: str


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    """Log in with an entry number OR an email.

    The browser sends whatever the student typed. If it is an entry number we
    look up the matching email here on the server (so emails are never exposed
    to the browser), then sign in with Supabase Auth and return the tokens.
    """
    if not (settings.supabase_configured and settings.supabase_admin_configured):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Supabase is not configured on the server.",
        )

    identifier = body.identifier.strip()

    if "@" in identifier:
        email = identifier.lower()
    else:
        rows = (
            supabase_admin.table("profiles")
            .select("email")
            .eq("entry_number", identifier.upper())
            .limit(1)
            .execute()
            .data
        )
        if not rows or not rows[0].get("email"):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_LOGIN)
        email = rows[0]["email"]

    try:
        result = new_anon_client().auth.sign_in_with_password(
            {"email": email, "password": body.password}
        )
        session = result.session
    except Exception:
        session = None

    if session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_LOGIN)

    return TokenResponse(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        expires_in=session.expires_in,
    )


@router.get("/me", response_model=MeResponse)
def me(user: CurrentUser = Depends(get_current_user)):
    """Who am I? Also a quick way to test that a token works."""
    return MeResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        entry_number=user.entry_number,
        role=user.role,
    )


@router.get("/admin-check")
def admin_check(user: CurrentUser = Depends(require_admin)):
    """Example admin-only route. Copy the `Depends(require_admin)` pattern
    onto every route that only admins may call."""
    return {"ok": True, "admin": user.full_name}
