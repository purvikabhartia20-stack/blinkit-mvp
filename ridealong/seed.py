"""Rebuild and seed the local RideAlong database."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

from db import get_connection, rebuild_schema


USERS = (
    (1, "User A — Frequent (2–3×/week)", "BLR-HSR-01"),
    (2, "User B — Occasional (not eligible)", "BLR-HSR-01"),
    (3, "User C — New (not eligible)", "BLR-HSR-02"),
)

# (product_id, name, unit, category, price, in_stock,
#  safe_for_auto_trial, color_hex, image)
# color_hex stays as the placeholder tint shown if an image fails to load.
PRODUCTS = (
    (1, "Fresh Banana Robusta", "500 g",
     "grocery", 20, 1, 1, "#F4D35E", "banana.jpg"),
    (2, "Amul Taaza Toned Milk", "500 ml",
     "grocery", 32, 1, 1, "#DCEEFF", "milk.jpg"),
    (3, "Britannia Whole Wheat Brown Bread", "400 g",
     "grocery", 40, 1, 1, "#D9A066", "bread.jpg"),
    (4, "Fortune Rozana Basmati Rice", "1 kg",
     "grocery", 72, 1, 1, "#F5F1E8", "rice.jpg"),
    (5, "Aashirvaad Shudh Chakki Atta", "1 kg",
     "grocery", 58, 1, 1, "#D8B26E", "atta.jpg"),
    (6, "Fortune Sunlite Refined Sunflower Oil", "1 L",
     "grocery", 145, 1, 0, "#F0C75E", "oil.jpg"),
    (7, "Eggoz Protein Rich Brown Eggs", "6 pieces",
     "grocery", 54, 1, 0, "#EEE4CF", "eggs.jpg"),
    (8, "Lay's India's Magic Masala Chips", "52 g",
     "snacks", 20, 1, 1, "#FFCF33", "chips.jpg"),
    (9, "Haldiram's Aloo Bhujia", "200 g",
     "snacks", 45, 1, 1, "#F3A833", "bhujia.jpg"),
    (10, "Sunfeast Dark Fantasy Choco Fills", "75 g",
     "snacks", 35, 1, 1, "#8A5A44", "cookies.jpg"),
    (11, "Dove Intense Repair Shampoo", "180 ml",
     "personal_care", 129, 1, 0, "#8EC5FC", "shampoo.jpg"),
    (12, "Dettol Original Bathing Soap", "125 g",
     "personal_care", 38, 1, 1, "#A8D5BA", "soap.jpg"),
    (13, "Colgate Strong Teeth Toothpaste", "150 g",
     "personal_care", 89, 1, 0, "#E96B6B", "toothpaste.jpg"),
    (14, "Mamaearth Vitamin C Face Serum", "10 ml",
     "beauty", 149, 1, 1, "#E8B4CB", "serum.jpg"),
    (15, "Nivea Strawberry Shine Lip Balm", "4.8 g",
     "beauty", 49, 1, 1, "#D96C8A", "lipbalm.jpg"),
    (16, "Iris Vanilla Scented Votive Candle", "45 g",
     "home_fragrance", 42, 1, 1, "#FFD166", "candle.jpg"),
    (17, "Godrej Aer Pocket Air Freshener", "10 g",
     "home_fragrance", 39, 1, 1, "#86D4C7", "freshener.jpg"),
    (18, "Post-it Sticky Notes Cube", "100 sheets",
     "stationery", 38, 1, 1, "#FFE66D", "stickynotes.jpg"),
    (19, "Scotch-Brite Dishwash Scrub Pad", "2 pieces",
     "household", 25, 1, 1, "#5FCF80", "scrubpad.jpg"),
    (20, "Gala Microfibre Cleaning Cloth", "1 piece",
     "household", 45, 0, 1, "#62A8E5", "microfibre.jpg"),
    (21, "boAt Type-C Fast Charging Cable", "1 m",
     "electronics_accessories", 120, 1, 1, "#59636E", "usbcable.jpg"),
    (22, "Dolo 650 Paracetamol Tablets", "15 tablets",
     "pharmacy", 30, 1, 0, "#D7E8F7", "tablets.jpg"),
    (23, "Pampers All Round Protection Pants Medium", "26 pants",
     "baby_care", 399, 1, 0, "#B7D7F0", "diapers.jpg"),
    (24, "Nestle Lactogen 1 Infant Formula", "200 g",
     "baby_care", 280, 1, 0, "#F0E2B6", "formula.jpg"),
    (25, "Mee Mee Soft Plush Rattle Toy", "1 piece",
     "baby_toys", 149, 1, 1, "#F6A6C1", "rattle.jpg"),
    (26, "Lipton Lemon Iced Tea Can", "300 ml",
     "beverages", 45, 1, 1, "#C4E17F", "icetea.jpg"),
    (27, "Kinley Club Soda", "750 ml",
     "beverages", 30, 0, 1, "#A7D8F0", "soda.jpg"),
)

BASKET_AFFINITIES = (
    ("baby_care", "baby_toys", 0.98),
    ("personal_care", "beauty", 0.91),
    ("grocery", "home_fragrance", 0.76),
    ("grocery", "household", 0.72),
    ("grocery", "stationery", 0.41),
    ("snacks", "beverages", 0.89),
    ("snacks", "home_fragrance", 0.38),
    ("personal_care", "home_fragrance", 0.67),
    ("grocery", "beauty", 0.34),
    ("personal_care", "electronics_accessories", 0.25),
)

CATEGORY_PAIRINGS = (
    ("baby_care", "baby_toys", 150),
    ("personal_care", "beauty", 100),
    ("grocery", "home_fragrance", 80),
    ("snacks", "beverages", 50),
)

USER_A_VALUES = (
    238,
    264,
    247,
    255,
    229,
    271,
    249,
    258,
    242,
    267,
    236,
    253,
    261,
    244,
    276,
    231,
    252,
    259,
    246,
    268,
    239,
    257,
    243,
    262,
)

USER_B_VALUES = (132, 148, 165, 141, 159)


def iso_days_ago(days: int, now: datetime) -> str:
    """Return a sortable UTC timestamp relative to one seed-run clock."""
    value = now - timedelta(days=days)
    return value.replace(microsecond=0).isoformat()


ORDER_PROFILES = (
    {
        "user_id": 1,
        "totals": USER_A_VALUES,
        "category_cycle": (
            ["grocery"],
            ["grocery", "snacks"],
            ["grocery", "personal_care"],
            ["grocery", "snacks", "personal_care"],
        ),
        "first_order_days_ago": 1,
        "days_between_orders": 2,
        "base_item_count": 3,
        "item_count_cycle": 4,
    },
    {
        "user_id": 2,
        "totals": USER_B_VALUES,
        "category_cycle": (
            ["grocery"],
            ["grocery", "snacks"],
            ["grocery", "personal_care"],
            ["grocery", "household"],
            ["grocery", "snacks", "household"],
        ),
        "first_order_days_ago": 8,
        "days_between_orders": 14,
        "base_item_count": 2,
        "item_count_cycle": 3,
    },
)


def build_orders(now: datetime | None = None) -> list[tuple]:
    """Build all historical orders from the two shopper profiles."""
    seed_time = now or datetime.now(timezone.utc)
    orders = []

    for profile in ORDER_PROFILES:
        for index, total in enumerate(profile["totals"]):
            categories = profile["category_cycle"][
                index % len(profile["category_cycle"])
            ]
            days_ago = (
                profile["first_order_days_ago"]
                + index * profile["days_between_orders"]
            )
            orders.append(
                (
                    len(orders) + 1,
                    profile["user_id"],
                    iso_days_ago(days_ago, seed_time),
                    total,
                    profile["base_item_count"]
                    + index % profile["item_count_cycle"],
                    json.dumps(categories),
                )
            )

    return orders


def seed() -> None:
    """Drop, rebuild, and seed every RideAlong table."""
    with get_connection() as connection:
        rebuild_schema(connection)
        connection.executemany(
            "INSERT INTO users (user_id, name, dark_store_id) VALUES (?, ?, ?)",
            USERS,
        )
        connection.executemany(
            """
            INSERT INTO products (
                product_id, name, unit, category, price, in_stock,
                safe_for_auto_trial, color_hex, image
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            PRODUCTS,
        )
        connection.executemany(
            """
            INSERT INTO orders (
                order_id, user_id, placed_at, total_value, item_count, categories
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            build_orders(),
        )
        connection.executemany(
            """
            INSERT INTO basket_affinity (
                from_category, to_category, confidence
            ) VALUES (?, ?, ?)
            """,
            BASKET_AFFINITIES,
        )
        connection.executemany(
            """
            INSERT INTO category_pairings (
                cart_category, suggested_category, value_ceiling
            ) VALUES (?, ?, ?)
            """,
            CATEGORY_PAIRINGS,
        )

    print("RideAlong database rebuilt and seeded successfully.")


if __name__ == "__main__":
    seed()
