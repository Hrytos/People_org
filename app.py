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
from pathlib import Path
from datetime import datetime

# Add project root to path so src.* packages resolve (and relative imports inside src work)
sys.path.insert(0, str(Path(__file__).parent))

from src.core.config import validate_config, SUPABASE_URL, SUPABASE_SERVICE_KEY
from src.core.logging import setup_logger
from src.services.people_search import PeopleSearchService
from src.services.enrichment import EnrichmentService

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
        st.session_state.selected_account = None  # From accounts table if dropdown used
    if 'selected_people' not in st.session_state:
        st.session_state.selected_people = []
    if 'enrichment_results' not in st.session_state:
        st.session_state.enrichment_results = None


def reset_state():
    """Reset to initial state."""
    st.session_state.step = 1
    st.session_state.search_results = None
    st.session_state.company_data = None
    st.session_state.selected_account = None
    st.session_state.selected_people = []
    st.session_state.enrichment_results = None


# =============================================================================
# Main Application
# =============================================================================

def main():
    init_session_state()
    
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


# =============================================================================
# Step 1: Search People
# =============================================================================

def render_search_step():
    """Step 1: Search for people at a company."""
    st.markdown('<span class="step-badge">STEP 1</span>', unsafe_allow_html=True)
    st.header("Find People at Company")
    
    st.info("💡 **Tip:** Search returns people with their LinkedIn profiles and job titles")
    
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
    
    with st.form("search_form"):
        # ========== SECTION 1: Select Existing Account ==========
        if account_options:
            st.subheader("🏢 Select Existing Account")
            st.caption(f"💡 {len(account_options)} accounts available - start typing to search")
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                selected_account = st.selectbox(
                    "Choose from existing accounts (optional)",
                    options=[""] + sorted(account_options.keys()),
                    format_func=lambda x: "Type below or select..." if x == "" else x,
                    help="Quick select from your existing accounts. Start typing to filter."
                )
            
            with col2:
                account_limit = st.number_input(
                    "Max Results",
                    min_value=10,
                    max_value=100,
                    value=25,
                    step=5,
                    key="account_limit"
                )
            
            account_title = st.text_input(
                "Job Title (optional)",
                placeholder="e.g., VP of Engineering, Director of Sales",
                help="Filter by job title (partial match)",
                key="account_title"
            )
        else:
            selected_account = ""
            account_limit = 25
            account_title = ""
        
        st.divider()
        
        # ========== SECTION 2: Enter Company Domain ==========
        st.subheader("🔍 Or Enter Company Domain")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            company_domain_input = st.text_input(
                "Company Domain *",
                placeholder="e.g., google.com, openai.com, tesla.com",
                help="Enter company domain (e.g., company.com)",
                key="domain_input"
            )
        
        with col2:
            domain_limit = st.number_input(
                "Max Results",
                min_value=10,
                max_value=100,
                value=25,
                step=5,
                key="domain_limit"
            )
        
        domain_title = st.text_input(
            "Job Title (optional)",
            placeholder="e.g., VP of Engineering, Director of Sales",
            help="Filter by job title (partial match)",
            key="domain_title"
        )
        
        submitted = st.form_submit_button("🔍 Search People", type="primary", width="stretch")
        
        if submitted:
            # Determine which section was used
            if selected_account and selected_account != "":
                # ===== SECTION 1: Using existing account =====
                company_name = selected_account
                account_data = account_options.get(selected_account)
                st.session_state.selected_account = account_data
                domain = account_data.get("account_domain", "")
                title = account_title
                limit = account_limit
                
            elif company_domain_input:
                # ===== SECTION 2: Using manual domain entry =====
                company_name = company_domain_input  # Use domain as identifier
                st.session_state.selected_account = None
                domain = company_domain_input  # Direct domain input
                title = domain_title
                limit = domain_limit
                
            else:
                st.error("Please either select an existing account OR enter a company domain")
                return
            
            run_people_search(company_name, title, limit, domain)


