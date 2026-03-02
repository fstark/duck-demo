"""Configuration constants for the duck-demo application."""

import os

# Pricing constants
PRICING_DEFAULT_UNIT_PRICE = 12.0
PRICING_VOLUME_QTY_THRESHOLD = 24
PRICING_VOLUME_DISCOUNT_PCT = 0.05
PRICING_FREE_SHIPPING_THRESHOLD = 300.0
PRICING_FLAT_SHIPPING = 20.0
PRICING_CURRENCY = "EUR"

# Substitution constants
SUBSTITUTION_PRICE_SLACK_PCT = 0.15  # within ±15% of requested SKU

# Invoice constants
INVOICE_PAYMENT_TERMS_DAYS = 30

# Quote constants
QUOTE_VALIDITY_DAYS = 30

# Lead time constants
TRANSIT_DAYS_DEFAULT = 2
PRODUCTION_LEAD_DAYS_DEFAULT = 30
PRODUCTION_LEAD_DAYS_BY_TYPE = {"finished_good": 30}

# Warehouse & location constants
WAREHOUSE_DEFAULT = "WH-LYON"
LOC_FINISHED_GOODS = "FG"
LOC_PRODUCTION_OUT = "PROD-OUT"
LOC_RAW_MATERIAL_RECV = "RM/RECV-01"

# Logging configuration
LOG_FILE = os.getenv("LOG_FILE", "duck-demo.log")

# Base URL for all absolute URLs (API resources, UI deep links)
# Override with API_BASE environment variable for production/tunnel deployments
# Examples: http://localhost:5173, https://yourdomain.com, https://abc123.ngrok.io
API_BASE = os.getenv("API_BASE", "http://127.0.0.1:5173")

# Work center capacity (max concurrent operations per center)
WORK_CENTER_CAPACITY = {
    "MOLDING": 3,
    "PAINTING": 4,
    "CURING": 2,
    "ASSEMBLY": 2,
    "QC": 2,
    "PACKAGING": 3,
}
