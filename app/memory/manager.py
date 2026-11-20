"""Memory facade: purani findings (vector DB) + knowledge graph + source archive."""
from datetime import datetime, timezone

from app import config, storage
from app.memory.kg import KnowledgeGraph
from app.memory.vector import VectorStore


class MemoryManager:
    def __init__(self, vector=None, kg=None):
        self.vector = vector or VectorStore("memory")
        self.kg = kg or KnowledgeGraph()

    def recall(self, topic, k=6, min_sim=None):
        """Topic se related purani findings. Sirf wahi jinka source text archive me hai (verify ho sake)."""
        min_sim = config.MEMORY_MIN_SIM if min_sim is None else min_sim
        now = datetime.now(timezone.utc)
        out, seen = [], set()
        for h in self.vector.query(topic, k=k):
            m = h["meta"]
            if h["sim"] < min_sim or h["doc"] in seen:
                continue
            age = (now - datetime.fromisoformat(m["saved_at"])).days
            if age > config.MEMORY_MAX_AGE_DAYS or storage.archive_get(m["source_url"]) is None:
                continue
            seen.add(h["doc"])
            out.append({"claim": h["doc"], "source_url": m["source_url"], "topic": m["topic"],
                        "run_id": m["run_id"], "saved_at": m["saved_at"], "age_days": age,
                        "confidence": m.get("confidence", ""), "sim": h["sim"]})
        return out

    def kg_related(self, topic, limit=6):
        return self.kg.related(topic, limit)

    def remember(self, run_id, topic, findings, pages, metas, confidence_label, triples=None):
        """findings: [{"claim","url"}]. Source text archive me, claim vector DB me, triples KG me."""
        now = datetime.now(timezone.utc).isoformat()
        for u in {f["url"] for f in findings}:
            if pages.get(u):
                storage.archive_put(u, pages[u], metas.get(u))
        self.vector.add(
            ids=[f"{run_id}-{i}" for i in range(len(findings))],
            docs=[f["claim"] for f in findings],
            metas=[{"run_id": int(run_id or 0), "topic": topic, "source_url": f["url"], "saved_at": now,
                    "confidence": confidence_label} for f in findings])
        return self.kg.add_triples(triples or [], run_id=run_id)

    def stats(self):
        return {"findings": self.vector.count(), **self.kg.stats()}
