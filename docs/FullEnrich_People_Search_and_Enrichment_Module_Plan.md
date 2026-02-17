# FullEnrich People Search + Contact Enrichment Module (API v2) — Implementation Plan

This plan implements the flow you described:

1) **Find people at a company** (optionally filtered by role/title)  
2) **Enrich those people** to retrieve contact information (emails/phones)  
3) **Store + serve results** to your product reliably (async webhooks, dedupe, rate-limit safe)

---

## 0) Key API behaviors you must design around (from FullEnrich docs)

### Auth
- All requests use **Bearer authentication** via `Authorization: Bearer <API_KEY>`. citeturn23view0

### Search is synchronous (instant response)
- Search endpoints return results immediately (no webhooks). citeturn28view0

### Enrichment is asynchronous (results come later)
- Enrich API returns an ID immediately, and results are delivered later via **webhooks**. citeturn29view0  
- Typical processing time: **30–90 seconds per contact**. citeturn29view0  
- Webhooks retry automatically **every minute up to 5 times** if your endpoint returns non-2xx. citeturn29view0

### Rate limits & batching
- 60 API calls/minute for all endpoints. citeturn25view0  
- Enrich supports **up to 100 contacts per bulk request**. citeturn25view0  
- Default queue size: **100 concurrent enrichments**. citeturn25view0  

### Credits
- Enrichment uses credits only when results are found (e.g., email/phone found). citeturn27view0  
- Search API costs **0.25 credit per person/company returned**, and re-exporting is free. citeturn27view0  
- FullEnrich only stores enrichment data for **3 months** (GDPR); after that, fetching by enrichment ID errors — store results on your side. citeturn27view0  

### Dedupe realities
- FullEnrich dedupes across history only when the *input data matches*; it does **not dedupe within the same bulk**, and variations in input can bypass dedupe. citeturn27view0  
- Therefore you should dedupe before sending to enrichment.

### Enrich input requirements + best practice
- To enrich a contact, provide either:  
  1) `first_name` + `last_name` + company (`domain` or `company_name`), OR  
  2) `linkedin_url` citeturn22view1  
- Including LinkedIn URL improves enrichment rates and returns richer profiles. citeturn22view1  
- `custom` is supported to track which internal record a webhook belongs to, but **all values must be strings**. citeturn29view0  

---

## 1) Product-level scope and assumptions

### Inputs (your spec)
- `company_name` (required)
- `title` (optional)

### Outputs
- List of people matching the company (+ optional title filter)
- Enriched contact info (work emails, personal emails, phones) + verification status

### What this plan ships
- Backend service wrapper around FullEnrich v2
- Endpoints to:
  - search people
  - start enrichments
  - receive webhooks
  - query stored results
- Database schema (recommended) to store:
  - search runs & people
  - enrichment runs & enrichment results

---

## 2) Data model (recommended tables)

> You *can* build without DB at first, but because FullEnrich only stores results for ~3 months, storing results is the stable design. citeturn27view0

### `fe_companies`
- `id` (uuid, pk)
- `company_name_input` (text) — what user typed
- `fullenrich_company_id` (text, nullable)
- `name` (text)
- `domain` (text) — important for enrichment
- `linkedin_url` (text)
- `raw` (jsonb) — full object from `/company/search`
- timestamps

### `fe_people`
- `id` (uuid, pk)
- `fullenrich_person_id` (text, unique)
- `company_id` (uuid fk -> fe_companies)
- `full_name`, `first_name`, `last_name`
- `current_title` (text)
- `linkedin_url` (text)
- `location_city`, `location_region`, `location_country`
- `raw` (jsonb) — full person record from `/people/search`
- timestamps

### `fe_search_runs`
- `id` (uuid, pk)
- `company_id` (uuid fk)
- `title_input` (text, nullable)
- `request_payload` (jsonb)
- `response_metadata` (jsonb) — includes pagination info
- timestamps

