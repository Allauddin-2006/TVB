"""
Applies the four qualifying parameters from the brief. A company only
qualifies if the evidence explicitly supports each check — missing data
means the company is excluded (not assumed to pass).
"""

import config


def passes_revenue_or_funding(facts: dict) -> bool:
    amount = facts.get("funding_or_revenue_usd_amount")
    if amount is None:
        return False
    return config.REVENUE_OR_FUNDING_MIN_USD <= amount <= config.REVENUE_OR_FUNDING_MAX_USD


def passes_tech_platform(facts: dict) -> bool:
    sector = (facts.get("sector") or "").lower()
    desc = (facts.get("description") or "").lower()
    tech_terms = [
        "platform", "software", "saas", "app", "api", "ai", "cloud",
        "digital", "tech", "automation", "infrastructure",
    ]
    return any(t in sector for t in tech_terms) or any(t in desc for t in tech_terms)


def passes_minimal_us_presence(facts: dict) -> bool:
    # Excluded only if there's explicit evidence OF a US presence.
    # If we simply don't know, we do NOT assume "no US presence" —
    # require at least a stated HQ country outside the US.
    if facts.get("has_us_office_or_entity") is True:
        return False
    hq = (facts.get("hq_country") or "").strip().lower()
    if not hq:
        return False
    return hq not in {"us", "usa", "united states", "united states of america"}


def passes_ceo_contact_available(facts: dict) -> bool:
    return bool(facts.get("ceo_or_founder_name")) and bool(facts.get("verified_email"))


def qualifies(facts: dict) -> tuple[bool, dict]:
    checks = {
        "revenue_or_funding_in_range": passes_revenue_or_funding(facts),
        "is_tech_platform": passes_tech_platform(facts),
        "minimal_no_us_presence": passes_minimal_us_presence(facts),
        "ceo_name_and_verified_email": passes_ceo_contact_available(facts),
    }
    return all(checks.values()), checks
