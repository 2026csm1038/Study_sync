from supabase import Client, create_client
from .config import settings

supabase: Client | None = None

if settings.supabase_configured:
    supabase = create_client(settings.supabase_url, settings.supabase_anon_key)
