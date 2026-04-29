"""MyForterro API client — OAuth authentication and inference calls."""

import logging
import os
import time

import openai
import requests

logger = logging.getLogger("duck-demo")

_TOKEN_URL = "https://integration-myforterro-core.fcs-dev.eks.forterro.com/connect/token"
_API_BASE = "https://integration-myforterro-api.fcs-dev.eks.forterro.com"
_INFERENCE_BASE = f"{_API_BASE}/v1/ai/inference/openai"

# Module-level token cache (single-threaded server, no lock needed)
_token: str | None = None
_token_expires_at: float = 0.0


def _get_credentials() -> dict:
    """Read MyForterro credentials from environment variables."""
    return {
        "client_id": os.environ["CLIENT_APP_ID"],
        "client_secret": os.environ["CLIENT_APP_SECRET"],
        "tenant_id": os.environ["TENANT_ID"],
        "application_id": os.environ["TENANT_APPLICATION_ID"],
    }


def get_token() -> str:
    """Return a valid access token, refreshing if near expiry."""
    global _token, _token_expires_at
    if _token and time.time() < _token_expires_at:
        return _token

    creds = _get_credentials()
    resp = requests.post(_TOKEN_URL, data={
        "grant_type": "client_credentials",
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "application": creds["application_id"],
    })
    resp.raise_for_status()
    data = resp.json()

    _token = data["access_token"]
    _token_expires_at = time.time() + data.get("expires_in", 3600) - 100
    logger.info("MyForterro token acquired, expires in %ds", data.get("expires_in", 3600))
    return _token


def get_inference_client() -> openai.OpenAI:
    """Return an OpenAI client configured for MyForterro inference."""
    creds = _get_credentials()
    return openai.OpenAI(
        api_key=get_token(),
        base_url=_INFERENCE_BASE,
        default_headers={"MFT-Tenant-Id": creds["tenant_id"]},
    )


def chat_completion(*, model: str, messages: list[dict], **kwargs):
    """Send a chat completion request via MyForterro inference."""
    client = get_inference_client()
    return client.chat.completions.create(
        model=model, messages=messages, **kwargs
    )


def openai_chat_completion(*, model: str, messages: list[dict], **kwargs):
    """Send a chat completion request directly to OpenAI."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set — cannot use openai provider")
    client = openai.OpenAI(api_key=api_key)
    return client.chat.completions.create(
        model=model, messages=messages, **kwargs
    )
