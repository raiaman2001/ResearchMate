"""Zero-API Web Intelligence Scraper & Pre-Research Extractor.
Scrapes search results and pages deterministically using ddgs and requests without calling any LLM API.
Generates a structured Raw Intelligence Dossier for the user to review.
"""
import asyncio
import re
from typing import List, Dict, Any
try:
    from app.tools import ResearchSession
    from app import scoring
except ImportError:
    from researchmate.app.tools import ResearchSession
    from researchmate.app import scoring

async def perform_pre_research(query: str, session: ResearchSession = None, max_sources: int = 15) -> Dict[str, Any]:
    if session is None:
        session = ResearchSession()

    # 1. Search top results via DDGS (expanded up to 15-20 results)
    raw_results = await asyncio.to_thread(session._search_sync, query, max_results=max_sources)
    if isinstance(raw_results, str) or not raw_results:
        clean_q = re.sub(r'[^\w\s]', '', query)
        raw_results = await asyncio.to_thread(session._search_sync, clean_q, max_results=max_sources)

    if isinstance(raw_results, str) or not raw_results:
        raw_results = []

    # 2. Parallel async scrape using a concurrency semaphore (5 workers max, prevents IP-rate limits while keeping speed ultra-fast)
    sem = asyncio.Semaphore(5)

    async def _fetch_single_page(item: dict) -> dict:
        url = item.get("url")
        if not url:
            return None
        async with sem:
            ok, text = await asyncio.to_thread(session._read_sync, url)
            meta = session.meta.get(url, {})
            title = item.get("title") or meta.get("title") or url
            snippet = item.get("snippet") or ""

            key_excerpts = []
            if ok and text:
                sentences = re.split(r'(?<=[.!?])\s+', text)
                for s in sentences:
                    s_clean = s.strip()
                    if len(s_clean) > 40 and not any(bad in s_clean.lower() for bad in ["cookie", "privacy policy", "subscribe", "terms of service", "all rights reserved"]):
                        key_excerpts.append(s_clean)
                    if len(key_excerpts) >= 3:
                        break
            elif snippet:
                key_excerpts.append(snippet)

            return {
                "title": title,
                "url": url,
                "snippet": snippet,
                "text": text if ok else "",
                "key_excerpts": key_excerpts,
                "published": meta.get("published"),
                "author": meta.get("author", False)
            }

    tasks = [_fetch_single_page(item) for item in raw_results[:max_sources]]
    scraped_results = await asyncio.gather(*tasks, return_exceptions=True)

    pages_data = [p for p in scraped_results if isinstance(p, dict) and p is not None]

    # 3. Score sources with existing scoring engine
    cited_urls = [p["url"] for p in pages_data]
    by_url = {p["url"]: p["key_excerpts"] for p in pages_data}
    scored = scoring.score_sources(cited_urls, session.pages, session.meta, by_url)

    for p in pages_data:
        score_obj = scored.get(p["url"])
        if score_obj:
            p["score"] = score_obj.score
            p["label"] = score_obj.label
            p["domain_type"] = score_obj.domain_type
        else:
            p["score"] = 0.5
            p["label"] = "Medium"
            p["domain_type"] = "general"

    # 4. Generate structured raw Markdown dossier for manual mode export
    md_lines = [
        f"# Pre-Research Intelligence Dossier: {query}",
        f"\n**Scraped Sources**: {len(pages_data)} verified links | **Mode**: Free Web-Scrape (Zero-API)\n",
        "---",
        "## 📑 Key Extracted Intelligence Highlights\n"
    ]

    for i, p in enumerate(pages_data, 1):
        md_lines.append(f"### {i}. [{p['title']}]({p['url']})")
        md_lines.append(f"- **Source Domain**: `{p['domain_type']}` | **Credibility**: `{p['label']}` ({p['score']})")
        if p.get("published"):
            md_lines.append(f"- **Date**: {p['published']}")
        md_lines.append("\n**Key Findings & Excerpts:**")
        for exc in p["key_excerpts"]:
            md_lines.append(f"> \"{exc}\"\n")
        md_lines.append("")

    md_lines.append("## 📝 Manual Research Notes Template\n")
    md_lines.append("- [ ] **Executive Summary Draft**:\n- [ ] **Market / Technical Insights**:\n- [ ] **Verdict & Final Takeaway**:\n")

    return {
        "query": query,
        "total_sources": len(pages_data),
        "sources": pages_data,
        "raw_markdown": "\n".join(md_lines)
    }
