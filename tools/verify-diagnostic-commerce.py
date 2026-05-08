#!/usr/bin/env python3
"""Verify the diagnostic offer is consistent across human and agent surfaces."""

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ID = "8bitconcepts_ai_diagnostic"
CHECKOUT_URL = "https://buy.stripe.com/7sY7sE2rMfY97Bu8iL6oo03"
AMOUNT_CENTS = 50000
TURNAROUND_DAYS = 2


def load_json(path):
    return json.loads((ROOT / path).read_text())


def assert_equal(label, actual, expected):
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def assert_in(label, needle, haystack):
    if needle not in haystack:
        raise AssertionError(f"{label}: missing {needle!r}")


def product_from_catalog():
    catalog = load_json("api/v1/catalog")
    products = catalog.get("products", [])
    matches = [product for product in products if product.get("id") == PRODUCT_ID]
    if len(matches) != 1:
        raise AssertionError(f"catalog has {len(matches)} records for {PRODUCT_ID}")
    return matches[0]


def product_from_commerce():
    commerce = load_json(".well-known/commerce.json")
    products = commerce.get("products", [])
    matches = [product for product in products if product.get("id") == PRODUCT_ID]
    if len(matches) != 1:
        raise AssertionError(f"commerce manifest has {len(matches)} records for {PRODUCT_ID}")
    return matches[0]


def verify():
    diagnostic_html = (ROOT / "diagnostic.html").read_text()
    catalog_product = product_from_catalog()
    commerce_product = product_from_commerce()
    quote = load_json("api/v1/quote")
    checkout = load_json("api/v1/checkout")

    assert_in("diagnostic page", "$500", diagnostic_html)
    assert_in("diagnostic page", "within 48 hours", diagnostic_html)
    assert_in("diagnostic page", CHECKOUT_URL, diagnostic_html)
    assert_in("diagnostic page", "hello@8bitconcepts.com to schedule", diagnostic_html)

    for label, surface in (
        ("catalog", catalog_product),
        ("quote", quote),
        ("checkout", checkout),
    ):
        assert_equal(f"{label} product_id", surface.get("product_id", surface.get("id")), PRODUCT_ID)
        assert_equal(f"{label} checkout_url", surface.get("checkout_url"), CHECKOUT_URL)
        assert_equal(f"{label} amount", surface.get("amount_cents", surface.get("price_cents")), AMOUNT_CENTS)
        assert_equal(
            f"{label} turnaround",
            surface.get("fulfillment", {}).get("turnaround_days"),
            TURNAROUND_DAYS,
        )

    checkout_meta = commerce_product.get("checkout", {})
    fulfillment = commerce_product.get("fulfillment", {})
    assert_equal("commerce checkout URL", checkout_meta.get("url"), CHECKOUT_URL)
    assert_equal("commerce amount", commerce_product.get("price", {}).get("amount"), AMOUNT_CENTS)
    assert_equal("commerce turnaround", fulfillment.get("turnaround_days"), TURNAROUND_DAYS)


if __name__ == "__main__":
    try:
        verify()
    except Exception as exc:
        print(f"diagnostic commerce verification failed: {exc}", file=sys.stderr)
        sys.exit(1)
    print("diagnostic commerce surfaces ok")
