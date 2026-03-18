"""
People Search Service

Orchestrates company search + people search. Results are kept in memory only
(session); nothing is written to the database until user enriches and saves.
"""

from typing import Dict, List, Any, Optional, Tuple

from ..fullenrich.client import FullEnrichClient
from ..fullenrich.mappers import PeopleMapper
from ..core.logging import setup_logger

logger = setup_logger(__name__)

# =============================================================================
# People Search Service
# =============================================================================

class PeopleSearchService:
    """
    Service for searching people at companies.
    
    Workflow (all in-memory, no DB):
    1. Search for company by name (FullEnrich API)
    2. Search for people at that company (FullEnrich API)
    3. Map results for UI
    4. Return (company_dict, people_list) for session state
    """
    
    def __init__(self):
        """Initialize service - no database dependency for search."""
        self.fullenrich = FullEnrichClient()
        self.people_mapper = PeopleMapper()
        logger.info("PeopleSearchService initialized (in-memory search only)")
    
    def search_company(self, company_name: str) -> Optional[Dict[str, Any]]:
        """
        Search for company by name. Returns first/best match from API.
        No database write.
        
        Args:
            company_name: Company name to search for
            
        Returns:
            Company dict with name, domain, id (from API), etc. or None
        """
        logger.info(f"Searching for company: {company_name}")
        
        companies = self.fullenrich.search_companies(
            company_name,
            exact_match=True,
            limit=5
        )
        
        if not companies:
            logger.warning(f"No companies found for: {company_name}")
            return None
        
        # Pick best match (exact name if possible)
        best = companies[0]
        for c in companies:
            if c.get("name", "").lower() == company_name.lower():
                best = c
                break
        
        # Return simple dict for UI and enrichment (no DB id)
        company_dict = {
            "id": best.get("id"),  # FullEnrich id, optional for session
            "name": best.get("name", ""),
            "domain": best.get("domain", ""),
            "linkedin_url": best.get("linkedin_url", ""),
            "employee_count": best.get("headcount"),
        }
        logger.info(f"Company resolved: {company_dict['name']} ({company_dict.get('domain')})")
        return company_dict
    
    def search_people(
        self,
        company_name: str,
        domain: Optional[str] = None,
        title: Optional[str] = None,
        titles: Optional[List[str]] = None,
        excluded_titles: Optional[List[str]] = None,
        seniority_levels: Optional[List[str]] = None,
        person_locations: Optional[List[str]] = None,
        limit: int = 50
    ) -> Tuple[Optional[Dict], List[Dict]]:
        """
        Search for people at a company. All results in memory only.
        
        Args:
            company_name: Company name
            domain: Optional domain (from accounts table) for better accuracy
            title: Optional single job title filter
            titles: Optional list of current position titles
            excluded_titles: Optional list of titles to exclude
            seniority_levels: Optional seniority filter
            person_locations: Optional person locations (city/region/country)
            limit: Target max results (auto-pagination in batches up to 100)
            
        Returns:
            Tuple of (company_dict, people_list). company_dict has name, domain, etc.
            people_list has full_name, first_name, last_name, current_title, linkedin_url, etc.
        """
        if domain:
            logger.info(f"Searching people at: {company_name} (domain: {domain})")
        else:
            logger.info(f"Searching people at: {company_name}")
        
        # If domain is provided, use it; if empty/missing, resolve via API
        if domain and domain.strip():
            # Use provided domain (from accounts table) - most accurate
            company = {
                "name": company_name,
                "domain": domain,
                "linkedin_url": "",
                "employee_count": None,
            }
            logger.info(f"Using domain from accounts table: {domain}")
        else:
            # No domain provided or empty - resolve company via FullEnrich API
            logger.info(f"No domain provided, resolving company via API: {company_name}")
            company = self.search_company(company_name)
            if not company:
                logger.error(f"Company not found: {company_name}")
                return None, []
            if company.get("domain"):
                logger.info(f"Resolved domain from API: {company.get('domain')}")
            else:
                logger.warning(f"No domain found for {company_name}, using company name (less accurate)")
        
        # Search people via API - use domain filter if we have a domain, otherwise use company name
        effective_titles = titles
        if not effective_titles and title:
            effective_titles = [title]

        target_count = max(1, int(limit or 25))
        collected_people: List[Dict[str, Any]] = []
        seen_ids = set()
        total = 0
        offset = 0
        search_after = None
        pages_fetched = 0

        while len(collected_people) < target_count:
            page_size = min(100, target_count - len(collected_people))

            request_kwargs: Dict[str, Any] = {
                "title": title,
                "titles": effective_titles,
                "excluded_titles": excluded_titles,
                "seniority_levels": seniority_levels,
                "person_locations": person_locations,
                "limit": page_size,
            }

            if company.get("domain"):
                request_kwargs["company_domain"] = company["domain"]
            else:
                request_kwargs["company_name"] = company["name"]

            if search_after:
                request_kwargs["search_after"] = search_after
            else:
                request_kwargs["offset"] = offset

            result = self.fullenrich.search_people(**request_kwargs)

            page_people = result.get("people", [])
            total = result.get("total", total)
            search_after = result.get("search_after")
            pages_fetched += 1

            if not page_people:
                break

            for person in page_people:
                dedupe_key = person.get("id") or person.get("linkedin_url")
                if dedupe_key and dedupe_key in seen_ids:
                    continue
                if dedupe_key:
                    seen_ids.add(dedupe_key)
                collected_people.append(person)
                if len(collected_people) >= target_count:
                    break

            if len(page_people) < page_size and not search_after:
                break

            if search_after is None:
                offset += page_size
                if total and offset >= total:
                    break

        people_raw = collected_people[:target_count]
        logger.info(f"Found {len(people_raw)} people (total: {total}, pages_fetched: {pages_fetched})")
        
        # Warn user if no exact matches found
        if total == 0 and len(people_raw) > 0:
            logger.warning(f"⚠️ FullEnrich returned suggestions but no exact matches for {company['name']} ({company.get('domain', 'no domain')}). These may be unrelated contacts.")
        
        # Map to display shape (no DB - use fake company_id for mapper compatibility)
        # PeopleMapper.map_person expects (person_data, company_id); we only need
        # full_name, first_name, last_name, current_title, linkedin_url, location_* for UI
        people_list = []
        for person in people_raw:
            # Extract nested employment data
            employment = person.get("employment", {})
            current = employment.get("current", {})
            # FullEnrich responses can return title in nested employment data
            # or as a top-level current_title depending on endpoint/version.
            title = current.get("title", "") or person.get("current_title", "")
            seniority = current.get("seniority", "")
            
            # Extract LinkedIn URL from social profiles
            social = person.get("social_profiles", {})
            linkedin = social.get("linkedin", {})
            linkedin_url = linkedin.get("url", "") or person.get("linkedin_url", "")
            
            # Simple in-memory shape for UI and for building enrichment payload later
            people_list.append({
                "id": person.get("id"),
                "fullenrich_person_id": person.get("id", ""),
                "full_name": person.get("full_name", ""),
                "first_name": person.get("first_name", ""),
                "last_name": person.get("last_name", ""),
                "title": title,
                "current_title": title,  # Keep both for compatibility
                "seniority_level": seniority,
                "linkedin_url": linkedin_url,
                "location_city": person.get("location", {}).get("city", ""),
                "location_region": person.get("location", {}).get("region", ""),
                "location_country": person.get("location", {}).get("country", ""),
                "company": current.get("company", {})
            })
        
        return company, people_list

    def search_people_by_linkedin_urls(
        self,
        linkedin_urls: List[str],
        limit: int = 100,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Search people directly by person LinkedIn profile URLs.

        Args:
            linkedin_urls: List of person LinkedIn profile URLs
            limit: Max number of people to return

        Returns:
            Tuple of (company_context, people_list)
        """
        clean_urls = [u.strip() for u in linkedin_urls if u and u.strip()]
        if not clean_urls:
            return {"name": "LinkedIn URL Search", "domain": ""}, []

        target_count = max(1, int(limit or 100))
        unique_urls = list(dict.fromkeys(clean_urls))
        collected_people: List[Dict[str, Any]] = []
        seen_ids = set()

        # FullEnrich people search limit is 100; chunk URL filters to keep payload bounded.
        for i in range(0, len(unique_urls), 100):
            url_batch = unique_urls[i:i + 100]
            result = self.fullenrich.search_people(
                person_linkedin_urls=url_batch,
                limit=min(100, target_count - len(collected_people)),
            )
            page_people = result.get("people", [])

            for person in page_people:
                dedupe_key = person.get("id") or person.get("linkedin_url")
                if dedupe_key and dedupe_key in seen_ids:
                    continue
                if dedupe_key:
                    seen_ids.add(dedupe_key)
                collected_people.append(person)
                if len(collected_people) >= target_count:
                    break

            if len(collected_people) >= target_count:
                break

        people_raw = collected_people[:target_count]

        people_list = []
        for person in people_raw:
            employment = person.get("employment", {})
            current = employment.get("current", {})
            title = current.get("title", "") or person.get("current_title", "")
            seniority = current.get("seniority", "")

            social = person.get("social_profiles", {})
            linkedin = social.get("linkedin", {})
            linkedin_url = linkedin.get("url", "") or person.get("linkedin_url", "")

            people_list.append({
                "id": person.get("id"),
                "fullenrich_person_id": person.get("id", ""),
                "full_name": person.get("full_name", ""),
                "first_name": person.get("first_name", ""),
                "last_name": person.get("last_name", ""),
                "title": title,
                "current_title": title,
                "seniority_level": seniority,
                "linkedin_url": linkedin_url,
                "location_city": person.get("location", {}).get("city", ""),
                "location_region": person.get("location", {}).get("region", ""),
                "location_country": person.get("location", {}).get("country", ""),
                "company": current.get("company", {}),
            })

        company_context = {
            "name": "LinkedIn URL Search",
            "domain": "",
            "linkedin_url": "",
            "employee_count": None,
        }
        logger.info(f"LinkedIn URL search mapped {len(people_list)} people")
        return company_context, people_list


# =============================================================================
# Module Test
# =============================================================================

if __name__ == "__main__":
    print("PeopleSearchService Test")
    print("=" * 60)
    try:
        service = PeopleSearchService()
        print("✅ Service initialized")
        company = service.search_company("Anthropic")
        if company:
            print(f"✅ Company: {company['name']}")
    except Exception as e:
        print(f"❌ Error: {e}")