### `fe_enrichment_runs`
- `id` (uuid, pk)
- `fullenrich_enrichment_id` (text, unique)
- `company_id` (uuid fk)
- `name` (text) — the batch label you send to FullEnrich
- `requested_fields` (text[]) — e.g. `contact.emails`, `contact.phones`
- `status` (text) — track locally (`QUEUED|IN_PROGRESS|DONE|FAILED`)
- `credits_cost` (numeric, nullable)
- timestamps

### `fe_enrichment_results`
- `id` (uuid, pk)
- `enrichment_run_id` (uuid fk)
- `person_id` (uuid fk -> fe_people)
- `custom` (jsonb) — must contain only strings in the request, but store as json
- `contact_info` (jsonb) — emails/phones + statuses
- `profile` (jsonb) — enriched profile returned (job title, etc.)
- `raw_webhook_payload` (jsonb)
- timestamps

---

## 3) Backend module structure (Cursor-friendly)

Example folder layout (Python + FastAPI style; adapt to your codebase):

```
app/
  config/
    settings.py
  integrations/
    fullenrich/
      client.py
      models.py
      mapper.py
  services/
    people_search_service.py
    enrichment_service.py
  api/
    routes/
      people_search.py
      fullenrich_webhooks.py
  db/
    repo/
      fe_companies_repo.py
      fe_people_repo.py
      fe_enrichment_repo.py
```

---

## 4) FullEnrich API mapping (what you’ll call)

### 4.1 Resolve company domain (optional but strongly recommended)
If the user provides only `company_name`, you should resolve the **company domain** for best enrichment.

- Endpoint: `POST https://app.fullenrich.com/api/v2/company/search` citeturn21view0  
- Use filter: `names: [{ value: <company_name>, exact_match: true, exclude: false }]` citeturn21view0  
- From response, pick the best match’s `domain`. citeturn21view0

**Selection heuristic (simple + robust):**
1) Prefer exact name matches (case-insensitive)  
2) Prefer company with a domain present  
3) If multiple, pick highest headcount / follower_count (if provided)  

Store the chosen company object into `fe_companies.raw` for traceability.

---

### 4.2 Search people at that company (title optional)
- Endpoint: `POST https://app.fullenrich.com/api/v2/people/search` citeturn26view0  
- Primary filter: `current_company_names` (exact match) citeturn26view0  
- Optional title filter: `current_position_titles` with `exact_match: false` to allow partial/contains matching citeturn26view2  
- Optional “decision-maker” filter: `current_position_seniority_level` values like `Director`, `VP`, etc. citeturn26view2  
- Pagination: `limit`, `offset`, and `search_after` (use `search_after` beyond offset 10k, per docs). citeturn21view0  

**Important note on filter logic:** multiple filters within the same field behave like AND logic in the Search endpoints. citeturn21view0

**Result mapping tips:**
- Use `fullenrich_person_id` as unique key in your DB.
- Capture LinkedIn from `social_profiles.linkedin.url` when present (useful for enrichment input and de-dupe).

---

### 4.3 Start bulk enrichment for returned people
- Endpoint: `POST https://app.fullenrich.com/api/v2/contact/enrich/bulk` citeturn22view0  
- Required top-level fields:
  - `name` (required) citeturn22view0
  - `data` (required array) citeturn22view0
  - `webhook_url` (batch completion webhook, optional but recommended) citeturn29view0
  - `webhook_events.contact_finished` (per-contact webhook, recommended for real-time updates) citeturn29view0

**Per-contact input:**
- Provide either:
  - `first_name`, `last_name`, and `domain` or `company_name`; OR
  - `linkedin_url` citeturn22view1

**Recommended per-contact payload:**
- Always send:
  - `first_name`, `last_name`
  - `domain` (best) and `company_name`
  - `linkedin_url` if you have it (improves success rates) citeturn22view1
  - `enrich_fields`: choose from `contact.emails`, `contact.phones` citeturn22view0
  - `custom`: include your internal IDs **as strings** (required by webhook rules) citeturn29view0

