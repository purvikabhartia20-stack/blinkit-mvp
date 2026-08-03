"""SQLite connection helpers and schema for RideAlong."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DATABASE_PATH = Path(__file__).resolve().parent / "ridealong.db"

SCHEMA = """
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    dark_store_id TEXT NOT NULL
);

CREATE TABLE products (
    product_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    unit TEXT NOT NULL,
    category TEXT NOT NULL,
    price REAL NOT NULL CHECK (price >= 0),
    in_stock INTEGER NOT NULL CHECK (in_stock IN (0, 1)),
    safe_for_auto_trial INTEGER NOT NULL
        CHECK (safe_for_auto_trial IN (0, 1)),
    color_hex TEXT NOT NULL,
    image TEXT NOT NULL
);

CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    placed_at TEXT NOT NULL,
    total_value REAL NOT NULL CHECK (total_value >= 0),
    item_count INTEGER NOT NULL CHECK (item_count > 0),
    categories TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE basket_affinity (
    from_category TEXT NOT NULL,
    to_category TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    PRIMARY KEY (from_category, to_category)
);

CREATE TABLE category_pairings (
    cart_category TEXT PRIMARY KEY,
    suggested_category TEXT NOT NULL,
    value_ceiling REAL NOT NULL CHECK (value_ceiling >= 0)
);

CREATE TABLE declined_offers (
    user_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    declined_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE TABLE offer_log (
    offer_id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    shown_at TEXT NOT NULL,
    product_id INTEGER,
    kept_trial INTEGER CHECK (kept_trial IN (0, 1)),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
"""

TABLES_IN_DROP_ORDER = (
    "offer_log",
    "declined_offers",
    "category_pairings",
    "basket_affinity",
    "orders",
    "products",
    "users",
)


def get_connection() -> sqlite3.Connection:
    """Open a row-addressable connection to the local database."""
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def rebuild_schema(connection: sqlite3.Connection) -> None:
    """Drop existing RideAlong tables and recreate the complete schema."""
    for table in TABLES_IN_DROP_ORDER:
        connection.execute(f"DROP TABLE IF EXISTS {table}")
    connection.executescript(SCHEMA)


def database_needs_seed() -> bool:
    """True when the DB is missing, empty, or missing required product columns."""
    if not DATABASE_PATH.exists():
        return True
    try:
        with get_connection() as connection:
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(products)")
            }
            if not {"unit", "image"}.issubset(columns):
                return True
            count = connection.execute(
                "SELECT COUNT(*) AS n FROM products"
            ).fetchone()["n"]
            return count == 0
    except sqlite3.Error:
        return True


def ensure_database() -> None:
    """Seed the catalog on first boot / after a schema change (needed on Render)."""
    if not database_needs_seed():
        return
    from seed import seed

    seed()
