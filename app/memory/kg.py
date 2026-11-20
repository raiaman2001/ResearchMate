"""Knowledge graph (NetworkX): entities + relations, har relation ek verified finding se grounded."""
import json
import re
from pathlib import Path

import networkx as nx

from app import config


def _key(name):
    return re.sub(r"\s+", " ", name.strip().lower())


class KnowledgeGraph:
    def __init__(self, path=None):
        self.path = Path(path or config.KG_PATH)
        self.g = nx.MultiDiGraph()
        self.load()

    # ----- persistence (apna simple JSON format: networkx version se independent) -----
    def load(self):
        self.g = nx.MultiDiGraph()
        if not self.path.exists():
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        for n in data.get("nodes", []):
            self.g.add_node(n["key"], name=n["name"], type=n.get("type", "other"))
        for e in data.get("edges", []):
            self.g.add_edge(e["s"], e["o"], key=e["rk"], relation=e["relation"], claim=e["claim"],
                            url=e["url"], run_id=e.get("run_id"), count=e.get("count", 1))

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        nodes = [{"key": k, "name": d["name"], "type": d.get("type", "other")} for k, d in self.g.nodes(data=True)]
        edges = [{"s": s, "o": o, "rk": rk, "relation": d["relation"], "claim": d["claim"], "url": d["url"],
                  "run_id": d.get("run_id"), "count": d.get("count", 1)} for s, o, rk, d in self.g.edges(keys=True, data=True)]
        self.path.write_text(json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False), encoding="utf-8")

    # ----- build -----
    def add_triples(self, triples, run_id=None):
        """triples: [{"subject","subject_type","relation","object","object_type","claim","url"}]"""
        added = 0
        for t in triples:
            s, o = _key(t["subject"]), _key(t["object"])
            rk = f"{_key(t['relation'])}"
            for k, name, typ in ((s, t["subject"], t.get("subject_type")), (o, t["object"], t.get("object_type"))):
                if k not in self.g:
                    self.g.add_node(k, name=name.strip(), type=typ or "other")
            if self.g.has_edge(s, o, key=rk):
                self.g[s][o][rk]["count"] += 1                  # same fact dobara mila: count badhao
            else:
                self.g.add_edge(s, o, key=rk, relation=t["relation"].strip(), claim=t["claim"], url=t["url"],
                                run_id=run_id, count=1)
                added += 1
        if triples:
            self.save()
        return added

    # ----- query -----
    def find_entities(self, text):
        """Text me jo known entities hain (word-boundary match, kam se kam 3 chars)."""
        low = text.lower()
        return [k for k in self.g.nodes if len(k) >= 3 and re.search(rf"(?<!\w){re.escape(k)}(?!\w)", low)]

    def related(self, text, limit=8):
        """Text me aaye entities se jude (1-hop) relations."""
        seen, out = set(), []
        for k in self.find_entities(text):
            for s, o, rk, d in list(self.g.out_edges(k, keys=True, data=True)) + list(self.g.in_edges(k, keys=True, data=True)):
                if (s, o, rk) in seen:
                    continue
                seen.add((s, o, rk))
                out.append({"subject": self.g.nodes[s]["name"], "relation": d["relation"],
                            "object": self.g.nodes[o]["name"], "claim": d["claim"], "url": d["url"],
                            "count": d.get("count", 1)})
        return sorted(out, key=lambda x: -x["count"])[:limit]

    def stats(self):
        return {"entities": self.g.number_of_nodes(), "relations": self.g.number_of_edges()}

    def top_entities(self, n=10):
        return [{"name": self.g.nodes[k]["name"], "type": self.g.nodes[k].get("type", "other"), "degree": d}
                for k, d in sorted(self.g.degree, key=lambda x: -x[1])[:n]]

    def to_dot(self, max_nodes=40):
        """Graphviz DOT (Streamlit st.graphviz_chart ke liye). Sabse zyada connected nodes."""
        keep = {k for k, _ in sorted(self.g.degree, key=lambda x: -x[1])[:max_nodes]}
        esc = lambda s: s.replace('"', "'")
        lines = ["digraph KG {", "rankdir=LR;", 'node [shape=box, style="rounded,filled", fillcolor="#eef3ff"];']
        for k in keep:
            lines.append(f'"{esc(self.g.nodes[k]["name"])}";')
        for s, o, d in self.g.edges(data=True):
            if s in keep and o in keep:
                lines.append(f'"{esc(self.g.nodes[s]["name"])}" -> "{esc(self.g.nodes[o]["name"])}" [label="{esc(d["relation"])}"];')
        return "\n".join(lines + ["}"])

    def to_json(self):
        return {"nodes": [{"id": k, **d} for k, d in self.g.nodes(data=True)],
                "edges": [{"source": s, "target": o, **d} for s, o, d in self.g.edges(data=True)]}
