# Rulebook — People Search + Enrichment (FullEnrich) with Streamlit + Poetry

This rulebook is meant to keep the build clean, safe, and deployable. Treat it as “non‑negotiable conventions” for the repo, the deployment, and the runtime behavior.

---

## 0) Non‑negotiables (read this first)

1) **Never expose the FullEnrich API key**  
   - API calls must happen server-side (Streamlit backend / your API service), never from the browser.

2) **PII handling is a product decision, not a coding afterthought**  
   - Store only what you truly need (emails/phones are sensitive).  
   - Add retention rules (e.g., delete raw payloads after N days).  
   - Log redaction: never log full emails/phones (mask them).

3) **Always assume webhooks can arrive late, twice, or out of order**  
   - Your system must be idempotent.

4) **Rate limits and credits are real constraints**  
   - Throttle requests.  
   - Show “estimated credits” before running large enrichments.  
   - Maintain a “stop button” for users.

---

## 1) Recommended architecture (Streamlit-first, production-safe)

Streamlit is a great UI, but it’s not a webhook receiver or a worker queue.

**Use this split:**

### A) Streamlit (UI)
- Collect inputs: `company_name`, optional `title`, optional filters.
- Trigger “Search People” (synchronous).
- Display results; allow user to select roles/people.
- Trigger “Enrich Selected” (asynchronous start call).
- Poll *your own database* for job status (not FullEnrich directly).

### B) API Service (FastAPI recommended, tiny)
- Owns:
  - FullEnrich calls (Search + Start Enrichment)
  - Webhook endpoint(s)
  - Job state machine
- Reason: streamlit deployments generally aren’t designed to accept arbitrary POST webhooks reliably.

### C) Worker (optional but recommended once volume grows)
- Handles:
  - chunking into batches of 100
  - rate limiting
  - retries
- Can be a lightweight background process or a job runner (Celery/RQ/Arq) depending on your infra.

### D) Storage (any DB works)
Minimum tables:
- `search_runs` (inputs, filters, created_at)
- `people_candidates` (results from Search API)
- `enrichment_jobs` (job_id, status, created_at, finished_at, custom correlation ids)
- `enrichment_results` (normalized contact info)
- `webhook_events` (raw payload, event type, received_at, processed boolean, idempotency key)

---

## 2) Project structure conventions (don’t freestyle)

Suggested layout:

```
repo/
  app.py                     # streamlit entrypoint
  pyproject.toml
  poetry.lock
  README.md
  .streamlit/
    config.toml
    secrets.toml             # local only; never commit
  src/
    core/
      settings.py            # env + secrets loader
      logging.py             # structured logging + redaction
      http.py                # shared http client, timeouts, retries
    fullenrich/
      client.py              # FullEnrich API wrapper
      mappers.py             # normalize payloads -> your schema
      rate_limit.py          # throttle + backoff logic
    services/
      people_search.py
      enrichment.py
      webhook_processor.py
    db/
      models.py
      repository.py
      migrations/            # if you use alembic
  api/
    main.py                  # fastapi app (webhooks + trigger endpoints)
  tests/
```

**Rule:** UI code (Streamlit) must not contain business logic beyond calling service functions.

---

## 3) Poetry rules (dependency hygiene)

### A) Pin Python version
- Set a single Python version for dev + prod (e.g., 3.12), and enforce it in `pyproject.toml`.

### B) Separate runtime vs dev deps
- Put lint/test tools under dev group.
- CI installs `--only main` (or equivalent) for runtime images.

### C) Lockfile is sacred
- Always commit `poetry.lock`.
- “Works on my machine” is usually “lockfile drift”.

### D) Export requirements when needed
Some deployment targets (especially Streamlit Community Cloud) often work best with a `requirements.txt` exported from Poetry:

```
poetry self add poetry-plugin-export
poetry export -f requirements.txt --without-hashes -o requirements.txt
```

Keep it automated (Makefile / task script) so you never hand-edit `requirements.txt`.

---

## 4) Streamlit deployment rulebook (Community Cloud + generic Docker)

### A) Streamlit Community Cloud
1) **Dependencies**
   - Use only one dependency file approach.
   - Easiest: export `requirements.txt` from Poetry and deploy with it.
2) **Secrets**
   - Put secrets in Streamlit Cloud “Secrets” UI.
   - Locally, use `.streamlit/secrets.toml` and add it to `.gitignore`.
3) **Python version**
   - Set it explicitly in Streamlit Cloud advanced settings to match your local.

### B) Docker (works everywhere)
Minimal Docker approach:
- Install deps via Poetry or exported requirements
- Start:
  - `streamlit run app.py --server.port=$PORT --server.address=0.0.0.0`

**Rule:** Do not run webhook receiving inside the Streamlit container unless you fully control routing + stability.

---

