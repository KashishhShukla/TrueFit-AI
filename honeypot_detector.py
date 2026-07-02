"""
Honeypot detection: identify candidates with subtly impossible profiles.
~80 honeypots exist in the dataset. >10% in top 100 = disqualification.
"""

from datetime import datetime, date


def is_honeypot(candidate):
    """
    Returns True if the candidate's profile has impossible characteristics.
    Checks multiple signals — any single strong signal is enough to flag.
    """
    flags = 0
    
    flags += _check_expert_zero_duration(candidate)
    flags += _check_too_many_experts(candidate)
    flags += _check_career_math(candidate)
    flags += _check_impossible_dates(candidate)
    
    # A single strong flag is enough
    return flags >= 1


def _check_expert_zero_duration(candidate):
    """Expert proficiency with 0 months of usage — impossible."""
    skills = candidate.get("skills", [])
    expert_zero = 0
    for s in skills:
        if s.get("proficiency") == "expert" and s.get("duration_months", 0) == 0:
            expert_zero += 1
    # Even one is suspicious; 2+ is almost certainly a honeypot
    if expert_zero >= 2:
        return 2
    if expert_zero == 1:
        return 1
    return 0


def _check_too_many_experts(candidate):
    """
    Claiming expert in 8+ skills where most have very low duration.
    Real experts don't have 10 expert-level skills with <6 months each.
    """
    skills = candidate.get("skills", [])
    expert_skills = [s for s in skills if s.get("proficiency") == "expert"]
    
    if len(expert_skills) >= 8:
        low_duration = sum(
            1 for s in expert_skills if s.get("duration_months", 0) < 6
        )
        if low_duration >= len(expert_skills) * 0.6:
            return 2
    return 0


def _check_career_math(candidate):
    """
    Check if career history durations are internally consistent.
    - Total career duration vs years_of_experience
    - Individual role duration impossibilities
    """
    profile = candidate.get("profile", {})
    yrs_exp = profile.get("years_of_experience", 0)
    career = candidate.get("career_history", [])
    
    if not career:
        return 0
    
    total_months = sum(c.get("duration_months", 0) for c in career)
    total_years = total_months / 12.0
    
    # If total career months exceeds stated experience by a huge margin
    if yrs_exp > 0 and total_years > yrs_exp * 1.8 + 2:
        return 1
    
    # Check if any single role duration is longer than total experience
    for c in career:
        role_months = c.get("duration_months", 0)
        if yrs_exp > 0 and role_months > (yrs_exp * 12) + 12:
            return 1
    
    return 0


def _check_impossible_dates(candidate):
    """
    Check for date impossibilities in career history.
    - end_date before start_date
    - career starting before education ended (with significant overlap)
    """
    career = candidate.get("career_history", [])
    
    for c in career:
        start = c.get("start_date")
        end = c.get("end_date")
        if start and end:
            try:
                s = datetime.strptime(start, "%Y-%m-%d").date()
                e = datetime.strptime(end, "%Y-%m-%d").date()
                if e < s:
                    return 2  # end before start is clearly impossible
            except (ValueError, TypeError):
                pass
    
    return 0
