"""
Email discovery + verification.

Priority order:
1. If the extractor already found a published email on the site, verify that.
2. Otherwise, generate common pattern guesses from the founder's name + the
   company domain (first@, firstlast@, first.last@, f.last@) and verify each
   candidate — only keep one if verification actually passes.

Verification uses Hunter.io's Email Verifier API when HUNTER_API_KEY is set
(recommended — free tier available, most reliable). If no Hunter key is
configured, falls back to a basic MX-record + SMTP RCPT-TO probe, which is
free but less reliable (many mail servers won't answer truthfully, and some
networks block outbound SMTP entirely — in that case leave the field blank
rather than report a false positive).
"""

import re
import smtplib
import socket

import dns.resolver
import requests

import config


def domain_from_url(url: str) -> str:
    domain = url.split("//")[-1].split("/")[0]
    return domain.replace("www.", "")


def name_to_candidates(full_name: str, domain: str):
    parts = re.sub(r"[^a-zA-Z\s]", "", full_name or "").lower().split()
    if len(parts) < 2:
        return []
    first, last = parts[0], parts[-1]
    return [
        f"{first}@{domain}",
        f"{first}.{last}@{domain}",
        f"{first}{last}@{domain}",
        f"{first[0]}{last}@{domain}",
        f"{first}.{last[0]}@{domain}",
    ]


def verify_with_hunter(email: str) -> tuple[bool, str]:
    if not config.HUNTER_API_KEY:
        return (False, "no_hunter_key")
    try:
        resp = requests.get(
            "https://api.hunter.io/v2/email-verifier",
            params={"email": email, "api_key": config.HUNTER_API_KEY},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        status = data.get("status")  # 'valid', 'invalid', 'accept_all', 'unknown', etc.
        return (status == "valid", status or "unknown")
    except Exception as e:
        return (False, f"error:{e}")


def verify_with_smtp_probe(email: str) -> tuple[bool, str]:
    """Best-effort, free fallback. Not fully reliable — treat as a weak signal."""
    try:
        domain = email.split("@")[1]
        answers = dns.resolver.resolve(domain, "MX", lifetime=10)
        mx_record = str(sorted(answers, key=lambda r: r.preference)[0].exchange)
    except Exception:
        return (False, "no_mx_record")

    try:
        server = smtplib.SMTP(timeout=10)
        server.connect(mx_record)
        server.helo(server.local_hostname)
        server.mail("verify@example.com")
        code, _ = server.rcpt(email)
        server.quit()
        return (code == 250, f"smtp_code_{code}")
    except (socket.error, smtplib.SMTPException) as e:
        return (False, f"smtp_error:{e}")


def verify_email(email: str) -> tuple[bool, str]:
    if config.HUNTER_API_KEY:
        return verify_with_hunter(email)
    return verify_with_smtp_probe(email)


def find_and_verify_email(company_facts: dict) -> dict:
    """
    Mutates/returns company_facts with:
      - verified_email: str or None
      - email_verification_source: str or None
    Never fabricates an email — only reports one that actually passed
    verification.
    """
    domain = None
    if company_facts.get("website"):
        domain = domain_from_url(company_facts["website"])
    elif company_facts.get("source_url"):
        domain = domain_from_url(company_facts["source_url"])

    candidates = []
    if company_facts.get("published_email"):
        candidates.append(company_facts["published_email"])
    if domain and company_facts.get("ceo_or_founder_name"):
        candidates.extend(name_to_candidates(company_facts["ceo_or_founder_name"], domain))

    verified_email = None
    verification_source = None
    for candidate in candidates:
        ok, status = verify_email(candidate)
        if ok:
            verified_email = candidate
            verification_source = "hunter" if config.HUNTER_API_KEY else "smtp_probe"
            break

    company_facts["verified_email"] = verified_email
    company_facts["email_verification_source"] = verification_source
    return company_facts
