"""
Text relevance scoring using TF-IDF cosine similarity.
Captures free-text nuance from summaries and career descriptions
that structured field matching alone would miss.
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

import config


def build_candidate_text(candidate):
    """
    Concatenate all textual content from a candidate into a single document.
    """
    parts = []
    
    profile = candidate.get("profile", {})
    parts.append(profile.get("headline", ""))
    parts.append(profile.get("summary", ""))
    
    for role in candidate.get("career_history", []):
        parts.append(role.get("title", ""))
        parts.append(role.get("description", ""))
    
    for skill in candidate.get("skills", []):
        parts.append(skill.get("name", ""))
    
    for cert in candidate.get("certifications", []):
        parts.append(cert.get("name", ""))
    
    return " ".join(parts)


def compute_text_scores(candidates):
    """
    Compute TF-IDF cosine similarity scores for all candidates against the JD query.
    
    Args:
        candidates: list of candidate dicts
    
    Returns:
        numpy array of scores (0.0–1.0), one per candidate, same order as input.
    """
    # Build corpus: JD query is document 0, candidates are 1..N
    corpus = [config.JD_QUERY]
    for c in candidates:
        corpus.append(build_candidate_text(c))
    
    # Fit TF-IDF
    vectorizer = TfidfVectorizer(
        max_features=config.TFIDF_MAX_FEATURES,
        ngram_range=config.TFIDF_NGRAM_RANGE,
        stop_words="english",
        sublinear_tf=True,  # apply log normalization
    )
    tfidf_matrix = vectorizer.fit_transform(corpus)
    
    # Cosine similarity of each candidate (rows 1..N) against JD (row 0)
    jd_vector = tfidf_matrix[0:1]
    candidate_vectors = tfidf_matrix[1:]
    
    similarities = cosine_similarity(candidate_vectors, jd_vector).flatten()
    
    # Normalize to 0–1 range
    min_sim = similarities.min()
    max_sim = similarities.max()
    if max_sim > min_sim:
        scores = (similarities - min_sim) / (max_sim - min_sim)
    else:
        scores = np.zeros_like(similarities)
    
    return scores
