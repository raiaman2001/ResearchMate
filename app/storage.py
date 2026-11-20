"""SQLite: run history + URL cache. Report ko .md file me bhi save karta hai."""
import json
import re
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

from app import config

_init_lock = threading.Lock()
_init_done = set()

NEW_COLUMNS = {          # Stage 3 ke naye columns (purane DB me auto-add honge)
    "plan": "TEXT", "cost_usd": "REAL", "input_tokens": "INTEGER",
    "output_tokens": "INTEGER", "elapsed": "REAL", "trace": "TEXT",
    "confidence": "TEXT", "verification": "TEXT",     # Stage 4
    "events": "TEXT", "mode": "TEXT",                  # Stage 5
}
CACHE_NEW_COLUMNS = {"meta": "TEXT"}                  # Stage 4: page ka date/author info


def _conn():
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    key = str(config.DB_PATH)
    with _init_lock:                      # threads se ek saath init/migrate na ho
        if key in _init_done:
            return
        with _conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL, report TEXT NOT NULL, sources TEXT NOT NULL,
                file_path TEXT, created_at TEXT NOT NULL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS page_cache (
                url TEXT PRIMARY KEY, text TEXT NOT NULL, fetched_at TEXT NOT NULL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS source_archive (
                url TEXT PRIMARY KEY, text TEXT NOT NULL, meta TEXT, saved_at TEXT NOT NULL)""")
            existing = {r["name"] for r in c.execute("PRAGMA table_info(runs)")}
            for col, typ in NEW_COLUMNS.items():
                if col not in existing:
                    c.execute(f"ALTER TABLE runs ADD COLUMN {col} {typ}")
            cache_cols = {r["name"] for r in c.execute("PRAGMA table_info(page_cache)")}
            for col, typ in CACHE_NEW_COLUMNS.items():
                if col not in cache_cols:
                    c.execute(f"ALTER TABLE page_cache ADD COLUMN {col} {typ}")
        _init_done.add(key)


# ---------- Cache ----------
def cache_get_entry(url):
    """(text, meta_dict) do, ya None agar cache me nahi / purana ho gaya."""
    init_db()
    with _conn() as c:
        row = c.execute("SELECT text, fetched_at, meta FROM page_cache WHERE url=?", (url,)).fetchone()
    if not row:
        return None
    age = datetime.now(timezone.utc) - datetime.fromisoformat(row["fetched_at"])
    if age > timedelta(hours=config.CACHE_TTL_HOURS):
        return None
    return row["text"], json.loads(row["meta"] or "{}")


def cache_get(url):
    entry = cache_get_entry(url)
    return entry[0] if entry else None


def cache_set(url, text, meta=None):
    init_db()
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO page_cache (url, text, fetched_at, meta) VALUES (?,?,?,?)",
                  (url, text, datetime.now(timezone.utc).isoformat(), json.dumps(meta or {})))


# ---------- Runs / History ----------
def slugify(text):
    return re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")[:50] or "report"


def save_report(topic, markdown, meta):
    """markdown: poori report. meta: sources, plan, cost_usd, input_tokens, output_tokens, elapsed, trace."""
    init_db()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = config.REPORTS_DIR / f"{stamp}_{slugify(topic)}.md"
    path.write_text(markdown, encoding="utf-8")
    with _conn() as c:
        cur = c.execute(
            """INSERT INTO runs (topic, report, sources, file_path, created_at,
               plan, cost_usd, input_tokens, output_tokens, elapsed, trace,
               confidence, verification, events, mode)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (topic, markdown, "\n".join(meta.get("sources", [])), str(path),
             datetime.now().isoformat(timespec="seconds"),
             json.dumps(meta.get("plan", []), ensure_ascii=False),
             meta.get("cost_usd"), meta.get("input_tokens"), meta.get("output_tokens"),
             meta.get("elapsed"), json.dumps(meta.get("trace", [])),
             meta.get("confidence"), json.dumps(meta.get("verification", {}), ensure_ascii=False),
             json.dumps(meta.get("events", []), ensure_ascii=False), meta.get("mode", "standard")))
    return cur.lastrowid, path


def list_runs(limit=50):
    init_db()
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT id, topic, created_at, cost_usd, confidence, mode FROM runs ORDER BY id DESC LIMIT ?", (limit,))]


def get_run(run_id):
    init_db()
    with _conn() as c:
        row = c.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    return dict(row) if row else None


# ---------- Source archive (memory reuse ke liye: findings ke source ka text) ----------
def archive_put(url, text, meta=None):
    init_db()
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO source_archive (url, text, meta, saved_at) VALUES (?,?,?,?)",
                  (url, text, json.dumps(meta or {}), datetime.now(timezone.utc).isoformat()))


def archive_get(url):
    init_db()
    with _conn() as c:
        row = c.execute("SELECT text, meta FROM source_archive WHERE url=?", (url,)).fetchone()
    return (row["text"], json.loads(row["meta"] or "{}")) if row else None
