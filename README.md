# TVB Lead Discovery Agent

An autonomous agent that discovers early-stage tech-platform companies matching
TVB's target investment/partnership profile, and outputs a clean, filtered
lead list with a verified CEO/founder email.

## Target profile it filters for

1. Revenue **or** funding raised between **$1M–$5M USD**
2. Operates a **tech-related platform**
3. **Minimal to no presence in the US**
4. **Name and email of the CEO/Co-founder** available and **email-verified**

Fields the agent can't confirm from real evidence are left blank — the
extraction prompt is explicitly instructed never to guess or fill in
generic/plausible-sounding data (see `agent/extractor.py`).

## How it works (architecture)

```
agent/discovery.py   -> Claude generates a fresh batch of search queries each run
                         (sector x region x funding-signal combos, directories,
                         local tech news, accelerator pages, etc.) and runs them
                         against a real search API. This is what makes discovery
                         dynamic instead of reading from one fixed list.

agent/extractor.py   -> Fetches each candidate company's site (home + About/Team
                         page) and asks Claude to extract only explicitly-stated
                         facts into a strict JSON schema.

agent/email_finder.py -> Verifies a published email if found, or generates
                         common name+domain patterns for the CEO/founder and
                         verifies each candidate via Hunter.io (or a free
                         MX/SMTP fallback) — only a verified address is kept.

agent/filters.py     -> Applies the 4 qualifying checks in filters.py.

agent/pipeline.py    -> Orchestrates the above end to end.

app.py               -> Streamlit UI: enter keys, click Run, see results,
                         export CSV.
```

Each run asks Claude for a **new** batch of discovery queries, so repeated
runs expand coverage rather than re-searching the same ground — this is how
it clears the "must discover new sources on its own" requirement instead of
depending on a hardcoded company list.

## Required API keys — what's actually free right now

You need your own keys — none are bundled (it's your spend and your data,
and there's no such thing as a universal shared "free key" for these
services). Figures below were checked in September 2026; free-tier terms
change, so double check each provider's pricing page before relying on them.

| Key | Used for | What's free | Get it at |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | query generation + fact extraction | New accounts get a one-time ~$5 trial credit, no credit card required. No ongoing free tier — after that it's pay-as-you-go (cheap: a full run costs well under $1 in tokens). | console.anthropic.com |
| `TAVILY_API_KEY` (recommended) | web discovery | 1,000 search credits/month, free, no credit card. | tavily.com |
| `SERPAPI_KEY` (alternative) | web discovery | 250 searches/month free. | serpapi.com |
| ~~`GOOGLE_CSE_KEY`+`GOOGLE_CSE_CX`~~ | web discovery | Supported in code for existing accounts, but **Google's Custom Search JSON API closed to new signups in early 2026** and is being retired entirely on Jan 1, 2027 — don't build on it if you're starting fresh. Use Tavily or SerpAPI instead. | — |
| `HUNTER_API_KEY` | email verification | 50 credits/month free (verification costs 0.5 credit each, so ~100 verifications/mo), no credit card. | hunter.io |

Without a `HUNTER_API_KEY`, the agent falls back to a free MX/SMTP probe,
which is noticeably less reliable (many mail servers don't answer truthfully
or block the probe outright) — expect fewer emails to pass verification.
For a serious run, get the free Hunter key — it costs nothing and materially
improves the "verified email" output the brief requires.

**Total cost to run this for real: $0 up front.** Tavily + Hunter's free
tiers cover discovery and verification with no card on file; Anthropic's
trial credit covers a handful of full runs before you'd need to add a small
amount of billing.

## Run it locally

```bash
git clone https://github.com/Allauddin-2006/TVB
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
streamlit run app.py
```

Open the local URL Streamlit prints, enter/confirm your keys in the sidebar
(or rely on the `.env` values), and click **Run Agent**.

## Deploy it so anyone can open a link and trigger a run (no cloning needed)

**Recommended: Streamlit Community Cloud (free)**

1. Push this repo to your own public GitHub repo.
2. Go to share.streamlit.io -> "New app" -> connect your GitHub -> pick this
   repo, branch `main`, main file `app.py`.
3. In the app's **Settings -> Secrets**, paste:
   ```toml
   ANTHROPIC_API_KEY = "sk-..."
   SERPAPI_KEY = "..."
   HUNTER_API_KEY = "..."
   ```
   (or the Google CSE equivalents)
4. Deploy. You get a public `*.streamlit.app` link — anyone can open it and
   click **Run Agent** with no setup on their end. Keys stay in Streamlit's
   secrets manager, not in the repo.

**Alternative: Render / Railway**

Both support "deploy from GitHub repo" with a start command of:
```bash
streamlit run app.py --server.port $PORT --server.address 0.0.0.0
```
Set the same environment variables (`ANTHROPIC_API_KEY`, `SERPAPI_KEY` or
`GOOGLE_CSE_KEY`/`GOOGLE_CSE_CX`, `HUNTER_API_KEY`) in the service's
environment settings.

## Getting to 15+ qualifying leads

Each click of **Run Agent**:
- generates a new batch of ~40 search queries,
- checks up to ~120 candidate company sites,
- extracts, verifies emails, and filters them.

Real-world yield depends heavily on how many sites publicly state a dollar
funding/revenue figure and a named founder — that's usually the bottleneck,
not the search step. If a single run doesn't clear 15, **click Run again**
(new queries = new companies) — the UI will tell you how many you have and
prompt you to re-run if short. You can also raise `MAX_QUERIES_PER_RUN` and
`MAX_CANDIDATES_PER_RUN` in `agent/config.py` for a wider sweep per click, at
the cost of more API spend and a longer run time.

## Honest limitations

- **Revenue/funding figures are only accepted when explicitly published**
  (press release, funding tracker, "we've raised $X" on the site). The agent
  does not estimate or infer financials — a company with real revenue in
  range but no public figure will be excluded, since the brief requires
  leaving unverified fields blank rather than guessing.
- **"No US presence" is evidence-based, not exhaustive.** It checks for
  explicit signals (stated HQ country, mentions of a US office/entity). It
  can't fully rule out, say, a handful of US customers.
- **Email verification quality depends on the verifier.** Hunter.io is
  fairly reliable; the free SMTP fallback is not — treat SMTP-probe-only
  results with more skepticism.
- This tool only searches and reads **public** web pages (company sites,
  press coverage, search snippets) and never accesses LinkedIn directly (per
  the brief's request to rely only on the TVB LinkedIn/website references
  for context on TVB itself, not as scraping targets).
