"""LangGraph workflow + Orchestrator.

recall(memory) -> plan -> approval(HUMAN, interrupt) -> research(parallel) -> analyze(score+conflicts)
   -> write/judge -> verify <-> rewrite (loop) -> finalize(confidence, save, memory)

Heavy objects (LLM client, session, tracker) graph state me nahi, RunContext me rehte hain (state sirf plain data).
"""
import asyncio
import os
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app import config, confidence, scoring, storage
from app.events_i18n import ev_text
from app.agents.conflicts import detect_conflicts as run_conflict_detector
from app.agents.debate import debate_stats, judge_report, plan_debate
from app.agents.extractor import extract_triples
from app.agents.planner import plan_query
from app.agents.researcher import research_question
from app.agents.verifier import annotate, verify_report
from app.agents.writer import write_report
from app.i18n import t
from app.lang import resolve_language
from app.llm import LLM, Tracker
from app.report import compose
from app.result import RunFailed, RunResult, friendly_error
from app.tools import ResearchSession

DEFAULT_OPTIONS = dict(mode="standard", verify=True, detect_conflicts=True, use_memory=False, use_docs=False,
                       max_retries=None, parallel=True, auto_approve=False, save=True, language=None)
MAX_CONTEXTS = 50


class RState(TypedDict, total=False):
    topic: str
    mode: str
    options: dict
    memory_hits: list
    kg_context: list
    plan: list
    debate_plan: dict
    approved: bool
    notes: list
    failed: list
    warnings: list
    flat: list
    cited: list
    scores: list
    conflicts: list
    gaps: list
    dropped_total: int
    memory_reused: int
    body: str
    first_body: str
    retries: int
    checks: list
    first: dict


@dataclass
class RunStatus:
    thread_id: str
    status: str                     # awaiting_approval | done | error | cancelled
    pending: dict | None = None
    result: RunResult | None = None
    error: str | None = None


class RunContext:
    def __init__(self, thread_id, topic, options, client_factory, memory, docs, on_event=None):
        self.thread_id, self.topic, self.options = thread_id, topic, options
        self.client_factory, self.memory, self.on_event = client_factory, memory, on_event
        docs_on = bool(options["use_docs"] and docs is not None and docs.has_docs())
        self.session = ResearchSession(docs=docs if docs_on else None)
        self.tracker, self.events, self.verify_cache = Tracker(), [], {}
        self.active, self._t = 0.0, time.perf_counter()
        self.llm = None
        self.status, self.result = "running", None

    def bind(self):
        """Har invocation (start/resume) me naya LLM client: asyncio loops alag ho sakte hain (Streamlit)."""
        self.llm = LLM(self.tracker, self.client_factory() if self.client_factory else None)
        self._t = time.perf_counter()

    def now(self):
        return self.active + (time.perf_counter() - self._t)

    def emit(self, msg, kind="log", **data):
        stage = data.get("stage")
        if not stage:
            if kind in ("plan", "approved", "cancelled"):
                stage = "planner"
            elif kind in ("researcher", "tool", "tool_result", "reject"):
                stage = "researchers"
            elif kind in ("scores", "conflict"):
                stage = "analyzer"
            elif kind in ("writer", "draft"):
                stage = "writer"
            elif kind in ("verify", "claim_check"):
                stage = "verifier"
            else:
                stage = "pipeline"

        agent = data.get("agent")
        if not agent:
            if "researcher" in data:
                agent = f"researcher-{data['researcher']}"
            elif kind in ("plan", "approved"):
                agent = "planner"
            elif kind == "conflict":
                agent = "contradiction-detector"
            elif kind in ("scores", "memory", "memory_reuse"):
                agent = "analyzer"
            elif kind == "writer":
                agent = "writer"
            elif kind in ("verify", "claim_check"):
                agent = "verifier"
            else:
                agent = "system"

        status = data.get("status")
        if not status:
            if kind in ("error", "reject"):
                status = "failed"
            elif kind in ("approved", "scores"):
                status = "done"
            else:
                status = "running"

        ev = {
            "t": round(self.now(), 2),
            "timestamp": round(self.now(), 2),
            "kind": kind,
            "msg": msg,
            "message": msg,
            "stage": stage,
            "agent": agent,
            "status": status,
            "tokens": self.tracker.input_tokens + self.tracker.output_tokens,
            "cost": self.tracker.cost_usd,
            **data
        }
        self.events.append(ev)
        if self.on_event:
            self.on_event(ev)          # exception swallow nahi karte: Streamlit ka stop signal yahin se guzarta hai


