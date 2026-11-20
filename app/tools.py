"""Tools. Ek ResearchSession ek run ka state rakhta hai (sources, cache hits, injection flags)."""
import asyncio
import re
import threading

import requests
from bs4 import BeautifulSoup

from app import config, guard, storage

WEB_SEARCH_TOOL = {
    "name": "web_search",
    "description": "Searches the internet and returns top web results with title, url and snippet.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search keyword or query string."
            }
        },
        "required": ["query"],
    },
}
READ_WEBPAGE_TOOL = {
    "name": "read_webpage",
    "description": "Reads full text from a given webpage URL.",
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The complete HTTP or HTTPS URL of the webpage to read."
            }
        },
        "required": ["url"],
    },
}

READ_HTMLPAGE_TOOL = {
    "name": "read_htmlpage",
    "description": "Alias for read_webpage. Reads full text from a given webpage URL.",
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The complete HTTP or HTTPS URL of the webpage to read."
            }
        },
        "required": ["url"],
    },
}


SEARCH_DOCS_TOOL = {
    "name": "search_documents",
    "description": "User ke upload kiye hue PDF documents me search karta hai. Text <source> tag me aata hai.",
    "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
}


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
]

def decode_response(resp):
    """Page ka text. UTF-8 pehle: bahut Hindi sites header me charset nahi deti, aur requests tab ISO-8859-1
    maan leta hai (resp.text = mojibake). UTF-8 fail ho to detected encoding."""
    raw = getattr(resp, "content", None)
    if isinstance(raw, (bytes, bytearray)):
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            enc = getattr(resp, "apparent_encoding", None) or getattr(resp, "encoding", None) or "latin-1"
            return raw.decode(enc, errors="replace")
    return resp.text


class ResearchSession:
    def __init__(self, docs=None):
        self.docs = docs                 # DocStore (optional): local PDF RAG
        self.sources = []        # sirf wo URLs jo sach me padhe gaye
        self.flagged = []        # jin pages me injection jaisa text mila
        self.pages = {}          # url -> padha gaya text (verifier ke liye)
        self.meta = {}           # url -> {"published":..., "author": bool, "title":...}
        self.cache_hits = 0
        self._lock = threading.Lock()

    # ----- sync kaam (thread me chalta hai) -----
    def _search_sync(self, query, max_results=15):
        try:
            from ddgs import DDGS
            results = DDGS().text(query, max_results=max_results)
            return [{"title": r["title"], "url": r["href"], "snippet": r["body"]} for r in results]
        except Exception as e:
            return f"Search error: {e}. Dusri query try karo."

    @property
    def docs_enabled(self):
        return self.docs is not None

    def restore_page(self, url, text, meta):
        """Memory se aayi finding ka source text wapas session me (verify/score ke liye). 'sources' me nahi jodta."""
        with self._lock:
            self.pages[url] = text
            self.meta[url] = meta or {}

    def _mark_read(self, url, text="", meta=None):
        with self._lock:
            if url not in self.sources:
                self.sources.append(url)
            self.pages[url] = text
            self.meta[url] = meta or {}

    @staticmethod
    def _extract_meta(soup, html):
        """Page ki publish date aur author ka pata (source credibility ke liye)."""
        published = None
        for attrs in ({"property": "article:published_time"}, {"itemprop": "datePublished"},
                      {"name": "date"}, {"name": "pubdate"}, {"name": "publishdate"},
                      {"property": "og:published_time"}):
            tag = soup.find("meta", attrs=attrs)
            if tag and tag.get("content"):
                published = tag["content"]
                break
        if not published:
            t = soup.find("time", attrs={"datetime": True})
            published = t["datetime"] if t else None
        if not published:
            m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', html)
            published = m.group(1) if m else None
        author = bool(soup.find("meta", attrs={"name": "author"})
                      or soup.find("meta", attrs={"property": "article:author"})
                      or soup.find(attrs={"rel": "author"})
                      or re.search(r'"author"\s*:', html))
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        return {"published": published, "author": author, "title": title[:150]}

    def _read_sync(self, url):
        """(ok, text) deta hai."""
        if not url.startswith(("http://", "https://")):
            return False, "Error: URL http:// ya https:// se shuru hona chahiye."

        entry = storage.cache_get_entry(url)
        if entry is not None:
            with self._lock:
                self.cache_hits += 1
            self._mark_read(url, entry[0], entry[1])
            return True, entry[0]

        try:
            import random
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
                "DNT": "1",
                "Connection": "keep-alive"
            }
            resp = requests.get(url, headers=headers, timeout=config.REQUEST_TIMEOUT)
            resp.raise_for_status()
        except requests.RequestException as e:
            return False, f"Could not read page: {e}"

        html = decode_response(resp)
        soup = BeautifulSoup(html, "html.parser")
        meta = self._extract_meta(soup, html)       # decompose se pehle
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = " ".join(soup.get_text(separator=" ").split())[: config.PAGE_CHAR_LIMIT]
        if len(text) < 100:
            return False, "Page me kaafi text nahi mila (JavaScript-heavy ya blocked). Dusra source try karo."
        storage.cache_set(url, text, meta)
        self._mark_read(url, text, meta)
        return True, text

    # ----- async wrappers (parallel research ke liye) -----
    async def web_search(self, query):
        return await asyncio.to_thread(self._search_sync, query)

    async def read_webpage(self, url):
        ok, text = await asyncio.to_thread(self._read_sync, url)
        if not ok:
            return text
        if guard.looks_injected(text):
            with self._lock:
                if url not in self.flagged:
                    self.flagged.append(url)
        return guard.wrap_source(url, text)

    async def read_htmlpage(self, url=None, **kwargs):
        """Fallback alias for models that hallucinate read_htmlpage instead of read_webpage."""
        target_url = url or kwargs.get("url") or kwargs.get("link") or kwargs.get("href")
        if not target_url:
            return "Error: URL is required"
        return await self.read_webpage(target_url)

    async def search_documents(self, query):
        if not self.docs_enabled:
            return "Koi document upload nahi hai."
        chunks = await asyncio.to_thread(self.docs.search, query, 4)
        if not chunks:
            return "Documents me kuch relevant nahi mila."
        out = []
        for c in chunks:
            url = c["url"]
            with self._lock:
                prev = self.pages.get(url, "")
                if c["text"] not in prev:
                    self.pages[url] = (prev + "\n" + c["text"]).strip()[:6000]
                self.meta.setdefault(url, {"published": None, "author": False, "title": c["doc"], "local": True})
                if url not in self.sources:
                    self.sources.append(url)
            if guard.looks_injected(c["text"]) and url not in self.flagged:
                self.flagged.append(url)
            out.append(guard.wrap_source(url, c["text"]))
        return "\n\n".join(out)
