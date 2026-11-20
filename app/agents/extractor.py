"""KG ke liye triples nikalna: (subject, relation, object), har ek ek finding se grounded."""
from app import config
from app.llm import LLM
from app.schemas import TripleBatch

EXTRACT_SYSTEM = """Tum ek knowledge-graph extractor ho. Tumhe findings ki list milegi ("F<n>: claim").
Har finding se 0-2 saaf (subject, relation, object) triples nikalo: subject/object naam wale entities hon
(company, person, organisation, place, product, metric, policy). relation chhota verb-phrase ho
(jaise "leads", "launched", "grew by"). subject_type/object_type me entity ka type likho.
Sirf wahi nikalo jo finding me likha hai. finding_id me F ke baad ka number daalo."""


async def extract_triples(llm: LLM, flat, max_triples=20):
    """flat: [{"id","claim","url"}]. Valid, grounded triples ki list (dicts)."""
    if not flat:
        return []
    text = "\n".join(f"F{f['id']}: {f['claim']}" for f in flat)
    batch = await llm.structured("kg-extract", TripleBatch, EXTRACT_SYSTEM, text, model=config.CONFLICT_MODEL)
    by_id = {f["id"]: f for f in flat}
    out, seen = [], set()
    for t in batch.triples:
        s, o, r = t.subject.strip(), t.object.strip(), t.relation.strip()
        if t.finding_id not in by_id or not (2 <= len(s) <= 60 and 2 <= len(o) <= 60 and 2 <= len(r) <= 40):
            continue
        if s.lower() == o.lower():
            continue
        key = (s.lower(), r.lower(), o.lower())
        if key in seen:
            continue
        seen.add(key)
        f = by_id[t.finding_id]
        out.append({"subject": s, "subject_type": t.subject_type, "relation": r, "object": o,
                    "object_type": t.object_type, "claim": f["claim"], "url": f["url"]})
        if len(out) >= max_triples:
            break
    return out
