"""F2: Contradiction Detector. Findings me aapas ke clash dhundhta hai."""
from app import config
from app.llm import LLM, StructuredOutputError
from app.schemas import ConflictReport

CONFLICT_SYSTEM = """Tum ek fact-consistency checker ho. Tumhe findings ki list milegi, har ek "F<n> [source <s>] claim" format me.
Sirf wahi conflicts batao jahan do ya zyada findings SAME topic/metric par aapas me takraate hain
(alag numbers, ulta direction ya ulta conclusion). Alag topics ya sirf alag detail ko conflict mat banao.
Koi conflict nahi hai to conflicts khali list rakho. claim_ids_a / claim_ids_b me F ke baad wale number daalo."""


async def detect_conflicts(llm: LLM, flat):
    """flat: [{"id","src","claim"}]. Valid conflicts ki list (dicts) deta hai."""
    if len(flat) < 2 or len({f["src"] for f in flat}) < 2:
        return []                                   # ek hi source me conflict nahi hota
    text = "\n".join(f"F{f['id']} [source {f['src']}] {f['claim']}" for f in flat)
    try:
        report = await llm.structured("conflicts", ConflictReport, CONFLICT_SYSTEM, text,
                                      model=config.CONFLICT_MODEL)
    except StructuredOutputError:
        return []                                   # detector fail ho to pipeline na ruke

    by_id = {f["id"]: f for f in flat}
    clean = []
    for c in report.conflicts:
        a, b = set(c.claim_ids_a), set(c.claim_ids_b)
        if not a or not b or (a & b) or not (a | b) <= set(by_id):
            continue                                # LLM ne galat/ulta-seedha ids diye
        if len({by_id[i]["src"] for i in a | b}) < 2:
            continue                                # dono sides same source se: asli conflict nahi
        clean.append({
            "topic": c.topic, "explanation": c.explanation,
            "side_a": [{"claim": by_id[i]["claim"], "src": by_id[i]["src"]} for i in sorted(a)],
            "side_b": [{"claim": by_id[i]["claim"], "src": by_id[i]["src"]} for i in sorted(b)],
        })
    return clean
