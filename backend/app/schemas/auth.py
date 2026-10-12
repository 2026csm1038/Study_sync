import re

from pydantic import BaseModel, Field, field_validator
from ..config import settings  
from .profile import ProfileOut

# Entry numbers look like 2026CSM1038 or 2026AIM1022. Change this if your college differs.
ENTRY_NUMBER_RE = re.compile(r"^\d{4}[A-Za-z]{2,5}\d{3,5}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def check_password_strength(value: str) -> str:
    if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise ValueError("Password must contain at least one letter and one number.")
    return value


# ---------------------------------------------------------------- requests ---

class LoginRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=254, description="Entry number or email")
    password: str = Field(min_length=1, max_length=128)


class SignupRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    entry_number: str
    email: str = Field(max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("full_name", mode="before")
    @classmethod
    def _strip_name(cls, v):
        return v.strip() if isinstance(v, str) else v

    @field_validator("entry_number")
    @classmethod
    def _check_entry(cls, v: str) -> str:
        v = v.strip()
        if not ENTRY_NUMBER_RE.match(v):
            raise ValueError("Enter a valid entry number, for example 2026CSM1038.")
        return v.upper()

    @field_validator("email")
    @classmethod
    def _check_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("Enter a valid email address.")
        allowed = settings.allowed_email_domains
        if allowed and v.rsplit("@", 1)[1] not in allowed:
            raise ValueError(f"Please use your college email (@{', @'.join(allowed)}).")
        return v

    @field_validator("password")
    @classmethod
    def _check_password(cls, v: str) -> str:
        return check_password_strength(v)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(max_length=254)


class ResetPasswordRequest(BaseModel):
    token_hash: str = Field(min_length=1, max_length=2048)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def _check_password(cls, v: str) -> str:
        return check_password_strength(v)


# --------------------------------------------------------------- responses ---

class SessionOut(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int | None = None
    profile: ProfileOut


class SignupResponse(BaseModel):
    needs_email_confirmation: bool
    session: SessionOut | None = None


class MessageOut(BaseModel):
    message: str
