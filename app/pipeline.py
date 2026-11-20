"""Non-interactive wrapper (CLI, evals, tests): graph ko auto_approve=True ke saath chalata hai.
Interactive (human approval) ke liye app.graph.Orchestrator use karo."""
import asyncio

from app.graph import Orchestrator
from app.result import RunResult, friendly_error  # noqa: F401  (re-export: purane imports ke liye)


def _adapt(on_event):
    return (lambda ev: on_event(ev["msg"])) if on_event else None


async def arun_research(topic, on_event=None, client=None, save=True, parallel=True, verify=True,
                        max_retries=None, detect_conflicts=True, mode="standard", use_memory=False,
                        use_docs=False, language=None, orchestrator=None):
    orch = orchestrator or Orchestrator(client_factory=(lambda: client) if client is not None else None)
    status = await orch.start(topic, on_event=_adapt(on_event), auto_approve=True, save=save, parallel=parallel,
                              verify=verify, max_retries=max_retries, detect_conflicts=detect_conflicts,
                              mode=mode, use_memory=use_memory, use_docs=use_docs, language=language)
    return status.result


def run_research(topic, **kw):
    """Sync wrapper."""
    return asyncio.run(arun_research(topic, **kw))
