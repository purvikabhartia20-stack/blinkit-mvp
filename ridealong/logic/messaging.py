"""Constrained Groq trial messages with deterministic safe fallback."""

from __future__ import annotations

import os
import re
from typing import Any

import requests

from config import (
    GROQ_CHAT_ENDPOINT,
    GROQ_MAX_MESSAGE_CHARS,
    GROQ_MODEL,
    GROQ_TIMEOUT_SECONDS,
)


def template_message(product: dict[str, Any], path: str) -> str:
    """Build the plain-language trial line from verified product fields only."""
    name = product["name"]
    price = (
        int(product["price"])
        if float(product["price"]).is_integer()
        else product["price"]
    )
    if path == "gap_fill":
        return (
            f"Since this is already on its way, we added a trial of {name} "
            f"for ₹{price} — no extra delivery, no extra wait."
        )
    return (
        f"Your order today is bigger than usual — here's a ₹{price} "
        f"trial of {name} on us."
    )


def _verified_price(product: dict[str, Any]) -> str:
    """Return the catalog price in the same compact form used in messages."""
    value = float(product["price"])
    return str(int(value)) if value.is_integer() else str(value)


def _prompt(product: dict[str, Any], path: str) -> list[dict[str, str]]:
    """Build a tightly constrained prompt using verified fields only."""
    context = (
        "The cart is close to free delivery."
        if path == "gap_fill"
        else "The shopper is placing a larger stocking-up order."
    )
    return [
        {
            "role": "system",
            "content": (
                "Write exactly one short checkout sentence for a grocery app. "
                "Use only the supplied product name and price as product facts. "
                "Never add benefits, ingredients, quality, popularity, urgency, "
                "discounts, or any other product claim. Do not use emojis, "
                "headings, quotation marks, or multiple sentences. "
                "Keep the sentence under 180 characters."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Context: {context}\n"
                f"Verified product name: {product['name']}\n"
                f"Verified price: ₹{_verified_price(product)}"
            ),
        },
    ]


def _safe_model_text(text: Any, product: dict[str, Any]) -> str | None:
    """Accept only a short, one-line response containing verified fields."""
    if not isinstance(text, str):
        return None
    cleaned = " ".join(text.strip().split())
    if not cleaned or len(cleaned) > GROQ_MAX_MESSAGE_CHARS:
        return None
    if "\n" in text or "\r" in text:
        return None
    if product["name"].casefold() not in cleaned.casefold():
        return None

    verified_price = _verified_price(product)
    if not re.search(rf"₹\s*{re.escape(verified_price)}(?!\d)", cleaned):
        return None

    # Reject obvious multi-sentence output while allowing decimal prices.
    sentence_marks = re.findall(r"(?<!\d)[.!?](?!\d)", cleaned)
    if len(sentence_marks) > 1:
        return None
    return cleaned


def generate_message(
    product: dict[str, Any],
    path: str,
    detail: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Return ``(message, source)`` without ever breaking checkout."""
    _ = detail
    fallback = template_message(product, path)
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        return fallback, "template_fallback_no_key"

    try:
        response = requests.post(
            GROQ_CHAT_ENDPOINT,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": _prompt(product, path),
                "temperature": 0.2,
                "max_tokens": 70,
            },
            timeout=GROQ_TIMEOUT_SECONDS,
        )
    except requests.Timeout:
        return fallback, "template_fallback_timeout"
    except requests.RequestException:
        return fallback, "template_fallback_network"
    except Exception:
        return fallback, "template_fallback_exception"

    if not response.ok:
        return fallback, f"template_fallback_http_{response.status_code}"

    try:
        text = response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError):
        return fallback, "template_fallback_invalid_response"

    safe_text = _safe_model_text(text, product)
    if safe_text is None:
        return fallback, "template_fallback_unsafe_response"
    return safe_text, "groq_live"
