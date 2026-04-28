"""Tariff code suggestion service — uses MyForterro inference API."""

import json
import logging

from services.myforterro import chat_completion

logger = logging.getLogger("duck-demo")

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
        model="claude-4.6-opus",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.2,
    )

    raw = response.choices[0].message.content.strip()
    # Strip markdown code fences if the model wraps JSON in ```json ... ```
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    results = json.loads(raw)

    return {
        "country_of_origin": country_of_origin.upper(),
        "country_of_destination": country_of_destination.upper(),
        "results": results,
    }
