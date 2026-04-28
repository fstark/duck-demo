# MyForterro Integration — Tariff Code Suggestions

## Overview

A new feature that suggests HS (Harmonized System) tariff codes for products, given an origin country, a destination country, and free-form product descriptions. It leverages the **MyForterro Inference API** (OpenAI-compatible) to call Claude Opus for structured tariff code suggestions.

## User Story

> As a sales agent, when preparing a quote for international shipment, I want to get tariff code suggestions for each product so that I can estimate customs duties and ensure trade compliance.

## Request / Response Contract

### Input

```json
{
  "country_of_origin": "FR",
  "country_of_destination": "US",
  "products": [
    "Yellow rubber duck, 8cm, children's bath toy",
    "Stainless steel duck-shaped bottle opener",
    "Organic lavender-scented duck soap, 100g"
  ]
}
```

- `country_of_origin` — ISO 3166-1 alpha-2 code
- `country_of_destination` — ISO 3166-1 alpha-2 code
- `products` — list of 1+ free-form product descriptions (strings)

### Output

```json
{
  "country_of_origin": "FR",
  "country_of_destination": "US",
  "results": [
    {
      "product_description": "Yellow rubber duck, 8cm, children's bath toy",
      "tariff_codes": [
        {
          "code": "9503.00",
          "description": "Toys; other toys, including miniatures and models for recreation",
          "confidence": "high"
        },
        {
          "code": "4016.99",
          "description": "Articles of vulcanised rubber, other than hard rubber",
          "confidence": "medium"
        }
      ]
    },
    {
      "product_description": "Stainless steel duck-shaped bottle opener",
      "tariff_codes": [
        {
          "code": "8205.51",
          "description": "Household hand tools and implements; non-mechanical",
          "confidence": "high"
        }
      ]
    },
    {
      "product_description": "Organic lavender-scented duck soap, 100g",
      "tariff_codes": [
        {
          "code": "3401.11",
          "description": "Soap; for toilet use, in bars or moulded shapes",
          "confidence": "high"
        }
      ]
    }
  ]
}
```

Each `tariff_codes` entry:
- `code` — HS code (6-digit or 8-digit depending on destination specifics)
- `description` — human-readable description of the tariff heading
- `confidence` — one of `"high"`, `"medium"`, `"low"`

## Architecture

### New Files

| File | Purpose |
|---|---|
| `services/myforterro.py` | MyForterro API client — auth + inference calls |
| `services/tariff.py` | Tariff suggestion business logic |
| `mcp_tools/tariff_tools.py` | MCP tool definition |
| `api_routes/tariff_routes.py` | REST endpoint |

### Layer Diagram

```
MCP Tool / REST Route
        │
        ▼
  services/tariff.py          ← orchestration + prompt construction
        │
        ▼
  services/myforterro.py      ← auth token cache + inference call
        │
        ▼
  MyForterro Inference API     ← OpenAI-compatible, proxies to Claude Opus
```

### services/myforterro.py — MyForterro Client

A reusable client for any future MyForterro integration. Handles:

1. **OAuth token acquisition** — client credentials flow with the `application` parameter
2. **Token caching** — cache the JWT in-memory, refresh when expired (3600s TTL, refresh at 3500s)
3. **Inference calls** — thin wrapper around the OpenAI SDK pointing at the MyForterro base URL

```python
# Pseudo-code structure

import os
import time
import openai
import requests

# Auth endpoint
_TOKEN_URL = "https://integration-myforterro-core.fcs-dev.eks.forterro.com/connect/token"
_API_BASE = "https://integration-myforterro-api.fcs-dev.eks.forterro.com"
_INFERENCE_BASE = f"{_API_BASE}/v1/ai/inference/openai"

# Cached token state (module-level)
_token: str | None = None
_token_expires_at: float = 0.0


def _get_credentials() -> dict:
    """Read credentials from environment variables."""
    return {
        "client_id": os.environ["CLIENT_APP_ID"],
        "client_secret": os.environ["CLIENT_APP_SECRET"],
        "tenant_id": os.environ["TENANT_ID"],
        "application_id": os.environ["TENANT_APPLICATION_ID"],
    }


def get_token() -> str:
    """Return a valid access token, refreshing if needed."""
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
    return _token


def get_inference_client() -> openai.OpenAI:
    """Return an OpenAI client configured for MyForterro inference."""
    creds = _get_credentials()
    return openai.OpenAI(
        api_key=get_token(),
        base_url=_INFERENCE_BASE,
        default_headers={"MFT-Tenant-Id": creds["tenant_id"]},
    )


def chat_completion(*, model: str, messages: list[dict], **kwargs) -> dict:
    """Send a chat completion request via MyForterro inference."""
    client = get_inference_client()
    response = client.chat.completions.create(
        model=model, messages=messages, **kwargs
    )
    return response
```

**Design decisions:**
- Module-level token cache (single-threaded server, no lock needed).
- `get_token()` refreshes 100s before expiry to avoid race conditions.
- `chat_completion()` is a thin wrapper — callers build their own messages/prompts.
- Credentials read from env vars (loaded by `secrets.sh` before server start).
- No `config.py` constants for URLs — these are external infrastructure, not app config.

### services/tariff.py — Tariff Suggestion Logic

Responsible for:
1. Validating inputs (country codes, non-empty product list)
2. Building the Claude prompt with structured output instructions
3. Calling `myforterro.chat_completion()`
4. Parsing the JSON response and returning the structured result

