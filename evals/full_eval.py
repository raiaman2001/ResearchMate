"""Full evaluation pipeline: 40 queries (en / hinglish / hi), LLM-as-judge, paired ablations.

Arms:
  main    : sab queries, standard mode, memory OFF, verifier ON            (baseline + verifier-loop ablation)
  debate  : debatable queries, debate mode                                 (debate ON vs OFF, paired with main)
  memory  : follow-up queries, memory ON (isolated store, seed run ke baad)  (memory ON vs OFF, paired with main)

Chalana:
  python -m evals.full_eval --out evals/results/run1 --dry-run         # plan + rough cost
  python -m evals.full_eval --out evals/results/pilot --limit 3         # chhota pilot (asli avg cost dekho)
  python -m evals.full_eval --out evals/results/run1 --max-cost 25      # poora eval
  python -m evals.full_eval --out evals/results/run1 --resume           # beech me ruka ho to
  python -m evals.full_eval --out evals/results/run1 --report-only      # sirf report dobara banao
  python -m evals.full_eval --out /tmp/demo --demo                      # fake LLM: sirf harness check (numbers asli NAHI)
"""
import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import config  # noqa: E402
from app.agents.verifier import split_claims  # noqa: E402
from app.graph import Orchestrator  # noqa: E402
from app.llm import LLM, Tracker  # noqa: E402
from app.memory.kg import KnowledgeGraph  # noqa: E402
from app.memory.manager import MemoryManager  # noqa: E402
from app.memory.vector import VectorStore  # noqa: E402
from evals import judge as J  # noqa: E402
from evals.stats import mean, mean_ci, paired  # noqa: E402

ALL_ARMS = ("main", "debate", "memory")
QUERIES_PATH = ROOT / "evals" / "queries.json"


class EvalError(Exception):
    pass


@dataclass
class EvalConfig:
    out_dir: Path
    arms: tuple = ALL_ARMS
    limit: int | None = None
    resume: bool = False
    max_cost: float | None = None
    concurrency: int = 1
    judge_model: str | None = None
    client_factory: object = None            # generation LLM (None = asli Anthropic)
    judge_client_factory: object = None
    queries_path: Path = QUERIES_PATH
    progress: object = print


# ============================ suite / planning ============================
def load_suite(path=None):
    return json.loads(Path(path or QUERIES_PATH).read_text(encoding="utf-8"))


def select(suite, arms, limit=None):
    main = suite[:limit] if limit else list(suite)
    plan = {"main": main if "main" in arms else [],
            "debate": [q for q in main if q["debatable"]] if "debate" in arms else [], "memory": []}
    if "memory" in arms:
        for q in main:
            if q["role"] == "followup":
                seed = next((s for s in suite if s["group"] == q["group"] and s["role"] == "seed"), None)
                if seed:
                    plan["memory"].append((seed, q))
    return plan


def plan_summary(plan):
    n_mem = len(plan["memory"]) * 2
    total = len(plan["main"]) + len(plan["debate"]) + n_mem
    return {"main": len(plan["main"]), "debate": len(plan["debate"]), "memory_pairs": len(plan["memory"]),
            "memory_runs": n_mem, "total_runs": total}


def rough_cost(total_runs, model=None):
    """MOTA anuman (assumptions niche): ek run ~ 60k input + 8k output tokens (planner+researchers+writer+verifier),
    judge ~ 40k input + 3k output. Asli number ke liye pehle --limit 3 pilot chalao."""
    p_in, p_out = config.price_for(model or config.MODEL)
    per_run = (60_000 * p_in + 8_000 * p_out) / 1e6 + (40_000 * p_in + 3_000 * p_out) / 1e6
    return round(per_run * total_runs, 2), round(per_run, 3)


# ============================ records ============================
def load_records(path):
    out = {}
    if Path(path).exists():
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                out[r["key"]] = r
    return out


