# Intelligent Candidate Ranking System — Strategy & Execution Plan

## 1. Problem Framing

**Goal**: Given a job description for "Senior AI Engineer" at Redrob AI, rank 100,000 candidates and output the top 100, best-fit first, with per-candidate reasoning.

**Output format**: CSV with columns `candidate_id, rank, score, reasoning` — exactly 100 rows, scores non-increasing, ranks 1–100, no duplicates.

**Constraints** (from submission_spec):
- 5-minute runtime on CPU-only, 16 GB RAM, no network during ranking
- Pre-computation (embeddings, indexes) is allowed to exceed 5 min
- No GPU, no hosted LLM API calls during ranking
- Max 3 submissions total

---

## 2. What the JD Actually Wants (Critical Reading)

Before writing any code, I dissected the JD to extract what a great recruiter would prioritize. The JD is unusually explicit — it tells you exactly what traps exist and what signals matter.

### 2.1 The Ideal Candidate Profile

| Dimension | What the JD Says | What It Means for Scoring |
|---|---|---|
| **Experience** | "5–9 years, not a hard cutoff" | Sweet spot = 5–9 yrs, but 4 or 12 yrs with strong signals shouldn't be killed |
| **Role type** | "AI Engineering, not research, not architecture" | Must have SHIPPED production ML systems. Pure researchers = reject. Pure managers = reject. |
| **Technical depth** | "Embeddings, retrieval, ranking, LLMs, fine-tuning" | Skills in IR/NLP/embeddings/vector-DBs are core. Generic SWE skills are supportive, not core. |
| **Attitude** | "Shipper > Researcher" | Product company experience >> research lab. Startup experience is a positive signal. |
| **Career pattern** | "No title-chasers, no consulting-only" | Penalize frequent short stints. Penalize entire-career-at-TCS/Wipro/Infosys. |
| **Location** | "Pune/Noida preferred, Tier-1 Indian cities OK, outside India case-by-case, no visa sponsorship" | India candidates score higher. Pune/Noida/Delhi NCR = top. |
| **Availability** | "Sub-30-day notice preferred, will buy out up to 30 days" | Notice period is a real factor. >90 days = friction. |
| **Behavioral** | "A perfect-on-paper candidate who hasn't logged in for 6 months and has 5% response rate is NOT available" | Behavioral signals are a multiplier, not an additive factor. |

### 2.2 Explicit Disqualifiers from the JD

These are directly stated in the JD — not inferences:

1. **Pure research career, zero production deployments** → "We will not move forward"
2. **Only recent LangChain/OpenAI wrapper experience** → "We will probably not move forward"
3. **Senior engineer who stopped writing code (moved to architecture/tech lead)** → "We will probably not move forward"
4. **Entire career at consulting firms (TCS, Infosys, Wipro, Accenture, Cognizant, Capgemini)** → "We've had bad fit experiences"
5. **Primary expertise in CV/speech/robotics without NLP/IR** → "You'd be re-learning fundamentals"
6. **Title-chasers** (switching companies every 1.5 yrs for title bumps) → "We need 3+ year commitment"
7. **Framework enthusiasts** (LangChain tutorials, demo projects) → Not what they need

### 2.3 The Trap They Built Into the Dataset

The JD explicitly warns:
> "The right answer is NOT find candidates whose skills section contains the most AI keywords. That's a trap we've explicitly built into the dataset."

Looking at the sample submission, candidates like "HR Manager with 9 AI core skills" are ranked high — that's the SAMPLE (format reference), not a quality reference. The actual dataset has:
- ~68,000 candidates with non-technical titles (HR, Marketing, Accountant, Sales, etc.) who have AI skills listed — these are keyword-stuffer traps
- ~994 candidates with genuinely AI-related titles
- ~80 honeypot candidates with impossible profiles

**A naive embedding/keyword system will rank the 68K traps above the 994 real candidates.** This is the central design challenge.

---

## 3. Architecture Decision: Why Rule-Based + TF-IDF

### 3.1 Options Considered

