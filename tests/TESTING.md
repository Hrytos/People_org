# Testing Guide

Run the full test suite before deploying or after changes.

## Quick Run

```bash
poetry run pytest tests/ -v --tb=short
```

## What’s Covered

| Area | Tests | Notes |
|------|--------|------|
| **Config** | `test_config.py` | `validate_config()`, `get_webhook_url()`, defaults (e.g. `WEBHOOK_PORT=8000`) |
| **Mappers** | `test_mappers.py` | `CompanyMapper`, `PeopleMapper`, `EnrichmentMapper` (role value, map_to_accounts_contacts) |
| **Rate limit** | `test_rate_limit.py` | Token bucket acquire/reset, singleton |
| **Supabase client** | `test_supabase_client.py` | `_ensure_metadata_dict`, `_contact_to_row` (mocked, no live DB) |
| **Webhook server** | `test_webhook_server.py` | FastAPI `POST /webhook`, `GET /health`, `GET /`, idempotency |
| **Services** | `test_services.py` | Enrichment mapper output; PeopleSearchService with mocked FullEnrich |

No live FullEnrich or Supabase connections are required for the suite.

## Commands

```bash
# All tests, verbose
poetry run pytest tests/ -v

# With coverage
poetry run pytest tests/ --cov=src --cov-report=term-missing

# Single file
poetry run pytest tests/test_mappers.py -v

# Single test
poetry run pytest tests/test_webhook_server.py::TestWebhookEndpoint::test_webhook_valid_payload_returns_200 -v
```

## Path / imports

Tests use the **project root** on `sys.path` and `src.*` imports (e.g. `from src.core.config import ...`) so that relative imports inside `src` (e.g. `from ..core.config`) resolve correctly. See `tests/conftest.py`.

## Before first run

1. `poetry install` (so dev deps like `pytest`, `pytest-cov` are installed).
2. No `.env` needed for the test suite; config tests set env via `monkeypatch`.

After tests pass, you’re good to run the app (Streamlit + webhook + tunnel) as in `README.md` / `PRE_FLIGHT_CHECKLIST.md`.
