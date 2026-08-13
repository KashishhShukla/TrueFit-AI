"""
Utilities: data loading, reasoning generation, helpers.
"""

import json
import csv
from pathlib import Path


def load_candidates(path):
    """Stream-read candidates from a JSON, JSONL, or GZ file. Yields one dict per candidate."""
    p = Path(path)
    if p.suffix == ".json":
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                yield item
        return

    if p.suffix == ".gz":
        import gzip
        opener = gzip.open(p, "rt", encoding="utf-8")
    else:
        opener = open(p, "r", encoding="utf-8")

    with opener as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def generate_reasoning(candidate, scores):
    """
    Build a specific, honest 1-2 sentence reasoning string.
    
    scores is a dict with keys:
      title, skills, career, experience, location, education,
      text_relevance, behavioral, final
    """
    profile = candidate["profile"]
    signals = candidate["redrob_signals"]
    
    parts = []
    
    # Core identity
    title = profile["current_title"]
    company = profile["current_company"]
    industry = profile["current_industry"]
    yrs = profile["years_of_experience"]
    parts.append(f"{title} at {company} ({industry}), {yrs} yrs exp")
    
    # Skills highlight
    skill_names = [s["name"] for s in candidate.get("skills", [])]
    # Pick up to 3 most relevant skills (those that matched must-have or nice-to-have)
    from config import MUST_HAVE_SKILLS, NICE_TO_HAVE_SKILLS
    relevant = [s for s in skill_names if s.lower() in MUST_HAVE_SKILLS]
    if not relevant:
        relevant = [s for s in skill_names if s.lower() in NICE_TO_HAVE_SKILLS]
    if relevant:
        top_skills = relevant[:3]
        parts.append(f"key skills: {', '.join(top_skills)}")
    
    # Location
    loc = profile.get("location", "Unknown")
    country = profile.get("country", "Unknown")
    parts.append(f"based in {loc}, {country}")
    
    # Behavioral highlights
    behavioral_notes = []
    rr = signals.get("recruiter_response_rate", 0)
    if rr >= 0.5:
        behavioral_notes.append(f"response rate {rr:.0%}")
    elif rr < 0.2:
        behavioral_notes.append(f"low response rate {rr:.0%}")
    
    otw = signals.get("open_to_work_flag", False)
    if otw:
        behavioral_notes.append("open to work")
    
    notice = signals.get("notice_period_days", 0)
    if notice <= 30:
        behavioral_notes.append(f"{notice}d notice")
    elif notice > 90:
        behavioral_notes.append(f"{notice}d notice (long)")
    
    if behavioral_notes:
        parts.append("; ".join(behavioral_notes))
    
    reasoning = "; ".join(parts) + "."
    
    # Keep under ~200 chars for CSV readability
    if len(reasoning) > 250:
        reasoning = reasoning[:247] + "..."
    
    return reasoning


def write_submission_csv(ranked_candidates, output_path):
    """
    Write the top-100 ranked candidates to a submission CSV.
    
    ranked_candidates: list of (candidate, scores_dict) tuples, already sorted.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    # Round scores to 4 decimal places, then re-sort to ensure
    # tie-break ordering (ascending candidate_id) is correct after rounding
    top = ranked_candidates[:100]
    rounded = []
    for candidate, scores in top:
        rounded_score = round(scores["final"], 4)
        rounded.append((candidate, scores, rounded_score))
    
    rounded.sort(key=lambda x: (-x[2], x[0]["candidate_id"]))
    
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        
        for rank, (candidate, scores, rscore) in enumerate(rounded, start=1):
            cid = candidate["candidate_id"]
            reasoning = generate_reasoning(candidate, scores)
            writer.writerow([cid, rank, f"{rscore:.4f}", reasoning])
