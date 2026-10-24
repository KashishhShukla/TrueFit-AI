import os

# =============================================================================
# Database Configuration (PostgreSQL / SQLite)
# =============================================================================
DATABASE_URL = os.environ.get("DATABASE_URL", "")
DB_AUTO_SEED = os.environ.get("DB_AUTO_SEED", "true").lower() == "true"

# =============================================================================
# Final score weights
# =============================================================================
CORE_FIT_WEIGHT = 0.55
TEXT_RELEVANCE_WEIGHT = 0.45

# =============================================================================
# Core fit sub-weights (must sum to 1.0)
# =============================================================================
TITLE_WEIGHT = 0.25
SKILLS_WEIGHT = 0.25
CAREER_WEIGHT = 0.20
EXPERIENCE_WEIGHT = 0.15
LOCATION_WEIGHT = 0.10
EDUCATION_WEIGHT = 0.05

# =============================================================================
# Title relevance tiers
# =============================================================================
TITLE_SCORES = {
    # Tier 1: Direct AI/ML engineering (1.0)
    "ML Engineer": 1.0,
    "AI Engineer": 1.0,
    "Machine Learning Engineer": 1.0,
    "NLP Engineer": 1.0,
    "Senior AI Engineer": 1.0,
    "Lead AI Engineer": 1.0,
    "Applied ML Engineer": 1.0,
    "Staff Machine Learning Engineer": 1.0,
    "Senior Machine Learning Engineer": 1.0,
    "Senior NLP Engineer": 1.0,
    "Senior Software Engineer (ML)": 0.95,
    "AI Research Engineer": 0.90,
    "AI Specialist": 0.85,
    "Junior ML Engineer": 0.80,

    # Tier 2: Data science (0.75-0.85)
    "Data Scientist": 0.80,
    "Senior Data Scientist": 0.85,

    # Tier 3: Data infra (0.50-0.60)
    "Data Engineer": 0.55,
    "Senior Data Engineer": 0.58,
    "Analytics Engineer": 0.55,
    "Backend Engineer": 0.50,
    "Data Analyst": 0.45,

    # Tier 4: General engineering (0.35-0.45)
    "Software Engineer": 0.40,
    "Senior Software Engineer": 0.45,
    "Full Stack Developer": 0.38,

    # Tier 5: Tech-adjacent (0.20-0.30)
    "DevOps Engineer": 0.22,
    "Cloud Engineer": 0.22,
    "QA Engineer": 0.18,
    "Frontend Engineer": 0.20,
    "Mobile Developer": 0.18,
    "Java Developer": 0.22,
    ".NET Developer": 0.18,

    # Tier 6: Non-technical / trap tier (0.05)
    "HR Manager": 0.05,
    "Marketing Manager": 0.05,
    "Accountant": 0.05,
    "Sales Executive": 0.05,
    "Operations Manager": 0.05,
    "Customer Support": 0.05,
    "Content Writer": 0.05,
    "Graphic Designer": 0.05,
    "Mechanical Engineer": 0.08,
    "Civil Engineer": 0.08,
    "Business Analyst": 0.15,
    "Project Manager": 0.12,
}

# Default score for titles not in the map
DEFAULT_TITLE_SCORE = 0.15

# Bonus if career history shows ML/AI progression
CAREER_TITLE_BONUS = 0.15

# =============================================================================
# Skills taxonomy
# =============================================================================
MUST_HAVE_SKILLS = {
    # Embeddings & retrieval
    "embeddings", "sentence-transformers", "faiss", "milvus", "pinecone",
    "weaviate", "qdrant", "opensearch", "elasticsearch", "vector database",
    "information retrieval", "search", "retrieval", "semantic search",
    # Core ML/NLP
    "nlp", "natural language processing", "transformers", "bert",
    "pytorch", "tensorflow", "hugging face", "huggingface",
    # Python
    "python",
    # Ranking & evaluation
    "ranking", "recommendation", "learning to rank",
    "a/b testing", "evaluation",
}

NICE_TO_HAVE_SKILLS = {
    "lora", "qlora", "peft", "fine-tuning", "fine-tuning llms",
    "llm", "gpt", "rag", "prompt engineering",
    "xgboost", "lightgbm", "gradient boosting",
    "docker", "kubernetes", "mlflow", "weights & biases",
    "distributed systems", "spark", "airflow",
    "deep learning", "neural networks",
    "scikit-learn", "pandas", "numpy",
    "langchain", "openai", "gans", "reinforcement learning",
    "feature engineering", "statistical modeling",
    "image classification", "object detection", "computer vision",
    "speech recognition", "tts",
    "bentoml", "mlops",
}

