---
name: myforterro-api
description: Connect to and interact with the MyForterro API (authentication, tenant management, AI agents, invoicing, inference).
---

## Purpose

Authenticate and call the MyForterro API — a multi-tenant SaaS platform providing Fx Rates, E-Invoicing, AI (inference + agentic platform), and Open Banking modules to Forterro products.

## When to use

- Obtaining access tokens for MyForterro
- Calling any MyForterro REST endpoint (AI agents, invoicing, tenant admin, etc.)
- Debugging authentication or authorization issues with MyForterro
- Using the MyForterro inference API via OpenAI SDK

## Reference links

| Resource | URL |
|---|---|
| Documentation | https://forterro-fwe.atlassian.net/wiki/spaces/MFT/pages/1685717006/How+to+use+the+MyForterro+API |
| Swagger UI | https://integration-myforterro-api.fcs-dev.eks.forterro.com/swagger/index.html |
| OpenAPI spec | https://integration-myforterro-api.fcs-dev.eks.forterro.com/openapi/v1.json |
| OpenID config | https://integration-myforterro-core.fcs-dev.eks.forterro.com/.well-known/openid-configuration |

## Credentials

Stored in `secrets.sh` (git-ignored). Source it before any API call:

```bash
source secrets.sh
```

| Variable | Purpose |
|---|---|
| `CLIENT_APP_ID` | OAuth client ID for the MyForterro application |
| `CLIENT_APP_SECRET` | OAuth client secret |
| `TENANT_ID` | UUID identifying the tenant (used as `MFT-Tenant-Id` header) |
| `TENANT_APPLICATION_ID` | UUID of the MyForterro business service application linked to the tenant |

## Authentication flow

MyForterro uses **OAuth 2.0 Client Credentials** with a custom `application` parameter.

### ⚠️ Critical: the `application` parameter

A standard `client_credentials` grant without the `application` parameter will return a valid JWT, but it will **lack the roles/permissions needed to access any API endpoint** (every call returns 401).

You **must** include `application=$TENANT_APPLICATION_ID` in the token request. This tells the MyForterro auth server to issue a token scoped to the specific tenant application, including proper roles and permissions.

### Token request

```bash
source secrets.sh

TOKEN=$(curl -s -X POST \
  https://integration-myforterro-core.fcs-dev.eks.forterro.com/connect/token \
  -d "grant_type=client_credentials" \
  -d "client_id=$CLIENT_APP_ID" \
  -d "client_secret=$CLIENT_APP_SECRET" \
  -d "application=$TENANT_APPLICATION_ID" \
  | jq -r '.access_token')
```

The token is a JWT, valid for **3600 seconds** (1 hour).

### Token endpoint details

- **URL**: `https://integration-myforterro-core.fcs-dev.eks.forterro.com/connect/token`
- **Auth methods supported**: `client_secret_post`, `client_secret_basic`, `private_key_jwt`
- **Grant types**: `client_credentials`, `authorization_code`, `refresh_token`, `token-exchange`

## Calling the API

Every API call requires two things:

1. **`Authorization: Bearer $TOKEN`** header
2. **`MFT-Tenant-Id: $TENANT_ID`** header (except `/v1/admin/tenants` which lists all accessible tenants)

```bash
curl -s \
  -H "Authorization: Bearer $TOKEN" \
  -H "MFT-Tenant-Id: $TENANT_ID" \
  https://integration-myforterro-api.fcs-dev.eks.forterro.com/v1/ai/agents | jq .
```

## Quick test: list tenants

`GET /v1/admin/tenants` does not require `MFT-Tenant-Id` and is a good first connectivity test:

```bash
source secrets.sh && \
TOKEN=$(curl -s -X POST \
  https://integration-myforterro-core.fcs-dev.eks.forterro.com/connect/token \
  -d "grant_type=client_credentials" \
  -d "client_id=$CLIENT_APP_ID" \
  -d "client_secret=$CLIENT_APP_SECRET" \
  -d "application=$TENANT_APPLICATION_ID" \
  | jq -r '.access_token') && \
curl -s -H "Authorization: Bearer $TOKEN" \
  https://integration-myforterro-api.fcs-dev.eks.forterro.com/v1/admin/tenants | jq .
```

Expected response:
```json
[
  {
    "tenantId": "efc8df60-508d-4d2d-936f-75ba256e7428",
    "slug": "stark-industries",
    "myForterroIdentifiers": {
      "applicationId": "f4c42de8-3bc1-420c-b72e-01f75df2f726",
      "clientId": "f4c42de8-3bc1-420c-b72e-01f75df2f726"
    }
  }
]
```

## Using the inference API with OpenAI SDK

The MyForterro AI inference API is OpenAI-compatible:

```python
import openai

API_BASE = "https://integration-myforterro-api.fcs-dev.eks.forterro.com/v1/ai/inference/openai"

client = openai.OpenAI(
    api_key=TOKEN,
    base_url=API_BASE,
    default_headers={"MFT-Tenant-Id": TENANT_ID},
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me a joke."},
    ],
    temperature=1.0,
)
```

## Available API modules

| Module | Endpoints prefix | Roles required |
|---|---|---|
| Fx Rates | `/v1/fx/rates` | None |
| E-Invoicing | `/v1/invoicing/` | Accounting or Admin |
| AI | `/v1/ai/` | User or Admin |
| Tenant Admin | `/v1/admin/tenants` | (varies) |

**Note**: Modules must be enabled in the MyForterro application overview page. Configuration is cached for 5 minutes.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| 401 on every endpoint | Missing `application` param in token request | Add `-d "application=$TENANT_APPLICATION_ID"` to the token POST |
| Valid JWT but empty scopes | Same as above — token has no roles without `application` | Same fix |
| 403 Forbidden | User/app lacks required role for the module | Check role assignments in MyForterro admin |
| 401 after ~1 hour | Token expired | Request a new token (they last 3600s) |

## JWT claims reference

A properly scoped token includes these MyForterro-specific claims:

| Claim | Description |
|---|---|
| `mf:sid` | MyForterro session ID |
| `mf:cid` | MyForterro company/context ID |
| `mf:app_id` | Application ID the token was issued for |
| `mf:app_name` | Human-readable application name |
| `aud` | Always `myforterro` |

Decode a token for debugging:
```bash
echo "$TOKEN" | cut -d. -f2 | (cat; echo '==') | base64 -d 2>/dev/null | jq .
```
