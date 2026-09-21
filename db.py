"""Supabase client factory.

Ace is a trusted server-side process, so it should hold the service-role key
rather than the anon key. The anon key is public by design -- it ships in
browsers -- and anything it can reach is reachable by anyone who has it. Running
the backend on it is what forces the permissive `USING (true)` RLS policies to
exist, and those policies are what expose every table to the internet.

Prefers SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_SECRET_KEY for the newer
sb_secret_... format) and falls back to the anon key so an unconfigured deploy
still boots -- loudly, so the fallback does not go unnoticed.
"""
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

_warned = False


def resolve_key() -> str:
    """Return the strongest Supabase key configured, warning on fallback."""
    global _warned

    service = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SECRET_KEY")
    )
    if service:
        return service

    if not _warned:
        print(
            "[db] WARNING: falling back to the anon key. Set "
            "SUPABASE_SERVICE_ROLE_KEY so the backend stops depending on "
            "permissive RLS policies that also expose every table publicly."
        )
        _warned = True

    return os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY") or ""


def get_client():
    """Build a Supabase client for server-side use."""
    url = os.getenv("SUPABASE_URL")
    if not url:
        raise RuntimeError("SUPABASE_URL is not set")
    return create_client(url, resolve_key())