# ====================== helpers ======================
def _norm(s):
    return " ".join(s.lower().split())


def _plan_labels(state):
    if state["mode"] == "debate":
        dp = state.get("debate_plan") or {}
        return [f"[PRO] {q}" for q in dp.get("pro", [])] + [f"[CON] {q}" for q in dp.get("con", [])]
    return list(state.get("plan") or [])


def _numbered(flat, scores_by_url):
    out = []
    for f in flat:
        tag = f" [{f['stance'].upper()}]" if f.get("stance") else ""
        mem = f" (purani research, {f['saved_at'][:10]})" if f.get("origin") == "memory" else ""
        out.append(f"[{f['src']}]{tag} (credibility: {scores_by_url[f['url']]['label']}){mem} {f['claim']}")
    return out


def _writer_fn(state):
    return judge_report if state["mode"] == "debate" else write_report


def _node_name(state, retry=0):
    base = "judge" if state["mode"] == "debate" else "writer"
    return f"{base}-retry-{retry}" if retry else base


# ====================== nodes ======================
async def n_recall(state, ctx):
    hits, kg_ctx = [], []
    lang = ctx.options.get("language", "en")
    if ctx.options["use_memory"] and ctx.memory is not None:
        hits = ctx.memory.recall(state["topic"])
        kg_ctx = ctx.memory.kg_related(state["topic"])
        if hits:
            ctx.emit(ev_text(lang, "memory_hits", n=len(hits)), kind="memory",
                     hits=[{"claim": h["claim"], "age_days": h["age_days"], "sim": h["sim"]} for h in hits])
        else:
            ctx.emit(ev_text(lang, "memory_none"), kind="memory", hits=[])
        if kg_ctx:
            ctx.emit(ev_text(lang, "kg_hits", n=len(kg_ctx)), kind="memory", kg=kg_ctx)
    return {"memory_hits": hits, "kg_context": kg_ctx}


async def n_plan(state, ctx):
    lang = ctx.options.get("language", "en")
    known = [h["claim"] for h in state.get("memory_hits", [])]
    known += [f"{t['subject']} {t['relation']} {t['object']}" for t in state.get("kg_context", [])]
    if state["mode"] == "debate":
        dp = await plan_debate(ctx.llm, state["topic"], known, ctx.options["language"])
        ctx.emit(ev_text(lang, "debate_plan", pro=" | ".join(dp.pro), con=" | ".join(dp.con)), kind="plan")
        return {"debate_plan": {"pro": dp.pro, "con": dp.con}}
    plan = (await plan_query(ctx.llm, state["topic"], known, ctx.options["language"])).sub_questions
    ctx.emit(ev_text(lang, "plan", plan=" | ".join(plan)), kind="plan")
    return {"plan": plan}


def _clean(qs, fallback, cap):
    cleaned = [q.strip() for q in (qs or []) if q and q.strip()][:cap]
    return cleaned or fallback


def make_approval_node(orch):
    async def approval(state, config):
        ctx = orch.contexts[config["configurable"]["thread_id"]]
        lang = ctx.options.get("language", "en")
        if state["options"]["auto_approve"]:
            return {"approved": True}
        payload = {"type": "plan_approval", "mode": state["mode"], "plan": state.get("plan"),
                   "debate_plan": state.get("debate_plan"),
                   "memory": [h["claim"] for h in state.get("memory_hits", [])][:5]}
        decision = interrupt(payload)                  # <-- graph yahin ruk jata hai, user ke resume tak
        if not decision.get("approved", False):
            ctx.emit(ev_text(lang, "user_cancelled"), kind="cancelled")
            return {"approved": False}
        if state["mode"] == "debate":
            dp, new = state["debate_plan"], decision.get("debate_plan") or {}
            out = {"debate_plan": {"pro": _clean(new.get("pro"), dp["pro"], 3), "con": _clean(new.get("con"), dp["con"], 3)}}
        else:
            out = {"plan": _clean(decision.get("plan"), state["plan"], 6)}
        ctx.emit(ev_text(lang, "plan_approved"), kind="approved", **out)
        return {"approved": True, **out}
    return approval


