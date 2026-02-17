# People Search + Enrichment - Complete Implementation Guide

**Version:** 1.0.0  
**Last Updated:** February 17, 2026  
**Tech Stack:** Python 3.10+, Streamlit, FullEnrich API v2, Supabase

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Project Structure](#4-project-structure)
5. [Core Components](#5-core-components)
6. [API Integration](#6-api-integration)
7. [Database Schema](#7-database-schema)
8. [Configuration](#8-configuration)
9. [User Workflows](#9-user-workflows)
10. [Data Flow](#10-data-flow)
11. [Error Handling](#11-error-handling)
12. [Testing](#12-testing)
13. [Deployment](#13-deployment)
14. [API Reference](#14-api-reference)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. Project Overview

### 1.1 Purpose

A Streamlit-based application that enables users to:
- **Search** for people at any company using domain-based filters
- **Enrich** contact information (emails and optionally phone numbers)
- **Save** enriched contacts to existing Supabase database

### 1.2 Key Features

- ✅ **Domain-First Search** - Search by company domain for accurate results
- ✅ **Existing Account Integration** - Dropdown with 1000+ accounts from your database
- ✅ **Selective Enrichment** - Choose email-only or email+phone (cost control)
- ✅ **API Polling** - Fast, reliable enrichment (60-120 seconds)
- ✅ **Credit Management** - Real-time credit balance and cost estimates
- ✅ **Existing Database Integration** - Works with your `accounts` and `contacts` tables
- ✅ **Rate Limiting** - Automatic 60 req/min throttling
- ✅ **Error Resilience** - Retry logic with exponential backoff

### 1.3 Design Philosophy

- **Simplicity First** - No complex webhook infrastructure, uses API polling
- **Cost Conscious** - Email-only enrichment by default (1 credit vs 11 credits)
- **Integration Friendly** - Uses existing database schema, no migrations required
- **Production Ready** - Comprehensive error handling, logging, and testing

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Streamlit UI (app.py)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Step 1:      │→ │ Step 2:      │→ │ Step 3:      │     │
│  │ Search       │  │ Select &     │  │ Preview &    │     │
│  │ People       │  │ Enrich       │  │ Save         │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    Service Layer                             │
│  ┌──────────────────────┐    ┌─────────────────────────┐   │
│  │ PeopleSearchService  │    │  EnrichmentService      │   │
│  │ - search_company()   │    │  - enrich_contacts()    │   │
│  │ - search_people()    │    │  - poll_for_results()   │   │
│  └──────────────────────┘    └─────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
         │                                   │
         ▼                                   ▼
┌──────────────────────────┐    ┌──────────────────────────┐
│  FullEnrich API Client   │    │   Supabase Client        │
│  - Company Search (v2)   │    │   - Read: accounts       │
│  - People Search (v2)    │    │   - Write: contacts      │
│  - Bulk Enrich (v2+v1)   │    │   - Optional: history    │
│  - Rate Limiting         │    │                          │
│  - Retry Logic           │    │                          │
└──────────────────────────┘    └──────────────────────────┘
         │                                   │
         ▼                                   ▼
┌──────────────────────────┐    ┌──────────────────────────┐
│  FullEnrich API v2       │    │   Supabase PostgreSQL    │
│  app.fullenrich.com      │    │   Your Database          │
└──────────────────────────┘    └──────────────────────────┘
```

### 2.2 Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| **UI Layer** (`app.py`) | User interaction, form handling, state management |
| **Service Layer** | Business logic, orchestration, data transformation |
| **API Client** (`FullEnrichClient`) | FullEnrich API communication, rate limiting, retries |
| **Database Client** (`SupabaseClient`) | Database operations, account lookups, contact persistence |
| **Mappers** | Transform API responses to internal data structures |
| **Config** | Environment variables, constants, validation |

### 2.3 Data Flow Patterns

**Search Flow:**
```
User Input → PeopleSearchService → FullEnrichClient 
  → FullEnrich API → Response Mapping → Session State
```

**Enrichment Flow:**
```
Selected People → EnrichmentService → FullEnrichClient
  → Start Enrichment (v2) → Poll Status (v1) → Get Results (v1)
  → Map Results → Save to Supabase → Display to User
```

---

## 3. Technology Stack

### 3.1 Core Technologies

| Technology | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.10+ | Primary language |
| **Streamlit** | 1.31+ | Web UI framework |
| **Poetry** | Latest | Dependency management |
| **Supabase** | 2.3.4+ | PostgreSQL database (Python client) |
| **httpx** | 0.27+ | HTTP client for API calls |
| **tenacity** | 8.2+ | Retry logic |

### 3.2 Key Dependencies

```toml
[tool.poetry.dependencies]
python = "^3.10"
httpx = "^0.27.0"          # Async HTTP client
tenacity = "^8.2.3"        # Retry decorator
supabase = "^2.3.4"        # Database client
streamlit = "^1.31.0"      # Web UI
pandas = "^2.2.0"          # Data display
python-dotenv = "^1.0.0"   # Config management
```

### 3.3 External Services

| Service | Purpose | Authentication |
|---------|---------|----------------|
| **FullEnrich API v2** | People search & enrichment | Bearer token |
| **FullEnrich API v1** | Get enrichment results | Bearer token |
| **Supabase** | PostgreSQL database | Service key |

---

## 4. Project Structure

### 4.1 Directory Layout

```
People_org/
├── app.py                          # Main Streamlit application
├── pyproject.toml                  # Poetry dependencies
├── .env                            # Environment variables (gitignored)
├── .env.example                    # Environment template
├── README.md                       # Project documentation
│
├── src/                            # Source code
│   ├── __init__.py
│   │
│   ├── core/                       # Core utilities
│   │   ├── __init__.py
│   │   ├── config.py               # Configuration management
│   │   ├── logging.py              # Logging setup
│   │   └── http.py                 # HTTP utilities
│   │
│   ├── fullenrich/                 # FullEnrich API integration
│   │   ├── __init__.py
│   │   ├── client.py               # API client (search, enrich, poll)
│   │   ├── mappers.py              # Response → internal data mappers
│   │   └── rate_limit.py           # Token bucket rate limiter
│   │
│   ├── services/                   # Business logic
│   │   ├── __init__.py
│   │   ├── people_search.py        # People search orchestration
│   │   └── enrichment.py           # Enrichment orchestration
│   │
│   └── db/                         # Database layer
│       ├── __init__.py
│       └── supabase_client.py      # Supabase operations
│
├── tests/                          # Test suite
│   ├── conftest.py                 # Pytest configuration
│   ├── test_config.py
│   ├── test_rate_limit.py
│   ├── test_mappers.py
│   ├── test_supabase_client.py
│   └── test_services.py
│
├── supabase/                       # Database resources
│   └── README_SCHEMA.md            # Database schema documentation
│
├── docs/                           # Documentation
│   └── IMPLEMENTATION_GUIDE.md     # This file
│
└── .streamlit/                     # Streamlit configuration
    └── config.toml                 # Server settings (port 8502, CORS)
```

### 4.2 File Responsibilities

| File | Lines | Purpose |
|------|-------|---------|
| `app.py` | ~700 | Streamlit UI, 3-step workflow, form handling |
| `src/core/config.py` | ~140 | Environment variables, validation, constants |
| `src/fullenrich/client.py` | ~650 | FullEnrich API calls, rate limiting, retries |
| `src/fullenrich/mappers.py` | ~500 | Transform API responses to DB schema |
| `src/services/people_search.py` | ~200 | People search business logic |
| `src/services/enrichment.py` | ~200 | Enrichment orchestration, polling |
| `src/db/supabase_client.py` | ~340 | Database operations, account lookups |

---

## 5. Core Components

### 5.1 Streamlit UI (`app.py`)

#### 5.1.1 Session State Management

```python
st.session_state = {
    'step': 1,                    # Current workflow step (1-3)
    'company_data': {...},        # Search result company info
    'search_results': [...],      # List of people found
    'selected_account': {...},    # Account from dropdown
    'selected_people': [...],     # People selected for enrichment
    'enrichment_results': {...}   # Enrichment API response
}
```

#### 5.1.2 Three-Step Workflow

**Step 1: Search People**
- Section 1: Select from existing accounts (dropdown with 1000+ accounts)
  - Account dropdown
  - Max results input
  - Job title filter
- Section 2: Enter company domain manually
  - Domain input (e.g., `google.com`)
  - Max results input
  - Job title filter
- Independent sections with separate parameters
- Priority: Use Section 1 if account selected, else Section 2

**Step 2: Select & Enrich**
- Display search results in table
- Select All checkbox (simplified selection)
- Enrichment options:
  - 📧 Include Emails (always on, disabled checkbox)
  - 📱 Include Phone Numbers (opt-in checkbox, default: unchecked)
- Cost estimate based on selection
- Enrich button

**Step 3: Preview & Save**
- Preview enriched data in table
- Company and contact statistics
- Save to database button
- Success/error feedback

#### 5.1.3 Key UI Functions

```python
def render_search_step():
    """Render Step 1 - Search form with two independent sections"""
    
def run_people_search(company_name, title, limit, domain):
    """Execute search via PeopleSearchService"""
    
def render_enrichment_step():
    """Render Step 2 - Selection and enrichment options"""
    
def run_enrichment(people, company, include_phones):
    """Execute enrichment with API polling"""
    
def render_preview_step():
    """Render Step 3 - Preview and save to database"""
```

---

### 5.2 FullEnrich API Client (`src/fullenrich/client.py`)

#### 5.2.1 Client Initialization

```python
class FullEnrichClient:
    def __init__(self):
        self.base_url = "https://app.fullenrich.com/api/v2"
        self.api_key = FULLENRICH_API_KEY
        self.rate_limiter = get_rate_limiter()  # 60 req/min
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.timeout = httpx.Timeout(30.0)
```

#### 5.2.2 Company Search

```python
def search_company(self, company_name: str, limit: int = 10) -> List[Dict]:
    """
    Search for companies by name.
    
    API: POST /api/v2/company/search
    Returns: List of {id, name, domain, linkedin_url, headcount, ...}
    """
    payload = {
        "name": company_name,
        "limit": limit
    }
    # Rate limiting, retry logic, error handling
```

#### 5.2.3 People Search

```python
def search_people(
    self, 
    company_domain: str,
    title: Optional[str] = None,
    limit: int = 50
) -> Tuple[Dict, List[Dict]]:
    """
    Search for people at a company by domain.
    
    API: POST /api/v2/people/search
    
    CRITICAL: Filters must be at root level, NOT nested in "filters" key
    
    Correct payload structure:
    {
        "current_company_domains": ["google.com"],
        "current_title": "engineer",
        "limit": 50,
        "offset": 0
    }
    
    Returns:
    - metadata: {total, search_after, ...}
    - results: List of people
    """
    filters = {"current_company_domains": [company_domain]}
    if title:
        filters["current_title"] = title
        
    payload = {
        **filters,  # Unpack filters at root level
        "limit": limit,
        "offset": 0
    }
```

**Common Pitfall:**
```python
# ❌ WRONG - This returns entire database (839M results)
payload = {
    "filters": {"current_company_domains": ["google.com"]},
    "limit": 50
}

# ✅ CORRECT - Filters at root level
payload = {
    "current_company_domains": ["google.com"],
    "limit": 50
}
```

#### 5.2.4 Bulk Enrichment

```python
def enrich_bulk(
    self,
    contacts: List[Dict],
    webhook_url: str,
    batch_name: str,
    include_phones: bool = False
) -> str:
    """
    Start bulk enrichment.
    
    API: POST /api/v2/contact/enrich/bulk
    
    Returns: enrichment_id (UUID)
    Processing time: 30-90 seconds
    """
    payload = self.build_enrichment_payload(
        contacts, webhook_url, batch_name, include_phones
    )
    
    response = httpx.post(
        f"{self.base_url}/contact/enrich/bulk",
        json=payload,
        headers=self.headers,
        timeout=self.timeout
    )
    
    return response.json()["enrichment_id"]
```

#### 5.2.5 Enrichment Payload Structure

```python
def build_enrichment_payload(
    self,
    contacts: List[Dict],
    webhook_url: str,
    batch_name: str,
    include_phones: bool = False
) -> Dict:
    """
    Build enrichment payload with dynamic enrich_fields.
    
    Key fields per contact:
    - first_name, last_name (required)
    - company_name (required)
    - domain (recommended for accuracy)
    - linkedin_url (optional, improves results by 5-60%)
    - enrich_fields: ["contact.emails"] or ["contact.emails", "contact.phones"]
    """
    enrich_fields = ["contact.emails"]
    if include_phones:
        enrich_fields.append("contact.phones")
    
    data = []
    for contact in contacts:
        item = {
            "first_name": contact["first_name"],
            "last_name": contact["last_name"],
            "company_name": contact["company_name"],
            "enrich_fields": enrich_fields,
            "custom": {
                "original_company": contact["company_name"],
                "original_domain": contact.get("domain", "")
            }
        }
        
        if contact.get("domain"):
            item["domain"] = contact["domain"]
            
        if contact.get("linkedin_url"):
            item["linkedin_url"] = contact["linkedin_url"]
            
        data.append(item)
    
    return {
        "name": batch_name,
        "webhook_url": webhook_url,
        "data": data
    }
```

#### 5.2.6 Polling for Results

```python
def get_enrichment_result(
    self,
    enrichment_id: str,
    force_results: bool = False
) -> Dict:
    """
    Poll for enrichment results.
    
    API: GET /api/v1/contact/enrich/bulk/{enrichment_id}
    
    NOTE: Uses v1 endpoint, not v2!
    
    Returns:
    {
        "id": "uuid",
        "name": "Batch name",
        "status": "FINISHED" | "IN_PROGRESS" | "FAILED",
        "datas": [...],  # Enriched contacts (note: "datas" not "data")
        "cost": {"credits": 11}
    }
    """
    base_v1 = self.base_url.replace("/api/v2", "/api/v1")
    url = f"{base_v1}/contact/enrich/bulk/{enrichment_id}"
    
    params = {}
    if force_results:
        params["forceResults"] = "true"
    
    response = httpx.get(url, headers=self.headers, params=params)
    return response.json()
```

**Important API Version Notes:**
- **Enrich (POST)**: Uses `/api/v2/contact/enrich/bulk`
- **Get Results (GET)**: Uses `/api/v1/contact/enrich/bulk/{id}` ⚠️ Different version!
- Response field: `"datas"` (with 's') in v1, `"data"` in v2

---

### 5.3 People Search Service (`src/services/people_search.py`)

#### 5.3.1 Service Responsibilities

- Resolve company by name or use provided domain
- Call FullEnrich people search API
- Map raw API response to clean internal format
- Extract nested employment and social profile data

#### 5.3.2 Main Method

```python
class PeopleSearchService:
    def search_people(
        self,
        company_name: str,
        domain: Optional[str] = None,
        title: Optional[str] = None,
        limit: int = 50
    ) -> Tuple[Optional[Dict], List[Dict]]:
        """
        Search for people at a company.
        
        Args:
            company_name: Company name (for display)
            domain: Company domain (if known, skips company search)
            title: Job title filter (optional)
            limit: Max results
            
        Returns:
            (company_dict, people_list)
            
        People dict structure:
        {
            "full_name": "John Doe",
            "first_name": "John",
            "last_name": "Doe",
            "current_title": "Software Engineer",
            "linkedin_url": "https://linkedin.com/in/johndoe",
            "location_city": "San Francisco",
            "location_region": "California",
            "company": {"name": "Google", "domain": "google.com"}
        }
        """
        # If domain provided, skip company resolution
        if domain and domain.strip():
            company = {
                "name": company_name,
                "domain": domain,
                "linkedin_url": "",
                "employee_count": None
            }
        else:
            # Resolve company via API
            company = self.search_company(company_name)
            if not company:
                return None, []
        
        # Search people
        metadata, results = self.fullenrich.search_people(
            company_domain=company["domain"],
            title=title,
            limit=limit
        )
        
        # Map results
        people = []
        for person_data in results:
            person = self._map_person(person_data)
            people.append(person)
        
        return company, people
```

#### 5.3.3 Person Data Mapping

```python
def _map_person(self, person_data: Dict) -> Dict:
    """
    Extract person data from nested API response.
    
    API Response Structure:
    {
        "person": {
            "full_name": "...",
            "first_name": "...",
            "last_name": "...",
            "employment": {
                "current": {
                    "title": "Software Engineer",
                    "company": {...}
                }
            },
            "social_profiles": {
                "linkedin": {
                    "url": "..."
                }
            },
            "location": {...}
        }
    }
    """
    person = person_data.get("person", {})
    employment = person.get("employment", {}).get("current", {})
    social = person.get("social_profiles", {}).get("linkedin", {})
    location = person.get("location", {})
    
    return {
        "full_name": person.get("full_name", ""),
        "first_name": person.get("first_name", ""),
        "last_name": person.get("last_name", ""),
        "current_title": employment.get("title", ""),
        "linkedin_url": social.get("url", ""),
        "location_city": location.get("city", ""),
        "location_region": location.get("region", ""),
        "company": employment.get("company", {})
    }
```

---

### 5.4 Enrichment Service (`src/services/enrichment.py`)

#### 5.4.1 Enrichment Workflow

```python
class EnrichmentService:
    def enrich_contacts(
        self,
        contacts: List[Dict],
        webhook_url: str,
        batch_name: str,
        include_phones: bool = False
    ) -> Dict:
        """
        Start enrichment and return enrichment_id.
        
        Workflow:
        1. Validate contacts
        2. Call FullEnrich API
        3. Return enrichment_id for polling
        """
        enrichment_id = self.fullenrich.enrich_bulk(
            contacts=contacts,
            webhook_url=webhook_url,
            batch_name=batch_name,
            include_phones=include_phones
        )
        
        return {
            "enrichment_id": enrichment_id,
            "contacts_count": len(contacts)
        }
```

#### 5.4.2 API Polling Implementation

```python
def poll_for_results(
    self,
    enrichment_id: str,
    timeout: int = 120,
    poll_interval: int = 10
) -> Optional[Dict]:
    """
    Poll FullEnrich API for enrichment results.
    
    Args:
        enrichment_id: UUID from enrich_bulk()
        timeout: Max wait time in seconds (default: 120)
        poll_interval: Seconds between polls (default: 10)
        
    Returns:
        Full enrichment response or None if timeout
        
    Status Values:
        - IN_PROGRESS: Still enriching
        - FINISHED: Complete, results ready
        - CANCELED: User canceled
        - CREDITS_INSUFFICIENT: Out of credits
    """
    import time
    
    start_time = time.time()
    elapsed = 0
    
    while elapsed < timeout:
        result = self.fullenrich.get_enrichment_result(enrichment_id)
        status = result.get("status", "UNKNOWN")
        
        logger.info(f"Status: {status} ({elapsed}s elapsed)")
        
        if status == "FINISHED":
            return result
        elif status in ["CANCELED", "CREDITS_INSUFFICIENT"]:
            logger.error(f"Enrichment failed: {status}")
            return None
        
        # Wait and retry
        time.sleep(poll_interval)
        elapsed = int(time.time() - start_time)
    
    logger.error(f"Enrichment timed out after {timeout}s")
    return None
```

**Why Polling Instead of Webhooks:**
- ✅ Simpler deployment (no webhook server, no tunneling)
- ✅ More reliable (no network issues with webhook delivery)
- ✅ Faster user experience (60-120s vs 300s webhook timeout)
- ✅ No infrastructure dependencies (ngrok/cloudflared)

---

### 5.5 Supabase Client (`src/db/supabase_client.py`)

#### 5.5.1 Database Tables

**Existing Tables (Read-Only):**
- `accounts` - Your existing accounts table
  - `account_id` (UUID, PK)
  - `company_name` (TEXT)
  - `account_domain` (TEXT, UNIQUE)
  - `linkedin_url`, `employee_count` (optional)

**Write Tables:**
- `contacts` - Your existing contacts table
  - `id` (UUID, PK)
  - `email` (TEXT NOT NULL UNIQUE) ⚠️ Required for insert
  - `first_name`, `last_name`, `full_name`
  - `company_name`, `account_id` (FK to accounts)
  - `job_title`, `location`, `phone`
  - `linkedin_url`, `linkedin_id`, `sales_navigator_id`
  - `headline`, `summary`, `job_description`
  - `role_value` (INT, FK to roles table)
  - `metadata` (JSONB)
  - `created_at`, `updated_at`

**Optional:**
- `enrichment_history` - Enrichment run tracking
  - `id`, `enrichment_id`, `batch_name`, `contacts_count`
  - `status`, `credits_used`, `created_at`

#### 5.5.2 Key Methods

```python
class SupabaseClient:
    def get_accounts(self, limit: int = 5000) -> List[Dict]:
        """
        Load accounts for UI dropdown.
        Returns: List of {account_id, company_name, account_domain, ...}
        """
        
    def get_account_id_by_company_name(self, company_name: str) -> Optional[str]:
        """
        Lookup account_id by company_name for linking contacts.
        Uses cache to avoid repeated queries.
        """
        
    def upsert_contacts(self, contacts: List[Dict]) -> int:
        """
        Insert or update contacts in bulk.
        
        Upsert strategy:
        - If email exists: UPDATE
        - If email new: INSERT
        
        Skips contacts without email (schema requires NOT NULL).
        Returns: Number of contacts successfully saved
        """
        
    def update_enrichment_history(self, enrichment_data: Dict):
        """
        Record enrichment run for audit trail (optional).
        """
```

#### 5.5.3 Contact Data Mapping

```python
def _contact_to_row(self, contact: Dict) -> Dict:
    """
    Map enrichment result to contacts table schema.
    
    Input (from EnrichmentMapper):
    {
        "email": "john@company.com",
        "first_name": "John",
        "last_name": "Doe",
        "company_name": "Google",
        "linkedin_url": "...",
        "phones": ["+1234567890"],
        "metadata": {...}
    }
    
    Output (contacts table row):
    {
        "email": "john@company.com",
        "first_name": "John",
        "last_name": "Doe",
        "full_name": "John Doe",
        "company_name": "Google",
        "account_id": "uuid-from-accounts-table",
        "job_title": "...",
        "phone": "+1234567890",
        "linkedin_url": "...",
        "role_value": 4,  # Calculated from title
        "metadata": {...},  # JSONB
        "created_at": "2026-02-17T...",
        "updated_at": "2026-02-17T..."
    }
    """
    # Resolve account_id by company_name
    account_id = None
    if contact.get("company_name"):
        account_id = self.get_account_id_by_company_name(
            contact["company_name"]
        )
    
    # Calculate role_value from job title
    role_value = self._calculate_role_value(contact.get("job_title", ""))
    
    # Extract first phone if available
    phones = contact.get("phones", [])
    phone = phones[0] if phones else None
    
    return {
        "email": contact["email"],
        "first_name": contact.get("first_name", ""),
        "last_name": contact.get("last_name", ""),
        "full_name": f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip(),
        "company_name": contact.get("company_name", ""),
        "account_id": account_id,
        "job_title": contact.get("job_title", ""),
        "location": contact.get("location", ""),
        "phone": phone,
        "linkedin_url": contact.get("linkedin_url", ""),
        "linkedin_id": contact.get("linkedin_id", ""),
        "headline": contact.get("headline", ""),
        "summary": contact.get("summary", ""),
        "role_value": role_value,
        "metadata": contact.get("metadata", {}),
        "updated_at": datetime.now().isoformat()
    }
```

---

### 5.6 Data Mappers (`src/fullenrich/mappers.py`)

#### 5.6.1 Purpose

Transform FullEnrich API responses into internal data structures that match database schema.

#### 5.6.2 Enrichment Mapper

```python
class EnrichmentMapper:
    def map_to_accounts_contacts(
        self, 
        enrichment_response: Dict
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Map enrichment response to (accounts, contacts) lists.
        
        Input: Full enrichment API response
        Output: ([], contacts) - We don't create accounts
        
        Handles both response formats:
        - "data": [...] (from GET endpoint)
        - "datas": [...] (from webhook)
        """
        # Support both field names
        datas = enrichment_response.get("data") or enrichment_response.get("datas", [])
        
        if not datas:
            return [], []
        
        contacts = []
        for item in datas:
            contact = self._map_contact(item)
            if contact:
                contacts.append(contact)
        
        return [], contacts  # Empty accounts list
```

#### 5.6.3 Contact Mapping

```python
def _map_contact(self, item: Dict, timestamp: str) -> Optional[Dict]:
    """
    Map single enrichment item to contact dict.
    
    API Response Structure:
    {
        "contact": {
            "firstname": "John",
            "lastname": "Doe",
            "domain": "company.com",
            "most_probable_email": "john@company.com",
            "emails": [{"email": "...", "status": "DELIVERABLE"}],
            "phones": [{"number": "+1...", "region": "US"}],
            "profile": {
                "linkedin_id": 123,
                "linkedin_url": "...",
                "headline": "...",
                "summary": "...",
                "position": {
                    "title": "Engineer",
                    "company": {"name": "Google"}
                }
            }
        },
        "custom": {"original_company": "..."}
    }
    
    Output:
    {
        "email": "john@company.com",
        "first_name": "John",
        "last_name": "Doe",
        "full_name": "John Doe",
        "company_name": "Google",
        "job_title": "Engineer",
        "location": "San Francisco, CA",
        "phones": ["+1234567890"],
        "linkedin_url": "...",
        "linkedin_id": "123",
        "headline": "...",
        "summary": "...",
        "metadata": {...}
    }
    """
    contact = item.get("contact", {})
    profile = contact.get("profile", {})
    position = profile.get("position", {})
    company = position.get("company", {})
    custom = item.get("custom", {})
    
    # Must have email
    email = contact.get("most_probable_email", "")
    if not email:
        return None
    
    # Extract phones
    phones = []
    for phone_obj in contact.get("phones", []):
        if phone_obj.get("number"):
            phones.append(phone_obj["number"])
    
    return {
        "email": email,
        "first_name": contact.get("firstname", ""),
        "last_name": contact.get("lastname", ""),
        "full_name": f"{contact.get('firstname', '')} {contact.get('lastname', '')}".strip(),
        "company_name": company.get("name", "") or custom.get("original_company", ""),
        "job_title": position.get("title", ""),
        "location": profile.get("location", ""),
        "phones": phones,
        "linkedin_url": profile.get("linkedin_url", ""),
        "linkedin_id": str(profile.get("linkedin_id", "")),
        "sales_navigator_id": profile.get("sales_navigator_id", ""),
        "headline": profile.get("headline", ""),
        "summary": profile.get("summary", ""),
        "metadata": {
            "custom": custom,
            "enrichment_date": timestamp
        }
    }
```

---

### 5.7 Rate Limiting (`src/fullenrich/rate_limit.py`)

#### 5.7.1 Token Bucket Implementation

```python
class TokenBucket:
    """
    Token bucket rate limiter for FullEnrich API (60 req/min).
    
    How it works:
    - Bucket holds max 60 tokens
    - Refills at 1 token/second (60/min)
    - Each API call consumes 1 token
    - If no tokens available, blocks until refill
    """
    
    def __init__(self, capacity: int = 60, refill_rate: float = 1.0):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate
        self.last_refill = time.time()
        self.lock = threading.Lock()
    
    def acquire(self, tokens: int = 1, block: bool = True):
        """
        Acquire token(s) for API call.
        Blocks if necessary until tokens available.
        """
        with self.lock:
            self._refill()
            
            while self.tokens < tokens:
                if not block:
                    return False
                
                wait_time = (tokens - self.tokens) / self.refill_rate
                time.sleep(wait_time)
                self._refill()
            
            self.tokens -= tokens
            return True
    
    def _refill(self):
        """Add tokens based on time elapsed."""
        now = time.time()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_rate
        
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now
```

#### 5.7.2 Usage

```python
# Singleton instance
_rate_limiter = None

def get_rate_limiter() -> TokenBucket:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = TokenBucket(
            capacity=RATE_LIMIT_PER_MINUTE,
            refill_rate=RATE_LIMIT_PER_MINUTE / 60.0
        )
    return _rate_limiter

# In FullEnrichClient
def enrich_bulk(self, ...):
    # Acquire token before making request
    self.rate_limiter.acquire()
    
    response = httpx.post(...)
```

---

## 6. API Integration

### 6.1 FullEnrich API Overview

| Endpoint | Method | Version | Purpose |
|----------|--------|---------|---------|
| `/company/search` | POST | v2 | Search companies by name |
| `/people/search` | POST | v2 | Search people by domain/title |
| `/contact/enrich/bulk` | POST | v2 | Start bulk enrichment |
| `/contact/enrich/bulk/{id}` | GET | v1 ⚠️ | Get enrichment results |

### 6.2 Authentication

```http
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json
```

### 6.3 Rate Limits

- **60 requests per minute** (all endpoints)
- Implemented via token bucket algorithm
- Automatic throttling in client

### 6.4 API Request Examples

#### 6.4.1 Company Search

```http
POST https://app.fullenrich.com/api/v2/company/search
Authorization: Bearer {API_KEY}
Content-Type: application/json

{
  "name": "Google",
  "limit": 10
}
```

**Response:**
```json
{
  "companies": [
    {
      "id": "12345",
      "name": "Google LLC",
      "domain": "google.com",
      "linkedin_url": "https://linkedin.com/company/google",
      "headcount": 150000,
      "industry": "Technology"
    }
  ]
}
```

#### 6.4.2 People Search

```http
POST https://app.fullenrich.com/api/v2/people/search
Authorization: Bearer {API_KEY}
Content-Type: application/json

{
  "current_company_domains": ["google.com"],
  "current_title": "engineer",
  "limit": 50,
  "offset": 0
}
```

**Response:**
```json
{
  "metadata": {
    "total": 2500,
    "search_after": "cursor_token",
    "limit": 50
  },
  "results": [
    {
      "person": {
        "full_name": "John Doe",
        "first_name": "John",
        "last_name": "Doe",
        "employment": {
          "current": {
            "title": "Software Engineer",
            "company": {
              "name": "Google",
              "domain": "google.com"
            }
          }
        },
        "social_profiles": {
          "linkedin": {
            "url": "https://linkedin.com/in/johndoe"
          }
        },
        "location": {
          "city": "San Francisco",
          "region": "California"
        }
      }
    }
  ]
}
```

#### 6.4.3 Start Enrichment

```http
POST https://app.fullenrich.com/api/v2/contact/enrich/bulk
Authorization: Bearer {API_KEY}
Content-Type: application/json

{
  "name": "Batch 2026-02-17 18:00",
  "webhook_url": "https://example.com/webhook",
  "data": [
    {
      "first_name": "John",
      "last_name": "Doe",
      "company_name": "Google",
      "domain": "google.com",
      "linkedin_url": "https://linkedin.com/in/johndoe",
      "enrich_fields": ["contact.emails"],
      "custom": {
        "id": "0",
        "original_company": "Google"
      }
    }
  ]
}
```

**Response:**
```json
{
  "enrichment_id": "83779b22-fa52-4f29-94d8-79c8acc59953"
}
```

#### 6.4.4 Get Enrichment Results

```http
GET https://app.fullenrich.com/api/v1/contact/enrich/bulk/83779b22-fa52-4f29-94d8-79c8acc59953
Authorization: Bearer {API_KEY}
```

**Response:**
```json
{
  "id": "83779b22-fa52-4f29-94d8-79c8acc59953",
  "name": "Batch 2026-02-17 18:00",
  "status": "FINISHED",
  "datas": [
    {
      "contact": {
        "firstname": "John",
        "lastname": "Doe",
        "domain": "google.com",
        "most_probable_email": "john.doe@google.com",
        "most_probable_email_status": "DELIVERABLE",
        "emails": [
          {
            "email": "john.doe@google.com",
            "status": "DELIVERABLE"
          }
        ],
        "phones": [],
        "profile": {
          "linkedin_id": 123456,
          "linkedin_url": "https://linkedin.com/in/johndoe",
          "headline": "Software Engineer at Google",
          "location": "San Francisco, CA"
        }
      },
      "custom": {
        "id": "0",
        "original_company": "Google"
      }
    }
  ],
  "cost": {
    "credits": 1
  }
}
```

### 6.5 Error Handling

#### 6.5.1 HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Process response |
| 400 | Bad Request | Check payload format |
| 401 | Unauthorized | Verify API key |
| 402 | Payment Required | Out of credits |
| 404 | Not Found | Check endpoint URL |
| 429 | Rate Limit | Wait and retry (handled automatically) |
| 500 | Server Error | Retry with backoff |

#### 6.5.2 Retry Strategy

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((
        httpx.TimeoutException,
        httpx.ConnectError
    ))
)
def api_call(...):
    # Automatic retry on timeout/connection errors
    # 3 attempts with exponential backoff: 4s, 8s, 10s
```

### 6.6 Credits & Pricing

| Operation | Credits | Notes |
|-----------|---------|-------|
| Email enrichment | 1 | Per contact |
| Phone enrichment | 10 | Per contact (optional) |
| Company search | 0 | Free |
| People search | 0 | Free |

**Cost Examples:**
- 10 contacts, email only: **10 credits**
- 10 contacts, email + phone: **110 credits** (10 × 11)
- 100 contacts, email only: **100 credits**

---

## 7. Database Schema

### 7.1 Integration Strategy

**Philosophy:** Use existing tables, minimal changes

- ✅ Read from `accounts` table (existing)
- ✅ Write to `contacts` table (existing)
- ✅ Optional `enrichment_history` for audit trail

### 7.2 Accounts Table (Read-Only)

```sql
CREATE TABLE accounts (
    account_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name TEXT NOT NULL,
    account_domain TEXT NOT NULL UNIQUE,
    linkedin_url TEXT,
    employee_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Usage:**
- UI dropdown: Load 1000-5000 accounts
- Domain extraction: Get `account_domain` for accurate search
- Account linking: Resolve `account_id` by `company_name` when saving contacts

### 7.3 Contacts Table (Read-Write)

```sql
CREATE TABLE contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL UNIQUE,  -- Required for upsert
    first_name TEXT,
    last_name TEXT,
    full_name TEXT,
    company_name TEXT,
    account_id UUID REFERENCES accounts(account_id),
    job_title TEXT,
    location TEXT,
    phone TEXT,
    linkedin_url TEXT,
    linkedin_id TEXT,
    sales_navigator_id TEXT,
    headline TEXT,
    summary TEXT,
    job_description TEXT,
    job_started_at TIMESTAMPTZ,
    job_ended_at TIMESTAMPTZ,
    role_value INTEGER REFERENCES roles(role_value),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_contacts_email ON contacts(email);
CREATE INDEX idx_contacts_account_id ON contacts(account_id);
CREATE INDEX idx_contacts_company_name ON contacts(company_name);
```

**Upsert Logic:**
```python
# Insert or update based on email
.upsert(
    contacts_data,
    on_conflict="email",  # Conflict resolution
    returning="id"
)
```

### 7.4 Enrichment History (Optional)

```sql
CREATE TABLE enrichment_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enrichment_id TEXT NOT NULL UNIQUE,
    batch_name TEXT,
    contacts_count INTEGER,
    status TEXT,
    credits_used INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Purpose:** Track enrichment runs for audit/reporting

### 7.5 Role Value Mapping

```python
ROLE_VALUE_KEYWORDS = {
    6: ["president", "chairman", "board member"],      # Executive
    1: ["ceo", "cto", "cfo", "chief", "founder"],     # C-Suite
    3: ["vice president", "vp", "director", "head"],  # VP/Director
    2: ["manager", "team lead", "supervisor"],        # Manager
    4: ["senior", "staff", "engineer", "analyst"],    # IC Senior
    5: ["junior", "intern", "associate", "entry"]     # IC Junior
}
```

**Calculation:**
```python
def _calculate_role_value(title: str) -> Optional[int]:
    if not title:
        return None
    
    title_lower = title.lower()
    
    # Check in priority order
    for role_value in [6, 3, 1, 2, 4, 5]:
        keywords = ROLE_VALUE_KEYWORDS[role_value]
        if any(keyword in title_lower for keyword in keywords):
            return role_value
    
    return None
```

---

## 8. Configuration

### 8.1 Environment Variables

#### 8.1.1 `.env` File Structure

```bash
# FullEnrich API
FULLENRICH_API_KEY=your_api_key_here
FULLENRICH_BASE_URL=https://app.fullenrich.com/api/v2

# Supabase
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_KEY=your_service_key_here

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60
BATCH_SIZE=100
REQUEST_TIMEOUT=30
```

#### 8.1.2 Configuration Constants

```python
# src/core/config.py

# API Configuration
FULLENRICH_API_KEY = os.getenv("FULLENRICH_API_KEY", "")
FULLENRICH_BASE_URL = os.getenv("FULLENRICH_BASE_URL", "https://app.fullenrich.com/api/v2")

# Database
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

# Rate Limits
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

# Search Defaults
DEFAULT_SEARCH_LIMIT = 25
MAX_SEARCH_LIMIT = 100
```

### 8.2 Streamlit Configuration

#### 8.2.1 `.streamlit/config.toml`

```toml
[server]
port = 8502
enableCORS = true
enableXsrfProtection = true

[theme]
primaryColor = "#4CAF50"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
font = "sans serif"
```

### 8.3 Validation

```python
def validate_config() -> bool:
    """Validate required configuration."""
    required = {
        "FULLENRICH_API_KEY": FULLENRICH_API_KEY,
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_SERVICE_KEY": SUPABASE_SERVICE_KEY,
    }
    
    missing = []
    for key, value in required.items():
        if not value or value == "your_api_key_here":
            missing.append(key)
    
    if missing:
        logger.error(f"Missing configuration: {', '.join(missing)}")
        return False
    
    return True
```

---

## 9. User Workflows

### 9.1 Workflow 1: Search by Existing Account

```
User Journey:
1. Open app (http://localhost:8502)
2. Step 1 - Search:
   a. Click dropdown in Section 1
   b. Type to search: "Google"
   c. Select "Google LLC"
   d. Set limit: 25
   e. Optional: Enter job title: "engineer"
   f. Click "Search People"
3. Step 2 - Enrich:
   a. Review 25 people found
   b. "Select All" checked by default
   c. Leave "Include Phone Numbers" unchecked (email only)
   d. See cost: "~1 credit per contact"
   e. Click "Enrich Selected"
   f. Wait 60-120 seconds (polling)
4. Step 3 - Preview:
   a. Review enriched emails
   b. See statistics: 25 contacts, 23 with emails
   c. Click "Save to Database"
   d. Success: "23 contacts saved"
5. Done: Click "Start Over" or close

Credits used: ~23 (email only)
```

### 9.2 Workflow 2: Search by Domain

```
User Journey:
1. Open app
2. Step 1 - Search:
   a. Leave Section 1 dropdown empty
   b. In Section 2, enter domain: "microsoft.com"
   c. Set limit: 50
   d. Optional: Enter job title: "product manager"
   e. Click "Search People"
3. Step 2 - Enrich:
   a. Review 50 people found
   b. "Select All" checked
   c. Check "Include Phone Numbers" ✓
   d. See cost: "~11 credits per contact"
   e. Click "Enrich Selected"
   f. Wait 60-120 seconds
4. Step 3 - Preview:
   a. Review enriched emails AND phones
   b. See statistics: 50 contacts, 47 with emails, 35 with phones
   c. Click "Save to Database"
   d. Success: "47 contacts saved"
5. Done

Credits used: ~517 (47 × 11)
```

### 9.3 Workflow 3: Error Handling

```
Scenario: Company not in FullEnrich database

1. Step 1 - Search:
   - Enter domain: "small-startup.com"
   - Click "Search People"
2. Error Message:
   "❌ Domain 'small-startup.com' not found in FullEnrich database"
3. Suggestions Shown:
   - Try these companies: Google, Microsoft, Salesforce, etc.
   - Why: FullEnrich doesn't have complete coverage
4. User Action:
   - Enter different domain
   - Or select from existing accounts
```

---

## 10. Data Flow

### 10.1 Search Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. User Input (Step 1)                                      │
│    - Account dropdown OR domain input                       │
│    - Job title filter (optional)                            │
│    - Limit (10-100)                                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. run_people_search()                                      │
│    - Validate input                                         │
│    - Extract domain (from dropdown or direct input)         │
│    - Create PeopleSearchService                             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. PeopleSearchService.search_people()                      │
│    - If domain provided: Use directly                       │
│    - If no domain: Call search_company() first              │
│    - Call FullEnrichClient.search_people()                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. FullEnrichClient.search_people()                         │
│    - Acquire rate limit token                               │
│    - Build payload: {current_company_domains: [...]}        │
│    - POST /api/v2/people/search                             │
│    - Parse response: metadata + results                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Map Results                                              │
│    - Extract nested fields (employment, social, location)   │
│    - Create clean person dicts                              │
│    - Return (company, people_list)                          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Store in Session State                                   │
│    - st.session_state.company_data = company                │
│    - st.session_state.search_results = people               │
│    - st.session_state.step = 2                              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. Display Results (Step 2)                                 │
│    - Show people in table                                   │
│    - Select All checkbox                                    │
│    - Enrichment options                                     │
└─────────────────────────────────────────────────────────────┘
```

### 10.2 Enrichment Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. User Selection (Step 2)                                  │
│    - Select people (all or subset)                          │
│    - Choose: Email only OR Email + Phone                    │
│    - Click "Enrich Selected"                                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. run_enrichment()                                         │
│    - Format contacts list                                   │
│    - Create EnrichmentService                               │
│    - Show progress bar                                      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. EnrichmentService.enrich_contacts()                      │
│    - Validate contacts (required fields)                    │
│    - Call FullEnrichClient.enrich_bulk()                    │
│    - Return enrichment_id                                   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. FullEnrichClient.enrich_bulk()                           │
│    - Acquire rate limit token                               │
│    - Build payload with enrich_fields                       │
│    - POST /api/v2/contact/enrich/bulk                       │
│    - Return enrichment_id (UUID)                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. EnrichmentService.poll_for_results()                     │
│    - Loop: timeout=120s, interval=10s                       │
│    - Call FullEnrichClient.get_enrichment_result()          │
│    - Check status: IN_PROGRESS → FINISHED                   │
│    - Return full response when FINISHED                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. FullEnrichClient.get_enrichment_result()                 │
│    - GET /api/v1/contact/enrich/bulk/{id} (v1 not v2!)     │
│    - Parse response: status, datas, cost                    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. EnrichmentMapper.map_to_accounts_contacts()              │
│    - Extract "data" or "datas" field                        │
│    - Map each item to contact dict                          │
│    - Extract: email, phones, profile, job info              │
│    - Return ([], contacts)                                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 8. Store in Session State                                   │
│    - st.session_state.enrichment_results = results          │
│    - st.session_state.step = 3                              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 9. Display Preview (Step 3)                                 │
│    - Show enriched contacts in table                        │
│    - Display statistics                                     │
│    - "Save to Database" button                              │
└─────────────────────────────────────────────────────────────┘
```

### 10.3 Save Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. User Clicks "Save to Database" (Step 3)                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. SupabaseClient.upsert_contacts()                         │
│    - For each contact:                                      │
│      a. Map to contacts table schema                        │
│      b. Lookup account_id by company_name                   │
│      c. Calculate role_value from job_title                 │
│      d. Skip if no email (NOT NULL constraint)              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Supabase Upsert                                          │
│    - INSERT OR UPDATE ON CONFLICT(email)                    │
│    - If email exists: UPDATE row                            │
│    - If email new: INSERT row                               │
│    - Return inserted/updated IDs                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Optional: Update enrichment_history                      │
│    - Record enrichment_id, batch_name, contacts_count       │
│    - Store status, credits_used                             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Show Success Message                                     │
│    - "✅ 23 contacts saved to database"                     │
│    - Show "Start Over" button                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 11. Error Handling

### 11.1 Error Categories

#### 11.1.1 User Input Errors

```python
# Missing required field
if not company_name:
    st.error("Please select or enter a company name")
    return

# Invalid limit
if limit < 10 or limit > 100:
    st.error("Limit must be between 10 and 100")
    return
```

#### 11.1.2 API Errors

```python
try:
    result = self.fullenrich.search_people(...)
except httpx.HTTPStatusError as e:
    if e.response.status_code == 401:
        logger.error("Invalid API key")
        raise ValueError("Authentication failed")
    elif e.response.status_code == 402:
        logger.error("Out of credits")
        raise ValueError("Insufficient credits")
    elif e.response.status_code == 429:
        logger.warning("Rate limited")
        # Automatic retry via tenacity
    else:
        raise
```

#### 11.1.3 Database Errors

```python
try:
    saved = db.upsert_contacts(contacts)
except Exception as e:
    logger.error(f"Database error: {e}")
    st.error("Failed to save contacts")
    return
```

#### 11.1.4 Data Validation Errors

```python
# Company not found
if total > 800_000_000:
    raise ValueError(
        f"Domain '{domain}' not found in FullEnrich database. "
        "This typically means the company is too small or not tracked."
    )

# Missing email
if not contact.get("email"):
    logger.warning("Skipping contact without email")
    continue
```

### 11.2 Logging Strategy

#### 11.2.1 Log Levels

```python
# INFO: Normal operations
logger.info("Starting enrichment: 25 contacts")

# WARNING: Recoverable issues
logger.warning("Skipping contact without email")

# ERROR: Failed operations
logger.error("Database connection failed")

# DEBUG: Detailed diagnostics
logger.debug(f"API payload: {json.dumps(payload)[:500]}")
```

#### 11.2.2 PII Redaction

```python
def redact_email(email: str) -> str:
    """Mask email for logging: john@company.com → j***@company.com"""
    if '@' not in email:
        return "***"
    local, domain = email.split('@', 1)
    return f"{local[0]}***@{domain}"

def redact_phone(phone: str) -> str:
    """Mask phone for logging: +1234567890 → +123***7890"""
    if len(phone) < 4:
        return "***"
    return f"{phone[:4]}***{phone[-4:]}"
```

### 11.3 Retry Logic

#### 11.3.1 Retry Configuration

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((
        httpx.TimeoutException,
        httpx.ConnectError
    )),
    reraise=True
)
def api_call(...):
    # Retries: 3 attempts
    # Wait: 4s, 8s, 10s (exponential backoff)
    # Triggers: Timeout or connection errors only
```

#### 11.3.2 Retry Strategy by Error Type

| Error Type | Retry? | Max Attempts | Backoff |
|------------|--------|--------------|---------|
| Timeout | ✅ Yes | 3 | Exponential (4s, 8s, 10s) |
| Connection Error | ✅ Yes | 3 | Exponential |
| 429 Rate Limit | ✅ Yes | Built into rate limiter |
| 401 Auth | ❌ No | - | Fail immediately |
| 402 Credits | ❌ No | - | Fail immediately |
| 400 Bad Request | ❌ No | - | Fail immediately |
| 500 Server Error | ✅ Yes | 3 | Exponential |

---

## 12. Testing

### 12.1 Test Structure

```
tests/
├── conftest.py              # Pytest fixtures
├── test_config.py           # Configuration validation
├── test_rate_limit.py       # Rate limiter logic
├── test_mappers.py          # Data mapping functions
├── test_supabase_client.py  # Database operations (mocked)
└── test_services.py         # Service layer (mocked)
```

### 12.2 Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=src --cov-report=html

# Run specific test file
poetry run pytest tests/test_mappers.py

# Run with verbose output
poetry run pytest -v

# Run with debug output
poetry run pytest -s
```

### 12.3 Test Examples

#### 12.3.1 Configuration Test

```python
def test_config_validation():
    """Test configuration validation"""
    # Valid config
    os.environ["FULLENRICH_API_KEY"] = "valid_key"
    assert validate_config() == True
    
    # Missing key
    os.environ["FULLENRICH_API_KEY"] = ""
    assert validate_config() == False
```

#### 12.3.2 Rate Limiter Test

```python
def test_rate_limiter_acquire():
    """Test token bucket acquire"""
    limiter = TokenBucket(capacity=10, refill_rate=1.0)
    
    # Should acquire immediately
    assert limiter.acquire(tokens=5) == True
    assert limiter.tokens == 5
    
    # Should block until tokens available
    start = time.time()
    limiter.acquire(tokens=10)
    elapsed = time.time() - start
    assert elapsed >= 5.0  # Had to wait for refill
```

#### 12.3.3 Mapper Test

```python
def test_enrichment_mapper():
    """Test enrichment response mapping"""
    response = {
        "datas": [
            {
                "contact": {
                    "firstname": "John",
                    "lastname": "Doe",
                    "most_probable_email": "john@company.com",
                    "profile": {
                        "linkedin_url": "https://linkedin.com/in/johndoe"
                    }
                }
            }
        ]
    }
    
    mapper = EnrichmentMapper()
    accounts, contacts = mapper.map_to_accounts_contacts(response)
    
    assert len(contacts) == 1
    assert contacts[0]["email"] == "john@company.com"
    assert contacts[0]["first_name"] == "John"
```

#### 12.3.4 Service Test (Mocked)

```python
@patch('src.services.enrichment.FullEnrichClient')
def test_enrichment_service(mock_client):
    """Test enrichment service with mocked API"""
    # Mock API response
    mock_client.return_value.enrich_bulk.return_value = "test-uuid"
    
    service = EnrichmentService()
    result = service.enrich_contacts(
        contacts=[{"first_name": "John", "last_name": "Doe", "company_name": "Google"}],
        webhook_url="https://example.com",
        batch_name="Test",
        include_phones=False
    )
    
    assert result["enrichment_id"] == "test-uuid"
    assert result["contacts_count"] == 1
    
    # Verify API was called correctly
    mock_client.return_value.enrich_bulk.assert_called_once()
```

### 12.4 Manual Testing Checklist

#### 12.4.1 Search Flow

- [ ] Search by existing account (dropdown)
- [ ] Search by domain (manual input)
- [ ] Search with job title filter
- [ ] Search with different limits (10, 25, 50, 100)
- [ ] Search for non-existent company (error handling)
- [ ] Search for known companies (Google, Microsoft, Salesforce)

#### 12.4.2 Enrichment Flow

- [ ] Enrich with email only (default)
- [ ] Enrich with email + phone (checkbox)
- [ ] Enrich 1 contact
- [ ] Enrich 10 contacts
- [ ] Enrich 50 contacts
- [ ] Verify cost estimates are accurate
- [ ] Verify credits deducted correctly
- [ ] Test polling timeout (120s limit)

#### 12.4.3 Save Flow

- [ ] Save new contacts (INSERT)
- [ ] Save existing contacts (UPDATE on conflict)
- [ ] Verify account_id linked correctly
- [ ] Verify role_value calculated correctly
- [ ] Check contacts appear in database
- [ ] Check enrichment_history recorded

---

## 13. Deployment

### 13.1 Local Development Setup

#### 13.1.1 Prerequisites

- Python 3.10+
- Poetry (Python package manager)
- Supabase account with database
- FullEnrich API key

#### 13.1.2 Installation Steps

```bash
# 1. Clone repository
cd People_org

# 2. Install Poetry (if not installed)
curl -sSL https://install.python-poetry.org | python3 -

# 3. Install dependencies
poetry install

# 4. Copy environment template
cp .env.example .env

# 5. Edit .env with your credentials
nano .env

# 6. Verify configuration
poetry run python -m src.core.config

# 7. Run tests (optional)
poetry run pytest

# 8. Start application
poetry run streamlit run app.py --server.port 8502
```

#### 13.1.3 Accessing the Application

```
Local URL:   http://localhost:8502
Network URL: http://192.168.1.X:8502  (accessible from local network)
```

### 13.2 Production Deployment

#### 13.2.1 Environment Setup

```bash
# Production .env
FULLENRICH_API_KEY=prod_api_key_here
FULLENRICH_BASE_URL=https://app.fullenrich.com/api/v2

SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_KEY=prod_service_key_here

RATE_LIMIT_PER_MINUTE=60
BATCH_SIZE=100
REQUEST_TIMEOUT=30
```

#### 13.2.2 Deployment Options

**Option 1: Streamlit Cloud**
```bash
# Not recommended - polling requires persistent connection
# Streamlit Cloud may terminate long-running requests
```

**Option 2: Docker**
```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install Poetry
RUN pip install poetry

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

# Copy application
COPY . .

# Expose Streamlit port
EXPOSE 8502

# Run application
CMD ["streamlit", "run", "app.py", "--server.port=8502", "--server.address=0.0.0.0"]
```

**Option 3: VM or Server**
```bash
# Install Python 3.10+
sudo apt update
sudo apt install python3.10 python3-pip

# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Clone and setup
git clone <repo>
cd People_org
poetry install
cp .env.example .env
nano .env  # Add credentials

# Run with systemd (persistent service)
sudo nano /etc/systemd/system/people-search.service
```

**Systemd Service File:**
```ini
[Unit]
Description=People Search + Enrichment
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/People_org
Environment="PATH=/home/ubuntu/.local/bin:/usr/bin"
ExecStart=/home/ubuntu/.local/bin/poetry run streamlit run app.py --server.port 8502
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable people-search
sudo systemctl start people-search
sudo systemctl status people-search
```

### 13.3 Monitoring

#### 13.3.1 Application Logs

```bash
# Streamlit logs (local)
tail -f ~/.streamlit/logs/streamlit.log

# Application logs (if using systemd)
sudo journalctl -u people-search -f

# Filter by log level
sudo journalctl -u people-search | grep ERROR
```

#### 13.3.2 Health Checks

```python
# Check FullEnrich API connection
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://app.fullenrich.com/api/v2/me

# Check Supabase connection
poetry run python -c "from src.db.supabase_client import SupabaseClient; \
  db = SupabaseClient(); print('Connected:', db.get_accounts(limit=1))"
```

#### 13.3.3 Performance Monitoring

- Monitor API rate limit usage (60 req/min)
- Track enrichment success rate
- Monitor credit consumption
- Database query performance
- Application memory usage

---

## 14. API Reference

### 14.1 Internal API (Python)

#### 14.1.1 PeopleSearchService

```python
service = PeopleSearchService()

# Search for people
company, people = service.search_people(
    company_name="Google",
    domain="google.com",        # Optional, skips company resolution
    title="engineer",           # Optional filter
    limit=50                    # 10-100
)

# Returns:
# company: {name, domain, linkedin_url, employee_count}
# people: List[{full_name, first_name, last_name, current_title, 
#               linkedin_url, location_city, location_region, company}]
```

#### 14.1.2 EnrichmentService

```python
service = EnrichmentService()

# Start enrichment
result = service.enrich_contacts(
    contacts=[
        {
            "first_name": "John",
            "last_name": "Doe",
            "company_name": "Google",
            "domain": "google.com",
            "linkedin_url": "https://linkedin.com/in/johndoe"
        }
    ],
    webhook_url="https://example.com/webhook",
    batch_name="Batch 2026-02-17",
    include_phones=False  # Default: email only
)
# Returns: {"enrichment_id": "uuid", "contacts_count": 1}

# Poll for results
enrichment_result = service.poll_for_results(
    enrichment_id=result["enrichment_id"],
    timeout=120,           # Seconds
    poll_interval=10       # Seconds between polls
)
# Returns: Full enrichment response or None if timeout
```

#### 14.1.3 SupabaseClient

```python
db = SupabaseClient()

# Get accounts for dropdown
accounts = db.get_accounts(limit=1000)
# Returns: List[{account_id, company_name, account_domain, ...}]

# Lookup account_id
account_id = db.get_account_id_by_company_name("Google")
# Returns: UUID string or None

# Save contacts
saved_count = db.upsert_contacts([
    {
        "email": "john@google.com",
        "first_name": "John",
        "last_name": "Doe",
        "company_name": "Google",
        "linkedin_url": "..."
    }
])
# Returns: Number of contacts saved

# Update history
db.update_enrichment_history({
    "enrichment_id": "uuid",
    "batch_name": "Batch",
    "contacts_count": 25,
    "status": "FINISHED",
    "credits_used": 25
})
```

#### 14.1.4 FullEnrichClient

```python
client = FullEnrichClient()

# Check credits
balance = client.check_credits()
# Returns: Integer (credit balance)

# Search companies
companies = client.search_company("Google", limit=10)
# Returns: List[{id, name, domain, linkedin_url, headcount, ...}]

# Search people
metadata, people = client.search_people(
    company_domain="google.com",
    title="engineer",
    limit=50
)
# Returns: (metadata, results)
# metadata: {total, search_after, limit}
# results: List[{person: {...}}]

# Start enrichment
enrichment_id = client.enrich_bulk(
    contacts=[...],
    webhook_url="https://example.com/webhook",
    batch_name="Batch",
    include_phones=False
)
# Returns: UUID string

# Get enrichment results
result = client.get_enrichment_result(
    enrichment_id="uuid",
    force_results=False  # Wait for completion
)
# Returns: {id, name, status, datas, cost}
```

---

## 15. Troubleshooting

### 15.1 Common Issues

#### 15.1.1 "Search returns wrong people (839M results)"

**Cause:** Payload structure incorrect, filters not at root level

**Solution:**
```python
# ❌ WRONG
payload = {"filters": {"current_company_domains": [...]}}

# ✅ CORRECT
payload = {"current_company_domains": [...], "limit": 50}
```

#### 15.1.2 "Enrichment returns 0 contacts"

**Cause:** API version mismatch (using v2 for GET instead of v1)

**Solution:**
```python
# Enrich uses v2
POST https://app.fullenrich.com/api/v2/contact/enrich/bulk

# Get results uses v1 (different!)
GET https://app.fullenrich.com/api/v1/contact/enrich/bulk/{id}
```

#### 15.1.3 "Company not found error"

**Cause:** Company/domain not in FullEnrich database

**Solution:**
- Try well-known companies (Google, Microsoft, Salesforce)
- Use existing account dropdown (verified domains)
- Contact FullEnrich to add company to database

#### 15.1.4 "Port 8502 is not available"

**Cause:** Streamlit already running or port in use

**Solution:**
```bash
# Find and kill process
Get-Process -Name streamlit | Stop-Process -Force

# Or use different port
poetry run streamlit run app.py --server.port 8503
```

#### 15.1.5 "Invalid API key"

**Cause:** API key incorrect or not set

**Solution:**
```bash
# Check .env file
cat .env | grep FULLENRICH_API_KEY

# Get new key from
https://app.fullenrich.com/app/api

# Restart app after updating .env
```

#### 15.1.6 "Database connection failed"

**Cause:** Supabase credentials incorrect or network issue

**Solution:**
```bash
# Test connection
poetry run python -c "
from src.db.supabase_client import SupabaseClient;
db = SupabaseClient();
print(db.get_accounts(limit=1))
"

# Check credentials
echo $SUPABASE_URL
echo $SUPABASE_SERVICE_KEY

# Verify network
ping YOUR_SUPABASE_HOST.supabase.co
```

#### 15.1.7 "Enrichment timeout after 120s"

**Cause:** FullEnrich taking longer than expected

**Solution:**
- Check FullEnrich dashboard for status
- Increase timeout in code (not recommended)
- Retry with smaller batch
- Verify credits available

#### 15.1.8 "Rate limit exceeded"

**Cause:** More than 60 requests per minute

**Solution:**
- Rate limiter should handle automatically
- If persists, reduce batch size
- Check for concurrent requests
- Wait 1 minute and retry

### 15.2 Debug Mode

#### 15.2.1 Enable Debug Logging

```python
# src/core/logging.py
import logging

def setup_logger(name: str, level=logging.DEBUG):  # Change to DEBUG
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    handler = logging.StreamHandler()
    handler.setLevel(level)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    return logger
```

#### 15.2.2 API Request Debugging

```python
# In FullEnrichClient, add detailed logging
logger.debug(f"Request URL: {url}")
logger.debug(f"Request headers: {self.headers}")
logger.debug(f"Request payload: {json.dumps(payload, indent=2)}")

response = httpx.post(...)

logger.debug(f"Response status: {response.status_code}")
logger.debug(f"Response headers: {response.headers}")
logger.debug(f"Response body: {response.text[:1000]}")
```

### 15.3 Support Resources

- **FullEnrich API Docs:** https://docs.fullenrich.com
- **Supabase Docs:** https://supabase.com/docs
- **Streamlit Docs:** https://docs.streamlit.io
- **Python httpx Docs:** https://www.python-httpx.org
- **Project Issues:** (Internal repository issues tracker)

---

## Appendix

### A. Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FULLENRICH_API_KEY` | ✅ Yes | - | FullEnrich API key |
| `FULLENRICH_BASE_URL` | No | `https://app.fullenrich.com/api/v2` | API base URL |
| `SUPABASE_URL` | ✅ Yes | - | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | ✅ Yes | - | Supabase service role key |
| `RATE_LIMIT_PER_MINUTE` | No | `60` | API rate limit |
| `BATCH_SIZE` | No | `100` | Max contacts per batch |
| `REQUEST_TIMEOUT` | No | `30` | HTTP request timeout (seconds) |

### B. File Size Reference

| File | Lines | Purpose |
|------|-------|---------|
| `app.py` | ~700 | Streamlit UI |
| `src/core/config.py` | ~140 | Configuration |
| `src/fullenrich/client.py` | ~650 | API client |
| `src/fullenrich/mappers.py` | ~500 | Data mappers |
| `src/services/people_search.py` | ~200 | Search service |
| `src/services/enrichment.py` | ~200 | Enrichment service |
| `src/db/supabase_client.py` | ~340 | Database client |
| `src/fullenrich/rate_limit.py` | ~100 | Rate limiter |
| `src/core/logging.py` | ~60 | Logging setup |

### C. Credits & Cost Reference

| Operation | Credits | Notes |
|-----------|---------|-------|
| Company search | 0 | Free |
| People search | 0 | Free |
| Email enrichment | 1 per contact | Includes most_probable_email, all emails |
| Phone enrichment | 10 per contact | Optional, mobile phones only |
| Full profile | Included | LinkedIn data, job info (with email/phone) |

**Cost Examples:**
- 10 contacts, email: 10 credits
- 10 contacts, email+phone: 110 credits
- 50 contacts, email: 50 credits
- 50 contacts, email+phone: 550 credits
- 100 contacts, email: 100 credits
- 100 contacts, email+phone: 1,100 credits

### D. Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-02-17 | Initial implementation |
| - | - | Two-section search (account/domain) |
| - | - | Email-only default enrichment |
| - | - | API polling (no webhooks) |
| - | - | Existing database integration |

---

## Document Information

**Filename:** `IMPLEMENTATION_GUIDE.md`  
**Location:** `docs/IMPLEMENTATION_GUIDE.md`  
**Author:** Hrytos Team  
**Created:** February 17, 2026  
**Last Updated:** February 17, 2026  
**Version:** 1.0.0  

**Purpose:** Complete implementation documentation for People Search + Enrichment system

**Audience:**
- Developers (new team members, maintainers)
- System administrators (deployment, monitoring)
- Technical product managers (architecture overview)

**Related Documents:**
- `README.md` - Quick start guide
- `supabase/README_SCHEMA.md` - Database schema
- `PHONE_ENRICHMENT_OPTION.md` - Phone enrichment feature
- `POLLING_IMPLEMENTATION.md` - API polling details

---

**End of Implementation Guide**
