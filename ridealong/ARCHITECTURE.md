# RideAlong architecture

## Request flow

```text
Cart UI (vanilla JS)
   │
   │  POST /api/evaluate
   ▼
app.py  (thin HTTP layer — no business rules)
   │
   ├─► logic.signal.evaluate_trigger
   │      hard suppressions → Rule A → Gap-Fill → Stocking-Up
   │
   ├─► logic.selection.select_product
   │      filters → curated pairing / tier cap → affinity rank
   │
   ├─► logic.messaging.generate_message
   │      Groq (constrained) or template fallback
   │
   └─► offer_log insert (weekly fire cap)
          │
          ▼
     JSON → trial card + transparency panel
```

## Modules

| Module | One-line role |
| --- | --- |
| `app.py` | Flask routes, request validation, JSON responses |
| `config.py` | Single source for all product/logic constants |
| `config_check.py` | Fail-fast sanity checks on startup |
| `db.py` | SQLite path, schema, connection helper |
| `seed.py` | Idempotent demo users, catalog, affinities, pairings |
| `env_loader.py` | Loads `.env` into `os.environ` without python-dotenv |
| `logic/signal.py` | Order history helpers + trigger evaluation |
| `logic/selection.py` | Trial-value caps + deterministic product pick |
| `logic/messaging.py` | Groq call with mandatory template fallback |
| `static/app.js` | Phone shopping UI driven only by real API results |
| `verify_logic.py` | Manual scenario walkthrough for core logic |

## API surface

- `GET /` — shopping UI
- `GET /health` — liveness
- `GET /api/users`, `/api/catalog`, `/api/user/<id>/history`
- `POST /api/evaluate` — trigger + select + message
- `POST /api/decline`, `/api/confirm`
- `POST /api/demo/reset` — clears offer/decline logs for demos only
