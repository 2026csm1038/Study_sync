"""Tests for the auth endpoints. Supabase is replaced by fakes, so no keys or network are needed.

Run from the backend folder:   pip install -r requirements-dev.txt   then   pytest
"""
from types import SimpleNamespace as NS

import pytest

from app.routers import auth as auth_mod

from .conftest import ADMIN, STUDENT, as_user, make_session


SIGNUP = {"full_name": "  New Student ", "entry_number": "2026csm1099", "email": "New@X.com", "password": "abcdefg1"}


# ---------------------------------------------------------------- config ---

def test_503_when_supabase_not_configured(env, monkeypatch):
    monkeypatch.setattr(auth_mod, "settings", NS(supabase_configured=False, supabase_admin_configured=False, frontend_url=""))
    assert env.client.post("/api/auth/login", json={"identifier": "2026CSM1038", "password": "x"}).status_code == 503


# ---------------------------------------------------------------- signup ---

@pytest.mark.parametrize("change", [
    {"entry_number": "12345"}, {"email": "not-an-email"}, {"password": "short1"},
    {"password": "onlyletters"}, {"password": "12345678"}, {"full_name": "A"},
])
def test_signup_validation(env, change):
    assert env.client.post("/api/auth/signup", json={**SIGNUP, **change}).status_code == 422


def test_signup_needs_confirmation(env):
    env.anon.auth.sign_up.return_value = NS(user=NS(id="u3", email="new@x.com", identities=[object()]), session=None)
    r = env.client.post("/api/auth/signup", json=SIGNUP)
    assert r.status_code == 201 and r.json() == {"needs_email_confirmation": True, "session": None}
    sent = env.anon.auth.sign_up.call_args.args[0]
    assert sent["email"] == "new@x.com"                                      # lower-cased
    assert sent["options"]["data"] == {"full_name": "New Student", "entry_number": "2026CSM1099"}  # trimmed, upper-cased


def test_signup_logs_in_when_confirmation_is_off(env):
    new = {"id": "u3", "email": "new@x.com", "full_name": "New Student", "entry_number": "2026CSM1099", "role": "student"}

    def sign_up(_credentials):
        env.db["profiles"].append(new)  # in real life the database trigger creates this row during sign-up
        return NS(user=NS(id="u3", email="new@x.com", identities=[object()]), session=make_session(new))

    env.anon.auth.sign_up.side_effect = sign_up
    body = env.client.post("/api/auth/signup", json=SIGNUP).json()
    assert body["needs_email_confirmation"] is False
    assert body["session"]["profile"]["role"] == "student" and body["session"]["access_token"] == "AT"


def test_signup_duplicate_entry_number(env):
    r = env.client.post("/api/auth/signup", json={**SIGNUP, "entry_number": "2026CSM1038"})
    assert r.status_code == 409
    env.anon.auth.sign_up.assert_not_called()


def test_signup_duplicate_email_variants(env):
    env.anon.auth.sign_up.return_value = NS(user=NS(id="x", email="n@x.com", identities=[]), session=None)  # confirmation on
    assert env.client.post("/api/auth/signup", json=SIGNUP).status_code == 409
    env.anon.auth.sign_up.side_effect = Exception("User already registered")                              # confirmation off
    assert env.client.post("/api/auth/signup", json=SIGNUP).status_code == 409
    env.anon.auth.sign_up.side_effect = Exception("Database error saving new user")                       # unique index race
    assert env.client.post("/api/auth/signup", json=SIGNUP).status_code == 409


# ----------------------------------------------------------------- login ---

def test_login_with_entry_number(env):
    r = env.client.post("/api/auth/login", json={"identifier": "2026csm1038", "password": "pw"})
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] == "AT" and body["profile"]["full_name"] == "Vanshika"
    env.anon.auth.sign_in_with_password.assert_called_with({"email": "v@x.com", "password": "pw"})


