# People Search + Enrichment

**Complete FullEnrich API v2 Integration with Streamlit UI**

Find people at companies by domain and enrich their contact information (emails, phones, LinkedIn profiles) using the FullEnrich API. Built for production with existing database integration.

---

## 🎯 Features

### Search
- 🏢 **Existing Account Integration** - Dropdown with 1000+ accounts from your database
- 🌐 **Domain-First Search** - Search by company domain for accurate results
- 🎯 **Dual Search Options** - Select existing account OR enter domain manually
- 👥 **People Discovery** - Find people with LinkedIn profiles and job titles
- 🔍 **Title Filtering** - Filter by job title (e.g., "engineer", "VP")
- 📊 **Flexible Limits** - Choose 10-100 results per search

### Enrichment
- 📧 **Email Discovery** - Work & personal emails with verification status (1 credit)
- 📱 **Optional Phone Numbers** - Mobile phone enrichment opt-in (10 credits)
- 💰 **Cost Control** - Email-only by default, phone enrichment optional
- 💼 **Profile Data** - Job titles, LinkedIn profiles, company info
- ⚡ **Batch Processing** - Enrich up to 100 contacts per request
- 🔄 **Fast API Polling** - Results in 60-120 seconds (no webhooks!)
- 🚀 **Simple Setup** - No tunnels, no webhook servers required

### Data Management
- 💾 **Existing Database Integration** - Uses your `accounts` and `contacts` tables
- 🔗 **Account Linking** - Auto-links contacts to accounts by company name
- 🔄 **Smart Upsert** - Insert new contacts, update existing (by email)
- 🎯 **Role Calculation** - Auto-calculates role_value from job titles
- 📈 **Credit Tracking** - Real-time balance and cost estimates
- 📊 **Session-Based Search** - Search results in memory only

### UI/UX
- 🎨 **Modern Streamlit UI** - Clean 3-step workflow
- 👀 **Preview Before Save** - Review enriched data before committing
- 💡 **Cost Estimates** - See credit cost before enriching
- 📊 **Real-time Progress** - Live polling status updates
- ✅ **Select All** - Quick selection for bulk enrichment

---

## 📋 Requirements

