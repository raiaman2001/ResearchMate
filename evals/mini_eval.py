"""Mini eval: verifier loop OFF (pehla draft) vs ON (retry ke baad).

Ek hi run se dono numbers milte hain (same research data par):
  before = pehle draft me unsupported/uncited claims ka %    (loop ke bina)
  after  = final report me wahi %                            (loop ke baad)

Chalana:   python -m evals.mini_eval --limit 10
Demo mode: python -m evals.mini_eval --demo      (fake LLM: sirf harness check karne ke liye, numbers asli NAHI)
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import pipeline  # noqa: E402


def run_eval(queries, client_factory=None, **kw):
    rows = []
    for q in queries:
        client = client_factory() if client_factory else None
        res = pipeline.run_research(q, client=client, save=False, **kw)
        if not res.ok:
            rows.append({"query": q, "ok": False, "error": res.error})
            continue
        rows.append({"query": q, "ok": True, "claims": res.verify_final.get("claims", 0),
                     "before": res.verify_first.get("unsupported_rate", 0.0),
                     "after": res.verify_final.get("unsupported_rate", 0.0),
                     "retries": res.retries, "confidence": res.confidence_label,
                     "conflicts": len(res.conflicts), "cost": res.cost_usd, "time": res.elapsed})
    return rows


def summarize(rows):
    ok = [r for r in rows if r["ok"]]
    if not ok:
        return {"n": len(rows), "ok": 0}
    avg = lambda k: round(statistics.mean(r[k] for r in ok), 4)
    return {"n": len(rows), "ok": len(ok), "before": avg("before"), "after": avg("after"),
            "avg_retries": avg("retries"), "avg_cost": avg("cost"), "avg_time": avg("time"),
            "with_conflicts": sum(1 for r in ok if r["conflicts"])}


def to_markdown(rows, s, demo=False):
    out = ["# Eval results: Verifier loop OFF vs ON", ""]
    if demo:
        out += ["> ⚠️ DEMO (fake LLM): ye numbers asli nahi hain, sirf harness check hai.", ""]
    if s["ok"]:
        out += [f"- Queries: {s['ok']}/{s['n']} successful",
                f"- Unsupported/uncited claims: **{s['before']:.1%} → {s['after']:.1%}**  (loop OFF → ON)",
                f"- Avg retries: {s['avg_retries']} | Avg cost: ${s['avg_cost']} | Avg time: {s['avg_time']}s",
                f"- Queries with conflicts detected: {s['with_conflicts']}", ""]
    out += ["| Query | Claims | Before | After | Retries | Confidence | Cost |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["ok"]:
            out.append(f"| {r['query'][:50]} | {r['claims']} | {r['before']:.0%} | {r['after']:.0%} | "
                       f"{r['retries']} | {r['confidence']} | ${r['cost']:.4f} |")
        else:
            out.append(f"| {r['query'][:50]} | FAILED: {r['error'][:60]} | | | | | |")
    return "\n".join(out) + "\n"


def _demo_setup():
    import os, tempfile
    os.environ["DB_PATH"] = str(Path(tempfile.mkdtemp()) / "demo.db")
    sys.path.insert(0, str(ROOT / "tests"))
    import requests
    from fakes import CLEAN_REPORT, FakeLLMClient

    class R:
        status_code = 200
        text = "<html><body><p>" + "India EV market is growing quickly. " * 10 + "</p></body></html>"
        def raise_for_status(self): pass
    requests.get = lambda *a, **k: R()
    bad = CLEAN_REPORT.replace("## Limitations", "- HALLUCINATED sales hit 9 million [1].\n\n## Limitations")
    return lambda: FakeLLMClient(sub_questions=["Q one", "Q two"], report_text=bad, fixed_report=CLEAN_REPORT)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    queries = json.loads((ROOT / "evals" / "queries_mini.json").read_text(encoding="utf-8"))[: a.limit]
    factory = _demo_setup() if a.demo else None
    rows = run_eval(queries, factory)
    summary = summarize(rows)
    md = to_markdown(rows, summary, demo=a.demo)
    (ROOT / "evals" / ("mini_results_demo.md" if a.demo else "mini_results.md")).write_text(md, encoding="utf-8")
    print(md)
