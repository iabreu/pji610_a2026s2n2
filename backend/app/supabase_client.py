from functools import lru_cache

from supabase import Client, create_client
from supabase.lib.client_options import ClientOptions

from app.config import get_settings


@lru_cache
def get_supabase() -> Client:
    settings = get_settings()
    return create_client(
        supabase_url=settings.supabase_url,
        supabase_key=settings.supabase_service_role_key,
        options=ClientOptions(schema=settings.supabase_schema),
    )