def append_record(path, rec):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ============================ one run + judge ============================
async def judge_run(cfg, res, q):
    tracker = Tracker()
    llm = LLM(tracker, cfg.judge_client_factory() if cfg.judge_client_factory else None)
    model = cfg.judge_model or config.JUDGE_MODEL
    faith_final, details, uncited = await J.judge_claims(llm, res.body, res.source_texts, model)
    if res.retries and res.first_body and res.first_body != res.body:
        faith_first, _, _ = await J.judge_claims(llm, res.first_body, res.source_texts, model)
    else:
        faith_first = faith_final                                    # retry nahi hua: pehla draft hi final hai
    quality = await J.judge_quality(llm, q["query"], res.body, q["aspects"], q["lang"], q["debatable"], model) or {}
    control = [{"claim": d["sentence"], "text": res.source_texts[d["ids"][0]][1]}
               for d in details if d["verdict"] == "supported" and d["ids"][0] in res.source_texts][:3]
    return {"faith_final": faith_final, "faith_first": faith_first, "uncited_final": uncited,
            "coverage": quality.get("coverage"), "clarity": quality.get("clarity"), "balance": quality.get("balance"),
            "judge_ok": bool(quality), "judge_cost": tracker.cost_usd, "_control": control}


async def run_one(cfg, orch, q, arm, mode, use_memory, key):
    rec = {"key": key, "qid": q["id"], "arm": arm, "lang": q["lang"], "query": q["query"], "debatable": q["debatable"]}
    try:
        st = await orch.start(q["query"], auto_approve=True, save=True, mode=mode, use_memory=use_memory,
                              verify=True, detect_conflicts=True, language="auto")
    except Exception as e:                                           # orchestrator khud nahi gira; safety net
        return {**rec, "ok": False, "error": f"{type(e).__name__}: {e}", "cost": 0.0, "judge_cost": 0.0}
    res = st.result
    if res is None or not res.ok:
        return {**rec, "ok": False, "error": st.error or "unknown", "cost": getattr(res, "cost_usd", 0.0),
                "judge_cost": 0.0, "elapsed": getattr(res, "elapsed", None)}
    rec.update(ok=True, cost=res.cost_usd, tokens=res.input_tokens + res.output_tokens, elapsed=res.elapsed,
               retries=res.retries, confidence=res.confidence_label, claims=res.verify_final.get("claims", 0),
               pipeline_first_unsup=res.verify_first.get("unsupported_rate"),
               pipeline_final_unsup=res.verify_final.get("unsupported_rate"), memory_reused=res.memory_reused,
               conflicts=len(res.conflicts), debate_stats=res.debate_stats, language_detected=res.language,
               language_ok=J.language_ok(res.body, q["lang"]))
    try:
        rec.update(await judge_run(cfg, res, q))
    except Exception as e:                                           # judge fail ho to run ka baaki data bachao
        rec.update(judge_ok=False, judge_error=f"{type(e).__name__}: {str(e)[:150]}", judge_cost=0.0)
    return rec


FATAL = ("API key galat", "ANTHROPIC_API_KEY")


# ============================ orchestration ============================
MAX_CONSECUTIVE_FAILS = 5


async def judge_preflight(cfg):
    """Shuru me ek chhoti judge call: model naam/key galat ho to saare mehnge runs generate karne se pehle ruk jao."""
    llm = LLM(Tracker(), cfg.judge_client_factory() if cfg.judge_client_factory else None)
    model = cfg.judge_model or config.JUDGE_MODEL
    try:
        verdict, _ = await J._judge_one(llm, "The sky is blue.", J.guard.wrap_source("preflight://x", "On clear days the sky is blue."), model)
    except Exception as e:
        raise EvalError(f"Judge preflight fail (model `{model}`): {type(e).__name__}: {str(e)[:120]}. "
                        "JUDGE_MODEL / --judge-model / API key check karo; abhi tak koi run generate nahi hua.") from e
    if verdict is None:
        raise EvalError(f"Judge preflight fail: model `{model}` ne valid structured output nahi diya. Koi run generate nahi hua.")