**Batch sizing & concurrency:**
- Max 100 contacts per bulk request citeturn25view0  
- Respect 60 calls/minute overall citeturn25view0  
- If enriching many contacts, use a worker that sends bulks in a throttled loop.

---

## 5) Your API (what your frontend will call)

### 5.1 Search API (synchronous)
`POST /api/people/search`

Request:
```json
{
  "company_name": "Anthropic",
  "title": "VP of Engineering",
  "limit": 25,
  "cursor": null
}
```

Backend steps:
1) Resolve company domain via `/company/search` (cache by company name for ~7 days)
2) Call `/people/search` with:
   - `current_company_names` exact match
   - if `title`, add `current_position_titles` exact_match=false
3) Upsert people into `fe_people`
4) Return people list + pagination info (cursor = `search_after`)

Response:
```json
{
  "company": { "name": "...", "domain": "..." },
  "people": [
    {
      "person_id": "internal_uuid",
      "full_name": "...",
      "title": "...",
      "linkedin_url": "...",
      "location": { "city": "...", "region": "...", "country": "..." }
    }
  ],
  "next_cursor": "search_after_token_or_null"
}
```

---

### 5.2 Enrichment kickoff (async)
`POST /api/people/enrich`

Request:
```json
{
  "company_id": "uuid",
  "person_ids": ["uuid", "uuid"],
  "enrich_fields": ["contact.emails", "contact.phones"]
}
```

Backend steps:
1) Load people rows (names + linkedin_url) + company domain
2) De-dupe `person_ids` and skip those already enriched recently
3) Split into chunks of 100 and send `contact/enrich/bulk`
4) Create `fe_enrichment_runs` row per bulk (store returned `enrichment_id`)
5) Return `enrichment_run_ids` to frontend

Response:
```json
{
  "enrichment_runs": [
    { "run_id": "uuid", "status": "QUEUED" }
  ]
}
```

---

### 5.3 Webhook receiver endpoints (critical)

#### (A) Per-contact updates (recommended)
`POST /webhooks/fullenrich/contact-finished?token=<secret>`

- You configured this in `webhook_events.contact_finished`. citeturn29view0
- It fires once per contact with a payload that includes `contact_info` and `profile`. citeturn29view1

Server logic:
1) Validate `token` (shared secret)  
2) Parse payload
3) Read `custom` (contains internal IDs) and upsert into `fe_enrichment_results`
4) Mark person as `enriched=true` (optional)
5) Return 200 quickly (webhook retries happen if non-2xx). citeturn29view0

#### (B) Batch completion
`POST /webhooks/fullenrich/batch-complete?token=<secret>`

- You configured this in `webhook_url`. citeturn29view0
- Use this to flip the enrichment run status to `DONE`.

---

## 6) Implementation details Cursor should generate

### 6.1 FullEnrich HTTP client (`integrations/fullenrich/client.py`)
Requirements:
- Base URL: `https://app.fullenrich.com/api/v2`
- Adds Authorization header `Bearer <API_KEY>` citeturn23view0
- Handles:
  - retries on 429/5xx with exponential backoff (client-side)
  - per-minute token bucket rate limiter (60/min) citeturn25view0
- Methods:
  - `search_company(payload) -> CompanySearchResponse`
  - `search_people(payload) -> PeopleSearchResponse`
  - `start_bulk_enrichment(payload) -> {enrichment_id}`
  - (optional) `get_enrichment(enrichment_id)` for debugging/polling fallback

### 6.2 Payload builders (`integrations/fullenrich/models.py`)
Create typed request builders so you never send malformed filter objects.

**Filter object shape** (used in search endpoints):
```json
{ "value": "...", "exact_match": true, "exclude": false }
```
(Shown across both Search People and Search Company examples.) citeturn21view0turn26view0

