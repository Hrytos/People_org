"""
FullEnrich API Client

Handles both Search (synchronous) and Enrichment (asynchronous) APIs.
Implements rate limiting, retries, and proper error handling.

API Documentation: https://docs.fullenrich.com
"""

from typing import List, Dict, Any, Optional, Union
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ..core.config import (
    FULLENRICH_API_KEY,
    FULLENRICH_BASE_URL,
    BATCH_SIZE,
    REQUEST_TIMEOUT,
    ENRICH_FIELDS
)
from ..core.logging import setup_logger
from .rate_limit import get_rate_limiter

logger = setup_logger(__name__)

# =============================================================================
# FullEnrich Client
# =============================================================================

class FullEnrichClient:
    """
    FullEnrich API v2 Client.
    
    Supports:
    1. Company Search - Find and resolve company details
    2. People Search - Find people at a company
    3. Bulk Enrichment - Enrich contacts with emails/phones
    
    Features:
    - Automatic rate limiting (60 req/min)
    - Retry logic with exponential backoff
    - Bearer token authentication
    - Proper error handling
    """
    
    def __init__(self):
        """Initialize FullEnrich client."""
        if not FULLENRICH_API_KEY or FULLENRICH_API_KEY == "your_api_key_here":
            raise ValueError(
                "Invalid FULLENRICH_API_KEY. "
                "Get yours from: https://app.fullenrich.com/app/api"
            )
        
        self.base_url = FULLENRICH_BASE_URL
        self.api_key = FULLENRICH_API_KEY
        self.rate_limiter = get_rate_limiter()
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        self.timeout = httpx.Timeout(timeout=float(REQUEST_TIMEOUT))
        
        logger.info("FullEnrich client initialized")
    
    # =========================================================================
    # Credit Management
    # =========================================================================
    
    def check_credits(self, quiet: bool = False) -> Optional[int]:
        """
        Check account credit balance.
        
        Args:
            quiet: If True, suppress console output
            
        Returns:
            Credit balance or None if error
        """
        try:
            self.rate_limiter.acquire()
            
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(
                    f"{self.base_url}/account/credits",
                    headers=self.headers
                )
                response.raise_for_status()
                result = response.json()
                balance = result.get("balance", 0)
            
            if not quiet:
                logger.info(f"Credit balance: {balance}")
            
            return balance
            
        except Exception as e:
            logger.error(f"Credit check failed: {e}")
            return None
    
    # =========================================================================
    # Company Search (Synchronous)
    # =========================================================================
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((
            httpx.TimeoutException,
            httpx.ConnectError
        )),
        reraise=True
    )
    def search_companies(
        self,
        company_name: str,
        exact_match: bool = True,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for companies by name.
        
        API: POST /company/search
        
        Args:
            company_name: Company name to search for
            exact_match: If True, require exact name match
            limit: Maximum results to return
            
        Returns:
            List of company objects with domain, linkedin_url, etc.
            
        Example response:
        [
            {
                "id": "...",
                "name": "Anthropic",
                "domain": "anthropic.com",
                "linkedin_url": "...",
                "headcount": 150,
                ...
            }
        ]
        """
        logger.info(f"Searching companies: {company_name}")
        
        # Acquire rate limit token
        self.rate_limiter.acquire()
        
        payload = {
            "names": [{
                "value": company_name,
                "exact_match": exact_match,
                "exclude": False
            }],
            "limit": limit
        }
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/company/search",
                    headers=self.headers,
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
            
            companies = result.get("companies", [])
            logger.info(f"Found {len(companies)} companies")
            
            return companies
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Company search failed: {e.response.status_code}")
            if e.response.status_code == 401:
                raise ValueError("Authentication failed - check API key")
            elif e.response.status_code == 429:
                raise ValueError("Rate limit exceeded")
            raise
    
    # =========================================================================
    # People Search (Synchronous)
    # =========================================================================
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((
            httpx.TimeoutException,
            httpx.ConnectError
        )),
        reraise=True
    )
    def search_people(
        self,
        company_name: str = None,
        company_domain: str = None,
        person_linkedin_urls: Optional[List[str]] = None,
        title: Optional[str] = None,
        titles: Optional[List[str]] = None,
        excluded_titles: Optional[List[str]] = None,
        seniority_levels: Optional[List[str]] = None,
        person_locations: Optional[List[str]] = None,
        limit: int = 25,
        offset: Optional[int] = None,
        search_after: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search for people at a company.
        
        API: POST /people/search
        
        Args:
            company_name: Company name (less accurate than domain)
            company_domain: Company domain (e.g. 'anthropic.com') - more accurate than name
            person_linkedin_urls: Optional list of person LinkedIn profile URLs
            title: Optional single job title filter (partial match)
            titles: Optional list of job title filters (partial match)
            excluded_titles: Optional list of job titles to exclude
            seniority_levels: Optional list like ["Director", "VP", "C-Suite"]
            person_locations: Optional list of person locations (city/region/country)
            limit: Results per page (max 100)
            offset: Pagination offset (max 10,000)
            search_after: Pagination token (use for offset > 10k)
            
        Returns:
            Dict with:
                - people: List of person objects
                - total: Total matches
                - search_after: Next page token (if available)
                
        Example person object:
        {
            "id": "...",
            "full_name": "John Doe",
            "first_name": "John",
            "last_name": "Doe",
            "current_title": "VP of Engineering",
            "linkedin_url": "...",
            "location": {...},
            ...
        }
        """
        if company_domain:
            logger.info(f"Searching people at domain: {company_domain}")
        elif company_name:
            logger.info(f"Searching people at: {company_name}")
        elif person_linkedin_urls:
            logger.info(f"Searching people by LinkedIn URLs: {len(person_linkedin_urls)} URLs")
        else:
            raise ValueError("Provide company_name, company_domain, or person_linkedin_urls")
        
        # Acquire rate limit token
        self.rate_limiter.acquire()
        
        # Build filters - use domain if available (more accurate), otherwise use name
        filters = {}
        
        if company_domain:
            filters["current_company_domains"] = [{
                "value": company_domain,
                "exact_match": True,
                "exclude": False
            }]
        elif company_name:
            filters["current_company_names"] = [{
                "value": company_name,
                "exact_match": True,
                "exclude": False
            }]

        if person_linkedin_urls:
            clean_urls = [u.strip() for u in person_linkedin_urls if u and u.strip()]
            if clean_urls:
                filters["person_linkedin_urls"] = [{
                    "value": url,
                    "exact_match": True,
                    "exclude": False
                } for url in clean_urls]
        
        # Add title include/exclude filters.
        effective_titles = []
        if titles:
            effective_titles.extend(titles)
        elif title:
            effective_titles.append(title)

        effective_excluded_titles = excluded_titles or []

        effective_titles = [t.strip() for t in effective_titles if t and t.strip()]
        effective_excluded_titles = [t.strip() for t in effective_excluded_titles if t and t.strip()]

        title_filters = []
        if effective_titles:
            title_filters.extend([{
                "value": t,
                "exact_match": False,
                "exclude": False
            } for t in effective_titles])

        if effective_excluded_titles:
            title_filters.extend([{
                "value": t,
                "exact_match": False,
                "exclude": True
            } for t in effective_excluded_titles])

        if title_filters:
            filters["current_position_titles"] = title_filters
        
        # Add seniority filter if provided
        if seniority_levels:
            clean_seniority_levels = [s.strip() for s in seniority_levels if s and s.strip()]
            filters["current_position_seniority_level"] = [{
                "value": level,
                "exact_match": False,
                "exclude": False
            } for level in clean_seniority_levels]

        # Add person location filters if provided
        if person_locations:
            clean_locations = [loc.strip() for loc in person_locations if loc and loc.strip()]
            if clean_locations:
                filters["person_locations"] = [{
                    "value": loc,
                    "exact_match": False,
                    "exclude": False
                } for loc in clean_locations]
        
        # Build payload - filters at root level (not wrapped in "filters" key)
        payload = {
            **filters,  # Spread filters at root level
            "limit": min(limit, 100)  # Cap at 100
        }
        
        # Pagination
        if search_after:
            payload["search_after"] = search_after
        elif offset is not None:
            payload["offset"] = offset
        
        logger.info(f"🔍 People search request:")
        logger.info(f"  URL: {self.base_url}/people/search")
        logger.info(f"  Payload: {payload}")
        logger.debug("  Headers: {'Authorization': 'Bearer ***', 'Content-Type': 'application/json'}")
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/people/search",
                    headers=self.headers,
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
                
                # Log full response for debugging (first time only)
                import json
                logger.debug(f"📦 Full API Response: {json.dumps(result, indent=2)[:2000]}")
                
                # Log response structure
                logger.info(f"📦 API Response keys: {result.keys()}")
                if "metadata" in result:
                    logger.info(f"📊 Metadata: {result['metadata']}")
            
            people = result.get("people", [])
            metadata = result.get("metadata", {})
            total = metadata.get("total", 0)
            next_search_after = metadata.get("search_after")
            
            logger.info(f"Found {len(people)} people (total: {total})")
            
            # Debug: Show sample of companies in results
            if people and len(people) > 0:
                sample_companies = []
                for p in people[:3]:  # First 3 people
                    emp = p.get("employment", {})
                    curr = emp.get("current", {})
                    comp = curr.get("company", {})
                    comp_name = comp.get("name", "Unknown")
                    comp_domain = comp.get("domain", "No domain")
                    sample_companies.append(f"{comp_name} ({comp_domain})")
                logger.info(f"📋 Sample companies in results: {sample_companies}")
            
            # Check if domain doesn't exist in FullEnrich database
            # When a domain isn't found, API may return entire database (800M+ results)
            FULLENRICH_TOTAL_DB_SIZE = 800_000_000  # ~800M+ people
            if total > FULLENRICH_TOTAL_DB_SIZE:
                if company_domain:
                    logger.error(f"❌ Domain '{company_domain}' not found in FullEnrich database")
                    logger.error(f"   Returned {total:,} results (entire database)")
                    raise ValueError(f"Domain '{company_domain}' not found in FullEnrich database. Try a well-known company like Google, Microsoft, or Salesforce.")
                else:
                    logger.error(f"❌ Company '{company_name}' not found in FullEnrich database")
                    raise ValueError(f"Company '{company_name}' not found in FullEnrich database.")
            
            # Warn if no exact matches (but API didn't ignore filter)
            if total == 0 and len(people) > 0:
                if company_domain:
                    logger.warning(f"No employees found for domain '{company_domain}' in FullEnrich database (returned {len(people)} suggestions)")
                else:
                    logger.warning(f"No employees found for company '{company_name}' in FullEnrich database (returned {len(people)} suggestions)")
            
            return {
                "people": people,
                "total": total,
                "search_after": next_search_after,
                "has_more": next_search_after is not None
            }
            
        except httpx.HTTPStatusError as e:
            logger.error(f"People search failed: {e.response.status_code}")
            if e.response.status_code == 401:
                raise ValueError("Authentication failed - check API key")
            elif e.response.status_code == 429:
                raise ValueError("Rate limit exceeded")
            raise
    
    # =========================================================================
    # Bulk Enrichment (Asynchronous - webhook-based)
    # =========================================================================
    
    def build_enrichment_payload(
        self,
        contacts: List[Dict[str, Any]],
        webhook_url: str,
        batch_name: str = "Enrichment Batch",
        include_phones: bool = False
    ) -> Dict[str, Any]:
        """
        Build bulk enrichment payload.
        
        Args:
            contacts: List of contact dicts with keys:
                - first_name, last_name, company_name (required)
                - linkedin_url (optional but improves results)
                - domain (optional but recommended)
            webhook_url: Where FullEnrich will POST results
            batch_name: Batch description
            include_phones: Whether to enrich phone numbers (default: False, emails only)
            
        Returns:
            API request payload
        """
        # Build enrich_fields based on user preference
        enrich_fields = ["contact.emails"]  # Always include emails
        if include_phones:
            enrich_fields.append("contact.phones")
        
        logger.info(f"Enrichment fields: {enrich_fields}")
        
        datas = []
        
        for idx, contact in enumerate(contacts):
            # Skip contacts with empty required fields
            first_name = (contact.get("first_name") or "").strip()
            last_name = (contact.get("last_name") or "").strip()
            company_name = (contact.get("company_name") or "").strip()
            
            if not first_name or not last_name or not company_name:
                logger.warning(f"Skipping contact {idx}: missing required fields (first={first_name}, last={last_name}, company={company_name})")
                continue
            
            # Base payload - API expects first_name/last_name (with underscores)
            item = {
                "first_name": first_name,
                "last_name": last_name,
                "company_name": company_name,
                "enrich_fields": enrich_fields,  # Dynamic based on user choice
                "custom": {
                    "id": str(idx),
                    "original_first_name": first_name,
                    "original_last_name": last_name,
                    "original_company": company_name
                }
            }
            
            # Add domain if available (improves accuracy)
            if contact.get("domain"):
                item["domain"] = contact["domain"]
            
            # Add LinkedIn URL if available (best results)
            if contact.get("linkedin_url"):
                item["linkedin_url"] = contact["linkedin_url"]
                item["custom"]["has_linkedin"] = "true"
            else:
                item["custom"]["has_linkedin"] = "false"
            
            datas.append(item)
        
        payload = {
            "name": batch_name,
            "webhook_url": webhook_url,
            "data": datas  # API expects "data" not "datas"
        }
        
        return payload
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((
            httpx.TimeoutException,
            httpx.ConnectError
        )),
        reraise=True
    )
    def enrich_bulk(
        self,
        contacts: List[Dict[str, Any]],
        webhook_url: str,
        batch_name: str = "Enrichment Batch",
        include_phones: bool = False
    ) -> Union[str, Dict]:
        """
        Start bulk enrichment request.
        
        API: POST /contact/enrich/bulk
        
        Args:
            contacts: List of contacts (max 100)
            webhook_url: Webhook URL for results
            batch_name: Batch description
            include_phones: Whether to enrich phone numbers (default: False, emails only)
            
        Returns:
            enrichment_id (string) or full response dict if synchronous
            
        Processing time: 30-90 seconds per contact
        """
        if len(contacts) > BATCH_SIZE:
            raise ValueError(f"Maximum {BATCH_SIZE} contacts per batch")
        
        if not webhook_url:
            raise ValueError("webhook_url is required")
        
        enrichment_type = "emails + phones" if include_phones else "emails only"
        logger.info(f"Starting enrichment: {len(contacts)} contacts ({enrichment_type})")
        
        # Acquire rate limit token
        self.rate_limiter.acquire()
        
        # Build payload with enrich_fields based on user preference
        payload = self.build_enrichment_payload(contacts, webhook_url, batch_name, include_phones)
        logger.debug(f"Enrichment payload: {len(payload.get('data', []))} items")
        
        # Log first contact for debugging
        if payload.get("data"):
            logger.debug(f"Sample contact: {payload['data'][0]}")
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/contact/enrich/bulk",
                    headers=self.headers,
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
            
            # Extract enrichment ID
            enrichment_id = (
                result.get("enrichment_id") or
                result.get("id") or
                result.get("batch_id")
            )
            
            if enrichment_id:
                logger.info(f"Enrichment started: {enrichment_id}")
                return enrichment_id
            
            # Handle synchronous response
            if "datas" in result:
                logger.info("Enrichment completed synchronously")
                return result
            
            raise ValueError(f"Unexpected response: {result}")
            
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            try:
                error_detail = e.response.json()
                logger.error(f"Enrichment failed: {status} - {error_detail}")
            except:
                error_detail = e.response.text
                logger.error(f"Enrichment failed: {status} - {error_detail}")
            
            if status == 401:
                raise ValueError("Authentication failed - check API key")
            elif status == 429:
                raise ValueError("Rate limit exceeded")
            elif status == 402:
                raise ValueError("Insufficient credits")
            elif status == 400:
                raise ValueError(f"Bad request: {error_detail}")
            
            raise
    
    def get_enrichment_result(
        self,
        enrichment_id: str,
        force_results: bool = False
    ) -> Dict[str, Any]:
        """
        Poll enrichment status and get results.
        
        API: GET /contact/enrich/bulk/{enrichment_id}
        
        Args:
            enrichment_id: UUID of enrichment
            force_results: Force return of partial results (not recommended)
            
        Returns:
            {
                "status": "FINISHED" | "IN_PROGRESS" | "CREATED" | ...,
                "data": [...],  # Only present if FINISHED
                "name": "batch name",
                "created_at": "...",
                ...
            }
            
        Raises:
            ValueError: If enrichment not ready (400 status)
        """
        params = {}
        if force_results:
            params["forceResults"] = "true"
        
        try:
            # Note: GET enrichment uses v1 endpoint, not v2
            base_v1 = self.base_url.replace("/api/v2", "/api/v1")
            get_url = f"{base_v1}/contact/enrich/bulk/{enrichment_id}"
            
            logger.debug(f"Polling URL: {get_url}")
            
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(
                    get_url,
                    headers=self.headers,
                    params=params
                )
                response.raise_for_status()
                result = response.json()
                
                # Log response structure for debugging
                import json
                logger.info(f"GET enrichment response keys: {result.keys()}")
                if "datas" in result:
                    logger.info(f"Found {len(result['datas'])} enriched contacts in response")
                logger.debug(f"Full response: {json.dumps(result, indent=2)[:2000]}")
                
                return result
        
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            
            if status == 400:
                # Enrichment still in progress
                try:
                    error = e.response.json()
                    if error.get("code") == "error.enrichment.in_progress":
                        raise ValueError("Enrichment in progress - try again in 10 seconds")
                except:
                    pass
                raise ValueError(f"Enrichment not ready: {e.response.text}")
            
            elif status == 404:
                raise ValueError(f"Enrichment not found: {enrichment_id}")
            
            elif status == 401:
                raise ValueError("Authentication failed - check API key")
            
            raise


# =============================================================================
# Module Test
# =============================================================================

if __name__ == "__main__":
    print("FullEnrich Client Test")
    print("=" * 60)
    
    try:
        client = FullEnrichClient()
        
        # Test credit check
        credits = client.check_credits()
        print(f"✅ Credits: {credits}")
        
        # Test company search
        companies = client.search_companies("Anthropic", limit=3)
        print(f"✅ Found {len(companies)} companies")
        
        if companies:
            company = companies[0]
            print(f"   - {company.get('name')} ({company.get('domain')})")
        
        print("\n✅ Client initialized successfully")
        
    except Exception as e:
        print(f"❌ Error: {e}")
