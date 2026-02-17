"""
Enrichment Service

Orchestrates enrichment: start job, poll for results, map data.
Only writes to DB when user clicks "Save" (contacts table).
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from ..fullenrich.client import FullEnrichClient
from ..fullenrich.mappers import EnrichmentMapper
from ..db.supabase_client import SupabaseClient
from ..core.logging import setup_logger

logger = setup_logger(__name__)

# =============================================================================
# Enrichment Service
# =============================================================================

class EnrichmentService:
    """
    Service for enriching contact data.
    
    - Start enrichment → poll for results → map to contacts (in memory).
    - DB write only when user calls save_to_final_tables (e.g. after "Save" in UI).
    """
    
    def __init__(self):
        self.fullenrich = FullEnrichClient()
        self.db = SupabaseClient()
        self.mapper = EnrichmentMapper()
        logger.info("EnrichmentService initialized")
    
    def enrich_contacts(
        self,
        contacts: List[Dict[str, Any]],
        webhook_url: str,
        batch_name: Optional[str] = None,
        include_phones: bool = False,
    ) -> Dict[str, Any]:
        """
        Start bulk enrichment. No DB write for runs/results.
        
        Args:
            contacts: List with first_name, last_name, company_name, domain, linkedin_url
            webhook_url: Public webhook URL
            batch_name: Optional batch name
            include_phones: Whether to enrich phone numbers (default: False, emails only)
            
        Returns:
            Dict with enrichment_id, contacts_count, with_linkedin
        """
        if not batch_name:
            batch_name = f"Batch {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        enrichment_type = "emails + phones" if include_phones else "emails only"
        logger.info(f"Starting enrichment: {len(contacts)} contacts ({enrichment_type})")
        with_linkedin = sum(1 for c in contacts if c.get("linkedin_url"))
        
        enrichment_id = self.fullenrich.enrich_bulk(
            contacts=contacts,
            webhook_url=webhook_url,
            batch_name=batch_name,
            include_phones=include_phones
        )
        
        if not enrichment_id:
            raise ValueError("Failed to start enrichment")
        
        logger.info(f"Enrichment started: {enrichment_id}")
        return {
            "enrichment_id": enrichment_id,
            "contacts_count": len(contacts),
            "with_linkedin": with_linkedin
        }
    
    def poll_for_results(
        self,
        enrichment_id: str,
        timeout: int = 180,
        poll_interval: int = 10
    ) -> Optional[Dict]:
        """
        Poll FullEnrich API for enrichment results (more reliable than webhook).
        
        Args:
            enrichment_id: Enrichment UUID
            timeout: Max wait time in seconds (default: 180 = 3 minutes)
            poll_interval: Seconds between polls (default: 10)
            
        Returns:
            Enrichment result payload or None if timeout
        """
        import time
        
        logger.info(f"Polling for enrichment results: {enrichment_id}")
        logger.info(f"Timeout: {timeout}s, polling every {poll_interval}s")
        
        start_time = time.time()
        elapsed = 0
        
        while elapsed < timeout:
            try:
                result = self.fullenrich.get_enrichment_result(enrichment_id)
                status = result.get("status", "UNKNOWN")
                
                logger.info(f"Status: {status} ({elapsed}s elapsed)")
                
                if status == "FINISHED":
                    logger.info(f"✅ Enrichment completed in {elapsed}s")
                    # Log response structure for debugging
                    import json
                    logger.debug(f"Poll result keys: {result.keys()}")
                    logger.debug(f"Poll result sample: {json.dumps(result, indent=2)[:1000]}")
                    return result
                
                elif status in ["CANCELED", "CREDITS_INSUFFICIENT"]:
                    logger.error(f"❌ Enrichment failed with status: {status}")
                    return None
                
                # Still in progress - wait and retry
                time.sleep(poll_interval)
                elapsed = int(time.time() - start_time)
                
            except ValueError as e:
                if "in progress" in str(e).lower():
                    # Expected - still processing
                    time.sleep(poll_interval)
                    elapsed = int(time.time() - start_time)
                    if elapsed % 30 == 0:  # Log every 30s
                        logger.info(f"Still processing... ({elapsed}s elapsed)")
                else:
                    logger.error(f"Poll error: {e}")
                    return None
            
            except Exception as e:
                logger.error(f"Unexpected error during polling: {e}")
                return None
        
        logger.warning(f"⏱️ Polling timeout after {timeout}s")
        return None
    
    def process_webhook(self, webhook_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map webhook payload to accounts and contacts. No DB write.
        
        Args:
            webhook_payload: Full webhook JSON from FullEnrich
            
        Returns:
            Dict with accounts, contacts (ready for UI or save_to_final_tables)
        """
        enrichment_id = (
            webhook_payload.get("enrichment_id") or
            webhook_payload.get("id") or
            webhook_payload.get("batch_id")
        )
        logger.info(f"Processing webhook: {enrichment_id}")
        
        accounts, contacts = self.mapper.map_to_accounts_contacts(webhook_payload)
        logger.info(f"Mapped {len(accounts)} accounts, {len(contacts)} contacts")
        
        return {
            "accounts": accounts,
            "contacts": contacts
        }
    
    def save_to_final_tables(
        self,
        accounts: List[Dict],
        contacts: List[Dict]
    ) -> tuple:
        """
        Persist enriched data to DB (accounts_test, contacts_test).
        Call this only when user clicks Save.
        
        Returns:
            Tuple of (accounts_count, contacts_count)
        """
        logger.info(f"Saving to DB: {len(accounts)} accounts, {len(contacts)} contacts")
        acc_count, con_count = self.db.insert_all(accounts, contacts)
        logger.info(f"Saved: {acc_count} accounts, {con_count} contacts")
        return acc_count, con_count


# =============================================================================
# Module Test
# =============================================================================

if __name__ == "__main__":
    print("EnrichmentService Test")
    print("=" * 60)
    try:
        service = EnrichmentService()
        print("✅ Service initialized")
    except Exception as e:
        print(f"❌ Error: {e}")
