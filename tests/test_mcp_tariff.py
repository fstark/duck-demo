"""MCP tool contract tests — tariff code suggestions."""

import json
from unittest.mock import patch

import pytest

from tests.contract_helpers import assert_shape, ListOf

pytestmark = pytest.mark.mcp


def _call(mcp_app, tool_name, **kwargs):
    """Call an MCP tool function directly by name and return the result."""
    tool = mcp_app._tool_manager._tools[tool_name]
    return tool.fn(**kwargs)


# ── Mock helpers ───────────────────────────────────────────────────────────

_MOCK_LLM_JSON = json.dumps([
    {
        "product_description": "Yellow rubber duck",
        "tariff_codes": [
            {"code": "9503.00", "description": "Toys", "confidence": "high"},
            {"code": "4016.99", "description": "Rubber articles", "confidence": "medium"},
        ],
    }
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


def _structured(result):
    if hasattr(result, "structuredContent"):
        return result.structuredContent
    return result


# ── Tests ──────────────────────────────────────────────────────────────────

@patch("services.tariff.chat_completion", return_value=_FakeResponse(_MOCK_LLM_JSON))
def test_tariff_suggest_returns_results(_mock, mcp_app):
    result = _call(
        mcp_app, "tariff_suggest",
        country_of_origin="FR",
        country_of_destination="US",
        products=["Yellow rubber duck"],
    )
    assert isinstance(result, dict)
    assert result["country_of_origin"] == "FR"
    assert result["country_of_destination"] == "US"
    assert isinstance(result["results"], list)
    assert len(result["results"]) == 1

    entry = result["results"][0]
    assert_shape(entry, {
        "product_description": str,
        "tariff_codes": ListOf({"code": str, "description": str, "confidence": str}),
    })
    assert entry["tariff_codes"][0]["confidence"] in ("high", "medium", "low")


@patch("services.tariff.chat_completion", return_value=_FakeResponse(_MOCK_LLM_JSON))
def test_tariff_suggest_empty_products(_mock, mcp_app):
    with pytest.raises(Exception):
        _call(
            mcp_app, "tariff_suggest",
            country_of_origin="FR",
            country_of_destination="US",
            products=[],
        )


@patch("services.tariff.chat_completion", return_value=_FakeResponse(_MOCK_LLM_JSON))
def test_tariff_suggest_uppercases_countries(_mock, mcp_app):
    result = _call(
        mcp_app, "tariff_suggest",
        country_of_origin="fr",
        country_of_destination="us",
        products=["Yellow rubber duck"],
    )
    assert result["country_of_origin"] == "FR"
    assert result["country_of_destination"] == "US"


@patch("services.tariff.chat_completion", return_value=_FakeResponse(_MOCK_LLM_JSON))
def test_create_shipment_non_eu_missing_tariff_returns_redirect_error(_mock, mcp_app):
    """Non-EU destination without tariff codes asks caller to use dedicated picker tool."""
    result = _call(
        mcp_app,
        "logistics_create_shipment",
        ship_from={"warehouse": "WH-LYON"},
        ship_to={"line1": "123 Main St", "city": "New York", "postal_code": "10001", "country": "US"},
        planned_departure="2025-09-01",
        planned_arrival="2025-09-08",
        packages=[{"contents": [{"sku": "CLASSIC-DUCK-10CM", "qty": 12}]}],
    )

    payload = _structured(result)
    assert "error" in payload
    assert "logistics_pick_tariff_for_shipment" in payload["error"]


@patch("services.tariff.chat_completion", return_value=_FakeResponse(_MOCK_LLM_JSON))
def test_pick_tariff_for_shipment_non_eu_missing_tariff_returns_picker(_mock, mcp_app):
    """Dedicated tariff picker tool returns suggestions and original shipment arguments."""
    result = _call(
        mcp_app,
        "logistics_pick_tariff_for_shipment",
        ship_from={"warehouse": "WH-LYON"},
        ship_to={"line1": "123 Main St", "city": "New York", "postal_code": "10001", "country": "US"},
        planned_departure="2025-09-01",
        planned_arrival="2025-09-08",
        packages=[{"contents": [{"sku": "CLASSIC-DUCK-10CM", "qty": 12}]}],
    )

    payload = _structured(result)
    assert payload["destination_country"] == "US"
    assert payload["original_tool"] == "logistics_create_shipment"
    assert len(payload["items"]) >= 1
    assert len(payload["items"][0]["suggestions"]) >= 1


def test_create_shipment_non_eu_with_tariff_proceeds(mcp_app):
    """Non-EU destination with tariff codes proceeds to confirmation."""
    result = _call(
        mcp_app,
        "logistics_create_shipment",
        ship_from={"warehouse": "WH-LYON"},
        ship_to={"line1": "123 Main St", "city": "New York", "postal_code": "10001", "country": "US"},
        planned_departure="2025-09-01",
        planned_arrival="2025-09-08",
        packages=[
            {
                "contents": [
                    {
                        "sku": "CLASSIC-DUCK-10CM",
                        "qty": 12,
                        "tariff_code": "9503.00",
                        "tariff_description": "Toys",
                    }
                ]
            }
        ],
    )

    payload = _structured(result)
    assert payload["original_tool"] == "logistics_create_shipment"
    assert payload["arguments"]["ship_to"]["country"] == "US"


def test_create_shipment_eu_no_tariff_needed(mcp_app):
    """Intra-EU destination proceeds without tariff codes."""
    result = _call(
        mcp_app,
        "logistics_create_shipment",
        ship_from={"warehouse": "WH-LYON"},
        ship_to={"line1": "10 Unter den Linden", "city": "Berlin", "postal_code": "10117", "country": "DE"},
        planned_departure="2025-09-01",
        planned_arrival="2025-09-03",
        packages=[{"contents": [{"sku": "CLASSIC-DUCK-10CM", "qty": 12}]}],
    )

    payload = _structured(result)
    assert payload["original_tool"] == "logistics_create_shipment"
    assert payload["arguments"]["ship_to"]["country"] == "DE"


def test_create_shipment_unsupported_country(mcp_app):
    """Unsupported destination country returns standardized error payload."""
    result = _call(
        mcp_app,
        "logistics_create_shipment",
        ship_from={"warehouse": "WH-LYON"},
        ship_to={"line1": "1 Street", "city": "Somewhere", "postal_code": "00000", "country": "XX"},
        planned_departure="2025-09-01",
        planned_arrival="2025-09-03",
        packages=[{"contents": [{"sku": "CLASSIC-DUCK-10CM", "qty": 12}]}],
    )

    payload = _structured(result)
    assert "error" in payload
    assert "not supported" in payload["error"]