| Approach | Pros | Cons | Verdict |
|---|---|---|---|
| **Full sentence-transformer embeddings** | Best semantic matching | ~15 min to embed 100K candidates on CPU; marginal within budget | Could work as pre-computation, but adds complexity for marginal gain |
| **LLM-based re-ranking** | Deepest understanding | Cannot call APIs during ranking; local LLMs too slow for 100K on CPU | Infeasible within constraints |
| **Pure TF-IDF similarity** | Fast, simple | Doesn't understand structured signals (title, experience years, location) | Insufficient alone |
| **Rule-based structured scoring** | Directly encodes JD's explicit preferences; fast; transparent | Misses free-text nuance in career descriptions | Insufficient alone |
| **Rule-based + TF-IDF hybrid** | Encodes JD logic + captures free-text signals; fast; fully within budget | Requires careful weight tuning | **Selected** |

### 3.2 Why This Beats Embeddings for THIS Problem

1. **The discrimination is in structured fields.** When the JD says "no consulting-only careers," that's a lookup against company names, not a semantic similarity computation. When it says "5–9 years experience," that's a numeric range check.

2. **The traps are designed to fool embedding systems.** A Marketing Manager with skills ["NLP", "FAISS", "PyTorch", "embeddings"] will embed VERY close to the JD. A rule-based system that says "title = Marketing Manager → penalty" catches this trivially.

3. **TF-IDF on career descriptions catches the edge cases.** A Backend Engineer whose description says "built recommendation system, deployed to 10K users, evaluated with NDCG" will score high on text relevance even though their title doesn't scream "AI Engineer."

4. **Explainability.** The reasoning column needs to be specific and honest. A rule-based system naturally produces explanations ("ML Engineer at product company, 6.2 yrs, strong embeddings skills, Pune-based, 30-day notice"). An embedding system produces a cosine similarity number.

---

## 4. Scoring Pipeline — Step-by-Step Breakdown

### Step 1: Data Loading & Preprocessing
**File**: `utils.py`

- Stream-read `candidates.jsonl` (487 MB) line by line — don't load all into memory at once
- Parse each JSON line into a dict
- Store in a list of lightweight candidate objects (only fields we need for scoring)
- **Runtime**: ~30 seconds

### Step 2: Honeypot Detection
**File**: `honeypot_detector.py`

Honeypots have "subtly impossible" profiles. Detection rules:

| Check | Logic | Rationale |
|---|---|---|
| Expert skills with zero usage | Any skill with `proficiency == "expert"` AND `duration_months == 0` | Impossible to be expert with 0 months of use |
| Too many expert skills | Count of `proficiency == "expert"` skills ≥ 8 AND most have `duration_months < 6` | Statistically implausible |
| Experience vs career math | `years_of_experience` vs sum of `career_history[].duration_months / 12` — if difference > 3 years | Career doesn't add up |
| Impossible tenure | Any single role `duration_months` > total `years_of_experience * 12` | Can't work somewhere longer than your total career |
| Start date after end date | Any career entry where `start_date > end_date` | Impossible |
| Graduation after career start | `education.end_year` > first `career_history.start_date.year + 2` while claiming full-time | Timeline doesn't work |

Flagged candidates get `score = 0` and are excluded from the top 100.

**Runtime**: ~10 seconds (simple arithmetic per candidate)

### Step 3: Title & Role Relevance Scoring
**File**: `candidate_scorer.py` → `score_title_relevance()`

This is the single most important signal for defeating the keyword trap.

**Approach**: Map every observed title to a relevance score:

