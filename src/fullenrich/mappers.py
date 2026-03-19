"""
Data Mappers

Map FullEnrich API responses to database schema.
Handles both search results and enrichment webhooks.

Reference: People-sense/data_mapper.py for enrichment mapping patterns.
"""

import uuid
import json
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

from ..core.config import ROLE_VALUE_KEYWORDS, ROLE_CHECK_ORDER
from ..core.logging import setup_logger

logger = setup_logger(__name__)

# =============================================================================
# Company Mapper (from company search)
# =============================================================================

class CompanyMapper:
    """Map company search results to fe_companies table."""
    
    @staticmethod
    def map_company(
        company_data: Dict[str, Any],
        search_input: str
    ) -> Dict[str, Any]:
        """
        Map FullEnrich company to fe_companies row.
        
        Args:
            company_data: Company object from /company/search
            search_input: Original search query
            
        Returns:
            Dict ready for database insert
        """
        headquarters = company_data.get("headquarters", {})
        
        return {
            "id": str(uuid.uuid4()),
            "company_name_input": search_input,
            "fullenrich_company_id": company_data.get("id", ""),
            "name": company_data.get("name", ""),
            "domain": company_data.get("domain", ""),
            "linkedin_url": company_data.get("linkedin_url", ""),
            "employee_count": company_data.get("headcount"),
            "year_founded": company_data.get("year_founded"),
            "industry": company_data.get("industry", ""),
            "description": company_data.get("description", ""),
            "headquarters": json.dumps(headquarters) if headquarters else None,
            "raw": json.dumps(company_data),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }


# =============================================================================
# People Mapper (from people search)
# =============================================================================

class PeopleMapper:
    """Map people search results to fe_people table."""
    
    @staticmethod
    def map_person(
        person_data: Dict[str, Any],
        company_id: str
    ) -> Dict[str, Any]:
        """
        Map FullEnrich person to fe_people row.
        
        Args:
            person_data: Person object from /people/search
            company_id: UUID of parent company
            
        Returns:
            Dict ready for database insert
        """
        location = person_data.get("location", {})
        
        return {
            "id": str(uuid.uuid4()),
            "fullenrich_person_id": person_data.get("id", ""),
            "company_id": company_id,
            "full_name": person_data.get("full_name", ""),
            "first_name": person_data.get("first_name", ""),
            "last_name": person_data.get("last_name", ""),
            "current_title": person_data.get("current_title", ""),
            "seniority_level": person_data.get("seniority_level", ""),
            "linkedin_url": person_data.get("linkedin_url", ""),
            "location_city": location.get("city", ""),
            "location_region": location.get("region", ""),
            "location_country": location.get("country", ""),
            "raw": json.dumps(person_data),
            "enriched": False,
            "created_at": datetime.now().isoformat()
        }


# =============================================================================
# Enrichment Mapper (from webhook response)
# =============================================================================

