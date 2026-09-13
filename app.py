import os
import pandas as pd
import streamlit as st

import config
from pipeline import run_pipeline

st.set_page_config(page_title="TVB Lead Discovery Agent", page_icon="🧭", layout="wide")

st.title("🧭 TVB Lead Discovery Agent")
st.caption(
    "Autonomously discovers early-stage tech-platform companies matching TVB's target "
    "profile: $1M–$5M revenue/funding, tech platform, minimal-to-no US presence, and a "
    "named CEO/co-founder with a verified email."
)

with st.sidebar:
    st.header("API Keys")
    st.caption("Keys are only kept in this session — nothing is stored or logged.")

    anthropic_key = st.text_input(
        "Anthropic API Key", value=os.getenv("ANTHROPIC_API_KEY", ""), type="password"
    )
    st.markdown("**Search API** (pick one — Tavily is the easiest free option)")
    tavily_key = st.text_input("Tavily API Key", value=os.getenv("TAVILY_API_KEY", ""), type="password")
    serpapi_key = st.text_input("SerpAPI Key", value=os.getenv("SERPAPI_KEY", ""), type="password")
    with st.expander("Google CSE (legacy — closed to new signups)"):
        google_cse_key = st.text_input(
            "Google CSE Key", value=os.getenv("GOOGLE_CSE_KEY", ""), type="password"
        )
        google_cse_cx = st.text_input("Google CSE CX (Search Engine ID)", value=os.getenv("GOOGLE_CSE_CX", ""))

    st.markdown("**Email Verification** (optional but recommended)")
    hunter_key = st.text_input("Hunter.io API Key", value=os.getenv("HUNTER_API_KEY", ""), type="password")

    st.divider()
    st.markdown(
        "Don't have keys yet? See the README for where to get each one "
        "(all have free tiers sufficient for testing)."
    )

# Push whatever the user entered into config/env for this session
config.ANTHROPIC_API_KEY = anthropic_key
config.TAVILY_API_KEY = tavily_key
config.SERPAPI_KEY = serpapi_key
config.GOOGLE_CSE_KEY = google_cse_key
config.GOOGLE_CSE_CX = google_cse_cx
config.HUNTER_API_KEY = hunter_key

col1, col2 = st.columns([1, 3])
with col1:
    run_clicked = st.button("🚀 Run Agent", type="primary", use_container_width=True)

if "results" not in st.session_state:
    st.session_state.results = None

if run_clicked:
    missing = []
    if not anthropic_key:
        missing.append("Anthropic API Key")
    if not (tavily_key or serpapi_key or (google_cse_key and google_cse_cx)):
        missing.append("a search API (Tavily, SerpAPI, or Google CSE)")

    if missing:
        st.error(f"Missing required configuration: {', '.join(missing)}. Add it in the sidebar.")
    else:
        progress_bar = st.progress(0.0)
        status_box = st.empty()
        log_lines = []

        def on_progress(msg, frac):
            log_lines.append(msg)
            status_box.text(msg)
            if frac is not None:
                progress_bar.progress(min(max(frac, 0.0), 1.0))

        with st.spinner("Running discovery pipeline..."):
            try:
                result = run_pipeline(progress_cb=on_progress)
                st.session_state.results = result
            except Exception as e:
                st.error(f"Run failed: {e}")

if st.session_state.results:
    leads = st.session_state.results["leads"]
    st.subheader(f"✅ {len(leads)} Qualifying Leads")

    if leads:
        rows = []
        for l in leads:
            rows.append({
                "Company": l.get("company_name"),
                "Description": l.get("description"),
                "Sector": l.get("sector"),
                "HQ Country": l.get("hq_country"),
                "Funding/Revenue (USD)": l.get("funding_or_revenue_usd_amount"),
                "Basis": l.get("funding_or_revenue_basis"),
                "CEO/Founder": l.get("ceo_or_founder_name"),
                "Verified Email": l.get("verified_email"),
                "Website": l.get("website") or l.get("source_url"),
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download CSV", csv, "tvb_qualifying_leads.csv", "text/csv")

        if len(leads) < config.MIN_QUALIFYING_LEADS:
            st.warning(
                f"Only found {len(leads)} of the {config.MIN_QUALIFYING_LEADS} minimum leads "
                "in this run. Click Run Agent again to search a fresh batch of queries — "
                "each run generates new discovery queries, so re-running expands coverage."
            )
    else:
        st.info("No qualifying leads found in this run — try running again for a new query batch.")

    with st.expander("Run log"):
        st.text("\n".join(st.session_state.results["log"]))