def route_after_approval(state):
    return "research" if state.get("approved") else END


async def n_research(state, ctx):
    o = ctx.options
    if state["mode"] == "debate":
        dp = state["debate_plan"]
        tasks = [(q, "pro") for q in dp["pro"]] + [(q, "con") for q in dp["con"]]
    else:
        tasks = [(q, None) for q in state["plan"]]
    sem = asyncio.Semaphore(config.CONCURRENCY if o["parallel"] else 1)

    async def one(i, q, stance):
        async with sem:
            tag = f" [{stance.upper()}]" if stance else ""
            lang = ctx.options.get("language", "en")
            ctx.emit(ev_text(lang, "researcher_start", i=i, tag=tag, q=q), kind="researcher", researcher=i, stance=stance)
            return await research_question(ctx.llm, ctx.session, i, q, ctx.emit, stance, ctx.options["language"])

    results = await asyncio.gather(*[one(i, q, st) for i, (q, st) in enumerate(tasks, 1)], return_exceptions=True)

    import anthropic
    notes, failed, warnings = [], [], []
    lang = ctx.options.get("language", "en")
    for (q, st), r in zip(tasks, results):
        if isinstance(r, anthropic.AuthenticationError):
            raise r
        if isinstance(r, BaseException):
            failed.append(q)
            warnings.append(f"Research fail: {q} ({type(r).__name__})")
            ctx.emit(ev_text(lang, "researcher_fail", q=q), kind="warning")
        else:
            notes.append(r.model_dump())
            if r.dropped:
                warnings.append(f"{r.dropped} unverified finding hata di: {q}")
    return {"notes": notes, "failed": failed, "warnings": warnings}


async def n_analyze(state, ctx):
    o = ctx.options
    lang = o.get("language", "en")
    idx, cited, flat, gaps, dropped_total = {}, [], [], [], 0

    def add(url, claim, stance=None, origin=None, saved_at=None):
        if url not in idx:
            cited.append(url)
            idx[url] = len(cited)
        flat.append({"id": len(flat) + 1, "src": idx[url], "url": url, "claim": claim, "stance": stance,
                     "origin": origin, "saved_at": saved_at})

    for n in state["notes"]:
        dropped_total += n["dropped"]
        for f in n["findings"]:
            add(f["source_url"], f["claim"], n.get("stance"))
        if n["gaps"]:
            gaps.append(f"{n['sub_question']}: {n['gaps']}")

    # Memory se purani findings reuse (source text archive se wapas laakar, taaki verify ho sakein)
    reused, seen = 0, {_norm(f["claim"]) for f in flat}
    for h in state.get("memory_hits", [])[: config.MEMORY_MAX_REUSE]:
        arch = storage.archive_get(h["source_url"])
        if _norm(h["claim"]) in seen or not arch:
            continue
        ctx.session.restore_page(h["source_url"], arch[0], arch[1])
        add(h["source_url"], h["claim"], origin="memory", saved_at=h["saved_at"])
        seen.add(_norm(h["claim"]))
        reused += 1
        ctx.emit(ev_text(lang, "memory_reuse", days=h['age_days'], claim=h['claim'][:70]), kind="memory_reuse")

    if not flat:
        raise RunFailed("Koi verified finding nahi mili (pages padhe nahi gaye ya research fail hui).")

    by_url = defaultdict(list)
    for f in flat:
        by_url[f["url"]].append(f["claim"])
    scored = scoring.score_sources(cited, ctx.session.pages, ctx.session.meta, by_url)
    scores = [{**s.to_dict(), "id": idx[u]} for u, s in scored.items()]
    ctx.emit(ev_text(lang, "source_scores", scores=", ".join(f"[{s['id']}] {s['label']}" for s in scores)), kind="scores", scores=scores)

    conflicts = []
    if state["mode"] == "debate":
        ctx.emit(ev_text(lang, "debate_conflict_skip"), kind="log")
    elif o["detect_conflicts"]:
        conflicts = await run_conflict_detector(ctx.llm, flat)
        if conflicts:
            ctx.emit(ev_text(lang, "conflicts_found", n=len(conflicts)), kind="conflict", conflicts=conflicts)
    return {"flat": flat, "cited": cited, "scores": scores, "conflicts": conflicts, "gaps": gaps,
            "dropped_total": dropped_total, "memory_reused": reused}


