"""
Extraction layer.

Fetches a candidate company's website (home page + About/Team page when
findable) and asks Claude to extract ONLY facts it can actually support with
text found on the page. This is deliberately conservative: the brief requires
that unverified/unknown fields be left blank rather than filled with
plausible-sounding guesses, so the extraction prompt enforces that.
"""

import json
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TVB-LeadAgent/1.0)"}


def fetch_text(url: str, timeout: int = 15) -> str:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
    except Exception:
        return ""
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text)[:8000]


def find_about_or_team_link(url: str) -> str | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception:
        return None
    soup = BeautifulSoup(resp.text, "html.parser")
    keywords = ["about", "team", "leadership", "founders", "company"]
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        label = a.get_text(strip=True).lower()
        if any(k in href or k in label for k in keywords):
            href_full = a["href"]
            if href_full.startswith("http"):
                return href_full
            if href_full.startswith("/"):
                base = "/".join(url.split("/")[:3])
                return base + href_full
    return None


EXTRACTION_SCHEMA_PROMPT = """You are extracting structured facts about a
company for a venture-scouting database. You will be given raw text scraped
from the company's website (home page and possibly an About/Team page) plus
a search snippet that mentioned it.

STRICT RULE: only fill a field if the source text actually supports it. If a
fact is not clearly stated in the text, set that field to null. Do NOT guess,
infer from company name, or use generic/plausible-sounding filler. It is
correct and expected for several fields to be null.

Return ONLY a single JSON object with these exact keys:
{
  "company_name": string or null,
  "description": string or null,          // one sentence, from the page's own language
  "sector": string or null,                // e.g. "Healthtech", "Cybersecurity SaaS"
  "hq_country": string or null,            // only if explicitly stated
  "has_us_office_or_entity": true|false|null,  // explicit evidence only (e.g. "our New York office", ".com/us", US address, US phone/state)
  "funding_or_revenue_usd_amount": number or null,   // numeric only, only if an explicit dollar figure for funding raised or revenue is stated
  "funding_or_revenue_basis": "funding"|"revenue"|null,
  "ceo_or_founder_name": string or null,   // only if a named individual with title CEO/Founder/Co-founder appears
  "ceo_or_founder_title": string or null,
  "published_email": string or null,       // only if an actual email address appears in the text
  "website": string or null
}

Raw page text:
---
{PAGE_TEXT}
---

Search snippet that led here: {SNIPPET}
Source URL: {URL}

Output ONLY the JSON object, no commentary, no markdown fences."""


def extract_company_facts(claude_client, url: str, snippet: str = "") -> dict | None:
    home_text = fetch_text(url)
    if not home_text:
        return None

    extra_text = ""
    about_url = find_about_or_team_link(url)
    if about_url and about_url != url:
        extra_text = fetch_text(about_url)

    combined = (home_text + " " + extra_text)[:10000]

    prompt = (
        EXTRACTION_SCHEMA_PROMPT
        .replace("{PAGE_TEXT}", combined)
        .replace("{SNIPPET}", snippet)
        .replace("{URL}", url)
    )

    resp = claude_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
    raw = re.sub(r"^```json|```$", "", raw.strip(), flags=re.MULTILINE).strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None

    data["source_url"] = url
    return data
