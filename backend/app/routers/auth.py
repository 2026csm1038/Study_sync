"""Every authentication action for StudySync.

The React app never talks to Supabase. It calls these endpoints, and this file
talks to Supabase Auth on its behalf. Request/response shapes live in schemas/auth.py,
and reads of the profiles table live in repositories/profiles.py.

    POST /api/auth/signup           create an account (profile row is made once the email is confirmed)
    POST /api/auth/confirm-email    confirm the email from the emailed link
    POST /api/auth/resend-confirmation  send a fresh confirmation link
    POST /api/auth/login            entry number OR email + password
    POST /api/auth/refresh          swap a refresh token for fresh tokens
    POST /api/auth/logout           end the session
    POST /api/auth/forgot-password  email a reset link
    POST /api/auth/reset-password   set a new password from the emailed link
    GET  /api/auth/me               who am I?
    GET  /api/auth/admin-check      example admin-only route
"""
from fastapi import APIRouter, Depends, HTTPException, status

from .. import deps, supabase_client
from ..config import settings
from ..exceptions import AppError
from ..deps import CurrentUser, get_current_user, require_admin
from ..repositories import profiles
from ..schemas.auth import (
    EMAIL_RE,
    ConfirmEmailRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageOut,
    RefreshRequest,
    ResendConfirmationRequest,
    ResetPasswordRequest,
    SessionOut,
    SignupRequest,
    SignupResponse,
)
from ..schemas.profile import ProfileOut

router = APIRouter(prefix="/api/auth", tags=["auth"])

# One message for every login failure, so the API never reveals whether an
# entry number or email is registered.
INVALID_LOGIN = "Invalid entry number / email or password."

NOT_CONFIRMED = "Please confirm your email first. Check your inbox, or request a new link."
EMAIL_LIMIT_MESSAGE = (
    "We can't send any more emails right now. Please try again in about an hour."
)
REQUEST_LIMIT_MESSAGE = "Too many attempts. Please wait a minute and try again."


def _error_code(exc: Exception) -> str:
    """Supabase's machine-readable error code, e.g. 'over_email_send_rate_limit'."""
    return str(getattr(exc, "code", "") or "").lower()


def _is_email_limit(exc: Exception) -> bool:
    """Supabase's built-in mailer only sends a handful of emails per hour for the WHOLE
    project (every signup, resend and password reset counts). This is the usual cause of a
    "too many attempts" error while testing with only a few accounts."""
    return _error_code(exc) == "over_email_send_rate_limit" or "email rate limit" in str(exc).lower()


def _is_rate_limited(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        _error_code(exc) in ("over_email_send_rate_limit", "over_request_rate_limit")
        or getattr(exc, "status", None) == 429
        or "rate limit" in message
        or "too many" in message
    )


def _limit_error(exc: Exception) -> HTTPException:
    detail = EMAIL_LIMIT_MESSAGE if _is_email_limit(exc) else REQUEST_LIMIT_MESSAGE
    return HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail)


def _require_supabase() -> None:
    if not (settings.supabase_configured and settings.supabase_admin_configured):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The server is not configured for Supabase yet.",
        )


def _build_session(auth_session) -> SessionOut:
    """Turn a Supabase session into our response model, including the user's profile."""
    user = auth_session.user
    row = profiles.get_by_id(user.id)
    if row is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Your account is not set up yet. Confirm your email first, or contact an admin.",
        )
    return SessionOut(
        access_token=auth_session.access_token,
        refresh_token=auth_session.refresh_token,
        expires_in=auth_session.expires_in,
        profile=ProfileOut(
            id=row.id,
            email=user.email,
            full_name=row.full_name,
            entry_number=row.entry_number,
            role=row.role,
        ),
    )


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest):
    """Create an account. Every new account is a student; admins are promoted in the database."""
    _require_supabase()

    if profiles.entry_number_exists(body.entry_number):
        raise HTTPException(status.HTTP_409_CONFLICT, "This entry number is already registered.")

    try:
        result = supabase_client.new_anon_client().auth.sign_up(
            {
                "email": body.email,
                "password": body.password,
                "options": {
                    # Stored on the auth user. The database trigger copies it into `profiles`
                    # ONLY once the email is confirmed.
                    "data": {"full_name": body.full_name, "entry_number": body.entry_number},
                    "email_redirect_to": f"{settings.frontend_url}/confirm-email",
                },
            }
        )
    except Exception as exc:
        if _is_rate_limited(exc):
            raise _limit_error(exc)
        message = str(exc).lower()
        if "already registered" in message or "already been registered" in message:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "An account with this email already exists."
            )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Could not create the account.")

    user = result.user
    # With "confirm email" on, an email that already exists comes back as a user with no identities.
    if user is not None and user.identities is not None and len(user.identities) == 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")

    if result.session is None:
        # email confirmation is on: the student must click the link in their inbox first
        return SignupResponse(needs_email_confirmation=True)

    return SignupResponse(needs_email_confirmation=False, session=_build_session(result.session))


