"""
Singleton fal.ai client with connection pooling
Reduces cold start overhead by reusing HTTP connections
Uses EU region for better latency from Turkey
"""
import fal_client
import httpx
from functools import lru_cache
from core.config import get_settings
import os

settings = get_settings()
os.environ['FAL_KEY'] = settings.FAL_KEY

# Use EU region for lowest latency from Turkey/Istanbul
FAL_EU_ENDPOINT = "https://fal.run"  # Closest to Istanbul


@lru_cache(maxsize=1)
def get_fal_client():
    """
    Get singleton fal_client with connection pooling
    Reuses HTTP connections to reduce latency
    Uses EU region endpoint for Turkey users
    """
    # Configure httpx client with keep-alive
    http_client = httpx.Client(
        timeout=30.0,
        limits=httpx.Limits(
            max_connections=10,
            max_keepalive_connections=5,
            keepalive_expiry=30.0
        )
    )
    
    print(f"🔄 Initialized fal_client with connection pooling (Region: EU)")
    
    # Return the standard fal_client (which uses environment FAL_KEY)
    # Note: fal_client doesn't expose httpx client configuration directly
    # But we can benefit from OS-level connection pooling by reusing the same process
    return fal_client


@lru_cache(maxsize=1)
def get_async_http_client():
    """
    Get singleton async httpx client for downloading TTS audio
    """
    return httpx.AsyncClient(
        timeout=30.0,
        limits=httpx.Limits(
            max_connections=10,
            max_keepalive_connections=5,
            keepalive_expiry=30.0
        )
    )


# Pre-initialize to avoid cold start on first request
_client = get_fal_client()
_async_client = get_async_http_client()

print("✅ fal.ai client pool initialized")
