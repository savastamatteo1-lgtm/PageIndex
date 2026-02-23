"""Supabase client singleton.

Provides a cached Supabase client initialized from environment variables.
All database operations in the ``pageindex.db`` package obtain a client
through :func:`get_client` rather than creating their own connections.
"""

from __future__ import annotations

import os

from supabase import Client, create_client

_client: Client | None = None


def reset_client() -> None:
    """Reset the cached Supabase client, forcing re-initialization on next ``get_client()`` call.

    Called by :meth:`PageIndex.__init__() <pageindex.api.PageIndex.__init__>`
    when new credentials are provided via the constructor.  After env vars
    are updated and this function is called, the next ``get_client()`` will
    create a fresh client with the new credentials.
    """
    global _client
    _client = None


def get_client() -> Client:
    """Return the cached Supabase client, creating it on first call.

    Environment variables
    ---------------------
    SUPABASE_URL : str
        Full URL of the Supabase project (e.g. ``https://xyz.supabase.co``).
    SUPABASE_KEY : str
        Supabase anon or service-role key.

    Raises
    ------
    RuntimeError
        If either ``SUPABASE_URL`` or ``SUPABASE_KEY`` is not set.
    """
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        if not url or not key:
            missing = []
            if not url:
                missing.append("SUPABASE_URL")
            if not key:
                missing.append("SUPABASE_KEY")
            raise RuntimeError(
                f"Missing required environment variable(s): {', '.join(missing)}. "
                "Set them before using the database layer."
            )
        _client = create_client(url, key)
    return _client
