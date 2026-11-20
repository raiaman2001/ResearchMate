"""FastAPI server for ResearchMate.
Serves pure HTML/CSS/JS frontend from web/ directory and exposes REST/SSE APIs:
- POST /api/research
- GET  /api/research/{id}/stream
- POST /api/research/{id}/plan/approve
- POST /api/research/{id}/cancel
- GET  /api/research/{id}
- GET  /api/research/{id}/export?format=md|docx|pdf
- POST /api/documents
- GET  /api/documents
- DELETE /api/documents/{doc_id}
- GET  /api/history
- GET  /api/history/{id}
- GET  /api/memory/graph
- GET  /api/demo/fixture
"""
import asyncio
import json
import os
from pathlib import Path
from typing import Literal
import uuid

from dotenv import load_dotenv
load_dotenv(override=True)

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import deps, storage
from app.events_i18n import ev_text
from app.export import ExportError, content_disposition, export_report
from app.graph import Orchestrator
from app.agents.pre_research import perform_pre_research

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"

TERMINAL = {"done", "error", "cancelled"}
MAX_RUNS = 100


class ResearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    mode: Literal["standard", "debate"] = "standard"
    language: str = "auto"
    model: str | None = None
    require_approval: bool = True
    use_memory: bool = True
    attach_docs: bool = False
    parallel: bool = True


class PlanApproveRequest(BaseModel):
    approved: bool = True
    sub_questions: list[str] | None = None
    debate_plan: dict | None = None


def format_result(res):
    if res is None:
        return None
    return {
        "ok": res.ok,
        "topic": res.topic,
        "report": res.report,
        "body": res.body,
        "first_body": res.first_body,
        "plan": res.plan,
        "sources": res.sources,
        "trace": res.trace,
        "cost_usd": res.cost_usd,
        "input_tokens": res.input_tokens,
        "output_tokens": res.output_tokens,
        "tokens": res.input_tokens + res.output_tokens,
        "elapsed": res.elapsed,
        "confidence": res.confidence_label,
        "confidence_score": res.confidence_score,
        "warnings": res.warnings,
        "mode": res.mode,
        "claim_checks": res.claim_checks,
        "source_scores": res.source_scores,
        "conflicts": res.conflicts,
        "verification": res.verify_final,
        "verification_before": res.verify_first,
        "retries": res.retries,
        "memory_reused": res.memory_reused,
        "kg_added": res.kg_added,
        "debate_stats": res.debate_stats,
        "language": res.language,
        "db_run_id": res.run_id,
        "limitations": res.limitations,
        "error": res.error,
    }