async def run_eval(cfg: EvalConfig):
    out = Path(cfg.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    runs_path = out / "runs.jsonl"
    if runs_path.exists() and not cfg.resume:
        raise EvalError(f"{runs_path} pehle se hai. --resume lagao (beech se aage badhao) ya naya --out chuno: "
                        "purana mehnga data overwrite nahi karte.")
    saved = load_records(runs_path)
    suite = load_suite(cfg.queries_path)
    plan = select(suite, cfg.arms, cfg.limit)
    await judge_preflight(cfg)

    old_db, old_ttl = config.DB_PATH, config.CACHE_TTL_HOURS
    config.DB_PATH = out / "eval.db"          # eval ka alag DB: app history/memory ko gandA nahi karta
    config.CACHE_TTL_HOURS = 0                # page cache band: har arm ko barabar fetch/latency milti hai
    spent = {"usd": sum(r.get("cost", 0) + r.get("judge_cost", 0) for r in saved.values() if r["key"] != "controls")}
    stopped, fatal, sem = [], [], asyncio.Semaphore(max(1, cfg.concurrency))
    streak = {"fails": 0}
    t0 = time.time()
    try:
        orch_main = Orchestrator(client_factory=cfg.client_factory)

        async def do(key, q, arm, orch, mode, use_memory):
            if key in saved or fatal:
                return
            if cfg.max_cost is not None and spent["usd"] >= cfg.max_cost:
                stopped.append(key)
                return
            async with sem:
                # semaphore ke intezaar me kaafi der lag sakti hai: budget/fatal dobara check (warna queue ke saare runs chal jate)
                if fatal:
                    return
                if cfg.max_cost is not None and spent["usd"] >= cfg.max_cost:
                    stopped.append(key)
                    return
                rec = await run_one(cfg, orch, q, arm, mode, use_memory, key)
            spent["usd"] += rec.get("cost", 0) + rec.get("judge_cost", 0)
            saved[key] = rec
            append_record(runs_path, rec)
            status = "ok" if rec["ok"] else f"FAIL: {rec['error'][:60]}"
            cfg.progress(f"[{len(saved)}] {key:<18} {status}  (spent ${spent['usd']:.2f})")
            streak["fails"] = 0 if rec["ok"] else streak["fails"] + 1
            if not rec["ok"] and any(f in rec["error"] for f in FATAL):
                fatal.append(rec["error"])
            elif streak["fails"] >= MAX_CONSECUTIVE_FAILS and not fatal:
                fatal.append(f"{MAX_CONSECUTIVE_FAILS} runs lagataar fail hue (last: {rec['error'][:80]})")

        async def pair(seed, q):
            pdir = out / "memory" / q["group"]
            mm = MemoryManager(VectorStore("memory", path=pdir / "chroma"), KnowledgeGraph(pdir / "kg.json"))
            orch = Orchestrator(client_factory=cfg.client_factory, memory=mm)
            await do(f"memory-seed:{seed['id']}", seed, "memory-seed", orch, "standard", True)
            await do(f"memory:{q['id']}", q, "memory", orch, "standard", True)

        tasks = [do(f"main:{q['id']}", q, "main", orch_main, "standard", False) for q in plan["main"]]
        tasks += [do(f"debate:{q['id']}", q, "debate", orch_main, "debate", False) for q in plan["debate"]]
        tasks += [pair(s, q) for s, q in plan["memory"]]
        await asyncio.gather(*tasks)

        if "controls" not in saved and not fatal:                                # judge sanity checks
            items = [it for r in saved.values() for it in r.get("_control", [])]
            if items:
                llm = LLM(Tracker(), cfg.judge_client_factory() if cfg.judge_client_factory else None)
                ctrl = {"key": "controls", **await J.judge_controls(llm, items, n=15, model=cfg.judge_model),
                        "cost": llm.tracker.cost_usd, "judge_cost": 0.0}
                saved["controls"] = ctrl
                append_record(runs_path, ctrl)
    finally:
        config.DB_PATH, config.CACHE_TTL_HOURS = old_db, old_ttl

    meta = {"arms": list(cfg.arms), "limit": cfg.limit, "stopped_early": stopped, "spent_usd": round(spent["usd"], 4),
            "wall_seconds": round(time.time() - t0, 1), "generation_model": config.MODEL,
            "judge_model": cfg.judge_model or config.JUDGE_MODEL, "plan": plan_summary(plan)}
    summary = summarize(list(saved.values()))
    summary["meta"] = meta
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "results.md").write_text(to_markdown(summary), encoding="utf-8")
    if fatal:
        raise EvalError(f"Eval beech me ruka (fatal): {fatal[0]}. Jo ho chuka hai wo {runs_path} me hai; --resume se aage badhao.")
    return summary


