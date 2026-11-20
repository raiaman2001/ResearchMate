"""F3: Source credibility score (0-1). Bina LLM ke, deterministic aur explainable.

score = 0.45*domain + 0.20*recency + 0.10*author + 0.25*cross-source agreement
"""
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from urllib.parse import urlparse

from app.lang import DEVA_RE, nfc, normalize_digits

W_DOMAIN, W_RECENCY, W_AUTHOR, W_AGREE = 0.45, 0.20, 0.10, 0.25

HIGH_SUFFIXES = (".gov", ".gov.in", ".nic.in", ".edu", ".ac.in", ".edu.au", ".ac.uk", ".gov.uk", ".int", ".mil")
HIGH_DOMAINS = {"who.int", "worldbank.org", "imf.org", "oecd.org", "nature.com", "science.org", "arxiv.org",
                "nih.gov", "un.org", "iea.org", "rbi.org.in"}
NEWS_DOMAINS = {"reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "thehindu.com", "livemint.com",
                "economictimes.indiatimes.com", "bloomberg.com", "ft.com", "nytimes.com", "theguardian.com",
                "indianexpress.com", "hindustantimes.com", "business-standard.com", "wsj.com",
                "ndtv.com", "jagran.com", "amarujala.com", "bhaskar.com", "livehindustan.com", "aajtak.in",
                "jansatta.com", "navbharattimes.indiatimes.com", "prabhatkhabar.com"}
REFERENCE_DOMAINS = {"wikipedia.org", "britannica.com"}
LOW_DOMAINS = {"medium.com", "substack.com", "blogspot.com", "wordpress.com", "quora.com", "reddit.com",
               "facebook.com", "twitter.com", "x.com", "linkedin.com", "pinterest.com", "tumblr.com"}

STOP = set("""the and for that with this from are was were has have had will would can could not but its their
there which about into more than also been being over under between while such only other some what when where
who whom how why does did you your our they them these those then than very just said says per via
का की के है हैं में और से को पर यह वह था थी थे एक भी तो ही कि जो इस उस लिए साथ द्वारा""".split())


@dataclass
class SourceScore:
    url: str
    score: float
    label: str                 # High / Medium / Low
    domain_type: str
    year: int | None
    has_author: bool
    agreement: float | None    # None = sirf ek hi source tha, compare nahi ho saka

    def to_dict(self):
        return asdict(self)


def hostname(url):
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def _matches(host, domains):
    return any(host == d or host.endswith("." + d) for d in domains)


def domain_info(url):
    """(score, type) domain ke hisaab se."""
    if url.startswith("doc://"):
        return 0.8, "local document"                 # user ka apna upload kiya hua PDF
    host = hostname(url)
    if host.endswith(HIGH_SUFFIXES) or _matches(host, HIGH_DOMAINS):
        return 1.0, "government/academic/institution"
    if _matches(host, NEWS_DOMAINS):
        return 0.75, "major news"
    if _matches(host, REFERENCE_DOMAINS):
        return 0.65, "reference"
    if _matches(host, LOW_DOMAINS):
        return 0.3, "social/blog"
    return 0.5, "other"


def extract_year(text, now_year=None):
    now_year = now_year or datetime.now().year
    for y in re.findall(r"(?:19|20)\d{2}", text or ""):
        if 1990 <= int(y) <= now_year + 1:
            return int(y)
    return None


def recency_score(year, now_year=None):
    if year is None:
        return 0.5                                  # unknown: neutral
    age = (now_year or datetime.now().year) - year
    if age <= 1:
        return 1.0
    if age <= 3:
        return 0.7
    if age <= 5:
        return 0.4
    return 0.2


def label_for(score):
    return "High" if score >= 0.7 else "Medium" if score >= 0.45 else "Low"


def _tokens(s):
    s = normalize_digits(nfc(s)).lower()
    words = re.findall(r"[a-z0-9\u0900-\u097f]+(?:\.[0-9]+)?", s)
    return {w for w in words if w not in STOP and len(w) > (1 if DEVA_RE.search(w) else 2)}


def _is_num(t):
    return t.replace(".", "").isdigit()


def claims_agree(a, b):
    """Do claims same baat keh rahe hain? (shared number + 2 words) ya (word overlap >= 0.3)"""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    nums = {t for t in ta & tb if _is_num(t)}
    words = {t for t in ta & tb if not _is_num(t)}
    jacc = len(ta & tb) / len(ta | tb)
    return (bool(nums) and len(words) >= 2) or jacc >= 0.3


def agreement_scores(findings_by_url):
    """url -> 0..1 (kitne doosre sources uske kisi claim se agree karte hain)."""
    out = {}
    urls = list(findings_by_url)
    for u in urls:
        others = [o for o in urls if o != u]
        if not others:
            out[u] = None
            continue
        agreeing = sum(
            1 for o in others
            if any(claims_agree(a, b) for a in findings_by_url[u] for b in findings_by_url[o]))
        out[u] = min(1.0, agreeing / min(2, len(others)))
    return out


def score_source(url, text, meta, agreement, now_year=None):
    meta = meta or {}
    dom, dtype = domain_info(url)
    year = extract_year(meta.get("published") or "", now_year) or extract_year((text or "")[:2000], now_year)
    has_author = bool(meta.get("author"))
    agree_val = 0.5 if agreement is None else agreement
    score = (W_DOMAIN * dom + W_RECENCY * recency_score(year, now_year)
             + W_AUTHOR * (1.0 if has_author else 0.3) + W_AGREE * agree_val)
    score = round(score, 2)
    return SourceScore(url, score, label_for(score), dtype, year, has_author, agreement)


def score_sources(urls, pages, metas, findings_by_url, now_year=None):
    agree = agreement_scores({u: findings_by_url.get(u, []) for u in urls})
    return {u: score_source(u, pages.get(u, ""), metas.get(u), agree.get(u), now_year) for u in urls}