async def n_write(state, ctx):
    lang = ctx.options.get("language", "en")
    label = "Judge" if state["mode"] == "debate" else "Writer"
    ctx.emit(ev_text(lang, "writer_writing", label=label), kind="log")
    sbu = {s["url"]: s for s in state["scores"]}
    body = await _writer_fn(state)(ctx.llm, state["topic"], _numbered(state["flat"], sbu), state["gaps"],
                                   state["failed"], state["conflicts"], node=_node_name(state),
                                   lang=ctx.options["language"])
    return {"body": body, "first_body": body, "retries": 0}


async def n_verify(state, ctx):
    if not ctx.options["verify"]:
        return {"checks": [], "first": {}}
    lang = ctx.options.get("language", "en")
    ctx.emit(ev_text(lang, "verifier_checking"), kind="log")
    sources = {s["id"]: (s["url"], ctx.session.pages.get(s["url"], "")) for s in state["scores"]}
    score_by_id = {s["id"]: s["score"] for s in state["scores"]}
    checks = await verify_report(ctx.llm, state["body"], sources, ctx.verify_cache)
    for c in checks:
        c["score"], c["confidence"] = confidence.claim_confidence(
            c["verdict"], [score_by_id[i] for i in c["ids"] if i in score_by_id], len(c["ids"]))
    first = state.get("first") or confidence.summarize_checks(checks)
    bad = sum(1 for c in checks if c["verdict"] in ("unsupported", "uncited"))
    ctx.emit(ev_text(lang, "verifier_result", total=len(checks), bad=bad), kind="verify", bad=bad, total=len(checks))
    return {"checks": checks, "first": first}


def route_after_verify(state):
    o = state["options"]
    bad = [c for c in state.get("checks", []) if c["verdict"] in ("unsupported", "uncited")]
    max_retries = config.MAX_RETRIES if o["max_retries"] is None else o["max_retries"]
    return "rewrite" if (o["verify"] and bad and state["retries"] < max_retries) else "finalize"


async def n_rewrite(state, ctx):
    retries = state["retries"] + 1
    lang = ctx.options.get("language", "en")
    bad = [c for c in state["checks"] if c["verdict"] in ("unsupported", "uncited")]
    max_retries = config.MAX_RETRIES if ctx.options["max_retries"] is None else ctx.options["max_retries"]
    ctx.emit(ev_text(lang, "verifier_retry", bad=len(bad), retry=retries, max_retries=max_retries), kind="retry")
    sbu = {s["url"]: s for s in state["scores"]}
    body = await _writer_fn(state)(ctx.llm, state["topic"], _numbered(state["flat"], sbu), state["gaps"],
                                   state["failed"], state["conflicts"], previous=state["body"], bad_claims=bad,
                                   node=_node_name(state, retries), lang=ctx.options["language"])
    return {"body": body, "retries": retries}


