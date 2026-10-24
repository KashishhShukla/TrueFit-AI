# Intelligent Candidate Discovery & Ranking System (TrueFit-AI)

> 🌐 **Live Web Application Demo**: [https://truefit-ai-iiik.onrender.com](https://truefit-ai-iiik.onrender.com)  
> ⚡ **Live API Health Endpoint**: [https://truefit-ai-iiik.onrender.com/api/health](https://truefit-ai-iiik.onrender.com/api/health)  
> 🗄️ **Database Architecture**: Unified **PostgreSQL** (Production / Cloud) + **SQLite** (Local Zero-Config Fallback)

---

## Overview

A full-stack, rule-based multi-signal candidate scoring & discovery platform with **TF-IDF text relevance**, **honeypot trap detection**, **behavioral signal calibration**, and a **production-grade relational database** that ranks 100K candidates for a Senior AI Engineer role.

It features an interactive **Web Application Dashboard & Python REST API Backend** (`server.py`), persistent **PostgreSQL & SQLite Relational Storage** (`database.py`), a dedicated **Database Management CLI** (`db.py`), candidate shortlisting, and live weight tuning.

---

## 🗄️ Database Architecture (PostgreSQL + SQLite)

TrueFit-AI implements a **dual-engine relational database layer**:
1. **PostgreSQL** (Production / Cloud / Docker): Enterprise grade, multi-user concurrency, high-performance indexed queries. Auto-detected whenever `DATABASE_URL` is set (e.g. Render PostgreSQL, Supabase, Neon, AWS RDS, or Docker Compose).
2. **SQLite** (Local Development): File-based (`truefit.db`) zero-config fallback built into Python standard library. Anyone cloning the repository can start the server immediately without needing to configure a local PostgreSQL daemon!

### Relational Database Schema

```
 ┌──────────────────────┐         ┌──────────────────────┐
 │      candidates      │         │     scoring_runs     │
 ├──────────────────────┤         ├──────────────────────┤
 │ PK candidate_id      │         │ PK run_id            │
 │    name              │         │    created_at        │
 │    title             │         │    dataset_source    │
 │    company           │         │    total_candidates  │
 │    industry          │         │    valid_candidates  │
 │    location, country │         │    top_score         │
 │    years_of_exp      │         │    cutoff_score_100  │
 │    skills_json       │         │    weights_json      │
 │    redrob_signals    │         │    is_active         │
 └──────────┬───────────┘         └──────────┬───────────┘
            │ 1:N                            │ 1:N
            │         ┌──────────────────────┐
            └────────►│   candidate_scores   │◄─────────┘
                      ├──────────────────────┤
                      │ PK id                │
                      │ FK run_id            │
                      │ FK candidate_id      │
                      │    rank              │
                      │    final_score       │
                      │    core_fit_score    │
                      │    text_relevance    │
                      │    behavioral_mod    │
                      │    6 dimension scores│
                      │    is_honeypot       │
                      │    reasoning         │
                      └──────────────────────┘

 ┌──────────────────────┐         ┌──────────────────────┐
 │      shortlists      │         │    activity_logs     │
 ├──────────────────────┤         ├──────────────────────┤
 │ PK id                │         │ PK id                │
 │ FK candidate_id (UQ) │         │    action            │
 │    status            │         │    details           │
 │    starred           │         │    timestamp         │
 │    recruiter_notes   │         └──────────────────────┘
 │    updated_at        │
 └──────────────────────┘
```

### Table Descriptions

- **`candidates`**: Stores normalized candidate profiles, skills taxonomies, career histories, and behavioral platform signals.
- **`scoring_runs`**: Tracks history and metadata of every ranking run, model weights used, top scores, and cutoff metrics.
- **`candidate_scores`**: Relational itemized score breakdown across all 6 core fit dimensions, text cosine similarity, honeypot disqualifications, and AI recruiter reasoning.
- **`shortlists`**: Recruiter bookmarks, stars, hiring stages (`shortlisted`, `interviewing`, `offer`, `rejected`), and confidential evaluation notes.
- **`activity_logs`**: Audit trail of dataset imports, weight adjustments, exports, and shortlisting actions.

---

## 🚀 Quick Start

### Prerequisites
```
Python 3.10+
```

### 1. Installation
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

### 2. Database Setup Options

#### Option A: Zero-Config SQLite (Default Local Mode)
No configuration required! Simply launch the server:
```powershell
python server.py --port 8000
```
TrueFit-AI automatically initializes `truefit.db`, creates tables, and auto-seeds the candidate dataset.

#### Option B: Docker Compose (PostgreSQL + Web App)
Spin up a dedicated PostgreSQL 15 database and the TrueFit-AI web service in one command:
```bash
docker compose up -d
```
- App: `http://localhost:8000`
- PostgreSQL: `localhost:5432` (db: `truefit`, user: `postgres`, password: `truefit_password`)

#### Option C: Cloud PostgreSQL (Render / Supabase / Neon / AWS RDS)
Set the `DATABASE_URL` environment variable:
```powershell
$env:DATABASE_URL = "postgresql://user:password@hostname:5432/truefit"
python server.py --port 8000
```

---

### 3. Database Management CLI (`db.py`)

A built-in CLI utility for inspecting, seeding, and querying the database:

```powershell
# Check database status and engine
python db.py status

# Initialize / verify schema tables and indexes
python db.py init

# Ingest candidates dataset and run scoring pipeline
python db.py seed --data ./sample_candidates.json

# View past scoring runs saved in the database
python db.py runs

# Export top 100 candidates directly from database to CSV
python db.py export --out ./submission.csv
```

---

### 4. REST API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | System and database connection status |
| `GET` | `/api/db/status` | Detailed database diagnostics & candidate counts |
| `GET` | `/api/candidates` | Paginated candidate search with indexed SQL filtering |
| `GET` | `/api/candidates/:id` | Full candidate 360° record with recruiter notes |
| `POST` | `/api/candidates/:id/shortlist` | Bookmark candidate, update hiring status, add notes |
| `GET` | `/api/shortlists` | Fetch all shortlisted candidates and recruiter notes |
| `GET` | `/api/runs` | Fetch historical scoring runs stored in database |
| `POST` | `/api/runs/:id/activate` | Switch active scoring run |
| `GET` | `/api/honeypots` | List flagged honeypot profiles |
| `POST` | `/api/upload` | Upload & ingest custom candidates dataset into database |
| `POST` | `/api/rank` | Live weight re-tuning & re-scoring |
| `GET` | `/api/export` | Download validated top-100 `submission.csv` |

---

## File Structure

```
├── database.py             # Unified PostgreSQL & SQLite database layer & query engine
├── db.py                   # CLI database administration tool
├── server.py               # REST API server & static web server (PostgreSQL/SQLite enabled)
├── docker-compose.yml      # PostgreSQL 15 container + Web App configuration
├── render.yaml             # Render deployment with auto-provisioned PostgreSQL database
├── .env.example            # Environment variables template
├── rank.py                 # CLI ranking pipeline script (--save-db flag supported)
├── config.py               # Tunable constants, weights, and database configuration
├── candidate_scorer.py     # Core fit scoring (6 dimensions)
├── text_scorer.py          # TF-IDF text relevance scoring
├── behavioral_scorer.py    # Behavioral signal calibration
├── honeypot_detector.py    # Honeypot detection
├── utils.py                # Data loading, reasoning generation, CSV output
├── static/                 # Web Application Frontend
│   ├── index.html          # Dashboard HTML with DB indicator, Shortlists, & Runs
│   ├── styles.css          # Glassmorphism dark theme & styles
│   └── app.js              # Client SPA application logic with DB sync
├── requirements.txt        # Dependencies (scikit-learn, psycopg2-binary, SQLAlchemy)
└── submission.csv          # Ranked output (top 100)
```
