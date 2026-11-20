"""Parallel vs sequential speed compare (fake LLM, har call 0.3s latency).
Run: python bench.py"""
import os, sys, tempfile, time
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "bench.db")
os.environ.setdefault("ANTHROPIC_API_KEY", "dummy")
sys.path.insert(0, "."); sys.path.insert(0, "tests")

import requests
from app import config, pipeline
from fakes import FakeLLMClient


class R:
    status_code = 200
    text = "<html><body><p>" + "EV market text. " * 20 + "</p></body></html>"
    def raise_for_status(self): pass


requests.get = lambda *a, **k: R()
config.CONCURRENCY = 4
qs = ["market size", "key players", "government policy", "future outlook"]

for label, par in (("Sequential", False), ("Parallel  ", True)):
    t = time.perf_counter()
    res = pipeline.run_research("EV India", client=FakeLLMClient(delay=0.3, sub_questions=qs),
                                save=False, parallel=par, verify=False, detect_conflicts=False)
    print(f"{label}: {time.perf_counter()-t:5.2f}s  ok={res.ok}  calls={len(res.trace)}  cost=${res.cost_usd:.4f}")
    if par:
        print("\nTrace:")
        for e in res.trace:
            print(f"  {e['node']:<14} {e['latency_s']:>5}s  {e['input_tokens']}+{e['output_tokens']} tok  ${e['cost_usd']:.5f}")
