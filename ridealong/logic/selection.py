"""Trial-value caps and deterministic product selection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from config import (
    ABSOLUTE_MAX_TRIAL_VALUE,
    DECLINE_COOLDOWN_DAYS,
    GAP_FILL_PRICE_UPPER_FLOOR,
    GAP_PRICE_TOLERANCE,
    TIER_HIGH_CAP,
    TIER_HIGH_THRESHOLD,
    TIER_LOW_CAP,
    TIER_LOW_THRESHOLD,
    TIER_MID_CAP,
)
from db import get_connection
from logic.signal import get_order_history


def _tier_cap(cart_value: float, item_count: int) -> float:
    """Return the average-item-price tier cap."""
    if item_count <= 0:
        raise ValueError("item_count must be greater than zero")
    average_item_price = float(cart_value) / item_count
    if average_item_price < TIER_LOW_THRESHOLD:
        return float(TIER_LOW_CAP)
    if average_item_price <= TIER_HIGH_THRESHOLD:
        return float(TIER_MID_CAP)
    return float(TIER_HIGH_CAP)


def _affinity_score(
    cart_categories: set[str],
    candidate_category: str,
) -> float:
    """Return the strongest cart-to-candidate category affinity."""
    if not cart_categories:
        return 0.0
    placeholders = ",".join("?" for _ in cart_categories)
    query = f"""
        SELECT COALESCE(MAX(confidence), 0)
        FROM basket_affinity
        WHERE from_category IN ({placeholders}) AND to_category = ?
    """
    params = (*sorted(cart_categories), candidate_category)
    with get_connection() as connection:
        return float(connection.execute(query, params).fetchone()[0])


def _pairing_context(
    cart_categories: set[str],
) -> dict[str, Any] | None:
    """Return the highest-affinity curated pairing matching the cart."""
    if not cart_categories:
        return None
    placeholders = ",".join("?" for _ in cart_categories)
    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT cart_category, suggested_category, value_ceiling
            FROM category_pairings
            WHERE cart_category IN ({placeholders})
            """,
            tuple(sorted(cart_categories)),
        ).fetchall()
    if not rows:
        return None

    pairings = []
    for row in rows:
        pairing = dict(row)
        pairing["affinity_score"] = _affinity_score(
            cart_categories,
            pairing["suggested_category"],
        )
        pairings.append(pairing)
    return sorted(
        pairings,
        key=lambda row: (
            -row["affinity_score"],
            row["suggested_category"],
            row["cart_category"],
        ),
    )[0]


def compute_trial_value_cap(
    cart_value: float,
    item_count: int,
    cart_categories: list[str] | set[str],
) -> float:
    """Return pairing cap first, otherwise tier cap, always clamped to ₹150."""
    pairing = _pairing_context(set(cart_categories))
    raw_cap = (
        float(pairing["value_ceiling"])
        if pairing
        else _tier_cap(cart_value, item_count)
    )
    return min(raw_cap, float(ABSOLUTE_MAX_TRIAL_VALUE))


def _eligible_products(
    user_id: int,
    cart_categories: set[str],
) -> list[dict[str, Any]]:
    """Return products passing all non-price eligibility filters."""
    history = get_order_history(user_id)
    purchased_categories = {
        category
        for order in history
        for category in order["categories"]
    }
    declined_cutoff = (
        datetime.now(timezone.utc) - timedelta(days=DECLINE_COOLDOWN_DAYS)
    ).isoformat()

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT p.*
            FROM products AS p
            WHERE p.in_stock = 1
              AND p.safe_for_auto_trial = 1
              AND NOT EXISTS (
                  SELECT 1
                  FROM declined_offers AS d
                  WHERE d.user_id = ?
                    AND d.product_id = p.product_id
                    AND d.declined_at >= ?
              )
            """,
            (user_id, declined_cutoff),
        ).fetchall()

    return [
        dict(row)
        for row in rows
        if row["category"] not in purchased_categories
        and row["category"] not in cart_categories
    ]


def _rank(
    products: list[dict[str, Any]],
    cart_categories: set[str],
) -> dict[str, Any] | None:
    """Rank by affinity, then lowest price and product id."""
    ranked = []
    for product in products:
        candidate = dict(product)
        candidate["affinity_score"] = _affinity_score(
            cart_categories,
            candidate["category"],
        )
        ranked.append(candidate)
    if not ranked:
        return None
    return sorted(
        ranked,
        key=lambda item: (
            -item["affinity_score"],
            item["price"],
            item["product_id"],
        ),
    )[0]


def select_product(
    user_id: int,
    cart_categories: list[str] | set[str],
    path: str,
    detail: dict[str, Any],
) -> dict[str, Any] | None:
    """Select exactly one deterministic eligible product, or None."""
    categories = set(cart_categories)
    products = _eligible_products(user_id, categories)

    if path == "gap_fill":
        # Lower bound is the exact gap; upper is max(gap × 1.15, ₹50 floor).
        gap = float(detail["gap"])
        lower = gap
        upper = max(
            gap * (1 + GAP_PRICE_TOLERANCE),
            float(GAP_FILL_PRICE_UPPER_FLOOR),
        )
        return _rank(
            [
                product
                for product in products
                if lower <= float(product["price"]) <= upper
            ],
            categories,
        )

    if path != "stocking_up":
        raise ValueError(f"Unknown RideAlong path: {path}")

    cart_value = float(detail["cart_value"])
    item_count = int(detail["item_count"])
    pairing = _pairing_context(categories)

    if pairing:
        pairing_cap = min(
            float(pairing["value_ceiling"]),
            float(ABSOLUTE_MAX_TRIAL_VALUE),
        )
        paired_choice = _rank(
            [
                product
                for product in products
                if product["category"] == pairing["suggested_category"]
                and float(product["price"]) <= pairing_cap
            ],
            categories,
        )
        if paired_choice:
            paired_choice["selection_mode"] = "curated_pairing"
            paired_choice["trial_value_cap"] = pairing_cap
            return paired_choice

    tier_cap = min(
        _tier_cap(cart_value, item_count),
        float(ABSOLUTE_MAX_TRIAL_VALUE),
    )
    fallback_choice = _rank(
        [
            product
            for product in products
            if float(product["price"]) <= tier_cap
        ],
        categories,
    )
    if fallback_choice:
        fallback_choice["selection_mode"] = (
            "tier_fallback_after_pairing"
            if pairing
            else "tier_affinity"
        )
        fallback_choice["trial_value_cap"] = tier_cap
    return fallback_choice
