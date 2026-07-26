"""Startup sanity checks for RideAlong configuration."""

from __future__ import annotations

import config


def validate_config() -> None:
    """Fail fast if any active constant is missing or internally inconsistent."""
    required = {
        "MIN_ORDER_VALUE": config.MIN_ORDER_VALUE,
        "GAP_MIN": config.GAP_MIN,
        "GAP_MAX": config.GAP_MAX,
        "GAP_PRICE_TOLERANCE": config.GAP_PRICE_TOLERANCE,
        "GAP_FILL_PRICE_UPPER_FLOOR": config.GAP_FILL_PRICE_UPPER_FLOOR,
        "ABSOLUTE_MAX_TRIAL_VALUE": config.ABSOLUTE_MAX_TRIAL_VALUE,
        "STOCKING_ITEM_COUNT_MIN": config.STOCKING_ITEM_COUNT_MIN,
        "FREQUENT_ORDERS_IN_7_DAYS": config.FREQUENT_ORDERS_IN_7_DAYS,
        "FREQUENT_ORDERS_IN_28_DAYS": config.FREQUENT_ORDERS_IN_28_DAYS,
        "FREQUENT_WINDOW_DAYS_SHORT": config.FREQUENT_WINDOW_DAYS_SHORT,
        "FREQUENT_WINDOW_DAYS_LONG": config.FREQUENT_WINDOW_DAYS_LONG,
        "DECLINE_COOLDOWN_DAYS": config.DECLINE_COOLDOWN_DAYS,
        "WEEKLY_FIRE_CAP": config.WEEKLY_FIRE_CAP,
        "TIER_LOW_CAP": config.TIER_LOW_CAP,
        "TIER_MID_CAP": config.TIER_MID_CAP,
        "TIER_HIGH_CAP": config.TIER_HIGH_CAP,
        "TIER_LOW_THRESHOLD": config.TIER_LOW_THRESHOLD,
        "TIER_HIGH_THRESHOLD": config.TIER_HIGH_THRESHOLD,
        "GROQ_CHAT_ENDPOINT": config.GROQ_CHAT_ENDPOINT,
        "GROQ_MODEL": config.GROQ_MODEL,
        "GROQ_TIMEOUT_SECONDS": config.GROQ_TIMEOUT_SECONDS,
        "GROQ_MAX_MESSAGE_CHARS": config.GROQ_MAX_MESSAGE_CHARS,
    }

    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise SystemExit(
            "RideAlong config error: missing constants: "
            + ", ".join(missing)
        )

    errors: list[str] = []

    if config.GAP_MIN > config.GAP_MAX:
        errors.append(
            f"GAP_MIN ({config.GAP_MIN}) must be <= GAP_MAX ({config.GAP_MAX})"
        )
    if config.GAP_MIN < 0 or config.GAP_MAX < 0:
        errors.append("GAP_MIN and GAP_MAX must be non-negative")
    if not (0 <= config.GAP_PRICE_TOLERANCE <= 1):
        errors.append("GAP_PRICE_TOLERANCE must be between 0 and 1")
    if config.MIN_ORDER_VALUE <= 0:
        errors.append("MIN_ORDER_VALUE must be positive")
    if config.STOCKING_ITEM_COUNT_MIN < 2:
        errors.append("STOCKING_ITEM_COUNT_MIN must be at least 2")
    if config.FREQUENT_ORDERS_IN_7_DAYS < 1:
        errors.append("FREQUENT_ORDERS_IN_7_DAYS must be at least 1")
    if config.FREQUENT_ORDERS_IN_28_DAYS < config.FREQUENT_ORDERS_IN_7_DAYS:
        errors.append(
            "FREQUENT_ORDERS_IN_28_DAYS must be >= FREQUENT_ORDERS_IN_7_DAYS"
        )
    if config.FREQUENT_WINDOW_DAYS_SHORT >= config.FREQUENT_WINDOW_DAYS_LONG:
        errors.append(
            "FREQUENT_WINDOW_DAYS_SHORT must be < FREQUENT_WINDOW_DAYS_LONG"
        )
    if config.TIER_LOW_THRESHOLD >= config.TIER_HIGH_THRESHOLD:
        errors.append(
            "TIER_LOW_THRESHOLD must be < TIER_HIGH_THRESHOLD"
        )
    if not (
        config.TIER_LOW_CAP
        <= config.TIER_MID_CAP
        <= config.TIER_HIGH_CAP
        <= config.ABSOLUTE_MAX_TRIAL_VALUE
    ):
        errors.append(
            "Expected TIER_LOW_CAP <= TIER_MID_CAP <= TIER_HIGH_CAP "
            "<= ABSOLUTE_MAX_TRIAL_VALUE"
        )
    if config.WEEKLY_FIRE_CAP < 1:
        errors.append("WEEKLY_FIRE_CAP must be at least 1")
    if config.GROQ_TIMEOUT_SECONDS <= 0:
        errors.append("GROQ_TIMEOUT_SECONDS must be positive")
    if config.GROQ_MAX_MESSAGE_CHARS < 40:
        errors.append("GROQ_MAX_MESSAGE_CHARS must be at least 40")
    if not str(config.GROQ_CHAT_ENDPOINT).startswith("https://"):
        errors.append("GROQ_CHAT_ENDPOINT must be an https URL")
    if not str(config.GROQ_MODEL).strip():
        errors.append("GROQ_MODEL must be a non-empty string")

    if errors:
        raise SystemExit(
            "RideAlong config error:\n- " + "\n- ".join(errors)
        )
