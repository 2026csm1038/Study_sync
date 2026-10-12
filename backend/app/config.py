import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_anon_key: str = os.getenv("SUPABASE_ANON_KEY", "")
    # Server-only secret. NEVER put this in the frontend or commit it to git.
    supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    # Where the React app runs. Used for CORS and for the links inside auth emails.
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")

    allowed_email_domains = [d.strip().lower() for d in
    os.getenv("ALLOWED_EMAIL_DOMAINS", "iitrpr.ac.in").split(",") if d.strip()]

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_anon_key)

    @property
    def supabase_admin_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)

    

settings = Settings()