```python
# Pseudo-code structure

import json
import logging
from services.myforterro import chat_completion

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a trade compliance expert. Given a country of origin, a country of \
destination, and a list of product descriptions, suggest the most likely \
HS (Harmonized System) tariff codes for each product.

Respond ONLY with a JSON array. Each element corresponds to one product \
(in the same order as the input list) and has this shape:

{
  "product_description": "<echoed input>",
  "tariff_codes": [
    {"code": "<HS code>", "description": "<heading description>", "confidence": "high|medium|low"}
  ]
}

Rules:
- Suggest 1-3 tariff codes per product, ordered by confidence.
- Use 6-digit HS codes unless destination-specific 8-digit codes are well known.
- confidence: "high" = very likely correct, "medium" = plausible, "low" = possible but uncertain.
- If a product description is too vague, return a single entry with confidence "low".
"""


def suggest_tariff_codes(
    *, country_of_origin: str, country_of_destination: str, products: list[str]
) -> dict:
    """Return tariff code suggestions for a list of products."""
    if not products:
        raise ValueError("products list must not be empty")

    user_message = json.dumps({
        "country_of_origin": country_of_origin.upper(),
        "country_of_destination": country_of_destination.upper(),
        "products": products,
    })

    response = chat_completion(
        model="claude-opus",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.2,
    )

    raw = response.choices[0].message.content
    results = json.loads(raw)

    return {
        "country_of_origin": country_of_origin.upper(),
        "country_of_destination": country_of_destination.upper(),
        "results": results,
    }
```

**Design decisions:**
- Low temperature (0.2) for deterministic, factual output.
- System prompt requests JSON-only response to simplify parsing.
- Country codes are uppercased for consistency.
- No local tariff database — the LLM is the source of suggestions (appropriate for a demo; production would cross-reference an official HS database).

### mcp_tools/tariff_tools.py — MCP Tool

```python
from typing import Any, Dict
from mcp_tools._common import log_tool
from services.tariff import suggest_tariff_codes


def register(mcp):
    @mcp.tool(
        name="tariff_suggest",
        description=(
            "Suggest HS tariff codes for products being shipped between two countries. "
            "Provide country_of_origin and country_of_destination as ISO 3166-1 alpha-2 "
            "codes (e.g. 'FR', 'US', 'DE') and a list of free-form product descriptions. "
            "Returns 1-3 suggested tariff codes per product with confidence levels."
        ),
        meta={"tags": ["shared"]},
    )
    @log_tool("tariff_suggest")
    def tariff_suggest(
        country_of_origin: str,
        country_of_destination: str,
        products: list[str],
    ) -> Dict[str, Any]:
        return suggest_tariff_codes(
            country_of_origin=country_of_origin,
            country_of_destination=country_of_destination,
            products=products,
        )
```

**Design decisions:**
- Tagged `shared` — useful to both sales and production agents.
- `products` is a `list[str]` — flexible list-based parameter per MCP conventions.
- Thin wrapper; all logic lives in the service layer.

### api_routes/tariff_routes.py — REST Endpoint

```
POST /api/tariff/suggest
```

```python
import json
from starlette.requests import Request
from api_routes._common import _json, cors_handler
from services.tariff import suggest_tariff_codes


def register(mcp):
    @mcp.custom_route("/api/tariff/suggest", methods=["POST", "OPTIONS"])
    @cors_handler(["POST"])
    async def tariff_suggest(request: Request):
        body = await request.json()
        country_of_origin = body.get("country_of_origin", "")
        country_of_destination = body.get("country_of_destination", "")
        products = body.get("products", [])
        if not country_of_origin or not country_of_destination or not products:
            return _json({"error": "country_of_origin, country_of_destination, and products are required"}, status_code=400)
        result = suggest_tariff_codes(
            country_of_origin=country_of_origin,
            country_of_destination=country_of_destination,
            products=products,
        )
        return _json(result)
```

### Registration

Add to `mcp_tools/__init__.py`:
```python
from mcp_tools.tariff_tools import register as register_tariff_tools
# ... in register_all_tools():
register_tariff_tools(mcp)
```

Add to `api_routes/__init__.py`:
```python
from api_routes.tariff_routes import register as register_tariff_routes
# ... in register_all_routes():
register_tariff_routes(mcp)
```

## Dependencies

| Package | Purpose | Already in requirements.txt? |
|---|---|---|
| `openai` | OpenAI SDK for MyForterro inference API | No — must add |
| `requests` | HTTP client for OAuth token endpoint | Yes |

## Error Handling

| Scenario | Behaviour |
|---|---|
| Missing env vars (`CLIENT_APP_ID`, etc.) | `KeyError` at startup / first call — intentional fail-fast |
| MyForterro token request fails | `requests.HTTPError` raised — surfaces to caller |
| Inference API returns non-JSON | `json.JSONDecodeError` — log raw response, raise `ValueError` |
| Inference API timeout | `openai` SDK timeout — propagate to caller |
| Empty products list | `ValueError("products list must not be empty")` |

No silent failures. Errors propagate to the MCP/REST layer which returns them as error responses.

## Security

- Credentials are read from env vars, never hardcoded.
- The token is cached in memory only, never written to disk or logs.
- The MyForterro API is called over HTTPS.
- User input (product descriptions) is passed as structured JSON inside the prompt, not interpolated into raw strings.

## Future Considerations

- **`services/myforterro.py` is reusable** — any future MyForterro integration (fx rates, e-invoicing) can import `get_token()` or `chat_completion()` directly.
- **Model selection** — the model name (`"claude-opus"`) could be extracted to a parameter or config if multiple models become available.
- **Caching** — repeated identical queries could be cached (e.g. by hashing the input) to avoid redundant inference calls, but not needed for the demo.
- **Official HS database** — in production, LLM suggestions would be cross-referenced against an official tariff schedule for validation.
