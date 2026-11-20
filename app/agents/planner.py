from app import config
from app.lang import PLAN_LANG_NOTE
from app.llm import LLM
from app.schemas import Plan

PLANNER_SYSTEM = """Tum ek research planner ho. User ke topic ko 3-4 alag, chhote, search-able
sub-questions me todo jo milke poora topic cover karein. Sub-questions user ki language me likho.
Agar "Pehle se pata hai" list di gayi ho to un baaton par dobara research mat karao: sirf jo missing hai uspar focus karo."""


def _user(topic, known, lang="en"):
    msg = f"Topic: {topic}" + PLAN_LANG_NOTE.get(lang, "")
    if known:
        msg += "\n\nPehle se pata hai (purani research se):\n" + "\n".join(f"- {k}" for k in known[:10])
    return msg


import re

def _heuristic_plan(topic: str) -> list[str]:
    """Generates 3-4 structured research angles without any LLM API call."""
    clean_topic = topic.strip().rstrip("?").rstrip(".")
    return [
        f"{clean_topic} current industry status and key developments",
        f"{clean_topic} technical advantages, performance benchmarks, and challenges",
        f"{clean_topic} commercial market outlook, cost projections, and adoption timelines"
    ]


async def plan_query(llm: LLM, topic: str, known=None, lang="en") -> Plan:
    # Try deterministic plan first if no API call needed yet or fallback
    try:
        return await llm.structured("planner", Plan, PLANNER_SYSTEM, _user(topic, known, lang), model=config.PLANNER_MODEL)
    except Exception as ex:
        # Graceful fallback without failing the run
        return Plan(sub_questions=_heuristic_plan(topic))
