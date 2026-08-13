"""
Core fit scoring: title relevance, skills match, experience, career quality,
location, and education.
"""

import config


def score_title_relevance(candidate):
    """
    Score based on how relevant the current (and past) titles are to the JD.
    Returns 0.0–1.0.
    """
    profile = candidate["profile"]
    current_title = profile.get("current_title", "")
    
    # Get base score from title map
    base = config.TITLE_SCORES.get(current_title, config.DEFAULT_TITLE_SCORE)
    
    # Check career history for AI/ML progression
    career = candidate.get("career_history", [])
    best_historical = 0.0
    for role in career:
        role_title = role.get("title", "")
        role_score = config.TITLE_SCORES.get(role_title, 0.0)
        if role_score > best_historical:
            best_historical = role_score
    
    # If historical titles are much better than current, give a boost
    # (e.g., someone who was ML Engineer but is now Backend Engineer)
    if best_historical > base + 0.2:
        base = min(base + config.CAREER_TITLE_BONUS, best_historical * 0.9)
    
    # Penalty: if title is AI-related but ALL career descriptions are non-tech
    # (catches "AI Specialist" with only marketing career history)
    if base >= 0.80 and _career_is_purely_nontechnical(career):
        base *= 0.5
    
    return min(max(base, 0.0), 1.0)


def _career_is_purely_nontechnical(career):
    """Check if all career descriptions lack any technical substance."""
    if not career:
        return True
    
    tech_keywords = {
        "code", "software", "engineer", "develop", "deploy", "model",
        "algorithm", "data", "system", "api", "pipeline", "ml",
        "machine learning", "ai", "neural", "training",
    }
    
    for role in career:
        desc = role.get("description", "").lower()
        if any(kw in desc for kw in tech_keywords):
            return False
    return True


def score_skills_match(candidate):
    """
    Score based on how many must-have and nice-to-have skills the candidate has,
    weighted by trust (proficiency + endorsements + duration).
    Returns 0.0–1.0.
    """
    skills = candidate.get("skills", [])
    signals = candidate.get("redrob_signals", {})
    assessment_scores = signals.get("skill_assessment_scores", {})
    
    must_have_score = 0.0
    nice_to_have_score = 0.0
    
    for s in skills:
        name_lower = s["name"].lower()
        trust = _skill_trust(s, assessment_scores)
        
        if name_lower in config.MUST_HAVE_SKILLS:
            must_have_score += trust
        elif name_lower in config.NICE_TO_HAVE_SKILLS:
            nice_to_have_score += trust
    
    # Normalize
    must_norm = min(must_have_score / max(len(config.MUST_HAVE_SKILLS) * 0.15, 1), 1.0)
    nice_norm = min(nice_to_have_score / max(len(config.NICE_TO_HAVE_SKILLS) * 0.10, 1), 1.0)
    
    raw = must_norm * 0.7 + nice_norm * 0.3
    
    # Trap detection: non-tech title with high AI skills = keyword stuffer
    current_title = candidate["profile"].get("current_title", "")
    if current_title in config.NON_TECH_TITLES:
        ai_skill_count = sum(
            1 for s in skills if s["name"].lower() in config.AI_SKILL_KEYWORDS
        )
        if ai_skill_count >= 6:
            # This looks like a keyword stuffer — discount heavily
            raw *= 0.15
        elif ai_skill_count >= 3:
            raw *= 0.4
    
    return min(max(raw, 0.0), 1.0)


def _skill_trust(skill, assessment_scores):
    """
    Compute a trust weight for a single skill based on proficiency,
    endorsements, duration, and platform assessment scores.
    Returns 0.0–1.0.
    """
    prof = skill.get("proficiency", "beginner")
    endorsements = skill.get("endorsements", 0)
    duration = skill.get("duration_months", 0)
    name = skill["name"]
    
    # Platform assessment override
    if name in assessment_scores:
        score = assessment_scores[name]
        if score >= 70:
            return 1.0
        elif score >= 50:
            return 0.7
        elif score < 40:
            return 0.3
    
    # Proficiency-based trust
    if prof == "expert":
        if endorsements >= 10 and duration >= 24:
            return 1.0
        elif endorsements < 3 or duration < 6:
            return 0.3  # suspicious
        else:
            return 0.7
    elif prof == "advanced":
        if endorsements >= 5 and duration >= 12:
            return 0.9
        else:
            return 0.6
    elif prof == "intermediate":
        return 0.5
    else:  # beginner
        return 0.3


def score_experience_fit(candidate):
    """
    Score based on years of experience vs the JD's 5-9 year ideal.
    Returns 0.0–1.0.
    """
    yrs = candidate["profile"].get("years_of_experience", 0)
    
    for min_yrs, max_yrs, score in config.EXPERIENCE_BANDS:
        if min_yrs <= yrs < max_yrs:
            return score
    
    # Exact boundary: 9.0 should still be 1.0
    if yrs == 9.0:
        return 1.0
    
    return 0.15