# Skills that are AI-related for trap detection
AI_SKILL_KEYWORDS = {
    "nlp", "machine learning", "deep learning", "pytorch", "tensorflow",
    "transformers", "bert", "gpt", "llm", "embeddings", "faiss",
    "neural networks", "computer vision", "image classification",
    "object detection", "speech recognition", "tts", "gans",
    "reinforcement learning", "fine-tuning llms", "lora", "qlora",
    "rag", "prompt engineering", "milvus", "hugging face",
    "recommendation", "ranking", "retrieval", "semantic search",
    "feature engineering", "statistical modeling", "xgboost",
    "scikit-learn", "data science", "a/b testing",
}

# =============================================================================
# Non-technical titles (for trap detection)
# =============================================================================
NON_TECH_TITLES = {
    "HR Manager", "Marketing Manager", "Accountant", "Sales Executive",
    "Operations Manager", "Customer Support", "Content Writer",
    "Graphic Designer", "Mechanical Engineer", "Civil Engineer",
    "Project Manager", "Business Analyst",
}

# =============================================================================
# Consulting / services companies
# =============================================================================
CONSULTING_COMPANIES = {
    "tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini",
    "hcl", "tech mahindra", "mindtree", "mphasis", "ltimindtree",
    "hexaware", "persistent", "cyient", "niit", "l&t infotech",
    "atos", "dxc technology", "unisys", "cgi", "ntt data",
}

# Product-oriented industries
PRODUCT_INDUSTRIES = {
    "Fintech", "E-commerce", "SaaS", "AI/ML", "EdTech", "AdTech",
    "Food Delivery", "Transportation", "Insurance Tech",
}

# =============================================================================
# Location scoring
# =============================================================================
PREFERRED_CITIES = {
    "noida", "pune", "delhi", "new delhi", "gurgaon", "gurugram",
    "greater noida", "delhi ncr", "faridabad", "ghaziabad",
}

TIER1_INDIAN_CITIES = {
    "mumbai", "hyderabad", "bangalore", "bengaluru", "chennai", "kolkata",
}

# =============================================================================
# Experience scoring bands
# =============================================================================
EXPERIENCE_BANDS = [
    # (min_yrs, max_yrs, score)
    (5.0, 9.0, 1.0),
    (4.0, 5.0, 0.85),
    (9.0, 12.0, 0.80),
    (3.0, 4.0, 0.50),
    (12.0, 15.0, 0.45),
    (0.0, 3.0, 0.15),
    (15.0, 99.0, 0.25),
]

# =============================================================================
# Education relevance
# =============================================================================
RELEVANT_FIELDS = {
    "computer science", "machine learning", "artificial intelligence",
    "data science", "statistics", "mathematics", "computer engineering",
    "computational linguistics", "information systems",
}

ADJACENT_FIELDS = {
    "information technology", "electronics", "electrical engineering",
    "ece", "electronics and communication", "physics",
    "applied mathematics", "operations research", "informatics",
}

# =============================================================================
# Behavioral modifier clamps
# =============================================================================
BEHAVIORAL_MIN = 0.3
BEHAVIORAL_MAX = 1.25

# =============================================================================
# TF-IDF settings
# =============================================================================
TFIDF_MAX_FEATURES = 10000
TFIDF_NGRAM_RANGE = (1, 2)

# JD query for TF-IDF matching
JD_QUERY = (
    "ranking system retrieval embeddings hybrid search vector database "
    "production deployment evaluation NDCG MRR MAP A/B testing "
    "recruiter matching NLP information retrieval fine-tuning LLM "
    "startup product company scale real users candidate discovery "
    "semantic search re-ranking recommendation system "
    "embedding drift index refresh retrieval quality regression "
    "learning to rank evaluation framework sentence transformers "
    "Python code quality engineering ML pipeline inference "
    "Pinecone Weaviate Qdrant Milvus OpenSearch Elasticsearch FAISS "
    "LoRA QLoRA PEFT distributed systems large scale "
    "ranking signals candidate matching talent search "
)

# =============================================================================
# Production signals to look for in career descriptions
# =============================================================================
PRODUCTION_SIGNALS = [
    "production", "deployed", "shipped", "users", "scale",
    "a/b test", "real-time", "pipeline", "infrastructure",
    "system design", "million", "latency", "throughput",
    "recommendation", "ranking", "search", "retrieval",
    "embeddings", "vector", "nlp", "machine learning",
    "model serving", "inference", "monitoring",
    "end-to-end", "microservice", "api", "kubernetes",
    "docker", "ci/cd", "data pipeline",
]

# =============================================================================
# Dataset path (default)
# =============================================================================
DATA_DIR = r"[PUB] India_runs_data_and_ai_challenge\[PUB] India_runs_data_and_ai_challenge\India_runs_data_and_ai_challenge"