async def n_finalize(state, ctx):
    o, checks = ctx.options, state["checks"]
    flat, scores, conflicts = state["flat"], state["scores"], state["conflicts"]
    sbu = {s["url"]: s for s in scores}
    summary = confidence.summarize_checks(checks) if o["verify"] else {}
    annotated = annotate(state["body"], checks) if o["verify"] else state["body"]
    conf_score, conf_label = confidence.overall_confidence(checks, len(conflicts), len(state["failed"]))
    lang = o["language"]
    limitations = confidence.build_limitations(state["gaps"], state["failed"], conflicts, checks, scores,
                                               state["dropped_total"], lang)
    if state["memory_reused"]:
        limitations.append(t(lang, "lim_memory", n=state["memory_reused"]))
    warnings = list(state["warnings"])
    for u in ctx.session.flagged:
        warnings.append(f"Prompt-injection jaisa text mila (ignore kiya): {u}")

    new_flat = [f for f in flat if f.get("origin") != "memory"]
    store_memory = bool(o["use_memory"] and ctx.memory is not None and o["save"] and conf_label != "Low" and new_flat)
    triples = []
    if store_memory:
        try:
            triples = await extract_triples(ctx.llm, new_flat)
        except Exception as e:                           # KG optional hai: fail ho to run na ruke
            warnings.append(f"Knowledge-graph extraction fail: {type(e).__name__}")

    origin = {f["url"]: f["saved_at"] for f in flat if f.get("origin") == "memory"}
    dstats = debate_stats(flat, sbu) if state["mode"] == "debate" else {}
    other = [u for u in ctx.session.sources if u not in state["cited"]]
    plan = _plan_labels(state)
    markdown = compose(dict(topic=ctx.topic, body=annotated, plan=plan, cited=state["cited"], scores_by_url=sbu,
                            origin=origin, other_read=other, failed=state["failed"], conflicts=conflicts,
                            summary=summary, conf_label=conf_label, conf_score=conf_score, retries=state["retries"],
                            limitations=limitations, verified=o["verify"], mode=state["mode"], debate_stats=dstats,
                            language=lang))
    ctx.emit(ev_text(lang, "report_ready"), kind="log")
    res = RunResult(
        True, ctx.topic, markdown, plan, state["cited"], ctx.tracker.events, ctx.tracker.cost_usd,
        ctx.tracker.input_tokens, ctx.tracker.output_tokens, round(ctx.now(), 2), ctx.session.cache_hits,
        state["failed"], warnings, claim_checks=checks, source_scores=scores, conflicts=conflicts,
        confidence_label=conf_label, confidence_score=conf_score, retries=state["retries"],
        verify_first=state.get("first") or {}, verify_final=summary, limitations=limitations,
        mode=state["mode"], memory_reused=state["memory_reused"], debate_stats=dstats)
    res.events = ctx.events
    res.language, res.body, res.first_body = lang, state["body"], state.get("first_body", "")
    res.source_texts = {s["id"]: (s["url"], ctx.session.pages.get(s["url"], "")) for s in scores}

    if o["save"]:
        res.run_id, path = storage.save_report(ctx.topic, markdown, {
            "sources": state["cited"], "plan": plan, "cost_usd": res.cost_usd, "input_tokens": res.input_tokens,
            "output_tokens": res.output_tokens, "elapsed": res.elapsed, "trace": res.trace,
            "confidence": conf_label, "events": ctx.events, "mode": state["mode"],
            "verification": {"first": res.verify_first, "final": summary, "retries": res.retries,
                             "score": conf_score, "checks": checks, "source_scores": scores,
                             "conflicts": conflicts, "limitations": limitations,
                             "memory_reused": res.memory_reused, "debate_stats": dstats}})
        res.file_path = str(path)
        if store_memory:
            res.kg_added = ctx.memory.remember(res.run_id, ctx.topic, new_flat, ctx.session.pages,
                                               ctx.session.meta, conf_label, triples)
            ctx.emit(f"🧠 Memory me save: {len(new_flat)} finding(s), KG me {res.kg_added} nayi relation(s)",
                     kind="memory")
            res.events = ctx.events
    ctx.result = res
    return {}