# ============================ summary ============================
METRICS = {
    "supported_rate": lambda r: (r.get("faith_final") or {}).get("supported_rate"),
    "unsupported_rate": lambda r: (r.get("faith_final") or {}).get("unsupported_rate"),
    "coverage": lambda r: r.get("coverage"),
    "clarity": lambda r: r.get("clarity"),
    "balance": lambda r: r.get("balance"),
    "language_ok": lambda r: None if r.get("language_ok") is None else float(r["language_ok"]),
    "cost": lambda r: r.get("cost"),
    "elapsed": lambda r: r.get("elapsed"),
    "retries": lambda r: r.get("retries"),
}


def _col(recs, metric):
    return [METRICS[metric](r) for r in recs]


def _pooled(recs, which="faith_final"):
    s = {"n": 0, "supported": 0, "partial": 0, "unsupported": 0}
    for r in recs:
        f = r.get(which) or {}
        for k in s:
            s[k] += f.get(k, 0)
    n = s["n"]
    return {**s, "supported_rate": s["supported"] / n if n else None, "unsupported_rate": s["unsupported"] / n if n else None}


def _pair_rows(base, other, spec):
    """base/other: {qid: rec}. spec: [(metric, higher_is_better)]."""
    qids = sorted(set(base) & set(other))
    rows = []
    for metric, hib in spec:
        rows.append({"metric": metric, **paired([METRICS[metric](base[q]) for q in qids],
                                                [METRICS[metric](other[q]) for q in qids], higher_is_better=hib)})
    return rows


def summarize(records):
    controls = next((r for r in records if r["key"] == "controls"), None)
    runs = [r for r in records if r["key"] != "controls"]
    by_arm = lambda arm, ok_only=True: {r["qid"]: r for r in runs if r["arm"] == arm and (r["ok"] or not ok_only)}
    main_all, main = by_arm("main", False), by_arm("main")
    s = {"counts": {a: {"total": sum(1 for r in runs if r["arm"] == a), "ok": sum(1 for r in runs if r["arm"] == a and r["ok"])}
                    for a in ("main", "debate", "memory-seed", "memory")}}
    ok_main = list(main.values())
    s["overall"] = {m: mean_ci(_col(ok_main, m)) for m in METRICS}
    s["overall"]["pooled_faith"] = _pooled(ok_main)
    s["overall"]["confidence"] = {c: sum(1 for r in ok_main if r.get("confidence") == c) for c in ("High", "Medium", "Low")}
    s["overall"]["failure_rate"] = (1 - len(ok_main) / len(main_all)) if main_all else None
    s["by_language"] = {}
    for lang in ("en", "hinglish", "hi"):
        allr = [r for r in main_all.values() if r["lang"] == lang]
        okr = [r for r in allr if r["ok"]]
        s["by_language"][lang] = {"n": len(allr), "ok": len(okr), "pooled_faith": _pooled(okr),
                                  **{m: mean(_col(okr, m)) for m in ("coverage", "clarity", "language_ok", "cost", "elapsed")}}
    # --- ablation 1: verifier loop (pehla draft vs final), independent judge se, same research data par ---
    pairs = [r for r in ok_main if (r.get("faith_first") or {}).get("n") and (r.get("faith_final") or {}).get("n")]
    s["ablation_verifier"] = {
        "judge": paired([r["faith_first"]["unsupported_rate"] for r in pairs], [r["faith_final"]["unsupported_rate"] for r in pairs],
                        higher_is_better=False),
        "pipeline_self": paired([r.get("pipeline_first_unsup") for r in ok_main], [r.get("pipeline_final_unsup") for r in ok_main],
                                higher_is_better=False),
        "runs_with_retry": sum(1 for r in ok_main if r.get("retries"))}
    # --- ablation 2: debate vs standard ---
    deb = by_arm("debate")
    s["ablation_debate"] = _pair_rows(main, deb, [("balance", True), ("coverage", True), ("clarity", True),
                                                  ("supported_rate", True), ("unsupported_rate", False), ("cost", None), ("elapsed", None)])
    # --- ablation 3: memory ON vs OFF (follow-up queries) ---
    mem = by_arm("memory")
    s["ablation_memory"] = _pair_rows(main, mem, [("coverage", True), ("clarity", True), ("supported_rate", True),
                                                  ("unsupported_rate", False), ("cost", None), ("elapsed", None)])
    s["memory_reuse"] = {"followups": len(mem), "with_reuse": sum(1 for r in mem.values() if r.get("memory_reused")),
                         "avg_reused": mean([r.get("memory_reused") for r in mem.values()])}
    s["controls"] = controls
    s["failures"] = [{"key": r["key"], "error": r.get("error")} for r in runs if not r["ok"]]
    s["judge_failures"] = sum(1 for r in runs if r["ok"] and not r.get("judge_ok", True))
    return s