```
TIER 1 (score 1.0): Direct AI/ML engineering roles
  → ML Engineer, AI Engineer, Machine Learning Engineer, NLP Engineer,
    Senior AI Engineer, Lead AI Engineer, Applied ML Engineer,
    Staff Machine Learning Engineer, Senior Machine Learning Engineer,
    AI Research Engineer, Senior Software Engineer (ML)

TIER 2 (score 0.80): Adjacent data/ML roles
  → Data Scientist, Senior Data Scientist, Senior NLP Engineer

TIER 3 (score 0.55): Data infrastructure (could have ML exposure)
  → Data Engineer, Senior Data Engineer, Analytics Engineer, Backend Engineer

TIER 4 (score 0.40): General engineering (transferable skills)
  → Software Engineer, Senior Software Engineer, Full Stack Developer

TIER 5 (score 0.25): Tech-adjacent
  → DevOps Engineer, Cloud Engineer, QA Engineer, Frontend Engineer,
    Mobile Developer, Java Developer, .NET Developer

TIER 6 (score 0.05): Non-technical (the trap tier)
  → HR Manager, Marketing Manager, Accountant, Sales Executive,
    Operations Manager, Customer Support, Content Writer,
    Graphic Designer, Mechanical Engineer, Civil Engineer,
    Business Analyst, Project Manager
```

**Career history bonus**: Don't just look at `current_title`. Scan ALL titles in `career_history[]`. If a current "Backend Engineer" was previously an "ML Engineer," they get a boost. Conversely, if an "AI Specialist" has only non-tech career history, they get penalized.

**Weight in final score**: 0.25

### Step 4: Skills Match Scoring
**File**: `candidate_scorer.py` → `score_skills_match()`

