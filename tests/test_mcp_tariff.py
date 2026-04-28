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
