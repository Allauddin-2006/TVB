"""
Central configuration for the TVB Lead Discovery Agent.

Everything that encodes the target profile from the brief lives here so the
filtering logic in filters.py stays readable and auditable.
"""

import os

# ---------------------------------------------------------------------------
# API keys (set these as environment variables / Streamlit secrets — never
# hardcode real keys in this file)
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Discovery (pick ONE — the code will use whichever is present, checked in
# this order: SerpAPI > Tavily > Google CSE)
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
GOOGLE_CSE_KEY = os.getenv("GOOGLE_CSE_KEY", "")   # note: Google CSE JSON API is closed to new signups as of 2026
GOOGLE_CSE_CX = os.getenv("GOOGLE_CSE_CX", "")

# Email verification (optional but required to mark an email "verified")
HUNTER_API_KEY = os.getenv("HUNTER_API_KEY", "")

# ---------------------------------------------------------------------------
# Target profile (from the project brief)
# ---------------------------------------------------------------------------
REVENUE_OR_FUNDING_MIN_USD = 1_000_000
REVENUE_OR_FUNDING_MAX_USD = 5_000_000

# Sectors mirrored from TVB's existing Orbits (Healthcare, Education, AI,
# Cybersecurity, Digital Twin, Travel, Fintech/Payments) plus adjacent
# tech-platform categories worth covering.
TARGET_SECTORS = [
    "digital health platform",
    "healthtech SaaS",
    "edtech platform",
    "AI agents startup",
    "applied AI SaaS",
    "cybersecurity SaaS",
    "digital twin platform",
    "travel technology platform",
    "fintech platform",
    "embedded finance startup",
    "payments infrastructure startup",
]

# Regions to bias discovery toward companies with minimal/no US presence.
# These are used to build search queries, NOT as a hard geography filter —
# the actual "minimal to no US presence" check is done per-company in
# filters.py based on evidence found on the company's own site.
TARGET_REGIONS = [
    "UK", "Ireland", "France", "Germany", "Netherlands", "Spain", "Italy",
    "Nordics", "Eastern Europe", "India", "Singapore", "Southeast Asia",
    "UAE", "Saudi Arabia", "Middle East", "Africa", "Nigeria", "Kenya",
    "LATAM", "Brazil", "Mexico", "Colombia", "Pakistan", "Bangladesh",
]

# Search phrases that tend to surface companies disclosing revenue/funding
# figures in the target band.
FUNDING_SIGNAL_PHRASES = [
    "raises seed funding",
    "raises $2 million",
    "raises $3 million",
    "raises pre-series A",
    "closes seed round",
    "annual recurring revenue million",
]

MIN_QUALIFYING_LEADS = 15

# How many discovery queries / candidate companies to process per run before
# stopping (keeps API spend bounded — tune as needed).
MAX_QUERIES_PER_RUN = 40
MAX_CANDIDATES_PER_RUN = 120
