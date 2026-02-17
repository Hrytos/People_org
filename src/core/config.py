"""
Configuration Module

Loads environment variables and provides app-wide configuration.
Following the Rulebook: Secrets management and configuration standards.
"""

import os
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
