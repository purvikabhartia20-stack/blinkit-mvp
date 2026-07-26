"""RideAlong business-logic package."""

from logic.selection import compute_trial_value_cap, select_product
from logic.signal import (
    category_distribution,
    evaluate_trigger,
    get_order_history,
    is_frequent_shopper,
    personal_average_order_value,
)

__all__ = [
    "category_distribution",
    "compute_trial_value_cap",
    "evaluate_trigger",
    "get_order_history",
    "is_frequent_shopper",
    "personal_average_order_value",
    "select_product",
]