def score_career_quality(candidate):
    """
    Score based on product vs services experience, tenure stability,
    and production deployment signals in descriptions.
    Returns 0.0–1.0.
    """
    career = candidate.get("career_history", [])
    if not career:
        return 0.1
    
    # 6a: Product vs services company mix (40%)
    company_score = _score_company_mix(career)
    
    # 6b: Tenure stability (20%)
    tenure_score = _score_tenure(career)
    
    # 6c: Production signals in descriptions (40%)
    production_score = _score_production_signals(career)
    
    return company_score * 0.4 + tenure_score * 0.2 + production_score * 0.4


def _score_company_mix(career):
    """Score based on product company vs consulting firm experience."""
    total_months = 0
    product_months = 0
    consulting_months = 0
    ai_industry_months = 0
    
    for role in career:
        months = role.get("duration_months", 0)
        company = role.get("company", "").lower()
        industry = role.get("industry", "")
        
        total_months += months
        
        if company in config.CONSULTING_COMPANIES:
            consulting_months += months
        
        if industry in config.PRODUCT_INDUSTRIES:
            product_months += months
        
        if industry in ("AI/ML", "SaaS"):
            ai_industry_months += months
    
    if total_months == 0:
        return 0.3
    
    consulting_ratio = consulting_months / total_months
    product_ratio = product_months / total_months
    
    if consulting_ratio > 0.9:
        score = 0.2  # All consulting — JD explicitly flags this
    elif consulting_ratio > 0.5:
        score = 0.4
    elif product_ratio > 0.5:
        score = 0.85
    else:
        score = 0.6
    
    # AI/ML industry bonus
    if ai_industry_months > 12:
        score = min(score + 0.15, 1.0)
    
    return score


def _score_tenure(career):
    """Score based on average tenure and job-hopping patterns."""
    if not career or len(career) == 0:
        return 0.5
    
    durations = [r.get("duration_months", 0) for r in career]
    avg_tenure = sum(durations) / len(durations)
    
    short_stints = sum(1 for d in durations if d < 12)
    
    if len(career) >= 3 and short_stints >= len(career) * 0.6:
        return 0.3  # title-chaser pattern
    elif avg_tenure < 12:
        return 0.4
    elif avg_tenure < 18:
        return 0.6
    elif avg_tenure < 24:
        return 0.8
    else:
        return 1.0


def _score_production_signals(career):
    """Score based on production-related keywords in career descriptions."""
    all_text = " ".join(
        role.get("description", "").lower() for role in career
    )
    
    signal_count = sum(1 for sig in config.PRODUCTION_SIGNALS if sig in all_text)
    
    # Normalize with diminishing returns
    return min(signal_count / 8.0, 1.0)


def score_location(candidate):
    """
    Score based on location match with JD preferences.
    Returns 0.0–1.0.
    """
    profile = candidate["profile"]
    country = profile.get("country", "").strip()
    location = profile.get("location", "").lower().strip()
    signals = candidate.get("redrob_signals", {})
    willing = signals.get("willing_to_relocate", False)
    
    if country == "India":
        # Check for preferred cities
        if any(city in location for city in config.PREFERRED_CITIES):
            return 1.0
        elif any(city in location for city in config.TIER1_INDIAN_CITIES):
            return 0.9
        elif willing:
            return 0.8
        else:
            return 0.55
    else:
        if willing:
            return 0.3
        else:
            return 0.15


def score_education(candidate):
    """
    Score based on education field relevance and institution tier.
    Returns 0.0–1.0.
    """
    education = candidate.get("education", [])
    if not education:
        return 0.3
    
    best_score = 0.0
    
    for edu in education:
        field = edu.get("field_of_study", "").lower()
        degree = edu.get("degree", "").lower()
        tier = edu.get("tier", "unknown")
        
        # Field relevance
        if any(f in field for f in config.RELEVANT_FIELDS):
            field_score = 1.0
        elif any(f in field for f in config.ADJACENT_FIELDS):
            field_score = 0.7
        else:
            field_score = 0.3
        
        # Degree bonus
        if "ph.d" in degree or "phd" in degree:
            field_score = min(field_score + 0.10, 1.0)
        elif "m." in degree or "master" in degree or "msc" in degree:
            field_score = min(field_score + 0.05, 1.0)
        
        # Tier bonus
        if tier == "tier_1":
            field_score = min(field_score + 0.10, 1.0)
        elif tier == "tier_2":
            field_score = min(field_score + 0.05, 1.0)
        elif tier == "tier_4":
            field_score = max(field_score - 0.05, 0.0)
        
        best_score = max(best_score, field_score)
    
    return best_score


def compute_core_fit(candidate):
    """
    Compute the weighted core fit score from all sub-dimensions.
    Returns a dict with individual scores and the combined core_fit.
    """
    scores = {
        "title": score_title_relevance(candidate),
        "skills": score_skills_match(candidate),
        "experience": score_experience_fit(candidate),
        "career": score_career_quality(candidate),
        "location": score_location(candidate),
        "education": score_education(candidate),
    }
    
    scores["core_fit"] = (
        config.TITLE_WEIGHT * scores["title"]
        + config.SKILLS_WEIGHT * scores["skills"]
        + config.CAREER_WEIGHT * scores["career"]
        + config.EXPERIENCE_WEIGHT * scores["experience"]
        + config.LOCATION_WEIGHT * scores["location"]
        + config.EDUCATION_WEIGHT * scores["education"]
    )
    
    return scores
