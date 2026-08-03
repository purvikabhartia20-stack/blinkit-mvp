"""Flask entry point and thin HTTP API for RideAlong."""

from __future__ import annotations

from datetime import datetime, timezone
import socket
import sys

from flask import Flask, jsonify, render_template, request

from db import get_connection
from env_loader import load_dotenv
from config_check import validate_config
from logic import (
    category_distribution,
    evaluate_trigger,
    get_order_history,
    personal_average_order_value,
    select_product,
)
from logic.messaging import generate_message

load_dotenv()
validate_config()

HOST = "127.0.0.1"
PORT = 5000

app = Flask(__name__)


@app.get("/")
def index():
    """Render the application shell."""
    return render_template("index.html")


@app.get("/health")
def health():
    """Report whether the service is running."""
    return jsonify(status="ok")


def _error(message: str, status: int):
    """Return a JSON error payload with the given HTTP status."""
    return jsonify(error=message), status


def _require_json() -> tuple[dict | None, tuple | None]:
    """Parse a JSON body or return a 400 response."""
    if not request.is_json:
        return None, _error("Request body must be JSON", 400)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None, _error("Malformed JSON body", 400)
    return payload, None


def _require_fields(payload: dict, fields: list[str]) -> tuple | None:
    """Return a 400 response naming the first missing required field."""
    for field in fields:
        if field not in payload or payload[field] is None:
            return _error(f"Missing required field: {field}", 400)
    return None


def _user_exists(user_id: int) -> bool:
    """Return whether the user_id is present in the database."""
    with get_connection() as connection:
        row = connection.execute(
            "SELECT 1 FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return row is not None


def _product_exists(product_id: int) -> bool:
    """Return whether the product_id is present in the database."""
    with get_connection() as connection:
        row = connection.execute(
            "SELECT 1 FROM products WHERE product_id = ?",
            (product_id,),
        ).fetchone()
    return row is not None


def _serialize_product(product: dict) -> dict:
    """Expose the product fields the UI and side panel need."""
    return {
        "product_id": product["product_id"],
        "name": product["name"],
        "unit": product["unit"],
        "category": product["category"],
        "price": product["price"],
        "in_stock": bool(product["in_stock"]),
        "safe_for_auto_trial": bool(product["safe_for_auto_trial"]),
        "color_hex": product["color_hex"],
        "image": product["image"],
        "affinity_score": product.get("affinity_score"),
        "selection_mode": product.get("selection_mode"),
        "trial_value_cap": product.get("trial_value_cap"),
    }


def _log_offer_shown(user_id: int, product_id: int) -> int:
    """Record that a trial was shown (counts toward the weekly fire cap)."""
    shown_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO offer_log (user_id, shown_at, product_id, kept_trial)
            VALUES (?, ?, ?, NULL)
            """,
            (user_id, shown_at, product_id),
        )
        return int(cursor.lastrowid)


@app.get("/api/users")
def api_users():
    """List demo users."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT user_id, name, dark_store_id
            FROM users
            ORDER BY user_id
            """
        ).fetchall()
    return jsonify(users=[dict(row) for row in rows])


@app.get("/api/catalog")
def api_catalog():
    """List the full product catalog."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT product_id, name, unit, category, price, in_stock,
                   safe_for_auto_trial, color_hex, image
            FROM products
            ORDER BY category, product_id
            """
        ).fetchall()
    products = []
    for row in rows:
        item = dict(row)
        item["in_stock"] = bool(item["in_stock"])
        item["safe_for_auto_trial"] = bool(item["safe_for_auto_trial"])
        products.append(item)
    return jsonify(products=products)


@app.post("/api/demo/reset")
def api_demo_reset():
    """Clear demo interaction state without changing users, catalog, or history."""
    with get_connection() as connection:
        connection.execute("DELETE FROM declined_offers")
        connection.execute("DELETE FROM offer_log")
    return jsonify(
        ok=True,
        cleared=["declined_offers", "offer_log"],
    )


@app.get("/api/user/<int:user_id>/history")
def api_user_history(user_id: int):
    """Return order count, personal average, and category distribution."""
    if not _user_exists(user_id):
        return _error(f"Unknown user_id: {user_id}", 404)

    history = get_order_history(user_id)
    average = personal_average_order_value(history)
    return jsonify(
        user_id=user_id,
        order_count=len(history),
        personal_average_order_value=(
            None if average is None else round(average, 2)
        ),
        category_distribution=category_distribution(history),
    )


@app.post("/api/evaluate")
def api_evaluate():
    """Run trigger + selection and return the structured RideAlong result."""
    payload, error = _require_json()
    if error:
        return error
    missing = _require_fields(
        payload,
        ["user_id", "cart_value", "item_count", "cart_categories"],
    )
    if missing:
        return missing

    try:
        user_id = int(payload["user_id"])
        cart_value = float(payload["cart_value"])
        item_count = int(payload["item_count"])
    except (TypeError, ValueError):
        return _error(
            "user_id, cart_value, and item_count must be numeric",
            400,
        )

    cart_categories = payload["cart_categories"]
    if not isinstance(cart_categories, list) or not all(
        isinstance(category, str) for category in cart_categories
    ):
        return _error("cart_categories must be a list of strings", 400)

    if not _user_exists(user_id):
        return _error(f"Unknown user_id: {user_id}", 404)

    trigger = evaluate_trigger(
        user_id,
        cart_value,
        item_count,
        cart_categories,
    )
    response = {
        "triggered": trigger["triggered"],
        "path": trigger["path"],
        "detail": trigger["detail"],
        "product": None,
        "affinity_score": None,
        "message": None,
        "message_source": None,
        "offer_id": None,
    }

    if not trigger["triggered"]:
        return jsonify(response)

    product = select_product(
        user_id,
        cart_categories,
        trigger["path"],
        trigger["detail"],
    )
    if product is None:
        response["triggered"] = False
        response["path"] = None
        response["detail"] = {
            **trigger["detail"],
            "reason": "no_eligible_product",
            "trigger_reason": trigger["detail"].get("reason"),
        }
        return jsonify(response)

    message, message_source = generate_message(
        product,
        trigger["path"],
        trigger["detail"],
    )
    offer_id = _log_offer_shown(user_id, int(product["product_id"]))
    response.update(
        product=_serialize_product(product),
        affinity_score=product.get("affinity_score"),
        message=message,
        message_source=message_source,
        offer_id=offer_id,
    )
    return jsonify(response)


@app.post("/api/decline")
def api_decline():
    """Record that the user declined a trial product."""
    payload, error = _require_json()
    if error:
        return error
    missing = _require_fields(payload, ["user_id", "product_id"])
    if missing:
        return missing

    try:
        user_id = int(payload["user_id"])
        product_id = int(payload["product_id"])
    except (TypeError, ValueError):
        return _error("user_id and product_id must be integers", 400)

    if not _user_exists(user_id):
        return _error(f"Unknown user_id: {user_id}", 404)
    if not _product_exists(product_id):
        return _error(f"Unknown product_id: {product_id}", 404)

    declined_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO declined_offers (user_id, product_id, declined_at)
            VALUES (?, ?, ?)
            """,
            (user_id, product_id, declined_at),
        )
        connection.execute(
            """
            UPDATE offer_log
            SET kept_trial = 0, product_id = ?
            WHERE offer_id = (
                SELECT offer_id FROM offer_log
                WHERE user_id = ?
                ORDER BY shown_at DESC, offer_id DESC
                LIMIT 1
            )
            """,
            (product_id, user_id),
        )
    return jsonify(ok=True, user_id=user_id, product_id=product_id)


