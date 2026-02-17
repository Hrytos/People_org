# Database schema (your existing tables)

The app uses **your existing** `accounts` and `contacts` tables. It does not create them.

## Accounts table

- Used **read-only** for:
  - UI dropdown: loads accounts for quick selection
  - Account ID lookup: resolves `account_id` by `company_name` when saving contacts
  - Domain extraction: uses `account_domain` for more accurate people search
  
- **Key columns:**
  - `account_id` (UUID, PK) - Primary key
  - `company_name` (TEXT NOT NULL) - Company name for lookups
  - `account_domain` (TEXT NOT NULL UNIQUE) - Company domain (e.g. anthropic.com)
  - `linkedin_url`, `employee_count` - Optional, used in dropdown display

## Contacts table

- We **insert/update** enriched contacts into your `public.contacts` table.
- Expected columns we use:  
  `id`, `email` (NOT NULL UNIQUE), `first_name`, `last_name`, `company_name`, `created_at`, `account_id`, `full_name`, `job_title`, `location`, `linkedin_url`, `linkedin_id`, `sales_navigator_id`, `headline`, `summary`, `job_description`, `job_started_at`, `phone`, `updated_at`, `role_value`, `metadata`, `job_ended_at`.
- Contacts **without an email** are skipped (your schema has `email text not null`).
- `account_id` is set from your `accounts` table by matching `company_name`; if no row is found, `account_id` stays null.
- `role_value` is set from our role mapping; it must exist in your `roles` table (FK) or be null.

## Enrichment history (optional)

- Migration `02_minimal_tables_only.sql` creates only `enrichment_history` for run tracking.
- If you don’t need it, you can skip that migration; the app will still save contacts.
