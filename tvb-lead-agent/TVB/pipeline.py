"""
Orchestrates a full run: discover candidates -> extract facts -> find/verify
email -> filter against the target profile -> return qualifying leads.

Designed to be called from the Streamlit app with a progress callback so the
UI can show live status.
"""

import anthropic

from . import config, discovery, extractor, email_finder, filters


def run_pipeline(progress_cb=None):
    """
    progress_cb(message: str, fraction: float) is called periodically so a
    caller (e.g. Streamlit) can render progress. Returns:
        {
          "leads": [ {..qualifying company dict..}, ... ],
          "log": [ str, ... ],
        }
    """
    log = []

    def report(msg, frac=None):
        log.append(msg)
        if progress_cb:
            progress_cb(msg, frac)

    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    report("Generating discovery queries and searching the web...", 0.05)
    candidates = discovery.discover_candidates(client)
    report(f"Found {len(candidates)} unique candidate sources.", 0.15)

    leads = []
    total = max(len(candidates), 1)

    for i, cand in enumerate(candidates):
        frac = 0.15 + 0.75 * (i / total)
        url = cand.get("url", "")
        report(f"Checking {url}", frac)

        facts = extractor.extract_company_facts(client, url, cand.get("snippet", ""))
        if not facts or not facts.get("company_name"):
            continue

        facts = email_finder.find_and_verify_email(facts)
        ok, checks = filters.qualifies(facts)
        facts["_checks"] = checks

        if ok:
            leads.append(facts)
            report(f"  -> Qualified: {facts['company_name']}", frac)

        if len(leads) >= config.MIN_QUALIFYING_LEADS and i >= total - 1:
            break

    report(f"Done. {len(leads)} qualifying leads found.", 1.0)
    return {"leads": leads, "log": log}