# ============================ markdown ============================
def _pct(x, d=1):
    return "–" if x is None else f"{x * 100:.{d}f}%"


def _num(x, d=2):
    return "–" if x is None else f"{x:.{d}f}"


def _ci(m, pct=False):
    if not m or m.get("mean") is None:
        return "–"
    f = _pct if pct else _num
    return f"{f(m['mean'])} [{f(m['lo'])}, {f(m['hi'])}] (n={m['n']})"


def _paired_table(rows, pct_metrics=("supported_rate", "unsupported_rate", "coverage", "language_ok")):
    out = ["| Metric | Baseline (OFF) | Variant (ON) | Δ (ON − OFF) | 95% CI | Verdict |", "|---|---|---|---|---|---|"]
    for r in rows:
        f = _pct if r["metric"] in pct_metrics else _num
        out.append(f"| {r['metric']} | {f(r['mean_a'])} | {f(r['mean_b'])} | {f(r['diff']) if r['diff'] is not None else '–'} | "
                   f"{'[' + f(r['lo']) + ', ' + f(r['hi']) + ']' if r['lo'] is not None else '–'} | {r['verdict']} (n={r['n']}) |")
    return out


def to_markdown(s, demo=False):
    meta = s.get("meta", {})
    o, L = s["overall"], []
    L += ["# ResearchMate: full evaluation", ""]
    if demo:
        L += ["> ⚠️ **DEMO**: fake LLM par chala. Ye numbers asli nahi hain, sirf pipeline/harness check hai.", ""]
    L += [f"- Generation model: `{meta.get('generation_model', '–')}` | Judge model: `{meta.get('judge_model', '–')}`",
          f"- Runs: main {s['counts']['main']['ok']}/{s['counts']['main']['total']} ok, debate {s['counts']['debate']['ok']}/{s['counts']['debate']['total']}, "
          f"memory follow-ups {s['counts']['memory']['ok']}/{s['counts']['memory']['total']}",
          f"- Spent: ${meta.get('spent_usd', '–')} | wall time: {meta.get('wall_seconds', '–')}s | page cache: OFF (fair latency)"]
    if s.get("judge_failures"):
        L += [f"- ⚠️ **Judge {s['judge_failures']} runs me fail hua**: unka faithfulness/quality data missing hai (neeche numbers adhoore hain)."]
    if meta.get("stopped_early"):
        L += [f"- ⚠️ Budget cap par ruka: {len(meta['stopped_early'])} runs baaki (`--resume` se poore karo)"]
    pf = o["pooled_faith"]
    L += ["", "## 1. Overall (main arm: standard, memory OFF, verifier ON)", "",
          "| Metric | Value |", "|---|---|",
          f"| Claims judged (independent judge) | {pf['n']} |",
          f"| Supported (pooled over claims) | {_pct(pf['supported_rate'])} |",
          f"| Unsupported (pooled) | {_pct(pf['unsupported_rate'])} |",
          f"| Supported rate per report (mean [95% CI]) | {_ci(o['supported_rate'], True)} |",
          f"| Coverage of expected aspects | {_ci(o['coverage'], True)} |",
          f"| Clarity (1-5) | {_ci(o['clarity'])} |",
          f"| Report in expected language | {_ci(o['language_ok'], True)} |",
          f"| Cost per run (USD, generation only) | {_ci(o['cost'])} |",
          f"| Latency per run (s) | {_ci(o['elapsed'])} |",
          f"| Verifier retries per run | {_ci(o['retries'])} |",
          f"| Failure rate | {_pct(o['failure_rate'])} |",
          f"| Pipeline confidence label (High / Medium / Low) | {o['confidence']['High']} / {o['confidence']['Medium']} / {o['confidence']['Low']} |"]

    L += ["", "## 2. By query language", "", "| Language | Runs ok | Supported (pooled) | Coverage | Report in expected language | Cost/run | Latency |", "|---|---|---|---|---|---|---|"]
    for lang, b in s["by_language"].items():
        L.append(f"| {lang} | {b['ok']}/{b['n']} | {_pct(b['pooled_faith']['supported_rate'])} | {_pct(b['coverage'])} | "
                 f"{_pct(b['language_ok'])} | {_num(b['cost'], 3)} | {_num(b['elapsed'], 1)}s |")

    av = s["ablation_verifier"]
    L += ["", "## 3. Ablation: verifier + retry loop (OFF = pehla draft, ON = final; same research data)", "",
          f"Retry {av['runs_with_retry']} runs me chala.", "",
          "| Measured by | Unsupported rate OFF | ON | Δ | 95% CI | Verdict |", "|---|---|---|---|---|---|"]
    for name, k in (("Independent judge", "judge"), ("Pipeline's own verifier", "pipeline_self")):
        r = av[k]
        L.append(f"| {name} | {_pct(r['mean_a'])} | {_pct(r['mean_b'])} | {_pct(r['diff'])} | "
                 f"{'[' + _pct(r['lo']) + ', ' + _pct(r['hi']) + ']' if r['lo'] is not None else '–'} | {r['verdict']} (n={r['n']}) |")

    L += ["", "## 4. Ablation: debate mode (debatable queries; paired with standard mode)", ""] + _paired_table(s["ablation_debate"])
    mr = s["memory_reuse"]
    L += ["", "## 5. Ablation: memory ON vs OFF (follow-up queries; paired with main arm)", "",
          f"Follow-ups: {mr['followups']}; memory se reuse hua: {mr['with_reuse']} me (avg {_num(mr['avg_reused'])} findings).", ""] + _paired_table(s["ablation_memory"])

    c = s.get("controls")
    L += ["", "## 6. Judge sanity check (negative controls)", ""]
    if c and c.get("n"):
        L += [f"Judge ko jaan-boojh ke **galat source** ke saath claim diya: {c['rejected']}/{c['n']} sahi se reject hue ({_pct(c['rate'])}). "
              "Ye rate kam ho to faithfulness numbers par bharosa mat karo."]
    else:
        L += ["Controls nahi chale (koi supported claim nahi mila)."]

    L += ["", "## 7. Failures", ""]
    L += [f"- `{f['key']}`: {f['error']}" for f in s["failures"]] or ["- (koi nahi)"]
    if s["judge_failures"]:
        L += [f"- Judge fail hua {s['judge_failures']} runs me (unka quality/faithfulness data missing hai)."]
    L += ["", "## How to read / caveats", "",
          "- Faithfulness **independent judge** se naapa gaya (pipeline ke verifier se alag prompt aur, behtar hai, alag model). Judge LLM hai: galti kar sakta hai; section 6 usi ka check hai.",
          "- Judge generator ka hi model ho to **self-preference bias** ho sakta hai: `JUDGE_MODEL` alag rakho.",
          "- Ablations **paired** hain (same query dono arms me). 95% CI bootstrap se; CI 0 ko cover kare to 'no clear difference'. n chhota hai (debate ~12, memory 6): wide CI normal hai.",
          "- Coverage = judge ke hisaab se expected aspects ka hissa (aspects humne khud likhe, `evals/queries.json`).",
          "- Web aur search results badalte rehte hain: arms alag samay par chalne se thoda noise aata hai. Ek hi run = ek sample.",
          "- Cost me sirf generation pipeline hai (judge ka kharcha `Spent` me alag se jodta hai)."]
    return "\n".join(L) + "\n"


