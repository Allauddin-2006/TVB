"""
Discovery layer.

Responsible for finding *new* candidate companies on its own each run,
rather than reading from a fixed list. It does this by:

1. Asking Claude to propose a fresh batch of specific, varied search queries
   each run (sector x region x funding-signal combinations, plus whatever
   else it thinks of) — so the query set isn't static either.
2. Executing those queries against a real web search API (Google Programmable
   Search Engine or SerpAPI — whichever key is configured).
3. Returning deduplicated candidate URLs/domains for the extraction stage.
"""

import itertools
import random
import requests

import config


def _search_google_cse(query: str, num: int = 10):
    if not (config.GOOGLE_CSE_KEY and config.GOOGLE_CSE_CX):
        return []
    resp = requests.get(
        "https://www.googleapis.com/customsearch/v1",
        params={
            "key": config.GOOGLE_CSE_KEY,
            "cx": config.GOOGLE_CSE_CX,
            "q": query,
            "num": min(num, 10),
        },
        timeout=20,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    return [
        {"title": i.get("title", ""), "url": i.get("link", ""), "snippet": i.get("snippet", "")}
        for i in items
    ]


def _search_serpapi(query: str, num: int = 10):
    if not config.SERPAPI_KEY:
        return []
    resp = requests.get(
        "https://serpapi.com/search",
        params={"q": query, "num": num, "engine": "google", "api_key": config.SERPAPI_KEY},
        timeout=20,
    )
    resp.raise_for_status()
    items = resp.json().get("organic_results", [])
    return [
        {"title": i.get("title", ""), "url": i.get("link", ""), "snippet": i.get("snippet", "")}
        for i in items
    ]


def _search_tavily(query: str, num: int = 10):
    if not config.TAVILY_API_KEY:
        return []
    resp = requests.post(
        "https://api.tavily.com/search",
        json={
            "api_key": config.TAVILY_API_KEY,
            "query": query,
            "max_results": num,
            "search_depth": "basic",
        },
        timeout=20,
    )
    resp.raise_for_status()
    items = resp.json().get("results", [])
    return [
        {"title": i.get("title", ""), "url": i.get("url", ""), "snippet": i.get("content", "")}
        for i in items
    ]


def search_web(query: str, num: int = 10):
    """Try SerpAPI, then Tavily, then Google CSE. Returns [] if none configured."""
    if config.SERPAPI_KEY:
        return _search_serpapi(query, num)
    if config.TAVILY_API_KEY:
        return _search_tavily(query, num)
    if config.GOOGLE_CSE_KEY and config.GOOGLE_CSE_CX:
        return _search_google_cse(query, num)
    raise RuntimeError(
        "No search API configured. Set SERPAPI_KEY, or TAVILY_API_KEY, "
        "or GOOGLE_CSE_KEY + GOOGLE_CSE_CX."
    )


def generate_query_batch(claude_client, batch_size: int = 25):
    """
    Ask Claude to generate a fresh, varied batch of search queries this run,
    combining sector, region and funding-signal language, plus its own ideas
    for where such companies get mentioned (press releases, funding trackers,
    startup directories, local tech news, accelerator cohort pages, etc).
    This is what keeps discovery from relying on one fixed source list.
    """
    sectors = random.sample(config.TARGET_SECTORS, k=min(6, len(config.TARGET_SECTORS)))
    regions = random.sample(config.TARGET_REGIONS, k=min(8, len(config.TARGET_REGIONS)))
    signals = config.FUNDING_SIGNAL_PHRASES

    prompt = f"""You are helping build search queries to discover early-stage tech
companies for venture scouting. Generate {batch_size} distinct Google search
queries (plain text, one per line, no numbering, no quotes) that would surface
company websites, press releases, or news articles about tech-platform
companies (SaaS, AI, healthtech, edtech, cybersecurity, digital twin, travel
tech, fintech) that are:
- Headquartered outside the United States (bias toward: {", ".join(regions)})
- Likely to have raised funding or generated revenue in the $1M-$5M range
- Early stage (seed to Series A), not large enterprises

Vary the query style: some should target funding announcement language
(e.g. combining terms like {random.choice(signals)!r}), some should target
startup directories or "top N startups in <region>" style listicles, some
should target local tech news outlets, some should target accelerator/
incubator cohort or demo day pages, some should just combine a sector term
with a region term. Use sectors like: {", ".join(sectors)}.

Output ONLY the queries, one per line, nothing else."""

    resp = claude_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    queries = [q.strip("- ").strip() for q in text.splitlines() if q.strip()]
    return queries[:batch_size]


def discover_candidates(claude_client, max_queries=None):
    """
    Runs a batch of queries and returns a deduplicated list of candidate
    result dicts: {title, url, snippet}.
    """
    max_queries = max_queries or config.MAX_QUERIES_PER_RUN
    queries = generate_query_batch(claude_client, batch_size=max_queries)

    seen_domains = set()
    candidates = []
    for q in queries:
        try:
            results = search_web(q, num=10)
        except Exception:
            continue
        for r in results:
            url = r.get("url", "")
            if not url:
                continue
            domain = url.split("/")[2] if "//" in url else url
            if domain in seen_domains:
                continue
            seen_domains.add(domain)
            candidates.append(r)
        if len(candidates) >= config.MAX_CANDIDATES_PER_RUN:
            break

    return candidates