@router.post("/login", response_model=SessionOut)
def login(body: LoginRequest):
    """Log in with an entry number OR an email.

    If it is an entry number we look up the matching email here on the server,
    so emails are never exposed to the browser.
    """
    _require_supabase()

    identifier = body.identifier.strip()

    if "@" in identifier:
        email = identifier.lower()
    else:
        row = profiles.get_by_entry_number(identifier)
        if row is None or not row.email:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_LOGIN)
        email = row.email

    try:
        result = supabase_client.new_anon_client().auth.sign_in_with_password(
            {"email": email, "password": body.password}
        )
        auth_session = result.session
    except Exception as exc:
        # Supabase only reports this AFTER the password was correct, so it leaks nothing.
        if _error_code(exc) == "email_not_confirmed" or "email not confirmed" in str(exc).lower():
            raise HTTPException(status.HTTP_403_FORBIDDEN, NOT_CONFIRMED)
        if _is_rate_limited(exc):
            raise _limit_error(exc)
        auth_session = None

    if auth_session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_LOGIN)

    return _build_session(auth_session)


@router.post("/refresh", response_model=SessionOut)
def refresh(body: RefreshRequest):
    """Exchange a refresh token for a new access token (and a new refresh token)."""
    _require_supabase()
    try:
        result = supabase_client.new_anon_client().auth.refresh_session(body.refresh_token)
        auth_session = result.session
    except Exception:
        auth_session = None

    if auth_session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired. Please log in again.")
    return _build_session(auth_session)


@router.post("/logout", response_model=MessageOut)
def logout(credentials=Depends(deps.bearer_scheme)):
    """End the session on the Supabase side. Always succeeds, so a stale token never blocks logout."""
    if credentials is not None:
        try:
            supabase_client.admin().auth.admin.sign_out(credentials.credentials, "local")
        except Exception:
            pass
    return MessageOut(message="Logged out.")


@router.post("/forgot-password", response_model=MessageOut)
def forgot_password(body: ForgotPasswordRequest):
    """Email a reset link. The answer is always the same, so nobody can use this
    to find out which emails are registered."""
    _require_supabase()
    email = body.email.strip().lower()
    generic = MessageOut(message="If an account exists for that email, a reset link is on its way.")

    if not EMAIL_RE.match(email):
        return generic
    try:
        supabase_client.new_anon_client().auth.reset_password_for_email(
            email, {"redirect_to": f"{settings.frontend_url}/reset-password"}
        )
    except Exception as exc:
        if _is_rate_limited(exc):
            raise _limit_error(exc)
    return generic


@router.post("/confirm-email", response_model=MessageOut)
def confirm_email(body: ConfirmEmailRequest):
    """Confirm an email using the one-time `token_hash` from the confirmation email.

    Confirming is what makes the database create the student's profile row.
    The React page calls this only after the student clicks a button, so mail scanners
    that pre-open links can't use up the one-time token.
    """
    _require_supabase()
    try:
        result = supabase_client.new_anon_client().auth.verify_otp(
            {"token_hash": body.token_hash, "type": "signup"}
        )
    except Exception as exc:
        if _is_rate_limited(exc):
            raise _limit_error(exc)
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "This confirmation link is invalid or has expired. Please request a new one.",
        )
    if result.user is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "This confirmation link is invalid or has expired. Please request a new one.",
        )
    return MessageOut(message="Email confirmed. You can log in now.")


@router.post("/resend-confirmation", response_model=MessageOut)
def resend_confirmation(body: ResendConfirmationRequest):
    """Send a new confirmation email. Same answer whether or not the email exists."""
    _require_supabase()
    email = body.email.strip().lower()
    generic = MessageOut(message="If that email is waiting for confirmation, a new link is on its way.")

    if not EMAIL_RE.match(email):
        return generic
    try:
        supabase_client.new_anon_client().auth.resend(
            {
                "type": "signup",
                "email": email,
                "options": {"email_redirect_to": f"{settings.frontend_url}/confirm-email"},
            }
        )
    except Exception as exc:
        if _is_rate_limited(exc):
            raise _limit_error(exc)
    return generic


@router.post("/reset-password", response_model=MessageOut)
def reset_password(body: ResetPasswordRequest):
    """Set a new password using the link from the reset email.

    The link carries either a one-time `token_hash` (our custom email template) or an
    `access_token` (Supabase's default template, which verifies the link before redirecting).
    """
    _require_supabase()
    expired = HTTPException(
        status.HTTP_400_BAD_REQUEST,
        "This reset link is invalid or has expired. Please request a new one.",
    )
    try:
        if body.token_hash:
            user = (
                supabase_client.new_anon_client()
                .auth.verify_otp({"token_hash": body.token_hash, "type": "recovery"})
                .user
            )
        else:
            user = supabase_client.admin().auth.get_user(body.access_token).user
    except AppError:
        raise
    except Exception:
        raise expired
    if user is None:
        raise expired

    try:
        supabase_client.admin().auth.admin.update_user_by_id(user.id, {"password": body.password})
    except Exception:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Could not update the password. This link may already have been used, "
            "so please request a new one.",
        )
    return MessageOut(message="Password updated.")


@router.get("/me", response_model=ProfileOut)
def me(user: CurrentUser = Depends(get_current_user)):
    """Who am I? The frontend calls this on page load to restore the session."""
    return user


@router.get("/admin-check")
def admin_check(user: CurrentUser = Depends(require_admin)):
    """Example admin-only route. Copy the `Depends(require_admin)` pattern
    onto every route that only admins may call."""
    return {"ok": True, "admin": user.full_name}
