"""Saari settings ek jagah."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv()
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
DB_PATH = Path(os.getenv("DB_PATH", DATA_DIR / "researchmate.db"))
CHROMA_DIR = Path(os.getenv("CHROMA_DIR", DATA_DIR / "chroma"))
KG_PATH = Path(os.getenv("KG_PATH", DATA_DIR / "kg.json"))
PDF_FONT_DIR = Path(os.getenv("PDF_FONT_DIR", BASE_DIR / "static" / "fonts"))   # Noto Sans + Noto Sans Devanagari (OFL)

# Models (har agent ka alag model ho sakta hai: researchers par sasta lagao)
if os.getenv("GROQ_API_KEY"):
    _default_model = "qwen/qwen3.8-27b"
elif os.getenv("GEMINI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"):
    _default_model = "gemini/gemini-2.5-flash"
else:
    _default_model = "claude-sonnet-5-5"

MODEL = os.getenv("MODEL", _default_model)
PLANNER_MODEL = os.getenv("PLANNER_MODEL", MODEL)
RESEARCH_MODEL = os.getenv("RESEARCH_MODEL", MODEL)
WRITER_MODEL = os.getenv("WRITER_MODEL", MODEL)
VERIFIER_MODEL = os.getenv("VERIFIER_MODEL", MODEL)
CONFLICT_MODEL = os.getenv("CONFLICT_MODEL", MODEL)
JUDGE_MODEL = os.getenv("JUDGE_MODEL", MODEL)        # eval ka LLM-as-judge (behtar hai generator se alag model ho)
DEFAULT_REPORT_LANGUAGE = os.getenv("REPORT_LANGUAGE", "auto")   # auto / en / hi / hinglish

MAX_RETRIES = int(os.getenv("MAX_RETRIES", "2"))   # verifier fail hone par writer ko kitni baar wapas bhejna
MIN_QUOTE_CHARS = 15                               # evidence quote itna lamba ho tabhi valid

MAX_TOKENS = 2000
RESEARCHER_MAX_STEPS = int(os.getenv("RESEARCHER_MAX_STEPS", "6"))
CONCURRENCY = int(os.getenv("CONCURRENCY", "1" if os.getenv("GROQ_API_KEY") else "3"))   # Groq free tier ke liye 1 concurrency
PAGE_CHAR_LIMIT = 2000
CACHE_TTL_HOURS = 24
REQUEST_TIMEOUT = 10

# ---- Stage 5: memory, RAG, debate ----
SBERT_MODEL = os.getenv("SBERT_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")   # Hindi+English cross-lingual
EMBEDDER = os.getenv("EMBEDDER", "hashing")          # "hashing" (offline) ya "sbert" (sentence-transformers)
MEMORY_MIN_SIM = float(os.getenv("MEMORY_MIN_SIM", "0.25"))   # embedder badlo to ye bhi tune karo
MEMORY_MAX_REUSE = 5            # ek run me purani kitni findings reuse hongi
MEMORY_MAX_AGE_DAYS = int(os.getenv("MEMORY_MAX_AGE_DAYS", "90"))
DOC_MIN_SIM = float(os.getenv("DOC_MIN_SIM", "0.15"))
MAX_PDF_MB = 20
CHUNK_CHARS = 800
CHUNK_OVERLAP = 100

# Cost estimate ($ per 1M tokens). ESTIMATE hai: apne model ka asli price docs se check karo.
PRICES = {}   # e.g. {"claude-haiku-5-5": (1.0, 5.0)}
DEFAULT_PRICE_IN = float(os.getenv("PRICE_IN_PER_M", "3.0"))
DEFAULT_PRICE_OUT = float(os.getenv("PRICE_OUT_PER_M", "15.0"))


def price_for(model):
    return PRICES.get(model, (DEFAULT_PRICE_IN, DEFAULT_PRICE_OUT))


DATA_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)
