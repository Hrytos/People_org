# HubSpot Integration Memory

This document captures the current HubSpot integration behavior, mapping rules, and operational guidance for the People Search + Enrichment app.

## Overview

The HubSpot integration is a manual sync flow in Step 3 of the Streamlit app.

Flow:
1. Search and enrich contacts with FullEnrich.
2. Save enriched contacts to Supabase `contacts` table.
3. Pull saved rows back from Supabase by email.
4. Sync saved rows to HubSpot Contacts using batch upsert by email.

Key behavior:
- Sync is one-way: Supabase -> HubSpot.
- HubSpot sync does not block Supabase save.
- Sync summary is shown in UI with attempted/succeeded/failed/skipped counts.
- Failures can be exported as CSV from UI.

## Components

Core files:
- `src/integrations/hubspot.py`
- `src/services/hubspot_sync.py`
- `src/core/config.py`
- `src/db/supabase_client.py`
- `app.py`

Responsibilities:
- `HubSpotClient`: HTTP auth, retry/backoff, contact property discovery, batch upsert.
- `HubSpotSyncService`: payload mapping, property resolution, batching, failure reporting.
- `SupabaseClient`: fetch saved rows by email so sync uses real `contacts.id` values.
- `app.py`: exposes manual sync action and displays sync results.

## Authentication and Scopes

The app uses a HubSpot private app token in `HUBSPOT_SERVICE_KEY`.

Recommended scopes:
- `crm.objects.contacts.read`
- `crm.objects.contacts.write`
- `crm.objects.companies.read` (optional if account-level linking is needed)

## Environment Variables

Required for sync:
- `HUBSPOT_SERVICE_KEY`

Optional:
- `ENABLE_HUBSPOT_SYNC`
- `HUBSPOT_BASE_URL`
- `HUBSPOT_REQUEST_TIMEOUT`
- `HUBSPOT_BATCH_SIZE`
- `HUBSPOT_DRY_RUN`
- `HUBSPOT_SUPABASE_ID_PROPERTY`
- `HUBSPOT_CONTACT_FIELD_MAP`

Example:

```env
ENABLE_HUBSPOT_SYNC=true
HUBSPOT_SERVICE_KEY=pat-xxx
HUBSPOT_BASE_URL=https://api.hubapi.com
HUBSPOT_REQUEST_TIMEOUT=30
HUBSPOT_BATCH_SIZE=100
HUBSPOT_DRY_RUN=false
HUBSPOT_SUPABASE_ID_PROPERTY=contactID
HUBSPOT_CONTACT_FIELD_MAP={"summary":"linkedin_summary","job_description":"linkedin_job_description","linkedin_url":"LinkedIn URL"}
```

## Mapping Strategy

The mapping strategy is discovery-first and safe by default.

Rules:
1. Baseline fields map to standard HubSpot contact fields when available.
2. Custom fields map only if the property exists in the portal.
3. Explicit overrides can be supplied with `HUBSPOT_CONTACT_FIELD_MAP`.
4. Matching supports internal names and labels (normalized matching).
5. Missing properties are skipped with warning logs, not hard failures.

Baseline fields:
- `email` -> `email`
- `first_name` -> `firstname`
- `last_name` -> `lastname`
- `phone` -> `phone`
- `company_name` -> `company`
- `job_title` -> `jobtitle`

Custom candidates (auto-detected if present):
- `account_id`
- `linkedin_url`
- `linkedin_id`
- `sales_navigator_id`
- `summary`
- `job_description`
- `job_started_at`
- `job_ended_at`
- `role_value`
- `location`
- `headline`

## contactID Traceability

Purpose:
- Store Supabase `contacts.id` in HubSpot for cross-system traceability.

Behavior:
- The app resolves `HUBSPOT_SUPABASE_ID_PROPERTY` against discovered HubSpot properties.
- Resolution is tolerant to case and separator differences (`contactID`, `contactid`, `contact_id`).
- If property exists, sync writes Supabase `id` to that field.
- If property does not exist, trace field is skipped with warning.

Important:
- HubSpot record ID is different from Supabase `contacts.id` and should not be compared directly.
- `contactID` (custom property) is the place where Supabase id is stored.

## Runtime Sequence (Detailed)

1. User clicks Save in Step 3.
2. Contacts are inserted/upserted into Supabase.
3. App fetches saved rows by emails via `get_contacts_by_emails`.
4. UI preview is updated with real Supabase rows.
5. User clicks Sync to HubSpot.
6. Service discovers HubSpot contact properties.
7. Service resolves field mapping.
8. Service builds payload and upserts in batches.
9. Service returns summary with failure details.
10. UI displays summary and optional failure CSV.

## Error Handling

Handled failure categories:
- Missing email: skipped before API call.
- HubSpot 4xx/5xx: captured with detailed response snippet.
- Partial batch acknowledgment: tracked as failure records.
- Missing custom property: logged warning, sync proceeds with available fields.

Retries and throttling:
- Retry for 423/429/5xx with backoff.
- `Retry-After` header respected when present.
- Token-bucket limiter used for pacing.

## Troubleshooting

### Contact created but custom fields empty
- Verify field exists on HubSpot Contact object.
- Verify target is internal name or resolvable label.
- Add explicit `HUBSPOT_CONTACT_FIELD_MAP` override.

### contactID empty
- Verify `HUBSPOT_SUPABASE_ID_PROPERTY` value.
- Verify the property exists in your HubSpot portal.
- Re-sync after save so sync uses DB-backed rows with real ids.

### LinkedIn URL missing
- Confirm the exact HubSpot property or label.
- Add override in `HUBSPOT_CONTACT_FIELD_MAP`.

### 400 Bad Request on batch upsert
- Inspect error payload in logs (response snippet is included).
- Remove or remap invalid custom fields.
- Re-run with small batch to isolate payload issues.

## Validation Commands

Use these checks during operations:

```bash
python -c "from src.core.config import validate_hubspot_config; print(validate_hubspot_config(required=True))"
```

```bash
python -c "from src.services.hubspot_sync import HubSpotSyncService; s=HubSpotSyncService(dry_run=True); print(s.sync_contacts([{'id':'123','email':'test@example.com'}]))"
```

## Current Integration Status

Implemented and verified:
- Manual HubSpot sync UI action.
- Live batch upsert by email.
- Property discovery and dynamic mapping.
- Label-aware override mapping.
- Supabase id trace write via configurable property.
- Sync summary and failure export.

Known noisy warnings you may see:
- Configured mapping targets that do not exist in HubSpot are ignored and logged.
- This is expected and non-blocking.

## Maintenance Notes

When HubSpot schema changes:
1. Update `HUBSPOT_CONTACT_FIELD_MAP` in environment.
2. Re-run a dry-run sync to confirm mapping.
3. Run one-contact live smoke test.
4. Then run normal batch sync.