# ============================ CLI ============================
def _demo_setup(cfg):
    import os
    sys.path.insert(0, str(ROOT / "tests"))
    import requests
    from fakes import CLEAN_REPORT, FakeLLMClient

    import hashlib
    words = "zebra giraffe lattice quantum orchid harbor violin glacier pepper anchor meadow falcon cobalt tundra marble saffron".split()

    class R:
        status_code = 200

        def __init__(self, url):
            h = int(hashlib.md5(url.encode()).hexdigest(), 16)
            extra = " ".join(words[(h >> (3 * i)) % len(words)] for i in range(14))
            self.text = "<html><body><p>India EV market is growing quickly. " + extra + "</p></body></html>"   # har URL ka alag text

        def raise_for_status(self):
            pass
    requests.get = lambda url, **k: R(url)
    bad = CLEAN_REPORT.replace("## Limitations", "- HALLUCINATED sales will hit 9 million by 2035 [1].\n\n## Limitations")
    cfg.judge_client_factory = cfg.client_factory = lambda: FakeLLMClient(topic_questions=True, pro_questions=["P"], con_questions=["C"],
                                               report_text=bad, fixed_report=CLEAN_REPORT, claim_prefix="India EV market data on")
    os.environ.setdefault("ANTHROPIC_API_KEY", "demo")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--arms", default=",".join(ALL_ARMS))
    ap.add_argument("--limit", type=int)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--max-cost", type=float, help="USD: generation+judge ka total, isse upar naye runs nahi")
    ap.add_argument("--concurrency", type=int, default=1)
    ap.add_argument("--judge-model")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args(argv)

    arms = tuple(x.strip() for x in a.arms.split(",") if x.strip())
    if bad := [x for x in arms if x not in ALL_ARMS]:
        ap.error(f"unknown arm: {bad} (choose from {ALL_ARMS})")
    out = Path(a.out)
    if a.report_only:
        summary = summarize(list(load_records(out / "runs.jsonl").values()))
        meta_path = out / "summary.json"
        summary["meta"] = json.loads(meta_path.read_text(encoding="utf-8")).get("meta", {}) if meta_path.exists() else {}
        (out / "results.md").write_text(to_markdown(summary), encoding="utf-8")
        print((out / "results.md").read_text(encoding="utf-8"))
        return 0
    cfg = EvalConfig(out_dir=out, arms=arms, limit=a.limit, resume=a.resume, max_cost=a.max_cost,
                     concurrency=a.concurrency, judge_model=a.judge_model)
    plan = select(load_suite(cfg.queries_path), arms, a.limit)
    ps = plan_summary(plan)
    if a.dry_run:
        total, per = rough_cost(ps["total_runs"], a.judge_model)
        print(f"Plan: {ps}\nRough cost: ~${total} (~${per}/run). ASSUMPTIONS: ek run ~60k in/8k out tokens + judge ~40k in/3k out, "
              f"prices from config (PRICE_IN_PER_M/PRICE_OUT_PER_M). Pehle `--limit 3` pilot chalao aur asli avg cost dekho.")
        return 0
    if a.demo:
        _demo_setup(cfg)
    try:
        summary = asyncio.run(run_eval(cfg))
    except EvalError as e:
        print("ERROR:", e)
        return 1
    md = (out / "results.md").read_text(encoding="utf-8")
    if a.demo:
        md = md.replace("# ResearchMate: full evaluation", "# ResearchMate: full evaluation\n\n> ⚠️ **DEMO**: fake LLM. Numbers asli nahi.", 1)
        (out / "results.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
