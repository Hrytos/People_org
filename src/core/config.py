"""
Configuration Module

Loads environment variables and provides app-wide configuration.
Following the Rulebook: Secrets management and configuration standards.
"""

import os
import json
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# =============================================================================
# FullEnrich API Configuration
# =============================================================================

FULLENRICH_API_KEY = os.getenv("FULLENRICH_API_KEY", "")
FULLENRICH_BASE_URL = os.getenv(
    "FULLENRICH_BASE_URL", 
    "https://app.fullenrich.com/api/v2"
)

# =============================================================================
# Supabase Configuration
# =============================================================================

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

# =============================================================================
# HubSpot Configuration
# =============================================================================

ENABLE_HUBSPOT_SYNC = os.getenv("ENABLE_HUBSPOT_SYNC", "false").lower() in {"1", "true", "yes"}
HUBSPOT_SERVICE_KEY = os.getenv("HUBSPOT_SERVICE_KEY", "")
HUBSPOT_BASE_URL = os.getenv("HUBSPOT_BASE_URL", "https://api.hubapi.com")
HUBSPOT_REQUEST_TIMEOUT = int(os.getenv("HUBSPOT_REQUEST_TIMEOUT", "30"))
HUBSPOT_BATCH_SIZE = min(100, int(os.getenv("HUBSPOT_BATCH_SIZE", "100")))
HUBSPOT_DRY_RUN = os.getenv("HUBSPOT_DRY_RUN", "false").lower() in {"1", "true", "yes"}
HUBSPOT_RATE_LIMIT_PER_MINUTE = int(os.getenv("HUBSPOT_RATE_LIMIT_PER_MINUTE", "100"))
HUBSPOT_MAX_RETRIES = int(os.getenv("HUBSPOT_MAX_RETRIES", "4"))
HUBSPOT_SUPABASE_ID_PROPERTY = os.getenv("HUBSPOT_SUPABASE_ID_PROPERTY", "contactID")
_hubspot_field_map_raw = os.getenv("HUBSPOT_CONTACT_FIELD_MAP", "")
try:
    HUBSPOT_CONTACT_FIELD_MAP = json.loads(_hubspot_field_map_raw) if _hubspot_field_map_raw else {}
    if not isinstance(HUBSPOT_CONTACT_FIELD_MAP, dict):
        HUBSPOT_CONTACT_FIELD_MAP = {}
except Exception:
    HUBSPOT_CONTACT_FIELD_MAP = {}

# =============================================================================
# App Authentication (optional)
# =============================================================================

APP_AUTH_ENABLED = os.getenv("APP_AUTH_ENABLED", "false").lower() in {"1", "true", "yes"}
APP_AUTH_USERNAME = os.getenv("APP_AUTH_USERNAME", "")
APP_AUTH_PASSWORD = os.getenv("APP_AUTH_PASSWORD", "")

# =============================================================================
# API Rate Limits (from FullEnrich docs)
# =============================================================================

RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

# =============================================================================
# Enrichment Fields
# =============================================================================

ENRICH_FIELDS = [
    "contact.emails",
    "contact.phones"
]

# =============================================================================
# Search Configuration
# =============================================================================

DEFAULT_SEARCH_LIMIT = 25
MAX_SEARCH_LIMIT = 100

# Company search cache duration (days)
COMPANY_CACHE_DAYS = 7

# =============================================================================
# Role Value Mapping
# =============================================================================

# Role value keywords for title matching
# Based on seniority levels in database
ROLE_VALUE_KEYWORDS = {
    6: ["president", "chairman", "board member", "board of directors"],
    1: ["ceo", "cto", "cfo", "coo", "chief", "founder", "co-founder", "owner"],
    3: ["vice president", "vp", "director", "head of", "lead"],
    2: ["manager", "team lead", "supervisor"],
    4: ["senior", "staff", "principal", "engineer", "developer", "analyst", "designer"],
    5: ["junior", "intern", "associate", "entry", "trainee"]
}

# Check order - VP/Director before C-Suite to avoid false positives
ROLE_CHECK_ORDER = [6, 3, 1, 2, 4, 5]

# =============================================================================
# Validation Functions
# =============================================================================

def validate_config() -> bool:
    """
    Validate that all required configuration is present.
    
    Returns:
        True if configuration is valid, False otherwise
    """
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
        print(f"❌ Missing configuration: {', '.join(missing)}")
        print("Please update your .env file")
        return False
    
    return True


def validate_hubspot_config(required: bool = False) -> bool:
    """
    Validate HubSpot configuration for sync workflows only.

    Args:
        required: If True, validates even when feature flag is disabled.

    Returns:
        True when configuration is usable for HubSpot sync.
    """
    if not required and not ENABLE_HUBSPOT_SYNC:
        return False

    if not HUBSPOT_SERVICE_KEY:
        return False

    return True


def get_webhook_url(tunnel_url: str) -> str:
    """
    Construct webhook URL from tunnel URL.
    
    Args:
        tunnel_url: Base tunnel URL (e.g., https://abc123.ngrok.io)
        
    Returns:
        Full webhook URL
    """
    return f"{tunnel_url}/webhook"


# =============================================================================
# Module Test
# =============================================================================

if __name__ == "__main__":
    print("Configuration Module")
    print("=" * 60)
    print(f"FullEnrich API: {FULLENRICH_BASE_URL}")
    print(f"Supabase URL: {SUPABASE_URL[:30]}..." if SUPABASE_URL else "Not configured")
    print(f"Rate Limit: {RATE_LIMIT_PER_MINUTE} req/min")
    print(f"Batch Size: {BATCH_SIZE} contacts")
    print("=" * 60)
    print()
    
    if validate_config():
        print("✅ Configuration is valid")
    else:
        print("❌ Configuration is invalid")