def run_people_search(company_name: str, title: str, limit: int, domain: str = None):
    """Execute people search."""
    with st.spinner(f"Searching people at {company_name}..."):
        try:
            service = PeopleSearchService()
            
            # Search (use domain if available for better accuracy)
            company, people = service.search_people(
                company_name=company_name,
                domain=domain,
                title=title if title else None,
                limit=limit
            )
            
            if not company:
                st.error(f"Company not found: {company_name}")
                return
            
            if not people:
                st.warning(f"No people found at {company['name']}")
                if title:
                    st.info(f"Try searching without the title filter")
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
    
    # Select all checkbox
    select_all = st.checkbox("Select All", value=True)
    
    # Build selection - if "Select All" is checked, select everyone; otherwise use empty list for now
    # (Individual selection would require data_editor or multiselect, keeping it simple with Select All for now)
    if select_all:
        selected_indices = list(range(len(people)))
        selected_count = len(people)
    else:
        selected_indices = []
        selected_count = 0
    
    # Create DataFrame for display
    display_data = []
    for person in people:
        display_data.append({
            "full_name": person.get("full_name", ""),
            "current_title": person.get("current_title", ""),
            "location": f"{person.get('location_city', '')}, {person.get('location_region', '')}".strip(", "),
            "has_linkedin": "✓" if person.get("linkedin_url") else "✗"
        })
    
    df = pd.DataFrame(display_data)
    
    # Show table
    st.dataframe(
        df,
        column_config={
            "full_name": "Name",
            "current_title": "Title",
            "location": "Location",
            "has_linkedin": st.column_config.TextColumn("LinkedIn", width="small")
        },
        hide_index=True,
        width="stretch"
    )
    
    with_linkedin = sum(1 for p in people if p.get("linkedin_url"))
    
    st.info(f"""
    **Selection Summary:**
    - Selected: {selected_count} people
    - With LinkedIn URLs: {with_linkedin} (better enrichment results)
    - Without LinkedIn: {selected_count - with_linkedin} (email/phone only)
    """)
    
    st.divider()
    
    # Enrichment options
    st.subheader("⚙️ Enrichment Options")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        include_emails = st.checkbox("📧 Include Emails", value=True, disabled=True, help="Email enrichment is always included")
    
    with col2:
        include_phones = st.checkbox("📱 Include Phone Numbers", value=False, help="Include mobile phone number enrichment (10 credits per contact)")
    
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
                run_enrichment(selected, company, include_phones=include_phones)


def run_enrichment(people: list, company: dict, include_phones: bool = False):
    """Execute enrichment."""
    st.session_state.selected_people = people
    
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
        status_text.text("⏳ Enriching contacts (typically 60-120 seconds)...")
        progress_bar.progress(50)
        
        # Use polling instead of webhook (timeout: 120s = 2 minutes)
        poll_result = service.poll_for_results(enrichment_id, timeout=120, poll_interval=10)
        
        progress_bar.progress(90)
        
        if not poll_result:
            st.error("❌ Enrichment timed out after 2 minutes. Check FullEnrich dashboard for status.")
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
    
    # Summary metrics
    credits_used = webhook.get("cost", {}).get("credits", 0) or 0
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Accounts", len(accounts))
    with col2:
        st.metric("Contacts", len(contacts))
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
    
    # Accounts Preview
    with st.expander("🏢 View Accounts"):
        if accounts:
            accounts_df = pd.DataFrame(accounts)
            st.dataframe(accounts_df, width="stretch")
    
    st.divider()
    
    # Actions
    st.subheader("⚡ Actions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("✅ Save to Database", type="primary", width="stretch"):
            save_to_database(accounts, contacts, webhook)
    
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


def save_to_database(accounts: list, contacts: list, webhook: dict):
    """Save enriched data to database."""
    with st.spinner("Saving to database..."):
        try:
            service = EnrichmentService()
            
            # Save to final tables
            acc_count, con_count = service.save_to_final_tables(accounts, contacts)
            
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
            
            st.success(f"""
            ✅ **Saved to Database!**
            
            - **Accounts:** {len(accounts)}
            - **Contacts:** {len(contacts)}
            - **Credits:** {credits}
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