### 6.3 Mapper (`integrations/fullenrich/mapper.py`)
- Convert FullEnrich person -> `fe_people` row
- Extract:
  - full name / first / last
  - current title
  - linkedin url (if present)
  - location
  - company domain/name (if in response)

### 6.4 Services

#### `people_search_service.py`
- `get_or_create_company(company_name)`:
  - cache lookup
  - fallback to `/company/search`
- `search_people(company_id, title, limit, cursor)`:
  - builds `/people/search` payload using:
    - `current_company_names` exact match citeturn26view0
    - optional `current_position_titles` exact_match=false citeturn26view2
  - writes `fe_search_runs` + upserts `fe_people`

#### `enrichment_service.py`
- `start_enrichment(company_id, person_ids, enrich_fields)`
  - chunk up to 100 citeturn25view0
  - build `custom` with strings only citeturn29view0
  - send `webhook_events.contact_finished` (recommended) citeturn29view0
  - store `fe_enrichment_runs`

### 6.5 Webhook route (`api/routes/fullenrich_webhooks.py`)
- Validates query token or header secret (your own)
- Upserts results
- Must be fast + always return 2xx for valid payloads (or FullEnrich retries) citeturn29view0

---

## 7) Operational safeguards

### Dedupe before enrichment
Because FullEnrich does not dedupe within the same bulk and input variations can bypass dedupe, you should:
- Deduplicate on `(linkedin_url)` if available
- Else dedupe on `(first_name, last_name, company_domain)` normalized citeturn27view0

### Store results immediately
Since FullEnrich retains data for 3 months, store webhook payloads in your DB. citeturn27view0

### Testing without spending credits
Use the provided FullEnrich test contact (0 credits) payload exactly as-is for dev testing. citeturn27view0

---

## 8) Minimal “first version” checklist (ship fast)

1) ✅ Add env vars:
   - `FULLENRICH_API_KEY`
   - `FULLENRICH_WEBHOOK_TOKEN` (your own secret)
   - `PUBLIC_BASE_URL` (needed to construct webhook URLs)

2) ✅ Implement client:
   - `POST /company/search`
   - `POST /people/search`
   - `POST /contact/enrich/bulk`

3) ✅ Build endpoints:
   - `POST /api/people/search`
   - `POST /api/people/enrich`
   - `POST /webhooks/fullenrich/contact-finished`
   - `POST /webhooks/fullenrich/batch-complete`

4) ✅ DB tables (or a temporary store)
5) ✅ End-to-end test using webhook.site + test contact citeturn29view0turn27view0

---

## 9) “Nice next” improvements (after MVP)

- Add “role presets” (e.g., decision makers) by injecting `current_position_seniority_level` with values like Director/VP. citeturn26view2
- Add credit balance checks + alerting (protect prod from “no credits” situations). citeturn27view0
- Add backpressure: if you’re near the queue limit (100 concurrent enrichments), delay sending additional bulks. citeturn25view0
- Add robust company matching UI when company resolution returns multiple candidates.

---

## 10) Cursor prompt (copy-paste)

Use this prompt in Cursor to generate code from this plan:

> Implement the FullEnrich v2 People Search + Enrichment module as described in `FullEnrich_People_Search_and_Enrichment_Module_Plan.md`.  
> Use FastAPI, Pydantic, and an HTTP client (httpx). Create:  
> 1) `app/integrations/fullenrich/client.py` with typed methods for company search, people search, start bulk enrichment.  
> 2) `app/services/people_search_service.py` and `app/services/enrichment_service.py`.  
> 3) `app/api/routes/people_search.py` and `app/api/routes/fullenrich_webhooks.py`.  
> 4) DB models/repositories for the recommended tables (or SQLAlchemy models if using ORM).  
> Add rate-limiting to 60 calls/min and chunk enrichment requests to max 100 contacts.  
> Ensure webhook handlers validate a shared token and store results.  
> Include unit tests for payload building and dedupe.
