"""
Supabase Client

Uses your existing tables:
- accounts: read-only lookups (company_name -> account_id) for linking contacts
- contacts: insert/update enriched contacts (your schema)
- enrichment_history: optional run history

We do NOT create or write to accounts – we only resolve account_id from
your accounts table to set contacts.account_id.
"""

import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

from ..core.config import SUPABASE_URL, SUPABASE_SERVICE_KEY
from ..core.logging import setup_logger

logger = setup_logger(__name__)


def _ensure_metadata_dict(val: Any) -> dict:
    """Ensure metadata is a dict for JSONB (accepts dict or JSON string)."""
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            import json
            return json.loads(val) if val else {}
        except Exception:
            return {}
    return {}

# =============================================================================
# Your table names and contact column mapping
# =============================================================================

ACCOUNTS_TABLE = "accounts"   # Read-only: lookup account_id by company name
CONTACTS_TABLE = "contacts"   # Your schema (email NOT NULL UNIQUE, company_name, account_id, etc.)
HISTORY_TABLE = "enrichment_history"


class SupabaseClient:
    """
    Writes only to contacts (and optionally enrichment_history).
    Resolves account_id from your existing accounts table by company_name.
    """

    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        from supabase import create_client, Client

        url = url or SUPABASE_URL
        key = key or SUPABASE_SERVICE_KEY

        if not url or not key:
            raise ValueError("Supabase URL and KEY are required")

        self.client: Client = create_client(url, key)
        self._account_cache = {}  # company_name -> account_id

        logger.info("Supabase client initialized (uses existing accounts + contacts)")

    # =========================================================================
    # Account lookup only (your existing accounts table)
    # =========================================================================

    def get_accounts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get accounts from your accounts table for UI dropdown.
        Returns list of {account_id, company_name, account_domain, ...}.
        """
        try:
            # Select columns from user's schema.
            cols = "account_id, company_name, account_domain, linkedin_url, employee_count"
            page_size = min(limit, 1000)

            # Fallback chain if some columns don't exist.
            for col_set in (cols, "account_id, company_name, account_domain", "*"):
                try:
                    all_rows: List[Dict[str, Any]] = []
                    start = 0

                    while start < limit:
                        end = min(start + page_size - 1, limit - 1)
                        result = (
                            self.client
                            .table(ACCOUNTS_TABLE)
                            .select(col_set)
                            .order("company_name")
                            .range(start, end)
                            .execute()
                        )

                        page_rows = result.data if result.data else []
                        if not page_rows:
                            break

                        all_rows.extend(page_rows)

                        # Last page reached.
                        if len(page_rows) < page_size:
                            break

                        start += page_size

                    return all_rows
                except Exception:
                    continue

            return []
        except Exception as e:
            logger.error(f"Get accounts failed: {e}")
            return []
    
    def get_account_id_by_company_name(self, company_name: str) -> Optional[str]:
        """
        Get account_id from your accounts table by company name.
        Used to set contacts.account_id when saving enriched contacts.
        Tries column 'company_name' first, then 'name' (adjust if your schema differs).
        """
        if not company_name:
            return None
        if company_name in self._account_cache:
            return self._account_cache[company_name]
        for col in ("company_name", "name"):
            try:
                r = self.client.table(ACCOUNTS_TABLE).select("account_id").eq(
                    col, company_name
                ).limit(1).execute()
                if r.data:
                    aid = r.data[0].get("account_id")
                    self._account_cache[company_name] = aid
                    return aid
            except Exception:
                continue
        logger.debug(f"No account found for company_name={company_name!r}")
        return None

    # =========================================================================
    # Contacts (your public.contacts schema)
    # =========================================================================

    def _contact_to_row(self, contact: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map our enriched contact dict to your contacts table columns.
        Your schema: id, email (not null, unique), first_name, last_name,
        company_name, created_at, account_id, full_name, job_title, location,
        linkedin_url, linkedin_id, sales_navigator_id, headline, summary,
        job_description, job_started_at, phone, updated_at, role_value, metadata, job_ended_at.
        """
        company_name = contact.get("company_name") or contact.get("account") or ""
        account_id = contact.get("account_id")

        row = {
            "email": (contact.get("email") or "").strip(),
            "first_name": contact.get("first_name") or None,
            "last_name": contact.get("last_name") or None,
            "company_name": company_name or None,
            "account_id": account_id,
            "full_name": contact.get("full_name") or None,
            "job_title": contact.get("job_title") or None,
            "location": contact.get("location") or None,
            "linkedin_url": contact.get("linkedin_url") or None,
            "linkedin_id": contact.get("linkedin_id") or None,
            "sales_navigator_id": contact.get("sales_navigator_id") or None,
            "headline": contact.get("headline") or None,
            "summary": contact.get("summary") or None,
            "job_description": contact.get("job_description") or None,
            "job_started_at": contact.get("job_started_at") or None,
            "phone": contact.get("phone") or None,
            "updated_at": datetime.now().isoformat(),
            "role_value": contact.get("role_value"),
            "metadata": _ensure_metadata_dict(contact.get("metadata")),
        }
        return row

    def upsert_contacts(
        self,
        contacts: List[Dict[str, Any]],
        forced_account_id: Optional[str] = None,
        skip_duplicates: bool = False,
    ) -> Tuple[int, int, int]:
        """
        Upsert into your contacts table.
        - email is required (NOT NULL UNIQUE); contacts without email are skipped.
        - If forced_account_id is provided (user picked an account from the dropdown),
          it is stamped on EVERY contact unconditionally — no name lookup needed.
        - Otherwise, account_id is resolved by company_name lookup.
        - If skip_duplicates=True, existing contacts are skipped (not updated).
        
        Returns:
            (inserted_count, updated_count, skipped_count)
        """
        if not contacts:
            return 0, 0, 0

        if forced_account_id:
            logger.info(f"Forced account_id for all contacts: {forced_account_id}")

        inserted = 0
        updated = 0
        skipped_no_email = 0
        skipped_duplicate = 0

        for contact in contacts:
            row = self._contact_to_row(contact)
            email = row.get("email") or ""
            if not email:
                skipped_no_email += 1
                logger.debug("Skipping contact with no email")
                continue

            if forced_account_id:
                # ✅ User chose an existing account — use it directly, no lookup
                row["account_id"] = forced_account_id
            else:
                # Fallback: resolve by company_name if account_id still missing
                company_name = row.get("company_name")
                if company_name and not row.get("account_id"):
                    row["account_id"] = self.get_account_id_by_company_name(company_name)

            existing = self._find_contact_by_email(email)

            if existing:
                if skip_duplicates:
                    # Don't update existing contacts — skip them
                    skipped_duplicate += 1
                    logger.info(f"Skipped duplicate contact: {email}")
                    continue
                else:
                    # Update existing contact
                    try:
                        update_data = {k: v for k, v in row.items() if k != "email"}
                        update_data["updated_at"] = datetime.now().isoformat()
                        self.client.table(CONTACTS_TABLE).update(update_data).eq(
                            "id", existing["id"]
                        ).execute()
                        updated += 1
                        logger.info(f"Updated existing contact: {email}")
                    except Exception as e:
                        logger.error(f"Contact update failed: {e}")
            else:
                try:
                    # Let DB generate id; include created_at default
                    insert_row = {k: v for k, v in row.items()}
                    self.client.table(CONTACTS_TABLE).insert(insert_row).execute()
                    inserted += 1
                    logger.info(f"Inserted new contact: {email}")
                except Exception as e:
                    logger.error(f"Contact insert failed: {e}")

        if skipped_no_email:
            logger.info(f"Skipped {skipped_no_email} contacts (no email)")
        if skipped_duplicate:
            logger.info(f"Skipped {skipped_duplicate} duplicate contacts")
        logger.info(f"Contacts: {inserted} inserted, {updated} updated")
        return inserted, updated, skipped_duplicate

    def _find_contact_by_email(self, email: str) -> Optional[Dict]:
        """Find contact by email (your table has unique constraint on email)."""
        if not email:
            return None
        try:
            result = self.client.table(CONTACTS_TABLE).select("*").eq(
                "email", email
            ).limit(1).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.warning(f"Contact lookup failed: {e}")
            return None

    def insert_all(
        self,
        accounts: List[Dict[str, Any]],
        contacts: List[Dict[str, Any]],
        selected_account_id: Optional[str] = None,
        skip_duplicates: bool = True,
    ) -> Tuple[int, int]:
        """
        Upsert contacts only. We never create new accounts.

        If selected_account_id is provided (user chose an account from the dropdown),
        that UUID is stamped directly on every contact — overriding anything the
        mapper may have set (mapper generates throwaway UUIDs for display only).

        If no selected_account_id, we fall back to resolving by company_name.
        
        Args:
            skip_duplicates: If True, existing contacts are skipped (not updated).
                            Default: True to avoid overwriting existing data.
        """
        con_inserted, con_updated, con_skipped = self.upsert_contacts(
            contacts, 
            forced_account_id=selected_account_id,
            skip_duplicates=skip_duplicates
        )
        total_saved = con_inserted + con_updated
        logger.info(f"Total saved: {total_saved} ({con_inserted} new, {con_updated} updated, {con_skipped} skipped)")
        return 0, total_saved

    # =========================================================================
    # Enrichment History
    # =========================================================================

    def create_enrichment_history(
        self,
        batch_name: str,
        contacts_count: int,
        with_linkedin: int,
        source: str = "streamlit",
    ) -> Optional[str]:
        try:
            record = {
                "batch_name": batch_name,
                "contacts_count": contacts_count,
                "with_linkedin": with_linkedin,
                "source": source,
                "status": "pending",
            }
            result = self.client.table(HISTORY_TABLE).insert(record).execute()
            if result.data:
                history_id = result.data[0]["id"]
                logger.info(f"Enrichment history created: {history_id}")
                return history_id
            return None
        except Exception as e:
            logger.error(f"Create history failed: {e}")
            return None

    def update_enrichment_history(
        self,
        record_id: str,
        status: str = "completed",
        credits_used: int = 0,
        accounts_inserted: int = 0,
        contacts_inserted: int = 0,
    ) -> bool:
        try:
            update_data = {
                "completed_at": datetime.now().isoformat(),
                "status": status,
                "credits_used": credits_used,
                "contacts_inserted": contacts_inserted,
            }
            self.client.table(HISTORY_TABLE).update(update_data).eq(
                "id", record_id
            ).execute()
            logger.info(f"Enrichment history updated: {record_id}")
            return True
        except Exception as e:
            logger.error(f"Update history failed: {e}")
            return False

    def get_enrichment_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        try:
            result = self.client.table(HISTORY_TABLE).select("*").order(
                "started_at", desc=True
            ).limit(limit).execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Get history failed: {e}")
            return []

    def get_credit_summary(self) -> Dict[str, int]:
        try:
            result = self.client.table(HISTORY_TABLE).select(
                "credits_used, status"
            ).execute()
            data = result.data if result.data else []
            total_credits = sum(r.get("credits_used", 0) or 0 for r in data)
            total_enrichments = len(data)
            successful = sum(1 for r in data if r.get("status") == "completed")
            return {
                "total_credits": total_credits,
                "total_enrichments": total_enrichments,
                "successful_enrichments": successful,
            }
        except Exception as e:
            logger.error(f"Get credit summary failed: {e}")
            return {
                "total_credits": 0,
                "total_enrichments": 0,
                "successful_enrichments": 0,
            }


if __name__ == "__main__":
    print("Supabase Client Test")
    print("=" * 60)
    try:
        client = SupabaseClient()
        print("✅ Client initialized successfully")
        summary = client.get_credit_summary()
        print(f"✅ Credit summary: {summary}")
    except Exception as e:
        print(f"❌ Error: {e}")