@app.post("/api/confirm")
def api_confirm():
    """Confirm checkout and record whether the trial was kept."""
    payload, error = _require_json()
    if error:
        return error
    missing = _require_fields(payload, ["user_id", "kept_trial"])
    if missing:
        return missing

    try:
        user_id = int(payload["user_id"])
    except (TypeError, ValueError):
        return _error("user_id must be an integer", 400)

    kept_trial = payload["kept_trial"]
    if not isinstance(kept_trial, bool):
        return _error("kept_trial must be a boolean", 400)

    product_id = payload.get("product_id")
    if kept_trial:
        if product_id is None:
            return _error("product_id is required when kept_trial is true", 400)
        try:
            product_id = int(product_id)
        except (TypeError, ValueError):
            return _error("product_id must be an integer", 400)
        if not _product_exists(product_id):
            return _error(f"Unknown product_id: {product_id}", 404)

    if not _user_exists(user_id):
        return _error(f"Unknown user_id: {user_id}", 404)

    with get_connection() as connection:
        latest = connection.execute(
            """
            SELECT offer_id FROM offer_log
            WHERE user_id = ?
            ORDER BY shown_at DESC, offer_id DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        if latest is None:
            return _error("No offer has been shown for this user", 404)

        connection.execute(
            """
            UPDATE offer_log
            SET kept_trial = ?, product_id = COALESCE(?, product_id)
            WHERE offer_id = ?
            """,
            (
                1 if kept_trial else 0,
                product_id,
                latest["offer_id"],
            ),
        )

    return jsonify(
        ok=True,
        user_id=user_id,
        kept_trial=kept_trial,
        product_id=product_id,
        offer_id=latest["offer_id"],
    )


def port_is_available(host: str, port: int) -> bool:
    """Return whether a local TCP port can be bound."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, port))
        except OSError:
            return False
    return True


if __name__ == "__main__":
    if not port_is_available(HOST, PORT):
        print(
            f"RideAlong could not start: port {PORT} is already in use. "
            "Stop the other process and try again.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    app.run(host=HOST, port=PORT, debug=False, use_reloader=False)
