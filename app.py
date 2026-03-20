"""
People Search + Enrichment - Streamlit UI

2-Step Workflow:
Step 1: Search for people at a company (with optional title filter)
Step 2: Select people to enrich and preview results before saving

Following the Rulebook for UI/UX best practices.
"""

import streamlit as st
import pandas as pd
import sys
import re
import hmac
import time
from io import StringIO
from pathlib import Path
from datetime import datetime

# Add project root to path so src.* packages resolve (and relative imports inside src work)
sys.path.insert(0, str(Path(__file__).parent))

from src.core.config import (
    APP_AUTH_ENABLED,
    APP_AUTH_PASSWORD,
    APP_AUTH_USERNAME,
    SUPABASE_SERVICE_KEY,
    SUPABASE_URL,
    validate_config,
)
from src.core.logging import setup_logger
from src.services.people_search import PeopleSearchService
from src.services.enrichment import EnrichmentService
from src.services.hubspot_sync import HubSpotSyncService

logger = setup_logger(__name__)

# =============================================================================
# Page Configuration
# =============================================================================

st.set_page_config(
    page_title="People Search + Enrichment",
    page_icon="🔍",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main-header { font-size: 2.5rem; font-weight: bold; margin-bottom: 0; }
    .sub-header { color: #666; font-size: 1rem; margin-top: 0; }
    .step-badge { 
        background: #4CAF50; 
        color: white; 
        padding: 4px 12px; 
        border-radius: 12px; 
        font-size: 0.9rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# Session State Initialization
# =============================================================================

def init_session_state():
    """Initialize session state variables."""
    if 'step' not in st.session_state:
        st.session_state.step = 1  # 1=search, 2=enrich, 3=preview
    if 'search_results' not in st.session_state:
        st.session_state.search_results = None
    if 'company_data' not in st.session_state:
        st.session_state.company_data = None
    if 'selected_account' not in st.session_state:
        st.session_state.selected_account = None  # Full account dict from dropdown
    if 'selected_account_id' not in st.session_state:
        st.session_state.selected_account_id = None  # Dedicated UUID — used at save time
    if 'selected_people' not in st.session_state:
        st.session_state.selected_people = []
    if 'enrichment_results' not in st.session_state:
        st.session_state.enrichment_results = None
    if 'skip_duplicates' not in st.session_state:
        st.session_state.skip_duplicates = True
    if 'last_saved_contacts' not in st.session_state:
        st.session_state.last_saved_contacts = []
    if 'hubspot_sync_result' not in st.session_state:
        st.session_state.hubspot_sync_result = None
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'enrichment_selected_indices' not in st.session_state:
        st.session_state.enrichment_selected_indices = []
    if 'enrichment_title_filter' not in st.session_state:
        st.session_state.enrichment_title_filter = ""
    if 'people_editor_version' not in st.session_state:
        st.session_state.people_editor_version = 0
    if 'enrichment_selection_people_count' not in st.session_state:
        st.session_state.enrichment_selection_people_count = -1
    if 'auth_failed_attempts' not in st.session_state:
        st.session_state.auth_failed_attempts = 0
    if 'auth_lock_until' not in st.session_state:
        st.session_state.auth_lock_until = 0.0


def reset_state():
    """Reset to initial state."""
    st.session_state.step = 1
    st.session_state.search_results = None
    st.session_state.company_data = None
    st.session_state.selected_account = None
    st.session_state.selected_account_id = None
    st.session_state.selected_people = []
    st.session_state.enrichment_results = None
    st.session_state.skip_duplicates = True
    st.session_state.last_saved_contacts = []
    st.session_state.hubspot_sync_result = None
    st.session_state.enrichment_selected_indices = []
    st.session_state.enrichment_title_filter = ""
    st.session_state.people_editor_version = 0
    st.session_state.enrichment_selection_people_count = -1
    st.session_state.auth_failed_attempts = 0
    st.session_state.auth_lock_until = 0.0


def _render_login_gate() -> bool:
    """Render simple username/password login form when auth is enabled."""
    if not APP_AUTH_ENABLED:
        return True

    if st.session_state.get("authenticated"):
        return True

    now = time.time()
    lock_until = float(st.session_state.get("auth_lock_until", 0.0))
    if now < lock_until:
        wait_seconds = int(lock_until - now)
        st.warning(f"Too many failed attempts. Try again in {wait_seconds}s.")
        return False

    left, center, right = st.columns([1.2, 1, 1.2])
    with center:
        st.markdown("### People Search + Enrichment")
        st.caption("Login required")

        with st.container(border=True):
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login", type="primary", width="stretch")

                if submitted:
                    valid_user = bool(APP_AUTH_USERNAME) and hmac.compare_digest(
                        str(username), str(APP_AUTH_USERNAME)
                    )
                    valid_pass = bool(APP_AUTH_PASSWORD) and hmac.compare_digest(
                        str(password), str(APP_AUTH_PASSWORD)
                    )

                    if (
                        valid_user
                        and valid_pass
                    ):
                        st.session_state.authenticated = True
                        st.session_state.auth_failed_attempts = 0
                        st.session_state.auth_lock_until = 0.0
                        st.rerun()
                    else:
                        attempts = int(st.session_state.get("auth_failed_attempts", 0)) + 1
                        st.session_state.auth_failed_attempts = attempts
                        if attempts >= 5:
                            st.session_state.auth_lock_until = time.time() + 60
                            st.session_state.auth_failed_attempts = 0
                            st.error("Too many failed attempts. Login locked for 60 seconds.")
                            return False
                        st.error("Invalid credentials")

    return False


def parse_csv_values(raw: str) -> list[str]:
    """Parse comma/newline-separated user input into a cleaned list."""
    if not raw:
        return []
    return [item.strip() for item in re.split(r"[,\n]+", raw) if item and item.strip()]


FILTERS_DIR = Path(__file__).parent / "src" / "core" / "filters"


def load_default_filter_text(filename: str) -> str:
    """Load multiline defaults from a text file in src/core/filters."""
    file_path = FILTERS_DIR / filename
    try:
        return file_path.read_text(encoding="utf-8").strip()
    except Exception as e:
        logger.warning(f"Could not load filter defaults from {file_path}: {e}")
        return ""


def normalize_linkedin_url(url: str) -> str:
    """Normalize LinkedIn person URL for matching and dedupe."""
    if not url:
        return ""
    clean = url.strip()
    clean = re.sub(r"\?.*$", "", clean)
    clean = clean.rstrip("/")
    return clean


def extract_linkedin_urls(raw_urls: str, csv_file) -> list[str]:
    """Extract LinkedIn profile URLs from text input and optional CSV upload."""
    candidates: list[str] = []

    if raw_urls:
        for token in re.split(r"[,\n\s;]+", raw_urls):
            if token and "linkedin.com/in/" in token.lower():
                candidates.append(token.strip())

    if csv_file is not None:
        try:
            csv_text = csv_file.getvalue().decode("utf-8", errors="ignore")
            df = pd.read_csv(StringIO(csv_text))

            linkedin_columns = [
                col for col in df.columns
                if "linkedin" in str(col).lower() or "url" in str(col).lower()
            ]

            for col in linkedin_columns:
                for value in df[col].dropna().astype(str).tolist():
                    if "linkedin.com/in/" in value.lower():
                        candidates.append(value)

            # Fallback scan all cells for linkedin profile URLs.
            if not candidates and not df.empty:
                pattern = re.compile(r"https?://(?:www\.)?linkedin\.com/in/[^\s,;]+", re.IGNORECASE)
                for value in df.astype(str).values.flatten().tolist():
                    for match in pattern.findall(value):
                        candidates.append(match)

        except Exception as e:
            logger.warning(f"Failed parsing LinkedIn CSV upload: {e}")

    normalized = [normalize_linkedin_url(u) for u in candidates]
    filtered = [u for u in normalized if "linkedin.com/in/" in u.lower()]
    return list(dict.fromkeys(filtered))


# =============================================================================
# Main Application
# =============================================================================

def main():
    init_session_state()

    if not _render_login_gate():
        return
    
    # Header
    st.markdown('<p class="main-header">🔍 People Search + Enrichment</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Find and enrich contact information with FullEnrich API</p>', unsafe_allow_html=True)
    st.divider()
    
    # Sidebar
    render_sidebar()
    
    # Main content based on step
    if st.session_state.step == 1:
        render_search_step()
    elif st.session_state.step == 2:
        render_enrichment_step()
    elif st.session_state.step == 3:
        render_preview_step()


# =============================================================================
# Sidebar
# =============================================================================

def render_sidebar():
    """Render sidebar with configuration and history."""
    with st.sidebar:
        # Configuration Status
        if validate_config():
            st.success("✅ Configuration valid")
        else:
            st.error("❌ Configuration invalid")
            st.caption("Check your .env file")
            st.stop()
        
        st.divider()
        
        # Progress indicator
        st.subheader("📍 Progress")
        step = st.session_state.step
        st.markdown(f"""
        {'**1️⃣ Search People**' if step == 1 else '1️⃣ Search People'}  
        {'**2️⃣ Select & Enrich**' if step == 2 else '2️⃣ Select & Enrich'}  
        {'**3️⃣ Preview & Save**' if step == 3 else '3️⃣ Preview & Save'}
        """)
        
        st.divider()
        
        # Quick stats
        st.subheader("📊 Current Session")
        if st.session_state.search_results:
            st.metric("People Found", len(st.session_state.search_results))
        if st.session_state.selected_people:
            st.metric("Selected", len(st.session_state.selected_people))
        
        st.divider()
        
        # Reset button
        if st.button("🔄 Start Over"):
            reset_state()
            st.rerun()

        if APP_AUTH_ENABLED and st.button("🔐 Logout"):
            st.session_state.authenticated = False
            reset_state()
            st.rerun()


# =============================================================================
# Step 1: Search People
# =============================================================================

def render_search_step():
    """Step 1: Search for people at a company."""
    st.markdown('<span class="step-badge">STEP 1</span>', unsafe_allow_html=True)
    st.header("Find People at Company")
    st.info("💡 Use either an existing account or a company domain, then adjust filters before searching")
    
    # Load existing accounts for dropdown (increased limit for large account lists)
    try:
        from src.db.supabase_client import SupabaseClient
        db = SupabaseClient()
        accounts = db.get_accounts(limit=5000)  # Increased from 100 to 5000
        account_options = {
            acc.get("company_name", ""): acc 
            for acc in accounts 
            if acc.get("company_name")
        }
        logger.info(f"Loaded {len(account_options)} accounts for dropdown")
    except Exception as e:
        logger.warning(f"Could not load accounts: {e}")
        account_options = {}

    default_titles_text = load_default_filter_text("titles_included.txt")
    default_excluded_titles_text = load_default_filter_text("titles_excluded.txt")
    
    with st.form("search_form"):
        st.subheader("🏢 Option A: Existing Account")
        if account_options:
            selected_account = st.selectbox(
                "Choose from existing accounts (optional)",
                options=[""] + sorted(account_options.keys()),
                format_func=lambda x: "Type to search or select..." if x == "" else x,
                help="Start typing to filter company names"
            )
        else:
            st.caption("No accounts available from database right now")
            selected_account = ""

        st.subheader("🔎 Option B: Enter Company Domain")
        company_domain_input = st.text_input(
            "Company domain",
            placeholder="e.g., google.com, openai.com",
            help="Use domain when possible for best FullEnrich precision"
        )

        with st.expander("Job titles include filter (optional)", expanded=False):
            titles_raw = st.text_area(
                "Current position titles",
                value=default_titles_text,
                height=220,
                help="One title per line, or comma-separated values"
            )

        with st.expander("Job titles exclude filter (optional)", expanded=False):
            excluded_titles_raw = st.text_area(
                "Exclude current position titles",
                value=default_excluded_titles_text,
                height=260,
                help="One title per line, or comma-separated values"
            )

        target_count = st.number_input(
            "People to fetch",
            min_value=25,
            max_value=500,
            value=100,
            step=25,
            help="Fetches profiles in pages up to this target count"
        )

        person_locations_raw = st.text_input(
            "Person locations (optional)",
            value="United States",
            placeholder="San Francisco, California, United States"
        )

        submitted = st.form_submit_button("🔍 Search People", type="primary", width="stretch")
        
        if submitted:
            # Determine which section was used
            if selected_account and selected_account != "":
                # ===== SECTION 1: Using existing account from dropdown =====
                company_name = selected_account
                account_data = account_options.get(selected_account)
                st.session_state.selected_account = account_data
                # ✅ Store account_id explicitly — this is used at save time
                st.session_state.selected_account_id = account_data.get("account_id")
                domain = account_data.get("account_domain", "")
                titles = parse_csv_values(titles_raw)
                
            elif company_domain_input:
                # ===== SECTION 2: Using manual domain entry =====
                company_name = company_domain_input.split(".")[0]
                st.session_state.selected_account = None
                st.session_state.selected_account_id = None  # No dropdown selection
                domain = company_domain_input
                titles = parse_csv_values(titles_raw)
                
            else:
                st.error("Please either select an existing account OR enter a company domain")
                return
            
            person_locations = parse_csv_values(person_locations_raw)
            excluded_titles = parse_csv_values(excluded_titles_raw)

            run_people_search(
                company_name=company_name,
                titles=titles,
                excluded_titles=excluded_titles,
                person_locations=person_locations,
                limit=int(target_count),
                domain=domain,
            )

    st.divider()
    st.subheader("🔗 Search by LinkedIn URLs")
    st.caption("Use this section when you already have person LinkedIn profile URLs")

    with st.form("linkedin_url_search_form"):
        linkedin_selected_account_name = st.selectbox(
            "Select account for save/enrichment context (optional)",
            options=[""] + sorted(account_options.keys()),
            format_func=lambda x: "No account selected" if x == "" else x,
            help="This account will be used for contact save linking and enrichment company context"
        )

        linkedin_urls_raw = st.text_area(
            "LinkedIn profile URLs (comma-separated or one per line)",
            placeholder="https://www.linkedin.com/in/john-doe, https://www.linkedin.com/in/jane-doe",
            height=140,
            help="Accepted format: person profile URLs like linkedin.com/in/..."
        )

        linkedin_csv = st.file_uploader(
            "Or upload CSV with LinkedIn URLs",
            type=["csv"],
            help="Any column containing LinkedIn profile URLs will be parsed"
        )

        linkedin_submitted = st.form_submit_button("🔎 Search by LinkedIn URLs", type="primary", width="stretch")

        if linkedin_submitted:
            linkedin_urls = extract_linkedin_urls(linkedin_urls_raw, linkedin_csv)
            if not linkedin_urls:
                st.error("Please provide at least one valid LinkedIn profile URL (linkedin.com/in/...) via text or CSV")
                return

            selected_account = account_options.get(linkedin_selected_account_name) if linkedin_selected_account_name else None

            run_people_search_by_linkedin_urls(
                linkedin_urls=linkedin_urls,
                selected_account=selected_account,
            )


def run_people_search(
    company_name: str,
    titles: list[str],
    excluded_titles: list[str],
    person_locations: list[str],
    limit: int,
    domain: str = None,
):
    """Execute people search."""
    with st.spinner(f"Searching people at {company_name}..."):
        try:
            service = PeopleSearchService()
            
            # Search (use domain if available for better accuracy)
            company, people = service.search_people(
                company_name=company_name,
                domain=domain,
                titles=titles if titles else None,
                excluded_titles=excluded_titles if excluded_titles else None,
                person_locations=person_locations if person_locations else None,
                limit=limit
            )
            
            if not company:
                st.error(f"Company not found: {company_name}")
                return
            
            if not people:
                st.warning(f"No people found at {company['name']}")
                if titles or excluded_titles or person_locations:
                    st.info("Try searching with fewer filters")
                return
            
            # Check terminal logs for "total: 0" warning
            # If total is 0, these are suggestions, not actual employees
            # This happens when the domain/company isn't in FullEnrich's database
            
            # Store in session state
            st.session_state.company_data = company
            st.session_state.search_results = people
            st.session_state.step = 2
            
            st.success(f"✅ Found {len(people)} people at {company['name']}")
            st.rerun()
            
        except ValueError as e:
            # Domain/company not found in FullEnrich
            error_msg = str(e)
            st.error(f"❌ {error_msg}")
            
            if "not found in FullEnrich database" in error_msg:
                st.warning("**Try these well-known companies instead:**")
                st.markdown("""
                - **Google** (google.com)
                - **Microsoft** (microsoft.com)
                - **Salesforce** (salesforce.com)
                - **HubSpot** (hubspot.com)
                - **Amazon** (amazon.com)
                
                These are guaranteed to be in FullEnrich's database.
                """)
                st.info("💡 **Why this happens:** FullEnrich doesn't have complete coverage of every company. Smaller companies or newer companies may not be in their database yet.")
            
        except Exception as e:
            st.error(f"Search failed: {str(e)}")
            import traceback
            with st.expander("Error details"):
                st.code(traceback.format_exc())


def run_people_search_by_linkedin_urls(
    linkedin_urls: list[str],
    selected_account: dict | None = None,
):
    """Execute people search by person LinkedIn URLs only."""
    with st.spinner(f"Searching {len(linkedin_urls)} LinkedIn URLs..."):
        try:
            service = PeopleSearchService()
            company, people = service.search_people_by_linkedin_urls(
                linkedin_urls=linkedin_urls,
                limit=len(linkedin_urls),
            )

            if not people:
                st.warning("No people matched the provided LinkedIn URLs")
                return

            if selected_account:
                st.session_state.selected_account = selected_account
                st.session_state.selected_account_id = selected_account.get("account_id")
                st.session_state.company_data = {
                    "name": selected_account.get("company_name", "LinkedIn URL Search"),
                    "domain": selected_account.get("account_domain", ""),
                    "linkedin_url": selected_account.get("linkedin_url", ""),
                    "employee_count": None,
                }
            else:
                st.session_state.selected_account = None
                st.session_state.selected_account_id = None
                st.session_state.company_data = company

            st.session_state.search_results = people
            st.session_state.step = 2

            st.success(f"✅ Found {len(people)} people from LinkedIn URL search")
            st.rerun()

        except Exception as e:
            st.error(f"LinkedIn URL search failed: {str(e)}")
            import traceback
            with st.expander("Error details"):
                st.code(traceback.format_exc())


# =============================================================================
# Step 2: Select People for Enrichment
# =============================================================================

def render_enrichment_step():
    """Step 2: Select people and start enrichment."""
    st.markdown('<span class="step-badge">STEP 2</span>', unsafe_allow_html=True)
    st.header("Select People to Enrich")
    
    company = st.session_state.company_data
    people = st.session_state.search_results
    
    if not company or not people:
        st.error("No search results found")
        reset_state()
        st.rerun()
        return
    
    # Company info
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Company", company.get("name", ""))
    with col2:
        st.metric("People Found", len(people))
    with col3:
        st.metric("Domain", company.get("domain", "N/A"))
    
    st.divider()
    
    # People selection
    st.subheader("👥 Select People")

    # Initialize selection state only when people list size changes.
    # Do not reset when list is intentionally empty (after deselect all).
    if st.session_state.get("enrichment_selection_people_count", -1) != len(people):
        st.session_state.enrichment_selected_indices = list(range(len(people)))
        st.session_state.enrichment_selection_people_count = len(people)

    selected_set = set(st.session_state.enrichment_selected_indices)

    title_filter = st.text_input(
        "Filter by title",
        value=st.session_state.get("enrichment_title_filter", ""),
        placeholder="e.g. manager",
        help="Shows only matching rows by title (case-insensitive)",
    )
    st.session_state.enrichment_title_filter = title_filter

    filter_term = (title_filter or "").strip().lower()
    filtered_indices = [
        i for i, person in enumerate(people)
        if not filter_term or filter_term in (person.get("current_title", "") or "").lower()
    ]

    ctrl1, ctrl2, ctrl3 = st.columns([1, 1, 6])
    with ctrl1:
        if st.button("Select All", type="secondary"):
            selected_set.update(filtered_indices)
            st.session_state.enrichment_selected_indices = sorted(selected_set)
            st.session_state.people_editor_version += 1
            st.rerun()
    with ctrl2:
        if st.button("Deselect All", type="secondary"):
            selected_set.difference_update(filtered_indices)
            st.session_state.enrichment_selected_indices = sorted(selected_set)
            st.session_state.people_editor_version += 1
            st.rerun()

    if not filtered_indices:
        st.warning("No people match this title filter.")
        return

    display_data = []
    for original_idx in filtered_indices:
        person = people[original_idx]
        location_parts = [
            person.get("location_city", ""),
            person.get("location_region", ""),
            person.get("location_country", ""),
        ]
        location_value = ", ".join([p for p in location_parts if p])
        display_data.append({
            "select": original_idx in selected_set,
            "full_name": person.get("full_name", ""),
            "current_title": person.get("current_title", ""),
            "location": location_value,
            "linkedin_url": person.get("linkedin_url", ""),
        })

    df = pd.DataFrame(display_data)
    editor_key = f"people_editor_v{st.session_state.get('people_editor_version', 0)}"
    edited = st.data_editor(
        df,
        column_config={
            "select": st.column_config.CheckboxColumn("Select", default=True),
            "full_name": "Name",
            "current_title": "Title",
            "location": "Location",
            "linkedin_url": st.column_config.LinkColumn("LinkedIn")
        },
        hide_index=True,
        width="stretch",
        key=editor_key
    )

    updated_selected = set(selected_set)
    for row_idx, row in edited.iterrows():
        original_idx = filtered_indices[int(row_idx)]
        if bool(row.get("select")):
            updated_selected.add(original_idx)
        else:
            updated_selected.discard(original_idx)

    st.session_state.enrichment_selected_indices = sorted(updated_selected)
    selected_indices = st.session_state.enrichment_selected_indices
    selected_count = len(selected_indices)
    
    with_linkedin = sum(1 for idx in selected_indices if people[idx].get("linkedin_url"))
    
    st.info(f"""
    **Selection Summary:**
    - Selected: {selected_count} people
    - With LinkedIn URLs: {with_linkedin} (better enrichment results)
    - Without LinkedIn: {max(0, selected_count - with_linkedin)} (email/phone only)
    - Visible with current filter: {len(filtered_indices)}
    """)
    
    st.divider()
    
    # Enrichment options
    st.subheader("⚙️ Enrichment Options")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        include_emails = st.checkbox("📧 Include Emails", value=True, disabled=True, help="Email enrichment is always included")
    
    with col2:
        include_phones = st.checkbox("📱 Include Phone Numbers", value=False, help="Include mobile phone number enrichment (10 credits per contact)")

    skip_duplicates = st.checkbox(
        "Skip existing contacts on save",
        value=st.session_state.get("skip_duplicates", True),
        help="If enabled, contacts with existing emails are skipped instead of updated"
    )
    
    # Cost estimate
    if include_phones:
        st.caption("💰 **Estimated cost:** ~11 credits per contact (1 for email + 10 for phone)")
    else:
        st.caption("💰 **Estimated cost:** ~1 credit per contact (email only)")
    
    st.divider()
    
    # Action buttons
    col1, col2 = st.columns([1, 3])
    
    with col1:
        if st.button("← Back to Search"):
            st.session_state.step = 1
            st.rerun()
    
    with col2:
        if st.button("▶️ Enrich Selected", type="primary", width="stretch"):
            if selected_count == 0:
                st.error("Please select at least one person")
            else:
                selected = [people[i] for i in selected_indices]
                run_enrichment(
                    selected,
                    company,
                    include_phones=include_phones,
                    skip_duplicates=skip_duplicates,
                )


def run_enrichment(
    people: list,
    company: dict,
    include_phones: bool = False,
    skip_duplicates: bool = True,
):
    """Execute enrichment."""
    st.session_state.selected_people = people
    st.session_state.skip_duplicates = skip_duplicates
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    tunnel = None
    
    try:
        # Use polling instead of webhooks (more reliable, no tunnel needed)
        # Webhook URL is still required by API but we'll poll for results
        status_text.text("Preparing enrichment...")
        progress_bar.progress(20)
        
        # Use a dummy webhook URL since we're polling
        # (API requires it but we won't wait for it)
        webhook_url = "https://example.com/webhook"  # Dummy - we're using polling
        
        enrichment_type = "emails + phones" if include_phones else "emails only"
        st.info(f"ℹ️ Using API polling (no webhook/tunnel needed) - Enriching: {enrichment_type}")
        
        # Step 2: Format contacts
        status_text.text("Preparing enrichment request...")
        progress_bar.progress(30)
        
        contacts = []
        for person in people:
            contact = {
                "first_name": person.get("first_name", ""),
                "last_name": person.get("last_name", ""),
                "company_name": company.get("name", ""),
                "domain": company.get("domain", ""),
                "linkedin_url": person.get("linkedin_url", "")
            }
            contacts.append(contact)
        
        logger.info(f"Prepared {len(contacts)} contacts for enrichment (phones: {include_phones})")
        if contacts:
            logger.info(f"Sample contact: first_name={contacts[0].get('first_name')}, last_name={contacts[0].get('last_name')}, company={contacts[0].get('company_name')}")
        
        # Step 3: Start enrichment
        status_text.text("Sending to FullEnrich API...")
        progress_bar.progress(40)
        
        service = EnrichmentService()
        
        batch_name = f"Batch {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        result = service.enrich_contacts(
            contacts=contacts,
            webhook_url=webhook_url,
            batch_name=batch_name,
            include_phones=include_phones
        )
        
        enrichment_id = result["enrichment_id"]
        
        # Step 4: Poll for results (faster and more reliable than webhook)
        # FullEnrich duration scales with batch size; avoid fixed 2-minute timeout.
        per_contact_seconds = 35 if include_phones else 25
        timeout_seconds = min(900, max(180, 60 + len(contacts) * per_contact_seconds))

        status_text.text(
            f"⏳ Enriching contacts (timeout {timeout_seconds // 60}m for {len(contacts)} contacts)..."
        )
        progress_bar.progress(50)
        
        # Use polling instead of webhook with dynamic timeout for larger batches.
        poll_result = service.poll_for_results(
            enrichment_id,
            timeout=timeout_seconds,
            poll_interval=10
        )
        
        progress_bar.progress(90)
        
        if not poll_result:
            st.error(
                f"❌ Enrichment timed out after {timeout_seconds // 60} minutes. "
                "Check FullEnrich dashboard for status."
            )
            st.info(f"Enrichment ID: `{enrichment_id}`")
            return
        
        # Extract data from poll result
        webhook_result = poll_result  # Same structure as webhook payload
        
        # Step 6: Process results
        status_text.text("Processing results...")
        progress_bar.progress(80)
        
        processed = service.process_webhook(webhook_result)
        
        # Store in session state (no DB write until user clicks Save)
        st.session_state.enrichment_results = {
            "accounts": processed["accounts"],
            "contacts": processed["contacts"],
            "webhook_payload": webhook_result
        }
        
        progress_bar.progress(100)
        status_text.text("Ready for review!")
        
        st.session_state.step = 3
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Enrichment failed: {str(e)}")
        import traceback
        with st.expander("Error details"):
            st.code(traceback.format_exc())


# =============================================================================
# Step 3: Preview & Save Results
# =============================================================================

def render_preview_step():
    """Step 3: Preview enriched data and save."""
    st.markdown('<span class="step-badge">STEP 3</span>', unsafe_allow_html=True)
    st.header("Preview & Save Results")
    
    results = st.session_state.enrichment_results
    
    if not results:
        st.error("No enrichment results found")
        reset_state()
        st.rerun()
        return
    
    accounts = results["accounts"]
    contacts = results["contacts"]
    webhook = results["webhook_payload"]
    
    # Show which account contacts will be saved under
    selected_account = st.session_state.get("selected_account")
    selected_account_id = st.session_state.get("selected_account_id")
    if selected_account and selected_account_id:
        st.success(
            f"🏢 Contacts will be saved under: **{selected_account.get('company_name', '')}** "
            f"(account_id: `{selected_account_id}`)"
        )
    else:
        st.info("ℹ️ No account selected from dropdown — account will be resolved by company name.")
    
    # Summary metrics
    credits_used = webhook.get("cost", {}).get("credits", 0) or 0
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Contacts Found", len(contacts))
    with col2:
        with_email = sum(1 for c in contacts if c.get("email"))
        st.metric("With Email", with_email)
    with col3:
        st.metric("Credits Used", credits_used)
    
    st.divider()
    
    # Contacts Preview
    st.subheader("👥 Enriched Contacts")
    if contacts:
        contacts_df = pd.DataFrame(contacts)
        
        # Show key columns first
        key_cols = ["full_name", "email", "phone", "job_title", "account", "linkedin_url"]
        cols = [c for c in key_cols if c in contacts_df.columns]
        cols += [c for c in contacts_df.columns if c not in cols]
        
        st.dataframe(contacts_df[cols], width="stretch")
        
        # Email stats
        with_email = sum(1 for c in contacts if c.get("email"))
        email_pct = (with_email / len(contacts) * 100) if contacts else 0
        st.caption(f"✉️ {with_email} contacts with email ({email_pct:.1f}%)")
    else:
        st.warning("No contacts enriched")
    
    st.divider()
    
    st.caption(
        f"Save mode: {'Skip duplicates' if st.session_state.get('skip_duplicates', True) else 'Update existing contacts'}"
    )

    st.divider()
    
    # Actions
    st.subheader("⚡ Actions")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("✅ Save to Database", type="primary", width="stretch"):
            # Use the dedicated account_id stored when user selected from dropdown
            selected_account_id = st.session_state.get("selected_account_id")
            logger.info(f"🔍 Save button clicked - selected_account_id from session: {selected_account_id}")
            logger.info(f"🔍 Full selected_account from session: {st.session_state.get('selected_account')}")
            save_to_database(
                accounts,
                contacts,
                webhook,
                selected_account_id=selected_account_id,
                skip_duplicates=st.session_state.get("skip_duplicates", True),
            )
    
    with col2:
        # Download CSV
        if contacts:
            csv = pd.DataFrame(contacts).to_csv(index=False)
            st.download_button(
                "📥 Download CSV",
                csv,
                f"enriched_contacts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "text/csv",
                width="stretch"
            )
    
    with col3:
        if st.button("❌ Cancel", width="stretch"):
            reset_state()
            st.rerun()

    with col4:
        can_sync = bool(st.session_state.get("last_saved_contacts"))
        if st.button(
            "🔄 Sync to HubSpot",
            width="stretch",
            disabled=not can_sync,
            help="Save contacts first, then sync the saved rows to HubSpot",
        ):
            run_hubspot_sync(st.session_state.get("last_saved_contacts", []))

    sync_result = st.session_state.get("hubspot_sync_result")
    if sync_result:
        st.divider()
        st.subheader("📤 HubSpot Sync Summary")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Attempted", sync_result.get("attempted", 0))
        with c2:
            st.metric("Succeeded", sync_result.get("succeeded", 0))
        with c3:
            st.metric("Failed", sync_result.get("failed", 0))
        with c4:
            st.metric("Skipped", sync_result.get("skipped", 0))

        failures = sync_result.get("failures", [])
        if failures:
            failure_df = pd.DataFrame(failures)
            st.dataframe(failure_df, width="stretch")
            st.download_button(
                "📥 Download Sync Failures CSV",
                failure_df.to_csv(index=False),
                f"hubspot_sync_failures_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "text/csv",
                width="stretch",
            )


def run_hubspot_sync(saved_contacts: list):
    """Run manual HubSpot sync for already-saved contacts."""
    if not saved_contacts:
        st.warning("No saved contacts available for HubSpot sync.")
        return

    with st.spinner("Syncing contacts to HubSpot..."):
        try:
            service = HubSpotSyncService()
            result = service.sync_contacts(saved_contacts)
            st.session_state.hubspot_sync_result = result

            if result.get("failed", 0) > 0:
                st.warning(
                    f"HubSpot sync completed with partial failures: "
                    f"{result.get('succeeded', 0)} succeeded, {result.get('failed', 0)} failed"
                )
            else:
                st.success(
                    f"✅ HubSpot sync completed: {result.get('succeeded', 0)} contacts synced"
                )
        except Exception as e:
            st.error(f"❌ HubSpot sync failed: {str(e)}")
            logger.error(f"HubSpot sync failed: {e}")


def save_to_database(accounts: list, contacts: list, webhook: dict, selected_account_id: str = None, skip_duplicates: bool = True):
    """Save enriched data to database, linking contacts to the selected account directly."""
    logger.info(f"💾 save_to_database called with selected_account_id={selected_account_id}, skip_duplicates={skip_duplicates}")
    
    # If user selected an account from dropdown, override company_name on all contacts
    # to match the account's company_name (not FullEnrich's version)
    selected_account = st.session_state.get("selected_account")
    if selected_account and selected_account_id:
        correct_company_name = selected_account.get("company_name", "")
        logger.info(f"Overriding company_name for all contacts: {correct_company_name}")
        for contact in contacts:
            contact["company_name"] = correct_company_name
    
    with st.spinner("Saving to database..."):
        try:
            service = EnrichmentService()
            
            # Save to final tables — pass selected_account_id so every contact
            # gets linked to the account the user chose from the dropdown
            logger.info(f"Calling save_to_final_tables with selected_account_id={selected_account_id}")
            acc_count, con_count = service.save_to_final_tables(
                accounts, contacts, 
                selected_account_id=selected_account_id,
                skip_duplicates=skip_duplicates
            )
            
            # Create history record
            from src.db.supabase_client import SupabaseClient
            db = SupabaseClient()
            
            batch_name = f"Batch {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            credits = webhook.get("cost", {}).get("credits", 0) or 0
            
            history_id = db.create_enrichment_history(
                batch_name=batch_name,
                contacts_count=len(contacts),
                with_linkedin=sum(1 for c in contacts if c.get("linkedin_url")),
                source="streamlit"
            )
            
            if history_id:
                db.update_enrichment_history(
                    record_id=history_id,
                    status="completed",
                    credits_used=credits,
                    accounts_inserted=len(accounts),
                    contacts_inserted=len(contacts)
                )

            # Pull saved rows (including DB IDs) for downstream HubSpot sync.
            saved_emails = [c.get("email", "") for c in contacts if c.get("email")]
            saved_contacts = db.get_contacts_by_emails(saved_emails)

            # Keep DB ids for traceability, but prefer latest enrichment field values
            # for HubSpot sync even when skip-duplicates is enabled.
            db_by_email = {
                (row.get("email") or "").strip().lower(): row
                for row in saved_contacts
                if row.get("email")
            }
            sync_contacts = []
            for contact in contacts:
                email_key = (contact.get("email") or "").strip().lower()
                if not email_key or email_key not in db_by_email:
                    continue
                merged = dict(db_by_email[email_key])
                merged.update(contact)
                merged["id"] = db_by_email[email_key].get("id")
                sync_contacts.append(merged)

            st.session_state.last_saved_contacts = sync_contacts if sync_contacts else saved_contacts

            # Replace preview contacts with DB rows so IDs shown in UI match Supabase.
            if st.session_state.get("enrichment_results") is not None and saved_contacts:
                st.session_state.enrichment_results["contacts"] = saved_contacts
            
            # Show correct account info
            if selected_account:
                account_info = f"**{selected_account.get('company_name', '')}** (ID: `{selected_account_id}`)"
            else:
                account_info = "Resolved by company name"
            
            st.success(f"""
            ✅ **Saved to Database!**
            
            - **Account:** {account_info}
            - **Contacts Saved:** {con_count}
            - **Credits Used:** {credits}
            """)
            
            if st.button("🔄 Start New Search"):
                reset_state()
                st.rerun()
                
        except Exception as e:
            st.error(f"❌ Save failed: {str(e)}")
            import traceback
            with st.expander("Error details"):
                st.code(traceback.format_exc())


# =============================================================================
# Run Application
# =============================================================================

if __name__ == "__main__":
    main()
