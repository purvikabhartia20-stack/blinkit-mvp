"""Checkout trigger evaluation for RideAlong."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Any

from config import (
    FREQUENT_ORDERS_IN_7_DAYS,
    FREQUENT_ORDERS_IN_28_DAYS,
    FREQUENT_WINDOW_DAYS_LONG,
    FREQUENT_WINDOW_DAYS_SHORT,
    GAP_MAX,
    GAP_MIN,
    MIN_ORDER_VALUE,
    STOCKING_ITEM_COUNT_MIN,
    WEEKLY_FIRE_CAP,
)
from db import get_connection


def get_order_history(user_id: int) -> list[dict[str, Any]]:
    """Return a user's orders with decoded category lists."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT order_id, user_id, placed_at, total_value, item_count, categories
            FROM orders
            WHERE user_id = ?
            ORDER BY placed_at DESC
            """,
            (user_id,),
        ).fetchall()

    history = []
    for row in rows:
        order = dict(row)
        order["categories"] = json.loads(order["categories"])
        history.append(order)
    return history


def personal_average_order_value(
    history: list[dict[str, Any]],
) -> float | None:
    """Return mean historical order value, or None for no history."""
    if not history:
        return None
    return sum(float(order["total_value"]) for order in history) / len(history)


def category_distribution(
    history: list[dict[str, Any]],
) -> dict[str, float]:
    """Return the fraction of orders containing each category."""
    if not history:
        return {}

    counts: dict[str, int] = {}
    for order in history:
        for category in set(order["categories"]):
            counts[category] = counts.get(category, 0) + 1
    return {
        category: count / len(history)
        for category, count in sorted(counts.items())
    }


def _parse_timestamp(value: str) -> datetime:
    """Parse an ISO timestamp stored in SQLite into an aware UTC datetime."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def is_frequent_shopper(
    history: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """
    RideAlong is for frequent shoppers only.

    Qualifies if either:
    - ≥ 2 orders in the last 7 days, or
    - ≥ 8 orders in the last 28 days (average ≥ 2/week over 4 weeks).
    """
    clock = now or datetime.now(timezone.utc)
    short_cutoff = clock - timedelta(days=FREQUENT_WINDOW_DAYS_SHORT)
    long_cutoff = clock - timedelta(days=FREQUENT_WINDOW_DAYS_LONG)

    orders_last_7 = 0
    orders_last_28 = 0
    for order in history:
        placed_at = _parse_timestamp(order["placed_at"])
        if placed_at >= long_cutoff:
            orders_last_28 += 1
        if placed_at >= short_cutoff:
            orders_last_7 += 1

    qualifies = (
        orders_last_7 >= FREQUENT_ORDERS_IN_7_DAYS
        or orders_last_28 >= FREQUENT_ORDERS_IN_28_DAYS
    )
    return {
        "qualifies": qualifies,
        "orders_last_7_days": orders_last_7,
        "orders_last_28_days": orders_last_28,
        "required_orders_last_7_days": FREQUENT_ORDERS_IN_7_DAYS,
        "required_orders_last_28_days": FREQUENT_ORDERS_IN_28_DAYS,
    }


def _result(
    triggered: bool,
    *,
    path: str | None = None,
    reason: str,
    **detail: Any,
) -> dict[str, Any]:
    """Build a consistent trigger response."""
    return {
        "triggered": triggered,
        "path": path,
        "detail": {"reason": reason, **detail},
    }


def evaluate_trigger(
    user_id: int,
    cart_value: float,
    item_count: int,
    cart_categories: list[str] | set[str],
) -> dict[str, Any]:
    """Evaluate hard suppressions, Gap-Fill, then simplified Stocking-Up."""
    categories = set(cart_categories)
    history = get_order_history(user_id)
    history_count = len(history)

    if item_count <= 1:
        return _result(False, reason="single_item_cart", item_count=item_count)

    if "pharmacy" in categories:
        return _result(
            False,
            reason="suppressed_category",
            suppressed_category="pharmacy",
        )

    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    with get_connection() as connection:
        recent_offer_count = connection.execute(
            """
            SELECT COUNT(*) FROM offer_log
            WHERE user_id = ? AND shown_at >= ?
            """,
            (user_id, cutoff),
        ).fetchone()[0]
    if recent_offer_count >= WEEKLY_FIRE_CAP:
        return _result(
            False,
            reason="weekly_fire_cap",
            recent_offer_count=recent_offer_count,
        )

    frequency = is_frequent_shopper(history)
    if not frequency["qualifies"]:
        return _result(
            False,
            reason="not_frequent_user",
            order_count=history_count,
            **frequency,
        )

    purchased_categories = {
        category
        for order in history
        for category in order["categories"]
    }
    new_categories_in_cart = sorted(categories - purchased_categories)
    if new_categories_in_cart:
        return _result(
            False,
            reason="already_exploring",
            new_categories_in_cart=new_categories_in_cart,
        )

    gap = MIN_ORDER_VALUE - float(cart_value)
    common = {
        "cart_value": float(cart_value),
        "item_count": item_count,
        "cart_categories": sorted(categories),
        "order_count": history_count,
        "orders_last_7_days": frequency["orders_last_7_days"],
        "orders_last_28_days": frequency["orders_last_28_days"],
    }
    if GAP_MIN <= gap <= GAP_MAX:
        return _result(
            True,
            path="gap_fill",
            reason="gap_fill_eligible",
            gap=gap,
            **common,
        )

    if item_count >= STOCKING_ITEM_COUNT_MIN:
        return _result(
            True,
            path="stocking_up",
            reason="stocking_up_eligible",
            minimum_item_count=STOCKING_ITEM_COUNT_MIN,
            **common,
        )

    return _result(
        False,
        reason="no_trigger_matched",
        gap=gap,
        minimum_item_count=STOCKING_ITEM_COUNT_MIN,
        **common,
    )