class EnrichmentMapper:
    """
    Map enrichment webhook payloads to database tables.
    
    Based on People-sense/data_mapper.py patterns but adapted for new schema.
    """
    
    def __init__(self):
        self.role_value_keywords = ROLE_VALUE_KEYWORDS
        self._account_ids = {}  # Cache: company_name -> account_id
    
    def map_enrichment_result(
        self,
        item: Dict[str, Any],
        enrichment_run_id: str,
        person_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Map single enrichment result to fe_enrichment_results table.
        
        Args:
            item: Single item from webhook payload["datas"]
            enrichment_run_id: UUID of enrichment run
            person_id: Optional person UUID to link
            
        Returns:
            Dict ready for database insert
        """
        custom = item.get("custom", {})
        contact = item.get("contact", {})
        profile = contact.get("profile", {})
        
        # Extract email
        email = contact.get("most_probable_email", "")
        email_status = contact.get("most_probable_email_status", "")
        
        if not email:
            emails = contact.get("emails", [])
            for e in emails:
                if e.get("status") in ["DELIVERABLE", "HIGH_PROBABILITY"]:
                    email = e.get("email", "")
                    email_status = e.get("status", "")
                    break
            if not email and emails:
                email = emails[0].get("email", "")
                email_status = emails[0].get("status", "")
        
        # Extract phone
        phones = contact.get("phones", [])
        phone = contact.get("most_probable_phone", "")
        phone_status = ""
        
        if not phone and phones:
            phone = phones[0].get("number", "")
            phone_status = phones[0].get("status", "")
        
        # Extract profile data (if LinkedIn URL was provided)
        first_name = profile.get("firstname", "") or custom.get("original_first_name", "")
        last_name = profile.get("lastname", "") or custom.get("original_last_name", "")
        full_name = f"{first_name} {last_name}".strip()
        
        position = profile.get("position", {})
        company = profile.get("company", {}) or position.get("company", {})
        
        return {
            "id": str(uuid.uuid4()),
            "enrichment_run_id": enrichment_run_id,
            "person_id": person_id,
            "email": email,
            "email_status": email_status,
            "phone": phone,
            "phone_status": phone_status,
            "full_name": full_name,
            "first_name": first_name,
            "last_name": last_name,
            "job_title": position.get("title", ""),
            "company_name": company.get("name", "") or custom.get("original_company", ""),
            "linkedin_url": profile.get("linkedin_url", ""),
            "linkedin_id": str(profile.get("linkedin_id", "")) if profile.get("linkedin_id") else "",
            "location": profile.get("location", ""),
            "headline": profile.get("headline", ""),
            "summary": profile.get("summary", ""),
            "custom": json.dumps(custom),
            "raw_webhook_payload": json.dumps(item),
            "created_at": datetime.now().isoformat()
        }
    
    def map_to_accounts_contacts(
        self,
        webhook_response: Dict[str, Any]
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Map enrichment webhook to accounts_test + contacts_test tables.
        
        This matches the People-sense pattern for final data storage.
        
        Args:
            webhook_response: Full webhook payload
            
        Returns:
            Tuple of (accounts_list, contacts_list)
        """
        # GET endpoint returns "data", webhook returns "datas" - support both
        datas = webhook_response.get("data") or webhook_response.get("datas", [])
        
        if not datas:
            logger.warning("No data in enrichment response")
            logger.debug(f"Response keys: {webhook_response.keys()}")
            return [], []
        
        accounts = []
        contacts = []
        seen_companies = set()
        
        timestamp = datetime.now().isoformat()
        
        for item in datas:
            # Map contact
            contact = self._map_contact(item, timestamp)
            
            if contact:
                contacts.append(contact)
                
                # Map account (deduplicated)
                company_name = contact.get("account", "")
                if company_name and company_name not in seen_companies:
                    account = self._map_account(item, timestamp)
                    if account and account.get("company_name"):
                        accounts.append(account)
                        seen_companies.add(company_name)
                        self._account_ids[company_name] = account.get("account_id")
        
        # Link contacts to accounts via account_id
        for contact in contacts:
            company = contact.get("account", "")
            if company in self._account_ids:
                contact["account_id"] = self._account_ids[company]
        
        logger.info(f"Mapped {len(accounts)} accounts, {len(contacts)} contacts")
        
        return accounts, contacts
    
    def _map_account(self, item: Dict[str, Any], timestamp: str) -> Dict[str, Any]:
        """Map to accounts_test table (matches People-sense schema)."""
        contact = item.get("contact", {})
        profile = contact.get("profile", {})
        position = profile.get("position", {})
        company = profile.get("company", {}) or position.get("company", {})
        headquarters = company.get("headquarters", {})
        custom = item.get("custom", {})
        
        company_name = (
            company.get("name") or
            contact.get("company_name") or
            custom.get("original_company", "")
        )
        
        if not company_name:
            return None
        
        metadata = {
            "source": "fullenrich",
            "enriched_at": timestamp,
            "industry": company.get("industry", ""),
            "company_type": company.get("type", "")
        }
        
        return {
            "account_id": str(uuid.uuid4()),
            "company_name": company_name,
            "company_description": company.get("description", ""),
            "website": company.get("website", ""),
            "linkedin_url": company.get("linkedin_url", ""),
            "employee_count": company.get("headcount"),
            "year_founded": company.get("year_founded"),
            "hq_city": headquarters.get("city", ""),
            "hq_region": headquarters.get("region", ""),
            "hq_country": headquarters.get("country", ""),
            "hq_country_code": headquarters.get("country_code", ""),
            "hq_postal_code": headquarters.get("postal_code", ""),
            "hq_address_line_1": headquarters.get("address_line_1", ""),
            "annual_revenue": None,
            "metadata": json.dumps(metadata),
            "created_at": timestamp,
            "updated_at": timestamp
        }
    
    def _map_contact(self, item: Dict[str, Any], timestamp: str) -> Dict[str, Any]:
        """Map to contacts_test table (matches People-sense schema)."""
        custom = item.get("custom", {})
        contact = item.get("contact", {})
        profile = contact.get("profile", {})
        position = profile.get("position", {})
        company = profile.get("company", {}) or position.get("company", {})
        phones = contact.get("phones", [])
        
        # Extract names
        first_name = (
            profile.get("firstname") or
            contact.get("firstname") or
            custom.get("original_first_name", "")
        )
        last_name = (
            profile.get("lastname") or
            contact.get("lastname") or
            custom.get("original_last_name", "")
        )
        full_name = f"{first_name} {last_name}".strip()
        
        # Extract email
        email = contact.get("most_probable_email", "")
        if not email:
            emails = contact.get("emails", [])
            for e in emails:
                if e.get("status") in ["DELIVERABLE", "HIGH_PROBABILITY"]:
                    email = e.get("email", "")
                    break
            if not email and emails:
                email = emails[0].get("email", "")
        
        # Extract company name
        company_name = (
            company.get("name") or
            contact.get("company_name") or
            custom.get("original_company", "")
        )
        
        # Extract LinkedIn URL
        linkedin_url = profile.get("linkedin_url", "")
        if not linkedin_url:
            for sm in contact.get("social_medias", []):
                if sm.get("type") == "LINKEDIN":
                    linkedin_url = sm.get("url", "")
                    break
        
        # Extract job title
        job_title = self._extract_job_title(profile, position, contact)
        
        # Extract phone
        phone = contact.get("most_probable_phone", "")
        if not phone and phones:
            phone = phones[0].get("number", "")
        
        # Job start date
        job_started = position.get("start_at", {})
        job_started_at = self._format_date(job_started)
        
        # Calculate role value
        role_value = self._get_role_value(job_title)
        
        # Metadata
        metadata = {
            "source": "fullenrich",
            "enriched_at": timestamp,
            "email_status": contact.get("most_probable_email_status", ""),
            "has_linkedin_url": custom.get("has_linkedin", "false") == "true"
        }
        
        return {
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "account": company_name,
            "company_name": company_name,  # For DB contacts table
            "metadata": metadata,  # Dict for JSONB; client can stringify if needed
            "created_at": timestamp,
            "account_id": None,  # Filled by SupabaseClient from accounts table
            "full_name": full_name,
            "job_title": job_title,
            "location": profile.get("location", ""),
            "linkedin_url": linkedin_url,
            "linkedin_id": str(profile.get("linkedin_id", "")) if profile.get("linkedin_id") else "",
            "sales_navigator_id": profile.get("sales_navigator_id", ""),
            "headline": profile.get("headline", ""),
            "summary": profile.get("summary", ""),
            "job_description": position.get("description", ""),
            "job_started_at": job_started_at,
            "phone": phone,
            "updated_at": timestamp,
            "role_value": role_value
        }
    
    def _format_date(self, date_obj: Dict) -> str:
        """Format date dict to YYYY-MM-DD."""
        if not date_obj:
            return ""
        
        year = date_obj.get("year")
        month = date_obj.get("month", 1)
        day = date_obj.get("day", 1)
        
        if not year:
            return ""
        
        return f"{year}-{month:02d}-{day:02d}"
    
    def _extract_job_title(self, profile: Dict, position: Dict, contact: Dict) -> str:
        """Extract job title from multiple sources (from People-sense pattern)."""
        # Try position title first
        title = position.get("title", "").strip()
        
        # Fallback to headline
        if not title:
            headline = profile.get("headline", "").strip()
            if headline:
                title = self._clean_headline(headline)
        
        # Fallback to contact-level
        if not title:
            title = contact.get("job_title", "").strip()
        
        return title
    
    def _clean_headline(self, headline: str) -> str:
        """Clean LinkedIn headline to extract job title (from People-sense)."""
        if not headline:
            return ""
        
        separators = [" at ", " @ ", " | ", " - ", ", "]
        title = headline
        
        for sep in separators:
            if sep in headline.lower():
                parts = headline.split(sep[0] if sep[0] != ' ' else sep)
                title = parts[0].strip()
                break
        
        return title
    
    def _get_role_value(self, job_title: str) -> Optional[int]:
        """Calculate role value from job title (from People-sense pattern)."""
        if not job_title:
            return None
        
        title_lower = job_title.lower().strip()
        
        if not title_lower:
            return None
        
        # Check in priority order
        for role_value in ROLE_CHECK_ORDER:
            keywords = self.role_value_keywords.get(role_value, [])
            for keyword in keywords:
                if len(keyword) <= 3:
                    if self._match_keyword(title_lower, keyword):
                        return role_value
                else:
                    if keyword in title_lower:
                        return role_value
        
        return None
    
    def _match_keyword(self, title: str, keyword: str) -> bool:
        """Match keyword with word boundaries."""
        import re
        pattern = r'\b' + re.escape(keyword) + r'\b'
        return bool(re.search(pattern, title))


# =============================================================================
# Module Test
# =============================================================================

if __name__ == "__main__":
    print("Mappers Module Test")
    print("=" * 60)
    
    # Test company mapping
    company_data = {
        "id": "comp123",
        "name": "Anthropic",
        "domain": "anthropic.com",
        "headcount": 150
    }
    
    mapper = CompanyMapper()
    company = mapper.map_company(company_data, "Anthropic")
    print(f"✅ Company mapped: {company['name']}")
    
    # Test role value
    enrichment_mapper = EnrichmentMapper()
    role = enrichment_mapper._get_role_value("VP of Engineering")
    print(f"✅ Role value for 'VP of Engineering': {role}")
    
    print("\n✅ Mappers test complete")
