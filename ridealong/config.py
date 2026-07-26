"""Central configuration for RideAlong."""

# Cart value required to qualify for free delivery.
MIN_ORDER_VALUE = 200

# Smallest delivery-value gap eligible for Gap-Fill.
GAP_MIN = 10

# Largest delivery-value gap eligible for Gap-Fill.
GAP_MAX = 50

# Upper stretch above the gap for Gap-Fill product prices (15%).
GAP_PRICE_TOLERANCE = 0.15

# Gap-Fill product upper bound is max(gap × 1.15, this floor).
# ~25% of free-delivery minimum.
GAP_FILL_PRICE_UPPER_FLOOR = 50

# Absolute ceiling for every trial product.
ABSOLUTE_MAX_TRIAL_VALUE = 150

# Minimum cart size for the simplified Stocking-Up rule.
STOCKING_ITEM_COUNT_MIN = 4

# Frequent shopper: at least this many orders in the last 7 days…
FREQUENT_ORDERS_IN_7_DAYS = 2

# …OR at least this many orders in the last 28 days (≈ 2/week × 4 weeks).
FREQUENT_ORDERS_IN_28_DAYS = 8

# Lookback windows for the frequent-shopper gate.
FREQUENT_WINDOW_DAYS_SHORT = 7
FREQUENT_WINDOW_DAYS_LONG = 28

# Number of days before a declined product may be offered again.
DECLINE_COOLDOWN_DAYS = 60

# Maximum RideAlong offers shown per user in a seven-day window.
WEEKLY_FIRE_CAP = 1

# Stocking-Up cap for carts averaging below the low threshold.
TIER_LOW_CAP = 50

# Stocking-Up cap for carts in the middle price tier.
TIER_MID_CAP = 100

# Stocking-Up cap for carts above the high threshold.
TIER_HIGH_CAP = 150

# Boundary between low- and mid-priced carts.
TIER_LOW_THRESHOLD = 60

# Boundary between mid- and high-priced carts.
TIER_HIGH_THRESHOLD = 150

# Groq's OpenAI-compatible chat-completions endpoint.
GROQ_CHAT_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

# Free-tier-compatible Groq model used for constrained trial messages.
GROQ_MODEL = "llama-3.3-70b-versatile"

# Keep network failure from delaying checkout.
GROQ_TIMEOUT_SECONDS = 5

# Defensive display limit for model-generated text.
GROQ_MAX_MESSAGE_CHARS = 180