- **Python 3.10+**
- **FullEnrich API Key** - [Get yours here](https://app.fullenrich.com/app/api)
- **Supabase Account** - [Sign up here](https://supabase.com)

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Using Poetry (recommended)
poetry install
poetry shell

# OR using pip
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your credentials
# Required:
#   - FULLENRICH_API_KEY
#   - SUPABASE_URL
#   - SUPABASE_SERVICE_KEY
```

### 3. Setup Database

The app uses your **existing tables**:
- `accounts` - Your company/account table (read-only for dropdown)
- `contacts` - Enriched contact data is saved here
- `enrichment_history` - Optional: Track enrichment runs and credits

**Note:** Search results are kept in-memory only. Only **enriched** contacts are saved to the `contacts` table when you click "Save".

### 4. Run Application

```bash
# Start Streamlit UI (that's it!)
streamlit run app.py
```

Open your browser to `http://localhost:8502`

---

## 📖 Usage Guide

### Step 1: Search for People

**Option A: Search by Existing Account**
1. Click the dropdown in Section 1
2. Type to search your 1000+ accounts
3. Select an account (e.g., "Google LLC")
4. Set max results (10-100)
5. Optional: Add job title filter
6. Click "Search People"

**Option B: Search by Domain**
1. Leave Section 1 dropdown empty
2. In Section 2, enter company domain (e.g., `google.com`)
3. Set max results (10-100)
4. Optional: Add job title filter
5. Click "Search People"

### Step 2: Select & Enrich

1. Review the people found (with LinkedIn profiles and titles)
2. "Select All" is checked by default
3. **Choose enrichment options:**
   - 📧 **Include Emails** (always on) - 1 credit per contact
   - 📱 **Include Phone Numbers** (optional) - 10 credits per contact
4. See cost estimate before enriching
5. Click "Enrich Selected"
6. Wait 60-120 seconds (live polling status)

### Step 3: Preview & Save

1. Review enriched contact data (emails, phones, LinkedIn)
2. Check statistics (contacts found, enrichment success rate)
3. Click "Save to Database"
4. Contacts saved to your `contacts` table with `account_id` linked
5. Click "Start Over" for new search

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     STREAMLIT UI                        │
│                    (3-Step Workflow)                    │
└──────────────────────┬──────────────────────────────────┘
                       │
    ┌──────────────────┴──────────────────┐
    │                                      │
    ▼                                      ▼
┌────────────────┐                  ┌──────────────┐
│  PEOPLE SEARCH │                  │  ENRICHMENT  │
│    SERVICE     │                  │   SERVICE    │
└────────┬───────┘                  └──────┬───────┘
         │                                 │
         ▼                                 ▼
┌────────────────────────────────────────────────────────┐
│              FULLENRICH API CLIENT                     │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │Company Search│  │People Search │  │ Enrichment  │  │
│  └──────────────┘  └──────────────┘  └─────────────┘  │
└────────────────────────────────────────────────────────┘
         │                   │                  │
         └───────────────────┴──────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   SUPABASE DB   │
                    └─────────────────┘
```

---

## 📁 Project Structure

```
People_org/
├── app.py                          # Main Streamlit application
├── pyproject.toml                  # Poetry dependencies
├── .env.example                    # Environment template
├── .gitignore
├── README.md
├── src/
│   ├── core/                       # Core utilities
│   │   ├── config.py              # Configuration management
│   │   ├── logging.py             # Structured logging with PII redaction
│   │   └── http.py                # HTTP client with retries
│   ├── fullenrich/                # FullEnrich API integration
│   │   ├── client.py              # API client (search + enrichment + polling)
│   │   ├── mappers.py             # Response mapping
│   │   └── rate_limit.py          # Rate limiter (60 req/min)
│   ├── db/                        # Database layer
│   │   └── supabase_client.py     # Supabase client with upsert logic
│   └── services/                  # Business logic
│       ├── people_search.py       # Search orchestration
│       └── enrichment.py          # Enrichment orchestration (with polling)
├── supabase/
│   └── migrations/
│       └── 01_create_tables.sql   # Database schema
└── docs/
    ├── FullEnrich_People_Search_and_Enrichment_Module_Plan.md
    └── FullEnrich_Streamlit_Poetry_Deployment_Rulebook.md
```

---

## ⚙️ Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `FULLENRICH_API_KEY` | Yes | Your FullEnrich API key |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Yes | Supabase service role key |
| `RATE_LIMIT_PER_MINUTE` | No | API rate limit (default: 60) |
| `BATCH_SIZE` | No | Max contacts per enrichment (default: 100) |
| `REQUEST_TIMEOUT` | No | HTTP timeout in seconds (default: 30) |

---

## 🔧 API Rate Limits

FullEnrich API limits (as of API v2):

- **60 requests per minute** (all endpoints)
- **100 contacts per bulk enrichment**
- **100 concurrent enrichments** (queue size)

The application automatically handles rate limiting.

---

## 💰 Credit Usage

**Search APIs (Free):**
- Company Search: **0 credits**
- People Search: **0 credits**

**Enrichment (Pay-per-contact):**
- **Email enrichment:** 1 credit per contact
  - Includes: most_probable_email, all emails, verification status
- **Phone enrichment:** 10 credits per contact (optional)
  - Includes: mobile phone number with region
- **Profile data:** Included free with email/phone
  - LinkedIn profile, job title, company info, location

**Cost Examples:**
- 10 contacts, email only: **10 credits**
- 10 contacts, email + phone: **110 credits** (10 × 11)
- 50 contacts, email only: **50 credits**
- 50 contacts, email + phone: **550 credits** (50 × 11)

**Default:** Email-only enrichment to save credits. Check "Include Phone Numbers" to enable phone enrichment.

Check your balance in the UI sidebar.

---

## 🐛 Troubleshooting

### "Domain not found in FullEnrich database"
- **Cause:** Company/domain not tracked by FullEnrich
- **Solution:** 
  - Try well-known companies (Google, Microsoft, Salesforce, HubSpot)
  - Use the account dropdown (verified domains from your database)
  - Smaller/newer companies may not be in FullEnrich's database

### "Search returns wrong people (839M results)"
- **Cause:** Should not happen (fixed in current version)
- **If it does:** Report immediately - this indicates API payload issue

### "Port 8502 is not available"
- **Cause:** Streamlit already running or port in use
- **Solution:** 
  ```bash
  # Windows PowerShell
  Get-Process -Name streamlit | Stop-Process -Force
  
  # Or use different port
  streamlit run app.py --server.port 8503
  ```

### "Rate limit exceeded"
- **Cause:** More than 60 requests per minute
- **Solution:** Built-in rate limiter should handle this automatically. Wait 60 seconds if you see this error.

### "Enrichment timeout after 120s"
- **Typical time:** 60-120 seconds for most batches
- **If timeout occurs:**
  1. Check FullEnrich dashboard for enrichment status
  2. Verify you have sufficient credits
  3. Try smaller batch size
  4. Check internet connection

### "0 contacts returned after enrichment"
- **Cause:** API version mismatch (fixed in current version)
- **If it happens:** Restart the app and try again

### "No emails found"
- People with LinkedIn URLs get 5-20% better email results
- People without LinkedIn get email/phone only (lower success rate)
- Not all contacts have publicly available emails
- This is normal - enrichment success varies by person

### "Database connection failed"
- Verify `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` in `.env`
- Check network connection to Supabase
- Test: `poetry run python -c "from src.db.supabase_client import SupabaseClient; db = SupabaseClient(); print('OK')"`

---

## 🔐 Security & PII

Following the Rulebook:

- ✅ API keys stored in `.env` (never committed)
- ✅ PII redaction in logs (emails/phones masked)
- ✅ Database-side deduplication (email as unique key)
- ✅ Preview before saving (user control)
- ✅ Secure polling (direct API, no exposed webhooks)

---

## 📚 Documentation

- **[Complete Implementation Guide](docs/IMPLEMENTATION_GUIDE.md)** - Comprehensive 2600+ line guide covering architecture, APIs, data flow, deployment, and troubleshooting
- [Implementation Plan](docs/FullEnrich_People_Search_and_Enrichment_Module_Plan.md)
- [Deployment Rulebook](docs/FullEnrich_Streamlit_Poetry_Deployment_Rulebook.md)
- [FullEnrich API Docs](https://docs.fullenrich.com)
- [Database Schema](supabase/README_SCHEMA.md)

---

## 🧪 Testing

Free test contact (0 credits):

```csv
First Name,Last Name,Company Name,LinkedIn URL
Grégoire,Démogé,FullEnrich,https://www.linkedin.com/in/demoge/
```

---

## 🚢 Deployment

### Streamlit Community Cloud

1. Push code to GitHub
2. Connect Streamlit Cloud
3. Add secrets in Streamlit UI
4. Deploy

**Note:** Uses API polling - no webhook server needed!

### Docker

```bash
# Build
docker build -t people-enrichment .

# Run
docker run -p 8501:8501 --env-file .env people-enrichment
```

---

## 📝 License

MIT

---

## 🙏 Acknowledgments

- Built with [FullEnrich API v2](https://fullenrich.com)
- UI powered by [Streamlit](https://streamlit.io)
- Database by [Supabase](https://supabase.com)
- Reference implementation: People-sense

---

## 📞 Support

For issues or questions:
1. Check the troubleshooting section
2. Review the documentation
3. Check FullEnrich API docs
4. Open an issue on GitHub

---

**Built following best practices from the FullEnrich Rulebook**
