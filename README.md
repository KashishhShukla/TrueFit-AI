# Intelligent Candidate Discovery & Ranking System

## Demo Video

You can watch the project demonstration here:

https://drive.google.com/file/d/1Er3OPDtF6cFLhnOHJyg4BfzmwNOinvVd/view?usp=sharing

## Overview

A rule-based multi-signal scoring system with TF-IDF text relevance that ranks 100K candidates for a Senior AI Engineer role. Designed to think like a great recruiter — not match keywords, but understand who actually fits.

## How It Works

**4-Layer Pipeline:**

1. **Honeypot Detection** — Flags ~42 candidates with impossible profiles (expert skills with 0 months usage, career math that doesn't add up)
2. **Core Fit Scoring** — 6 weighted dimensions: title relevance (0.25), skills match with trust weighting (0.25), career quality (0.20), experience fit (0.15), location (0.10), education (0.05)
3. **TF-IDF Text Relevance** — Cosine similarity of candidate summaries + career descriptions against JD-derived query terms
4. **Behavioral Modifier** — Multiplicative adjustment based on 11 platform signals (recency, response rate, notice period, verification, etc.)

**Final Score** = (0.55 × Core Fit + 0.45 × Text Relevance) × Behavioral Modifier

## Key Design Decisions

- **Rule-based over embeddings**: The dataset contains keyword-stuffer traps (68K non-tech candidates with AI skills listed). Embedding similarity would rank them high. Rule-based title checking catches them trivially.
- **Skills trust weighting**: Skills aren't binary — "expert" proficiency with 0 endorsements and 0 months duration is suspicious. Platform assessment scores override self-reported proficiency.
- **Behavioral signals as multiplier, not additive**: A perfect-on-paper candidate who hasn't logged in for 6 months gets 0.5x, as the JD explicitly instructs.

## Quick Start

### Prerequisites

```
Python 3.10+
```

### Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install scikit-learn numpy
```

### Run

```powershell
python rank.py --candidates "path/to/candidates.jsonl" --out .\submission.csv
```

### Dataset Access

The raw candidate dataset file `candidates.jsonl` (~487 MB) is too large to be uploaded directly to GitHub.

- **To get the dataset:** Download it directly from the official **[Redrob | H2S India.runs Hackathon Portal](https://hack2skill.com/)** or use your challenge dashboard.
- **To run the project locally:** Download the dataset, name it `candidates.jsonl`, and place it in the project directory, then update the `--candidates` path in the run command.

**Expected output:**

```
[1/6] Loading candidates...
       Loaded 100000 candidates in 5.9s
[2/6] Detecting honeypots...
       Flagged 42 honeypots in 3.4s
[3/6] Computing core fit scores...
       Done in 5.9s
[4/6] Computing TF-IDF text relevance...
       Done in 27.7s
[5/6] Computing behavioral modifiers...
       Done in 0.8s
[6/6] Combining scores and ranking...

       Wrote top 100 to .\submission.csv
       Total runtime: 44.3s
       Score range: 1.1360 (rank 1) to 0.5737 (rank 100)

       Top 5 candidates:
         1. CAND_0002025 | Senior AI Engineer at Apple | 5.9 yrs | score=1.1360
         2. CAND_0046064 | Senior NLP Engineer at Salesforce | 8.9 yrs | score=1.1310
         3. CAND_0011687 | Senior NLP Engineer at Niramai | 7.8 yrs | score=1.0585
         4. CAND_0046525 | Senior Machine Learning Engineer at Genpact AI | 6.1 yrs | score=1.0161
         5. CAND_0071974 | Senior AI Engineer at Netflix | 7.8 yrs | score=0.9982
```

### Validate

```powershell
python ".\[PUB] India_runs_data_and_ai_challenge\[PUB] India_runs_data_and_ai_challenge\India_runs_data_and_ai_challenge\validate_submission.py" .\submission.csv
```

**Expected output:**

```
Submission is valid.
```

## Performance

- **Runtime**: ~60 seconds on CPU (well within 5-minute budget)
- **Memory**: <4 GB peak
- **No GPU, no network calls, no external APIs**

## Results Summary

- **0 non-tech titles** in top 100 (keyword trap fully defeated)
- **100% ML/AI/Data Science titles** — ML Engineers, NLP Engineers, AI Engineers, Recommendation Systems Engineers, Applied Scientists
- **92% India-based** candidates (matches JD's strong India preference)
- **42 honeypots** detected and excluded

## File Structure

```
├── rank.py                 # Main entry point
├── config.py               # All tunable constants and weights
├── candidate_scorer.py     # Core fit scoring (title, skills, career, experience, location, education)
├── text_scorer.py          # TF-IDF text relevance scoring
├── behavioral_scorer.py    # Behavioral signal modifier
├── honeypot_detector.py    # Honeypot detection
├── utils.py                 # Data loading, reasoning generation, CSV output
├── requirements.txt         # Dependencies
└── output/
    ├── submission.csv       # Final ranked output (CSV format)
    └── submission.xlsx      # Final ranked output (Excel format)
```

## Dependencies

- `scikit-learn` — TF-IDF vectorization + cosine similarity
- `numpy` — numerical operations
- Standard library only beyond these two
