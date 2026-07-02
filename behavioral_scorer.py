"""
Behavioral signal modifier: adjusts scores based on candidate availability,
responsiveness, and platform engagement.

This is a MULTIPLIER on the fit score, not an additive component.
A perfect-on-paper candidate who is unreachable gets down-weighted.
"""

from datetime import datetime, date

import config


def compute_behavioral_modifier(candidate):
    """
    Compute a multiplicative behavioral modifier from redrob_signals.
    Returns a float, clamped to [BEHAVIORAL_MIN, BEHAVIORAL_MAX].
    """
    signals = candidate.get("redrob_signals", {})
    
    modifiers = []
    
    modifiers.append(_recency_modifier(signals))
    modifiers.append(_open_to_work_modifier(signals))
    modifiers.append(_response_rate_modifier(signals))
    modifiers.append(_response_time_modifier(signals))
    modifiers.append(_notice_period_modifier(signals))
    modifiers.append(_interview_completion_modifier(signals))
    modifiers.append(_profile_completeness_modifier(signals))
    modifiers.append(_verification_modifier(signals))
    modifiers.append(_github_modifier(signals))
    modifiers.append(_linkedin_modifier(signals))
    modifiers.append(_work_mode_modifier(signals))
    
    # Geometric mean of all modifiers (multiplicative combination)
    combined = 1.0
    for m in modifiers:
        combined *= m
    
    return max(config.BEHAVIORAL_MIN, min(combined, config.BEHAVIORAL_MAX))


def _recency_modifier(signals):
    """How recently was the candidate active on the platform?"""
    last_active = signals.get("last_active_date", "")
    if not last_active:
        return 0.7
    
    try:
        last = datetime.strptime(last_active, "%Y-%m-%d").date()
        today = date(2026, 6, 15)  # approximate "now" for the dataset
        days_ago = (today - last).days
        
        if days_ago < 30:
            return 1.05
        elif days_ago < 90:
            return 1.0
        elif days_ago < 180:
            return 0.8
        else:
            return 0.5
    except (ValueError, TypeError):
        return 0.7


def _open_to_work_modifier(signals):
    """Is the candidate actively looking?"""
    if signals.get("open_to_work_flag", False):
        return 1.08
    return 0.85


def _response_rate_modifier(signals):
    """How often do they respond to recruiter messages?"""
    rate = signals.get("recruiter_response_rate", 0)
    return 0.6 + (rate * 0.4)


def _response_time_modifier(signals):
    """How quickly do they respond?"""
    hours = signals.get("avg_response_time_hours", 168)
    
    if hours < 24:
        return 1.05
    elif hours < 72:
        return 1.0
    elif hours < 168:
        return 0.9
    else:
        return 0.75


def _notice_period_modifier(signals):
    """JD prefers sub-30-day notice. Can buy out up to 30 days."""
    days = signals.get("notice_period_days", 60)
    
    if days <= 30:
        return 1.08
    elif days <= 60:
        return 1.0
    elif days <= 90:
        return 0.9
    else:
        return 0.75


def _interview_completion_modifier(signals):
    """Do they actually show up to interviews?"""
    rate = signals.get("interview_completion_rate", 0.5)
    return 0.75 + (rate * 0.25)


def _profile_completeness_modifier(signals):
    """How complete is their profile?"""
    score = signals.get("profile_completeness_score", 50)
    
    if score < 40:
        return 0.85
    elif score < 70:
        return 0.95
    else:
        return 1.03


def _verification_modifier(signals):
    """Are their email and phone verified?"""
    email = signals.get("verified_email", False)
    phone = signals.get("verified_phone", False)
    
    if email and phone:
        return 1.03
    elif email or phone:
        return 1.0
    else:
        return 0.9


def _github_modifier(signals):
    """GitHub activity score. -1 means no GitHub linked."""
    score = signals.get("github_activity_score", -1)
    
    if score > 50:
        return 1.08
    elif score > 20:
        return 1.03
    elif score >= 0:
        return 1.0
    else:
        return 0.97


def _linkedin_modifier(signals):
    """Is LinkedIn connected?"""
    if signals.get("linkedin_connected", False):
        return 1.02
    return 0.98


def _work_mode_modifier(signals):
    """Does work mode preference align with JD (hybrid/onsite)?"""
    mode = signals.get("preferred_work_mode", "flexible")
    willing = signals.get("willing_to_relocate", False)
    
    if mode in ("onsite", "hybrid", "flexible"):
        return 1.0
    elif mode == "remote" and willing:
        return 0.95
    elif mode == "remote":
        return 0.85
    return 1.0
