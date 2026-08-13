# Intelligent Candidate Discovery & Ranking System (TrueFit-AI)

> 🌐 **Live Web Application Demo**: [https://truefit-ai-iiik.onrender.com](https://truefit-ai-iiik.onrender.com)  
> ⚡ **Live API Health Endpoint**: [https://truefit-ai-iiik.onrender.com/api/health](https://truefit-ai-iiik.onrender.com/api/health)

## Overview

A full-stack, rule-based multi-signal candidate scoring & discovery platform with **TF-IDF text relevance**, **honeypot trap detection**, and **behavioral signal calibration** that ranks 100K candidates for a Senior AI Engineer role.

It features an interactive **Web Application Dashboard & Python REST API Backend** (`server.py`) for real-time candidate search, live weight tuning, honeypot security auditing, candidate deep-dive inspection, and submission CSV generation.

---

## Architecture & Features

### 1. 4-Layer Scoring Pipeline

1. **Honeypot Trap Detection** — Flags ~42 candidates with impossible profiles (expert skills with 0 months usage, career math that doesn't add up, non-tech keyword stuffing).
2. **6-Dimension Core Fit Scoring** — Weighted dimensions: Title Relevance (0.25), Skills Match with Trust Weighting (0.25), Career Quality & Company Mix (0.20), Experience Fit (0.15), Location Alignment (0.10), Education (0.05).
3. **TF-IDF Text Relevance** — Cosine similarity of candidate summaries + career descriptions against JD-derived query terms.
4. **Behavioral Modifier** — Multiplicative adjustment based on 11 platform signals (recency, response rate, notice period, verification, OTW flag).

**Final Score** = `(0.55 × Core Fit + 0.45 × Text Relevance) × Behavioral Modifier`

---

### 2. Web Application & REST API (`server.py`)

- **📁 Custom Dataset Upload**: Anyone can upload their own candidate dataset (`.json` or `.jsonl`) directly from the Web UI (or via `POST /api/upload`) to evaluate and rank custom candidates instantly.
- **Interactive Leaderboard**: Filter candidates by title, country, experience range, honeypot status, and live search.
- **Candidate 360° Inspection Modal**: Itemized score decomposition across all 6 core fit dimensions, skill trust matrix, behavioral multipliers, and AI-generated recruiter reasoning narratives.
- **Live Weight Tuning Studio**: Adjust model weights (`CORE_FIT_WEIGHT`, `TEXT_RELEVANCE_WEIGHT`, sub-weights, custom JD prompt) and trigger instant re-ranking.
- **Honeypot Security Audit Console**: View flagged honeypots with detailed trap trigger analysis.
- **One-Click Export**: Download valid top-100 `submission.csv` directly from the dashboard.

---

## Quick Start

### Prerequisites
```
Python 3.10+
```

### Installation
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install scikit-learn numpy
```

---

### 1. Run Web Application Dashboard & REST API
```powershell
python server.py --port 8000
```
Then open your browser at:
- **Dashboard UI**: `http://localhost:8000`
- **API Health**: `http://localhost:8000/api/health`
- **REST Endpoints**: `http://localhost:8000/api/candidates`

---

### 2. CLI Ranking Pipeline (Direct CSV Generation)
```powershell
python rank.py --candidates ".[PUB] India_runs_data_and_ai_challenge\[PUB] India_runs_data_and_ai_challenge\India_runs_data_and_ai_challenge\candidates.jsonl" --out .\submission.csv
```

### 3. Validate Submission
```powershell
python ".[PUB] India_runs_data_and_ai_challenge\[PUB] India_runs_data_and_ai_challenge\India_runs_data_and_ai_challenge\validate_submission.py" .\submission.csv
```

---

## File Structure

```
├── server.py               # Python REST API backend server & static web server
├── rank.py                 # CLI ranking pipeline script
├── config.py               # All tunable constants and weights
├── candidate_scorer.py     # Core fit scoring (title, skills, career, experience, location, education)
├── text_scorer.py          # TF-IDF text relevance scoring
├── behavioral_scorer.py    # Behavioral signal modifier
├── honeypot_detector.py    # Honeypot detection
├── utils.py                # Data loading, reasoning generation, CSV output
├── static/                 # Web Application Frontend
│   ├── index.html          # Dashboard HTML structure
│   ├── styles.css          # Glassmorphism dark theme & styles
│   └── app.js              # Client SPA application logic
├── requirements.txt        # Dependencies
└── submission.csv          # Ranked output (top 100)
```
