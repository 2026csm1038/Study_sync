from supabase import Client, create_client
from .config import settings

# Shared client with the public (anon) key. Used only for non-user-specific work.
supabase: Client | None = None

if settings.supabase_configured:
    supabase = create_client(settings.supabase_url, settings.supabase_anon_key)

# Admin client with the service role key. It bypasses Row Level Security,
# so use it only inside backend code that has already checked who the caller is.
supabase_admin: Client | None = None

if settings.supabase_admin_configured:
    supabase_admin = create_client(settings.supabase_url, settings.supabase_service_role_key)


def new_anon_client() -> Client:
    """A fresh anon client for one request.

    supabase-py clients remember the last signed-in session, so a shared client
    must never be used to sign users in on a server: one user's session could
    leak into another user's request.
    """
    return create_client(settings.supabase_url, settings.supabase_anon_key)