# ====================== Orchestrator ======================
class Orchestrator:
    def __init__(self, client_factory=None, memory=None, docs=None, checkpointer=None):
        self.client_factory = client_factory       # None = asli Anthropic client
        self._memory, self._docs = memory, docs
        self.contexts = {}
        self.graph = self._build(checkpointer or MemorySaver())

    # lazily default stores (sirf jab use hon)
    @property
    def memory(self):
        if self._memory is None:
            from app.memory.manager import MemoryManager
            self._memory = MemoryManager()
        return self._memory

    @property
    def docs(self):
        if self._docs is None:
            from app.rag import DocStore
            self._docs = DocStore()
        return self._docs

    def _wrap(self, name, fn):
        async def node(state, config):
            ctx = self.contexts[config["configurable"]["thread_id"]]
            c0, t = ctx.tracker.cost_usd, time.perf_counter()
            ctx.emit(f"▶ {name}", kind="node_start", node=name)
            out = await fn(state, ctx)
            ctx.emit(f"✔ {name}", kind="node_end", node=name, latency_s=round(time.perf_counter() - t, 2),
                     cost_usd=round(ctx.tracker.cost_usd - c0, 6))
            return out
        return node

    def _build(self, checkpointer):
        g = StateGraph(RState)
        for name, fn in [("recall", n_recall), ("plan", n_plan), ("research", n_research), ("analyze", n_analyze),
                         ("write", n_write), ("verify", n_verify), ("rewrite", n_rewrite), ("finalize", n_finalize)]:
            g.add_node(name, self._wrap(name, fn))
        g.add_node("approval", make_approval_node(self))       # traced nahi: resume par dobara chalta hai
        g.add_edge(START, "recall")
        g.add_edge("recall", "plan")
        g.add_edge("plan", "approval")
        g.add_conditional_edges("approval", route_after_approval, {"research": "research", END: END})
        g.add_edge("research", "analyze")
        g.add_edge("analyze", "write")
        g.add_edge("write", "verify")
        g.add_conditional_edges("verify", route_after_verify, {"rewrite": "rewrite", "finalize": "finalize"})
        g.add_edge("rewrite", "verify")
        g.add_edge("finalize", END)
        return g.compile(checkpointer=checkpointer)

    # ----- public API -----
    async def start(self, topic, on_event=None, thread_id=None, **options):
        opts = {**DEFAULT_OPTIONS, **options}
        thread_id = thread_id or uuid.uuid4().hex[:12]
        ctx = RunContext(thread_id, topic, opts, self.client_factory,
                         self.memory if opts["use_memory"] else None,
                         self.docs if opts["use_docs"] else None, on_event)
        try:
            opts["language"] = resolve_language(opts.get("language"), topic)
        except ValueError as e:
            return self._fail(ctx, str(e))
        if opts["mode"] not in ("standard", "debate"):
            return self._fail(ctx, f"Unknown mode: {opts['mode']}")
        if not topic.strip():
            return self._fail(ctx, "Topic khali hai.")
        self._prune()
        self.contexts[thread_id] = ctx
        return await self._drive(ctx, {"topic": topic, "mode": opts["mode"], "options": opts})

    async def resume(self, thread_id, approved=True, plan=None, debate_plan=None, on_event=None):
        ctx = self.contexts.get(thread_id)
        if ctx is None:
            return RunStatus(thread_id, "error", error="Ye run nahi mila (server restart ho gaya ya expire).")
        if ctx.status != "awaiting_approval":
            return RunStatus(thread_id, ctx.status, error=f"Run abhi approval ka intezaar nahi kar raha ({ctx.status}).")
        if on_event:
            ctx.on_event = on_event
        return await self._drive(ctx, Command(resume={"approved": approved, "plan": plan, "debate_plan": debate_plan}))

    # ----- internals -----
    def _fail(self, ctx, msg):
        ctx.status = "error"
        ctx.emit(f"❌ {msg}", kind="error")
        res = RunResult(False, ctx.topic, trace=ctx.tracker.events, cost_usd=ctx.tracker.cost_usd,
                        input_tokens=ctx.tracker.input_tokens, output_tokens=ctx.tracker.output_tokens,
                        elapsed=round(ctx.now(), 2), error=msg, mode=ctx.options.get("mode", "standard"))
        res.events = ctx.events
        return RunStatus(ctx.thread_id, "error", result=res, error=msg)

    async def _drive(self, ctx, graph_input):
        ctx.bind()
        cfg = {"configurable": {"thread_id": ctx.thread_id}, "recursion_limit": 60}
        try:
            await self.graph.ainvoke(graph_input, cfg)
            snap = await self.graph.aget_state(cfg)
            lang = ctx.options.get("language", "en")
            if snap.next:
                pending = next(i.value for t in snap.tasks for i in t.interrupts)
                ctx.status = "awaiting_approval"
                ctx.emit(ev_text(lang, "awaiting_approval"), kind="awaiting_approval", **pending)
                return RunStatus(ctx.thread_id, "awaiting_approval", pending=pending)
            if snap.values.get("approved") is False:
                ctx.status = "cancelled"
                return RunStatus(ctx.thread_id, "cancelled")
            ctx.status = "done"
            ctx.emit(ev_text(lang, "done"), kind="done", cost_usd=ctx.result.cost_usd, confidence=ctx.result.confidence_label)
            ctx.result.events = ctx.events
            return RunStatus(ctx.thread_id, "done", result=ctx.result)
        except Exception as e:
            return self._fail(ctx, friendly_error(e))
        finally:
            ctx.active = ctx.now()

    def _prune(self):
        if len(self.contexts) < MAX_CONTEXTS:
            return
        for tid in [t for t, c in self.contexts.items() if c.status != "awaiting_approval"][: MAX_CONTEXTS // 2]:
            self.contexts.pop(tid, None)
