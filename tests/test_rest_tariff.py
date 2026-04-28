"""REST contract tests — tariff suggestion endpoint."""

import json
from unittest.mock import patch

import pytest

from tests.contract_helpers import assert_shape, ListOf

pytestmark = pytest.mark.rest


# ── Mock helpers ───────────────────────────────────────────────────────────

_MOCK_LLM_JSON = json.dumps([
    {
        "product_description": "Yellow rubber duck",
        "tariff_codes": [
            {"code": "9503.00", "description": "Toys", "confidence": "high"},
        ],
    },
    {
        "product_description": "Steel bottle opener",
        "tariff_codes": [
            {"code": "8205.51", "description": "Household tools", "confidence": "high"},
        ],
    },
])


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


# ── Tests ──────────────────────────────────────────────────────────────────

@patch("services.tariff.chat_completion", return_value=_FakeResponse(_MOCK_LLM_JSON))
def test_post_tariff_suggest_200(_mock, rest_client):
    resp = rest_client.post(
        "/api/tariff/suggest",
        json={
            "country_of_origin": "FR",
            "country_of_destination": "US",
            "products": ["Yellow rubber duck", "Steel bottle opener"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["country_of_origin"] == "FR"
    assert data["country_of_destination"] == "US"
    assert len(data["results"]) == 2

    for entry in data["results"]:
        assert_shape(entry, {
            "product_description": str,
            "tariff_codes": ListOf({"code": str, "description": str, "confidence": str}),
        })


def test_post_tariff_suggest_400_missing_fields(rest_client):
    resp = rest_client.post(
        "/api/tariff/suggest",
        json={"country_of_origin": "FR"},
    )
    assert resp.status_code == 400
    assert "error" in resp.json()


def test_post_tariff_suggest_400_empty_products(rest_client):
    resp = rest_client.post(
        "/api/tariff/suggest",
        json={
            "country_of_origin": "FR",
            "country_of_destination": "US",
            "products": [],
        },
    )
    assert resp.status_code == 400
    assert "error" in resp.json()
