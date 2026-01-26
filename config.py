"""Configuration constants for the duck-demo application."""

import os

# Pricing constants
PRICING_DEFAULT_UNIT_PRICE = 12.0
PRICING_VOLUME_QTY_THRESHOLD = 24
PRICING_VOLUME_DISCOUNT_PCT = 0.05
PRICING_FREE_SHIPPING_THRESHOLD = 300.0
PRICING_CURRENCY = "EUR"

# Substitution constants
SUBSTITUTION_PRICE_SLACK_PCT = 0.15  # within ±15% of requested SKU

# Lead time constants
TRANSIT_DAYS_DEFAULT = 2
PRODUCTION_LEAD_DAYS_DEFAULT = 30
PRODUCTION_LEAD_DAYS_BY_TYPE = {"finished_good": 30}

# Logging configuration
LOG_FILE = os.getenv("LOG_FILE", "duck-demo.log")

# Base URL for all absolute URLs (API resources, UI deep links)
# Override with API_BASE environment variable for production/tunnel deployments
# Examples: http://localhost:5173, https://yourdomain.com, https://abc123.ngrok.io
API_BASE = os.getenv("API_BASE", "http://127.0.0.1:5173")