**Must-have skill categories** (from the JD's "things you absolutely need"):

```python
MUST_HAVE_SKILLS = {
    # Embeddings & retrieval
    "embeddings", "sentence-transformers", "FAISS", "Milvus", "Pinecone",
    "Weaviate", "Qdrant", "OpenSearch", "Elasticsearch", "vector database",
    "information retrieval", "search", "retrieval",
    
    # Core ML/NLP
    "NLP", "natural language processing", "transformers", "BERT",
    "PyTorch", "TensorFlow", "Hugging Face",
    
    # Python
    "Python",
    
    # Ranking & evaluation
    "ranking", "recommendation", "learning to rank",
    "A/B testing", "evaluation",
}
```

**Nice-to-have skills**:
```python
NICE_TO_HAVE_SKILLS = {
    "LoRA", "QLoRA", "PEFT", "fine-tuning", "Fine-tuning LLMs",
    "LLM", "GPT", "RAG", "prompt engineering",
    "XGBoost", "LightGBM", "gradient boosting",
    "Docker", "Kubernetes", "MLflow", "Weights & Biases",
    "distributed systems", "Spark", "Airflow",
    "deep learning", "neural networks",
    "scikit-learn", "pandas", "NumPy",
}
```

**Scoring formula**:
```
raw_skill_score = (must_have_matched / len(MUST_HAVE_SKILLS)) * 0.7
                + (nice_to_have_matched / len(NICE_TO_HAVE_SKILLS)) * 0.3
```

**Skill trust multiplier** (catches keyword stuffing at skill level):
- For each matched skill, compute a trust weight:
  - `proficiency == "expert"` AND `endorsements >= 10` AND `duration_months >= 24` → trust = 1.0
  - `proficiency == "advanced"` AND `endorsements >= 5` AND `duration_months >= 12` → trust = 0.9
  - `proficiency == "expert"` AND (`endorsements < 3` OR `duration_months < 6`) → trust = 0.3 (suspicious)
  - `proficiency == "beginner"` → trust = 0.5
- The skill only counts as `trust_weight` of a full match, not a binary 1/0.

**Platform assessment override**: If `redrob_signals.skill_assessment_scores` has a score for a skill:
  - Score ≥ 70 → trust = 1.0 regardless of other signals (platform-verified)
  - Score < 40 → trust = 0.3 (failed assessment)

**Weight in final score**: 0.25

### Step 5: Experience Fit Scoring
**File**: `candidate_scorer.py` → `score_experience_fit()`

Simple piecewise function based on `years_of_experience`:

```
[5, 9]   → 1.0  (ideal range)
[4, 5)   → 0.85
(9, 12]  → 0.80
[3, 4)   → 0.50
(12, 15] → 0.45
< 3      → 0.15
> 15     → 0.25
```

**Weight in final score**: 0.15

### Step 6: Career Quality Scoring
**File**: `candidate_scorer.py` → `score_career_quality()`

This is the most nuanced component. Sub-signals:

**6a. Product vs Services company mix (40% of career score)**

```python
CONSULTING_COMPANIES = {
    "TCS", "Infosys", "Wipro", "Accenture", "Cognizant", "Capgemini",
    "HCL", "Tech Mahindra", "Mindtree", "Mphasis", "LTIMindtree",
    "Hexaware", "Persistent", "Cyient", "NIIT", "L&T Infotech",
}

PRODUCT_INDUSTRIES = {
    "Fintech", "E-commerce", "SaaS", "AI/ML", "EdTech", "AdTech",
    "Food Delivery", "Transportation", "Insurance Tech",
}
```

- All career at consulting companies → 0.2
- Mix of consulting + product → 0.6
- All career at product companies → 1.0
- Career at AI/ML industry company → bonus +0.15

**6b. Tenure stability (20% of career score)**
- Average tenure per role < 12 months AND 3+ roles → 0.3 (title-chaser)
- Average tenure 12–24 months → 0.7
- Average tenure > 24 months → 1.0
- Single long tenure > 48 months at one company → 0.9 (stable but maybe stagnant)

**6c. Production deployment signals in descriptions (40% of career score)**

Scan `career_history[].description` for evidence of production work. Look for these patterns:
```python
PRODUCTION_SIGNALS = [
    "production", "deployed", "shipped", "users", "scale",
    "A/B test", "real-time", "pipeline", "infrastructure",
    "system design", "million", "latency", "throughput",
    "recommendation", "ranking", "search", "retrieval",
    "embeddings", "vector", "NLP", "machine learning",
    "model serving", "inference", "monitoring",
]
```

Count the number of distinct production signals found across all career descriptions. Normalize to 0–1 with diminishing returns (e.g., `min(signal_count / 8, 1.0)`).

**Weight in final score**: 0.20

### Step 7: Location Scoring
**File**: `candidate_scorer.py` → `score_location()`

```
India + Pune/Noida/Delhi NCR/Gurgaon/Greater Noida      → 1.0
India + Mumbai/Hyderabad/Bangalore                        → 0.9
India + other + willing_to_relocate                       → 0.8
India + other + NOT willing_to_relocate                   → 0.55
Outside India + willing_to_relocate                       → 0.3
Outside India + NOT willing_to_relocate                   → 0.15
```

**Weight in final score**: 0.10

### Step 8: Education Scoring
**File**: `candidate_scorer.py` → `score_education()`

```
Relevant field (CS, ML, AI, Data Science, Statistics, Math, ECE)  → 1.0
Adjacent field (IT, Electronics, Physics, Informatics)            → 0.7
Unrelated field (Chemical, Mechanical, Civil, Arts, Commerce)     → 0.3

Degree bonus: PhD in relevant field → +0.1
             Masters in relevant field → +0.05

Tier bonus: tier_1 (IIT/IISc/BITS/NIT top) → +0.10
            tier_2                          → +0.05
            tier_3                          → +0.00
            tier_4                          → -0.05
```

Cap at 1.0. **Weight in final score**: 0.05

### Step 9: TF-IDF Text Relevance
**File**: `text_scorer.py`

**Why TF-IDF and not just keyword counts?**
- TF-IDF down-weights common terms (every candidate mentions "Python") and up-weights distinctive terms ("embedding drift," "NDCG," "retrieval regression")
- Cosine similarity is robust to document length differences
- scikit-learn's TfidfVectorizer processes 100K documents in <30 seconds

**Process**:

1. **Build the JD query document** — extract the most distinctive phrases from the JD:
   ```
   "ranking system retrieval embeddings hybrid search vector database
    production deployment evaluation NDCG MRR MAP A/B testing
    recruiter matching NLP information retrieval fine-tuning LLM
    startup product company scale real users candidate discovery
    semantic search re-ranking recommendation system
    embedding drift index refresh retrieval quality
    learning to rank evaluation framework"
   ```

2. **Build candidate documents** — for each candidate, concatenate:
   - `profile.summary`
   - All `career_history[].description` texts
   - All skill names (joined by space)
   - `profile.headline`

3. **Fit TfidfVectorizer** on the full corpus (100K candidate docs + 1 JD query doc)
   - `max_features=10000`, `ngram_range=(1,2)`, `stop_words='english'`

4. **Compute cosine similarity** of each candidate vector against the JD query vector

5. **Normalize** scores to [0, 1] range (min-max across all candidates)

**Weight in final score**: 0.40 of total (text relevance is blended with core fit)

### Step 10: Behavioral Modifier
**File**: `behavioral_scorer.py`

This is a **multiplier**, not an additive score. A candidate can be perfect on paper but unhireable if they're not responsive/available.

**Individual modifiers** (each is a multiplier around 1.0):

| Signal | Computation | Range |
|---|---|---|
| Recency | days since `last_active_date`: <30d → 1.05, 30-90d → 1.0, 90-180d → 0.8, >180d → 0.5 | 0.5–1.05 |
| Open to work | `true` → 1.08, `false` → 0.85 | 0.85–1.08 |
| Response rate | `0.6 + (rate * 0.4)` | 0.6–1.0 |
| Response time | <24h → 1.05, 24-72h → 1.0, 72-168h → 0.9, >168h → 0.75 | 0.75–1.05 |
| Notice period | ≤30d → 1.08, 31-60d → 1.0, 61-90d → 0.9, >90d → 0.75 | 0.75–1.08 |
| Interview completion | `0.75 + (rate * 0.25)` | 0.75–1.0 |
| Profile completeness | <40 → 0.85, 40-70 → 0.95, >70 → 1.03 | 0.85–1.03 |
| Verification | both email+phone → 1.03, one → 1.0, neither → 0.9 | 0.9–1.03 |
| GitHub activity | >50 → 1.08, 20-50 → 1.03, 0-20 → 1.0, -1 → 0.97 | 0.97–1.08 |
| LinkedIn connected | `true` → 1.02, `false` → 0.98 | 0.98–1.02 |
| Work mode match | onsite/hybrid → 1.0, remote + willing relocate → 0.95, remote + won't relocate → 0.85 | 0.85–1.0 |

**Combined modifier** = product of all individual modifiers, clamped to [0.3, 1.25]

### Step 11: Final Score Assembly
**File**: `rank.py`

```python
core_fit = (0.25 * title_score
          + 0.25 * skills_score
          + 0.20 * career_score
          + 0.15 * experience_score
          + 0.10 * location_score
          + 0.05 * education_score)

final_score = (0.55 * core_fit + 0.45 * text_relevance) * behavioral_modifier
```

For honeypots: `final_score = 0.0`

Sort all 100K candidates by `final_score` descending. Take top 100.

### Step 12: Reasoning Generation
**File**: `utils.py` → `generate_reasoning()`

For each top-100 candidate, generate a 1–2 sentence reasoning that is:
- **Specific** — references actual values from their profile
- **Honest** — doesn't claim skills they don't have
- **Non-templated** — varies based on which dimensions drove the score

**Template structure** (dynamically assembled):
```
"{current_title} at {current_company} ({current_industry}) with {years_of_experience} yrs;
 {top_skill_match_detail}; {career_quality_note}; {behavioral_note}.
 {location_note}."
```

**Examples of what good reasoning looks like**:
- "ML Engineer at a SaaS company with 6.2 yrs; production experience with embeddings and FAISS in career history; strong recruiter response rate (0.72). Based in Pune, hybrid, 30-day notice."
- "Senior Data Engineer transitioning to ML; 7 yrs experience with 3 at a product company; NLP and PyTorch skills with assessment scores >70. Located in Noida, open to work."

### Step 13: CSV Output & Validation
**File**: `rank.py`

1. Write CSV with header: `candidate_id,rank,score,reasoning`
2. Ensure exactly 100 data rows
3. Ranks 1–100, no duplicates
4. Scores are non-increasing (rank 1 has highest score)
5. Equal scores → tie-break by candidate_id ascending
6. Run `validate_submission.py` on the output to confirm

---

## 5. File Structure

```
AssignmentHR/
├── plan.md                      ← This file (strategy document)
├── rank.py                      ← Main entry point CLI
├── config.py                    ← All constants, weights, skill lists, thresholds
├── honeypot_detector.py         ← Honeypot detection logic
├── candidate_scorer.py          ← Core fit scoring (title, skills, experience, career, location, education)
├── text_scorer.py               ← TF-IDF text relevance scoring
├── behavioral_scorer.py         ← Behavioral signal modifier computation
├── utils.py                     ← Data loading, reasoning generation, helpers
├── requirements.txt             ← Dependencies (scikit-learn, python-docx)
├── README.md                    ← Setup & reproduction instructions
└── output/
    └── submission.csv           ← Final ranked output
```

---

## 6. Execution Order

| Step | Action | Depends On |
|------|--------|------------|
| 1 | Create `config.py` with all constants | Nothing |
| 2 | Create `utils.py` with data loading | Nothing |
| 3 | Create `honeypot_detector.py` | `config.py` |
| 4 | Create `candidate_scorer.py` | `config.py` |
| 5 | Create `text_scorer.py` | `config.py` |
| 6 | Create `behavioral_scorer.py` | `config.py` |
| 7 | Create `rank.py` orchestrator | Steps 2–6 |
| 8 | Create `requirements.txt` | Nothing |
| 9 | Run full pipeline on candidates.jsonl | Steps 1–8 |
| 10 | Validate output with `validate_submission.py` | Step 9 |
| 11 | Manual inspection of top-10 and bottom-10 | Step 9 |
| 12 | Tune weights if needed based on inspection | Step 11 |
| 13 | Re-run and finalize | Step 12 |
| 14 | Create `README.md` | Step 13 |

---

## 7. Risk Analysis & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Honeypot detection misses some honeypots | >10% honeypot rate → disqualification | Multiple detection heuristics; manual review of flagged candidates |
| Keyword-trap candidates leak into top 100 | Low quality ranking | Title relevance is 25% of score; non-tech titles get 0.05 which makes it nearly impossible to reach top 100 regardless of skills |
| TF-IDF misses semantic similarity | Good candidates with different vocabulary get under-ranked | TF-IDF with bigrams catches multi-word phrases; combined with structured scoring which is the primary signal |
| Weight tuning is wrong | Top-100 doesn't match JD intent | Manual inspection loop after first run; adjustable weights in config.py |
| Memory issues with 100K candidates | OOM on 16GB machine | Stream-read JSONL; TF-IDF with max_features=10000; no full candidate objects in memory during TF-IDF |
| Runtime exceeds 5 minutes | Submission disqualified | Estimated ~2 min; all operations are O(n) or O(n·d) where d is small |

---

## 8. Dependencies

```
scikit-learn>=1.3    # TF-IDF vectorization + cosine similarity
python-docx>=1.0     # Only needed if parsing JD from .docx at runtime (optional)
pyyaml>=6.0          # For submission_metadata.yaml handling (optional)
```

No PyTorch, no TensorFlow, no transformers, no FAISS. Deliberately minimal.

---

## 9. What Makes This Approach Win

1. **It reads the JD like a recruiter, not like an embedding model.** The JD says "no consulting-only careers" — we check for that. The JD says "5–9 years" — we score for that. No embedding model encodes these preferences.

2. **It defeats the keyword trap by design.** Title relevance is a primary signal, and a Marketing Manager can never outscore an ML Engineer no matter how many AI skills they list.

3. **It uses behavioral signals as the JD instructs.** A 0.5x multiplier for a candidate who hasn't been active in 6 months ensures they don't pollute the top 100.

4. **It still captures free-text nuance via TF-IDF.** The Backend Engineer who built a ranking system will surface through text relevance even if their title scores low.

5. **It produces specific, honest reasoning.** Not templates, not hallucinations, but actual data points from each candidate's profile.

6. **It runs in ~2 minutes with zero external dependencies.** Well within all constraints.
