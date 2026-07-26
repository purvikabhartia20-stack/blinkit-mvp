# RideAlong

RideAlong is a category-discovery feature for a Blinkit-style quick-commerce
checkout. For **frequent shoppers only**, it may offer exactly one small trial
product from a category the shopper has never bought — either when the cart is
slightly short of free delivery (**Gap-Fill**), or when the cart looks like a
larger stocking-up trip (**Stocking-Up**). If the shopper is already exploring a
new category on their own, RideAlong stays silent.

## Stack

- Python 3.11+ / Flask
- SQLite (local file)
- Vanilla HTML / CSS / JavaScript (no build step)
- Optional Groq chat API for trial copy, with a mandatory template fallback

## Install

```sh
cd ridealong
python3 -m venv ../.venv
source ../.venv/bin/activate   # Windows: ..\.venv\Scripts\activate
pip install -r requirements.txt
```

## Seed

```sh
python seed.py
```

Idempotent: running it again rebuilds a clean database.

## Run

```sh
python app.py
```

Open <http://127.0.0.1:5000>.

If port 5000 is busy, the process exits with a clear message (no stack trace).

### Optional Groq live messages

Create `ridealong/.env` (already gitignored):

```sh
GROQ_API_KEY=your_free_groq_key_here
```

Without a key or when the network/API fails, checkout still works and the UI
shows a deterministic template message. The side panel reports
`message_source` honestly (`groq_live` or a `template_fallback_*` tag).

## Demo tips

1. Use **User A — Frequent**.
2. Tap a preset (**Gap-Fill**, **Stocking-Up**, **Rule A**, **No trigger**).
3. Checkout and inspect the transparency panel.
4. Tap **Reset demo** between scenarios to clear the weekly offer cap and
   declines without wiping order history.

Users B and C are seeded as non-eligible shoppers so you can show the
frequent-user gate.

## Verify manually

```sh
python verify_logic.py
curl -i http://127.0.0.1:5000/health
curl -i http://127.0.0.1:5000/api/users
```

There is no automated unittest suite in this build (by design for the MVP).

## Trigger rules (summary)

1. Suppress single-item carts, pharmacy carts, weekly-cap hits, and
   non-frequent users.
2. **Rule A:** any never-bought category already in the cart → silent.
3. **Gap-Fill:** gap to ₹200 is between ₹10 and ₹50 → offer a product priced
   from the exact gap up to `max(gap × 1.15, ₹50)`.
4. Else **Stocking-Up:** ≥ 4 items → offer one never-bought-category product
   using curated pairings first, then average-price tier caps.

## What's real vs representative

| Real | Representative |
| --- | --- |
| Trigger and selection logic | Dark-store inventory is a static `in_stock` flag |
| Decline cooldown + weekly fire cap | Payment / checkout fulfilment is UI state only |
| Affinity ranking + curated pairings | Basket affinities are seeded scores, not live models |
| Groq call with constrained prompt + fallback | Live copy requires a free Groq key and network |

## Free deployment options

Push this folder to a free host that can run Flask + SQLite, for example:

- [Render](https://render.com/) free web service
- [Railway](https://railway.app/) free trial / hobby
- [PythonAnywhere](https://www.pythonanywhere.com/) free tier

No paid APIs or paid hosting are required. Persist or re-run `seed.py` on
deploy so the SQLite file exists.

## Project layout

```
ridealong/
  app.py              Flask UI + API
  config.py           All constants
  config_check.py     Startup config sanity
  db.py / seed.py     SQLite schema + seed
  env_loader.py       Loads local .env without extra deps
  logic/              Trigger, selection, messaging
  templates/ / static/
  verify_logic.py     Manual logic check script
```
