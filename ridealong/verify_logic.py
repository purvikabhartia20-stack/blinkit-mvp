"""Manual, deterministic Phase 3 verification (not an automated test suite)."""

from datetime import datetime, timezone

from db import get_connection
from logic import compute_trial_value_cap, evaluate_trigger, select_product
from seed import seed


def show(label, value):
    """Print one human-readable verification result."""
    print(f"{label}: {value}")


def main():
    """Exercise required trigger and selection scenarios from fresh seed data."""
    seed()

    gap = evaluate_trigger(1, 157, 5, ["grocery", "snacks"])
    show("Gap ₹43", (gap["triggered"], gap["path"], gap["detail"]["gap"]))
    gap_product = select_product(
        1, ["grocery", "snacks"], gap["path"], gap["detail"]
    )
    show("Gap product", (gap_product["name"], gap_product["price"]))
    show(
        "Gap ₹10 price band",
        (
            10,
            max(10 * 1.15, 50),
        ),
    )
    show(
        "Gap ₹5",
        evaluate_trigger(1, 195, 3, ["grocery"])["detail"]["reason"],
    )
    show(
        "Gap ₹80",
        evaluate_trigger(1, 120, 3, ["grocery"])["detail"]["reason"],
    )
    show(
        "Stocking-Up ≥4",
        evaluate_trigger(1, 300, 4, ["grocery", "personal_care"])["path"],
    )
    show(
        "Stocking-Up <4",
        evaluate_trigger(1, 300, 3, ["grocery"])["detail"]["reason"],
    )
    show(
        "Rule A",
        evaluate_trigger(1, 180, 4, ["grocery", "beauty"])["detail"]["reason"],
    )
    show(
        "New user (not frequent)",
        evaluate_trigger(3, 300, 4, ["grocery"])["detail"]["reason"],
    )
    show(
        "Occasional user (not frequent)",
        evaluate_trigger(2, 180, 4, ["grocery"])["detail"]["reason"],
    )
    show(
        "Single item",
        evaluate_trigger(1, 180, 1, ["grocery"])["detail"]["reason"],
    )
    show(
        "Pharmacy",
        evaluate_trigger(1, 180, 4, ["grocery", "pharmacy"])["detail"][
            "reason"
        ],
    )

    with get_connection() as connection:
        connection.execute(
            "INSERT INTO offer_log (user_id, shown_at) VALUES (?, ?)",
            (1, datetime.now(timezone.utc).isoformat()),
        )
    show(
        "Weekly cap",
        evaluate_trigger(1, 180, 4, ["grocery"])["detail"]["reason"],
    )
    with get_connection() as connection:
        connection.execute("DELETE FROM offer_log WHERE user_id = 1")

    baby = select_product(
        1,
        ["baby_care"],
        "stocking_up",
        {"cart_value": 679, "item_count": 5},
    )
    show(
        "Baby pairing",
        (baby["name"], baby["price"], baby["trial_value_cap"]),
    )

    show(
        "Tier boundaries",
        [
            compute_trial_value_cap(value, 1, ["unpaired"])
            for value in (59, 60, 150, 151)
        ],
    )
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE category_pairings SET value_ceiling = 999
            WHERE cart_category = 'baby_care'
            """
        )
    show(
        "Absolute cap",
        compute_trial_value_cap(679, 5, ["baby_care"]),
    )

    first = select_product(
        1,
        ["grocery", "snacks"],
        "gap_fill",
        {"gap": 43},
    )
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO declined_offers (user_id, product_id, declined_at)
            VALUES (?, ?, ?)
            """,
            (1, first["product_id"], datetime.now(timezone.utc).isoformat()),
        )
    second = select_product(
        1,
        ["grocery", "snacks"],
        "gap_fill",
        {"gap": 43},
    )
    show("Decline rotation", (first["name"], second["name"]))

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE products SET in_stock = 0
            WHERE category = 'home_fragrance'
            """
        )
    staples = select_product(
        1,
        ["grocery"],
        "stocking_up",
        {"cart_value": 92, "item_count": 3},
    )
    show(
        "Staples pairing fallback",
        (
            staples["name"],
            staples["price"],
            staples["trial_value_cap"],
            staples["selection_mode"],
        ),
    )

    with get_connection() as connection:
        connection.execute("UPDATE products SET in_stock = 0")
    show(
        "No eligible product",
        select_product(
            1,
            ["grocery"],
            "stocking_up",
            {"cart_value": 300, "item_count": 4},
        ),
    )


if __name__ == "__main__":
    main()