## 5) Secrets & configuration rules

### A) Local secrets
- `.streamlit/secrets.toml` (never commit)

Example:
```toml
FULLENRICH_API_KEY="..."
WEBHOOK_BASE_URL="https://your-api-service.com"
DATABASE_URL="..."
```

### B) Access pattern
- Prefer `st.secrets["FULLENRICH_API_KEY"]` in Streamlit.
- In FastAPI/worker, load from env vars (`os.environ["FULLENRICH_API_KEY"]`).

### C) Config file
- `.streamlit/config.toml` for UI behavior (theme, server settings).
- Keep configuration predictable; avoid “magic defaults”.

---

## 6) HTTP client standard (prevents 80% of production bugs)

Use one shared HTTP client (e.g., `httpx.Client`) with:
- **Timeouts** (connect/read/write)
- **Retries** only for safe cases:
  - 429, 500–599, transient network errors
- **Backoff** (exponential + jitter)
- **Circuit breaker** (optional but valuable)

**Rule:** Never retry non-idempotent operations blindly unless you have an idempotency key or can safely dedupe.

---

## 7) FullEnrich flow rules (search → enrich)

### A) Search People (synchronous)
- Input: `company_name`, optional `title`
- Output: list of people profiles (no contact info or limited info, depending on API)

Store:
- raw search response (short-term)
- normalized people list (longer-term)

### B) Enrichment (async)
- Start enrichment in batches of **<= 100 contacts per request** (batching rule).
- Always set:
  - `webhook_url` (where FullEnrich will POST results)
  - `custom` object with correlation keys:
    - `run_id`, `job_id`, `user_id`, etc.
- The UI should show “Enrichment started” and immediately return control to the user.

### C) Status & UX
- User sees:
  - queued → running → partial → complete
- Provide:
  - “Download CSV”
  - “Retry failed only”
  - “Stop” (mark as cancelled; do not enqueue new batches)

---

## 8) Webhook receiver rulebook (idempotent by design)

### A) Endpoint behavior (FastAPI)
- Validate request (auth/signature if FullEnrich provides; otherwise at least validate shape)
- Return **200 fast** (within ~1–2s). Don’t do heavy work inline.

### B) Idempotency keys
Compute an idempotency key from:
- `enrichment_id` (or equivalent) + event type + contact index/email hash

Store webhook event row first, then process.

### C) Processing pipeline
1) Persist raw payload
2) Normalize → upsert into `enrichment_results`
3) Update job status
4) Mark webhook event processed

### D) Retry safety
If your processor fails mid-way, re-running should not create duplicates.

---

## 9) Streamlit UI rulebook (keeps UI stable)

- Keep `st.session_state` minimal (store IDs, not entire payloads).
- Cache only safe things:
  - company search suggestions
  - user preferences
- Never cache PII for long durations.
- For progress:
  - show job status from DB (not from long-running UI thread)
  - use `st.autorefresh` (with reasonable intervals)

---

## 10) Quality gates (must pass before deployment)

### A) Lint + format
- ruff (or black + isort)
- mypy optional but great for API payloads

### B) Tests
- Unit tests:
  - payload normalization
  - webhook idempotency
  - rate limit/backoff behavior
- Integration tests (optional):
  - mocked FullEnrich API responses

### C) Pre-commit
- run: format + lint + basic tests before pushing

---

## 11) Operational runbook (what to do when things break)

### A) 401 Unauthorized
- Check API key in secrets
- Check Authorization header format

### B) 429 Too Many Requests
- Reduce concurrency
- Add queue + backoff
- Ensure you aren’t polling too frequently

### C) Webhooks not arriving
- Verify webhook URL is public + HTTPS
- Log incoming requests at the API service
- Use a temporary webhook testing URL (e.g., webhook.site) for quick debugging
- Confirm your service returns 200 quickly

### D) “Streamlit freezes”
- You’re doing long work in UI thread
- Move work to API service + worker
- UI should only trigger and then display status

---

## 12) Production checklist (print this)

- [ ] API key stored as secret, not in code
- [ ] Webhook receiver deployed and reachable
- [ ] Idempotency implemented for webhook processing
- [ ] Batch size enforced (<=100)
- [ ] Rate limiting enforced (<=60 req/min unless upgraded)
- [ ] PII logging redaction enabled
- [ ] Error monitoring enabled (Sentry or equivalent)
- [ ] Export/Download available (CSV)
- [ ] “Stop / cancel run” supported
- [ ] Docs: README with setup + deploy steps

---

## 13) Cursor prompt (how to use this rulebook)
When you feed this into Cursor, always add:
- “Follow the rulebook strictly”
- “Do not put business logic inside Streamlit app.py”
- “Implement webhooks in a separate FastAPI service”
- “Implement idempotency + rate limiting + batch chunking”