def test_login_with_email(env):
    assert env.client.post("/api/auth/login", json={"identifier": "V@X.com", "password": "pw"}).status_code == 200
    env.anon.auth.sign_in_with_password.assert_called_with({"email": "v@x.com", "password": "pw"})


def test_login_failures_look_identical(env):
    unknown = env.client.post("/api/auth/login", json={"identifier": "2026ZZZ0000", "password": "pw"})
    env.anon.auth.sign_in_with_password.side_effect = Exception("Invalid login credentials")
    wrong_pw = env.client.post("/api/auth/login", json={"identifier": "2026CSM1038", "password": "bad"})
    assert unknown.status_code == wrong_pw.status_code == 401
    assert unknown.json() == wrong_pw.json()


# ------------------------------------------------------ refresh / logout ---

def test_refresh(env):
    env.anon.auth.refresh_session.return_value = NS(session=make_session())
    r = env.client.post("/api/auth/refresh", json={"refresh_token": "old"})
    assert r.status_code == 200 and r.json()["refresh_token"] == "RT"
    env.anon.auth.refresh_session.assert_called_with("old")
    env.anon.auth.refresh_session.side_effect = Exception("expired")
    assert env.client.post("/api/auth/refresh", json={"refresh_token": "old"}).status_code == 401


def test_logout_always_succeeds(env):
    assert env.client.post("/api/auth/logout", headers={"Authorization": "Bearer tok"}).status_code == 200
    env.admin.auth.admin.sign_out.assert_called_with("tok", "local")
    env.admin.auth.admin.sign_out.side_effect = Exception("already gone")
    assert env.client.post("/api/auth/logout", headers={"Authorization": "Bearer tok"}).status_code == 200
    assert env.client.post("/api/auth/logout").status_code == 200


# ------------------------------------------------------- password reset ---

def test_forgot_password_never_reveals_accounts(env):
    ok = env.client.post("/api/auth/forgot-password", json={"email": "v@x.com"})
    env.anon.auth.reset_password_for_email.side_effect = Exception("User not found")
    unknown = env.client.post("/api/auth/forgot-password", json={"email": "nobody@x.com"})
    garbage = env.client.post("/api/auth/forgot-password", json={"email": "garbage"})
    assert ok.status_code == unknown.status_code == garbage.status_code == 200
    assert ok.json() == unknown.json() == garbage.json()


def test_reset_password(env):
    env.anon.auth.verify_otp.return_value = NS(user=NS(id="u1"), session=make_session())
    r = env.client.post("/api/auth/reset-password", json={"token_hash": "th", "password": "newpass12"})
    assert r.status_code == 200
    env.anon.auth.verify_otp.assert_called_with({"token_hash": "th", "type": "recovery"})
    env.admin.auth.admin.update_user_by_id.assert_called_with("u1", {"password": "newpass12"})


def test_reset_password_bad_link_or_weak_password(env):
    env.anon.auth.verify_otp.side_effect = Exception("Token has expired or is invalid")
    assert env.client.post("/api/auth/reset-password", json={"token_hash": "x", "password": "newpass12"}).status_code == 400
    env.admin.auth.admin.update_user_by_id.assert_not_called()
    assert env.client.post("/api/auth/reset-password", json={"token_hash": "x", "password": "weak"}).status_code == 422


# ---------------------------------------------------- me / role checks ---

def test_me_and_roles(env):
    assert env.client.get("/api/auth/me").status_code == 401  # no token
    me = env.client.get("/api/auth/me", headers=as_user(env, STUDENT))
    assert me.status_code == 200 and me.json()["entry_number"] == "2026CSM1038"
    assert env.client.get("/api/auth/admin-check", headers=as_user(env, STUDENT)).status_code == 403
    assert env.client.get("/api/auth/admin-check", headers=as_user(env, ADMIN)).status_code == 200


def test_invalid_token(env):
    env.admin.auth.get_user.side_effect = Exception("bad jwt")
    assert env.client.get("/api/auth/me", headers={"Authorization": "Bearer nope"}).status_code == 401