class RunManager:
    def __init__(self, orch: Orchestrator):
        self.orch = orch
        self.runs = {}

    def create(self, topic: str):
        if len(self.runs) >= MAX_RUNS:
            for rid in [r for r, e in self.runs.items() if e["status"] in TERMINAL][: MAX_RUNS // 2]:
                self.runs.pop(rid, None)
        rid = uuid.uuid4().hex[:12]
        self.runs[rid] = {
            "id": rid,
            "topic": topic,
            "status": "running",
            "events": [],
            "evt": asyncio.Event(),
            "pending": None,
            "result": None,
            "error": None,
            "task": None,
        }
        return rid

    def push(self, rid: str, ev: dict):
        if rid not in self.runs:
            return
        e = self.runs[rid]
        e["events"].append(ev)
        old, e["evt"] = e["evt"], asyncio.Event()
        old.set()

    def apply(self, rid: str, st):
        if rid not in self.runs:
            return
        e = self.runs[rid]
        e["status"] = st.status
        e["pending"] = st.pending
        e["result"] = st.result
        e["error"] = st.error
        if st.status in TERMINAL:
            self.push(rid, {
                "kind": "end",
                "stage": "pipeline",
                "agent": "system",
                "status": st.status,
                "msg": f"Research finished: {st.status}",
                "message": f"Research finished: {st.status}",
                "error": st.error,
                "timestamp": round(st.result.elapsed, 2) if st.result else 0.0,
                "tokens": (st.result.input_tokens + st.result.output_tokens) if st.result else 0,
                "cost": st.result.cost_usd if st.result else 0.0,
            })
        elif st.status == "awaiting_approval":
            lang = (e.get("opts") or {}).get("language", "en")
            self.push(rid, {
                "kind": "awaiting_approval",
                "stage": "planner",
                "agent": "planner",
                "status": "awaiting_approval",
                "msg": ev_text(lang, "plan_ready"),
                "message": ev_text(lang, "plan_ready"),
                "pending": st.pending,
                "timestamp": 0.0,
            })
        else:
            self.push(rid, {
                "kind": "status",
                "stage": "pipeline",
                "agent": "system",
                "status": st.status,
                "msg": st.status,
                "message": st.status,
            })

    async def drive(self, rid: str, coro):
        try:
            self.apply(rid, await coro)
        except Exception as ex:
            if rid in self.runs:
                e = self.runs[rid]
                e["status"] = "error"
                e["error"] = str(ex)
                self.push(rid, {
                    "kind": "end",
                    "stage": "pipeline",
                    "agent": "system",
                    "status": "error",
                    "msg": f"Internal error: {type(ex).__name__}",
                    "message": str(ex),
                    "error": str(ex),
                })

    async def stream(self, rid: str, start: int = 0):
        if rid not in self.runs:
            return
        e, i = self.runs[rid], start
        while True:
            evt = e["evt"]
            while i < len(e["events"]):
                ev = e["events"][i]
                yield f"id: {i}\ndata: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"
                i += 1
            if e["status"] in TERMINAL:
                return
            try:
                await asyncio.wait_for(evt.wait(), timeout=15)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"


storage.init_db()
orch = deps.get_orchestrator()
mgr = RunManager(orch)

app = FastAPI(title="ResearchMate Modern API", version="6.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== REST ENDPOINTS ====================

@app.get("/health")
def health():
    return {"status": "ok", "runs_active": len(mgr.runs)}


class PreResearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)


@app.post("/api/research/pre-scrape")
async def pre_scrape_intelligence(req: PreResearchRequest):
    try:
        data = await perform_pre_research(req.query)
        return data
    except Exception as ex:
        raise HTTPException(500, f"Pre-scrape failed: {str(ex)}")


@app.post("/api/research", status_code=202)
async def start_research(req: ResearchRequest):
    if req.model:
        os.environ["MODEL"] = req.model

    rid = mgr.create(req.query)
    opts = {
        "mode": req.mode,
        "language": req.language,
        "auto_approve": not req.require_approval,
        "use_memory": req.use_memory,
        "use_docs": req.attach_docs,
        "parallel": req.parallel,
        "verify": True,
        "detect_conflicts": True,
    }
    mgr.runs[rid]["opts"] = opts
    mgr.runs[rid]["task"] = asyncio.create_task(
        mgr.drive(rid, orch.start(req.query, on_event=lambda ev: mgr.push(rid, ev), thread_id=rid, **opts))
    )
    return {"id": rid, "status": "running"}


@app.get("/api/research/{rid}/stream")
async def stream_research(rid: str, from_: int = Query(0, alias="from", ge=0)):
    if rid not in mgr.runs:
        raise HTTPException(404, "Research run not found")
    return StreamingResponse(
        mgr.stream(rid, from_),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/research/{rid}/plan/approve")
async def approve_plan(rid: str, req: PlanApproveRequest):
    if rid not in mgr.runs:
        raise HTTPException(404, "Run not found")
    e = mgr.runs[rid]
    if e["status"] != "awaiting_approval":
        raise HTTPException(409, f"Run not waiting for approval (status: {e['status']})")

    e["status"] = "running"
    e["pending"] = None
    lang = (e.get("opts") or {}).get("language", "en")
    msg_approved = ev_text(lang, "plan_approved_msg")
    mgr.push(rid, {
        "kind": "approved",
        "stage": "planner",
        "agent": "planner",
        "status": "done",
        "msg": msg_approved,
        "message": msg_approved,
    })
    e["task"] = asyncio.create_task(
        mgr.drive(
            rid,
            orch.resume(
                rid,
                approved=req.approved,
                plan=req.sub_questions,
                debate_plan=req.debate_plan,
                on_event=lambda ev: mgr.push(rid, ev),
            ),
        )
    )
    return {"id": rid, "status": "running"}


@app.post("/api/research/{rid}/cancel")
async def cancel_research(rid: str):
    if rid not in mgr.runs:
        raise HTTPException(404, "Run not found")
    e = mgr.runs[rid]
    if e["task"] and not e["task"].done():
        e["task"].cancel()
    e["status"] = "cancelled"
    mgr.push(rid, {
        "kind": "end",
        "stage": "pipeline",
        "agent": "system",
        "status": "cancelled",
        "msg": "Research cancelled by user",
        "message": "Research cancelled by user",
    })
    return {"id": rid, "status": "cancelled"}


@app.get("/api/research/{rid}")
def get_research_result(rid: str):
    # Check live memory first
    if rid in mgr.runs:
        e = mgr.runs[rid]
        res = format_result(e["result"])
        return {
            "id": rid,
            "topic": e["topic"],
            "status": e["status"],
            "pending": e["pending"],
            "error": e["error"],
            "events": e["events"],
            "result": res,
        }

    # Fallback to DB if ID is numeric (or match DB run)
    if rid.isdigit():
        row = storage.get_run(int(rid))
        if row:
            for k in ("plan", "trace", "events", "verification"):
                if row.get(k):
                    try:
                        row[k] = json.loads(row[k])
                    except Exception:
                        pass
            return {
                "id": rid,
                "topic": row["topic"],
                "status": "done",
                "result": {
                    "ok": True,
                    "topic": row["topic"],
                    "report": row["report"],
                    "sources": (row.get("sources") or "").split("\n"),
                    "cost_usd": row.get("cost_usd", 0.0),
                    "tokens": (row.get("input_tokens") or 0) + (row.get("output_tokens") or 0),
                    "elapsed": row.get("elapsed", 0.0),
                    "confidence": row.get("confidence", "High"),
                    "plan": row.get("plan") or [],
                    "events": row.get("events") or [],
                    "verification": row.get("verification") or {},
                },
            }

    raise HTTPException(404, "Research not found")


class ExportRawRequest(BaseModel):
    markdown: str
    title: str = "Research_Dossier"
    format: Literal["md", "docx", "pdf"] = "pdf"


@app.post("/api/research/export-raw")
async def export_raw_data(req: ExportRawRequest):
    """Directly converts any markdown dossier into PDF, DOCX, or MD with zero LLM API calls."""
    try:
        data, mime, ext = await asyncio.to_thread(export_report, req.markdown, req.format, req.title)
    except ExportError as ex:
        raise HTTPException(422, str(ex))
    return Response(
        content=data,
        media_type=mime,
        headers={"Content-Disposition": content_disposition(req.title, ext)},
    )


@app.get("/api/research/{rid}/export")
async def export_research(rid: str, format: Literal["md", "docx", "pdf"] = Query("md")):
    markdown = None
    title = "Research Report"

    if rid == "demo-ev-sample" or rid == "demo":
        from app.demo import PAGES
        demo_data = get_demo_fixture()
        markdown = demo_data["result"]["report"]
        title = demo_data["topic"]
    elif rid in mgr.runs:
        e = mgr.runs[rid]
        if e["result"] and e["result"].report:
            markdown = e["result"].report
            title = e["topic"]
    elif rid.isdigit():
        row = storage.get_run(int(rid))
        if row:
            markdown = row["report"]
            title = row["topic"]

    if not markdown:
        raise HTTPException(404, "Report is not ready or not found")

    try:
        data, mime, ext = await asyncio.to_thread(export_report, markdown, format, title)
    except ExportError as ex:
        raise HTTPException(422, str(ex))
    return Response(
        content=data,
        media_type=mime,
        headers={"Content-Disposition": content_disposition(title, ext)},
    )


# ==================== DOCUMENTS / PDF RAG ====================

@app.post("/api/documents")
async def upload_document(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Only .pdf files are supported")
    data = await file.read()
    try:
        res = await asyncio.to_thread(orch.docs.ingest_pdf, data, file.filename)
        return res
    except Exception as ex:
        raise HTTPException(400, str(ex))


@app.get("/api/documents")
def list_documents():
    try:
        return orch.docs.list_docs()
    except Exception as ex:
        # Fallback gracefully if Chroma vector DB index has a local lock or initialization warning
        return []


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: str):
    if not any(d["doc_id"] == doc_id for d in orch.docs.list_docs()):
        raise HTTPException(404, "Document not found")
    orch.docs.delete(doc_id)
    return {"deleted": doc_id}


# ==================== HISTORY & KNOWLEDGE GRAPH ====================

@app.get("/api/history")
def get_history(limit: int = Query(50, ge=1, le=200)):
    return storage.list_runs(limit)


@app.get("/api/history/{db_id}")
def get_history_detail(db_id: int):
    row = storage.get_run(db_id)
    if not row:
        raise HTTPException(404, "Historical record not found")
    for k in ("plan", "trace", "events", "verification"):
        if row.get(k):
            try:
                row[k] = json.loads(row[k])
            except Exception:
                pass
    return row


@app.get("/api/memory/graph")
def get_knowledge_graph():
    return orch.memory.kg.to_json()


# ==================== DEMO FIXTURE ====================

@app.get("/api/demo/fixture")
def get_demo_fixture():
    from app.demo import PAGES
    sample_events = [
        {"kind": "plan", "stage": "planner", "agent": "planner", "status": "done",
         "message": "📋 Plan generated: EV Market Size, Policy incentives, Charging barriers", "timestamp": 1.2, "tokens": 420, "cost": 0.0001},
        {"kind": "researcher", "stage": "researchers", "agent": "researcher-1", "status": "running",
         "message": "🔎 Researcher 1: EV market size in India", "timestamp": 2.1, "tokens": 850, "cost": 0.0003},
        {"kind": "tool", "stage": "researchers", "agent": "researcher-1", "status": "running",
         "message": "web_search: {'query': 'India EV market growth 2025'}", "timestamp": 3.4, "tokens": 1200, "cost": 0.0005},
        {"kind": "tool_result", "stage": "researchers", "agent": "researcher-1", "status": "done",
         "message": "Found 5 high-authority market reports", "timestamp": 4.1, "tokens": 1500, "cost": 0.0006},
        {"kind": "scores", "stage": "analyzer", "agent": "analyzer", "status": "done",
         "message": "🏅 4 sources verified with High/Medium credibility", "timestamp": 6.8, "tokens": 2800, "cost": 0.0011},
        {"kind": "conflict", "stage": "analyzer", "agent": "contradiction-detector", "status": "done",
         "message": "⚖️ 1 conflict detected between Growth Projection numbers", "timestamp": 8.0, "tokens": 3400, "cost": 0.0014},
        {"kind": "writer", "stage": "writer", "agent": "writer", "status": "running",
         "message": "✍️ Synthesizing executive report with citations", "timestamp": 9.5, "tokens": 4900, "cost": 0.0019},
        {"kind": "verify", "stage": "verifier", "agent": "verifier", "status": "done",
         "message": "✅ 100% claims verified against source texts with exact quotes", "timestamp": 11.2, "tokens": 5800, "cost": 0.0022},
        {"kind": "end", "stage": "pipeline", "agent": "system", "status": "done",
         "message": "Research finished successfully", "timestamp": 12.0, "tokens": 6120, "cost": 0.0024}
    ]

    sample_report = """# Executive Research Report: Future of EV Market in India (2025-2030)

## 1. Market Overview & Growth Drivers
The Indian Electric Vehicle (EV) market is currently transitioning from an early-adoption phase to massive mainstream commercial scaling [1]. Two-wheelers and three-wheelers form over **75% of total electric registrations**, propelled by favorable operating unit economics and localized fleet adoption in delivery segments [2].

| Metric | 2024 Benchmark | 2030 Projection | Key Driver |
| :--- | :--- | :--- | :--- |
| **Market Value** | $5.28 Billion | $17.88 - $24 Billion | Subsidies, Local Battery Assembly |
| **EV Adoption Rate** | ~6.5% of total sales | ~30% target | Lower Battery Prices & Fuel Costs |
| **Fast Charging Stations** | ~12,000 public points | 100,000+ points | Private CPO Investments |

## 2. Policy Framework & Regulatory Catalysts
The central government's **FAME-II scheme and recent PM E-DRIVE initiatives** have significantly catalyzed both manufacturing capability and buyer interest [1]. State governments (such as Delhi, Maharashtra, and Karnataka) have further enhanced buyer viability by completely waiving road taxes and vehicle registration fees [1].

> *"Electric two-wheeler registrations grew by more than forty percent in the latest fiscal year, driven by operational cost parity with ICE counterparts."* — [Mobility Registrations Study, 2026] [2]

## 3. Critical Bottlenecks & Supply Chain Risks
Despite strong consumer demand, two structural challenges persist:
1. **Battery Cell Import Dependency:** India imports over 85% of critical battery raw elements (Lithium, Nickel, Cobalt) and cathode precursors [3].
2. **Uneven Highway Charging Infrastructure:** Public fast-charging stations make up less than **10%** of total installed charging points and remain predominantly clustered in tier-1 metro areas [5].
"""

    sample_sources = [
        {"id": 1, "url": "https://ev-policy.demo.gov.in/scheme-review", "domain": "ev-policy.demo.gov.in", "title": "National EV Policy & Scheme Review", "credibility": "High", "score": 92, "opened": True},
        {"id": 2, "url": "https://mobility.demo.ac.in/ev-registrations-study", "domain": "mobility.demo.ac.in", "title": "Academic Study on Urban EV Registrations", "credibility": "High", "score": 88, "opened": True},
        {"id": 3, "url": "https://www.business-daily.example.com/ev-outlook", "domain": "business-daily.example.com", "title": "Commercial Mobility Outlook 2025", "credibility": "Medium", "score": 74, "opened": True},
        {"id": 4, "url": "https://sample-blog.medium.com/why-the-ev-boom-is-overhyped", "domain": "sample-blog.medium.com", "title": "Opinion: Analyzing Structural Headwinds in EV Transition", "credibility": "Low", "score": 45, "opened": True},
        {"id": 5, "url": "https://stats.demo.org.in/charging-points", "domain": "stats.demo.org.in", "title": "Public Charging Infrastructure Statistics", "credibility": "High", "score": 90, "opened": True}
    ]

    sample_claims = [
        {"id": 1, "claim": "State governments announced additional road-tax waivers for electric vehicles", "source_id": 1, "url": "https://ev-policy.demo.gov.in/scheme-review", "verdict": "supported", "quote": "Several state governments announced additional road-tax waivers for electric vehicles.", "reason": "Exact match in policy review", "retry": 0},
        {"id": 2, "claim": "Electric two-wheeler registrations grew by more than forty percent in the latest fiscal year", "source_id": 2, "url": "https://mobility.demo.ac.in/ev-registrations-study", "verdict": "supported", "quote": "Electric two-wheeler registrations grew by more than forty percent in the latest fiscal year of the sample dataset.", "reason": "Academic data quote validated", "retry": 0},
        {"id": 3, "claim": "Dependence on imported battery cells is a critical supply-chain risk", "source_id": 3, "url": "https://www.business-daily.example.com/ev-outlook", "verdict": "supported", "quote": "Dependence on imported battery cells is a supply-chain risk.", "reason": "Confirmed by industry outlook", "retry": 0},
        {"id": 4, "claim": "Fast chargers make up less than ten percent of installed public points", "source_id": 5, "url": "https://stats.demo.org.in/charging-points", "verdict": "supported", "quote": "Fast chargers make up less than ten percent of the installed public points.", "reason": "Validated in public stats", "retry": 0}
    ]

    sample_conflicts = [
        {
            "topic": "Annual Growth Rate Forecast",
            "source_a": "Industry Outlook (2025)",
            "claim_a": "Analysts expect EV sales to keep growing, forecasting 15% to 20% annual growth [Source 3]",
            "source_b": "Critical Opinion Analysis",
            "claim_b": "The growth narrative is overhyped, realistic estimate is closer to 5% annual growth [Source 4]",
            "severity": "Medium",
            "explanation": "Commercial optimism projects 15-20% CAGR while conservative critique projects 5% due to upfront costs."
        }
    ]

    return {
        "id": "demo-ev-sample",
        "topic": "India me EV market ka future kaisa hoga? (Demo)",
        "status": "done",
        "events": sample_events,
        "result": {
            "ok": True,
            "topic": "India me EV market ka future kaisa hoga? (Demo)",
            "report": sample_report,
            "sources": [s["url"] for s in sample_sources],
            "source_scores": sample_sources,
            "claim_checks": sample_claims,
            "conflicts": sample_conflicts,
            "tokens": 6120,
            "cost_usd": 0.0024,
            "elapsed": 12.0,
            "confidence": "High",
            "confidence_score": 0.94,
            "plan": [
                "India EV market size and growth forecast 2025-2030",
                "Central and state government EV incentives & subsidies",
                "Charging infrastructure bottlenecks and battery cell imports"
            ],
            "verification": {"supported": 4, "partial": 0, "unsupported": 0, "total": 4, "ratio": 1.0},
            "retries": 0,
            "mode": "standard"
        }
    }


class TranslateRequest(BaseModel):
    language: str = Field(min_length=2, max_length=20)


@app.post("/api/research/{rid}/translate")
async def translate_research_report(rid: str, req: TranslateRequest):
    """Translate report markdown into target language using LLM wrapper."""
    markdown = None
    topic = "Research Report"

    if rid in mgr.runs:
        e = mgr.runs[rid]
        if e["result"] and e["result"].report:
            markdown = e["result"].report
            topic = e["topic"] or topic
    elif rid.isdigit():
        row = storage.get_run(int(rid))
        if row and row.get("report"):
            markdown = row["report"]
            topic = row.get("topic") or topic

    if not markdown:
        raise HTTPException(404, "Report not found or not ready to translate")

    lang_code = req.language.lower().strip()
    from app.lang import LANG_NAME, WRITER_LANG_INSTRUCTION

    target_name = LANG_NAME.get(lang_code, lang_code.capitalize())
    lang_inst = WRITER_LANG_INSTRUCTION.get(lang_code, f"\n\nReport language: {target_name}. Translate faithfully into {target_name}.")

    system_prompt = (
        f"You are a professional research translator. Translate the markdown research dossier into fluent, natural {target_name}.\n"
        "Preserve all markdown structure, tables, headings, and numerical values.\n"
        "CRITICAL: Keep all citation chips [1], [2], [3] exactly in place without altering numbers."
    )
    user_prompt = f"Topic: {topic}\n\nPlease translate this research report markdown into {target_name}:\n\n{markdown}{lang_inst}"

    try:
        from app.llm import LLM, Tracker
        tracker = Tracker()
        llm = LLM(tracker)
        resp = await llm.create("translator", model=config.WRITER_MODEL, max_tokens=3500,
                                system=system_prompt, messages=[{"role": "user", "content": user_prompt}])
        translated_md = "".join(b.text for b in resp.content if b.type == "text")
        return {
            "id": rid,
            "language": lang_code,
            "language_name": target_name,
            "report": translated_md
        }
    except Exception as ex:
        raise HTTPException(500, f"Translation failed: {str(ex)}")


# Serve static web frontend
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
