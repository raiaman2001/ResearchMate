"""LLM wrapper: har call yahin se jaati hai => trace + token + cost free me mil jata hai."""
import time
from dataclasses import dataclass, field

from pydantic import ValidationError

from app import config


class StructuredOutputError(Exception):
    pass


@dataclass
class Tracker:
    events: list = field(default_factory=list)

    def add(self, node, model, latency, in_tok, out_tok):
        p_in, p_out = config.price_for(model)
        cost = (in_tok * p_in + out_tok * p_out) / 1_000_000
        self.events.append({"node": node, "model": model, "latency_s": round(latency, 2),
                            "input_tokens": in_tok, "output_tokens": out_tok,
                            "cost_usd": round(cost, 6)})

    @property
    def input_tokens(self):
        return sum(e["input_tokens"] for e in self.events)

    @property
    def output_tokens(self):
        return sum(e["output_tokens"] for e in self.events)

    @property
    def cost_usd(self):
        return round(sum(e["cost_usd"] for e in self.events), 6)


import os
from app.gemini_client import GeminiClient
from app.groq_client import GroqClient


def default_client(model: str | None = None):
    # 1. Model explicit override
    target_model = model or os.getenv("MODEL", "")
    if target_model.startswith("gemini/") or target_model.startswith("gemini-"):
        return GeminiClient()
    if target_model.startswith("qwen/") or target_model.startswith("llama") or "groq" in target_model:
        return GroqClient()

    # 2. Key-based priority
    if os.getenv("GEMINI_API_KEY") and not os.getenv("GROQ_API_KEY"):
        return GeminiClient()
    if os.getenv("GROQ_API_KEY"):
        return GroqClient()
    if os.getenv("GEMINI_API_KEY"):
        return GeminiClient()
    try:
        import anthropic
        return anthropic.AsyncAnthropic(max_retries=3)
    except Exception:
        return GeminiClient()


class LLM:
    def __init__(self, tracker, client=None):
        self.tracker = tracker
        self.client = client or default_client()

    async def create(self, node, **kw):
        t = time.perf_counter()
        resp = await self.client.messages.create(**kw)
        usage = getattr(resp, "usage", None)
        self.tracker.add(node, kw.get("model", "?"), time.perf_counter() - t,
                         getattr(usage, "input_tokens", 0) or 0,
                         getattr(usage, "output_tokens", 0) or 0)
        return resp

    async def structured(self, node, schema_cls, system, user, model, max_tokens=1500, retries=1):
        """LLM ko ek tool (= Pydantic schema) bharne par force karo, phir validate karo."""
        tool = {"name": "submit", "description": "Final structured answer yahan submit karo.",
                "input_schema": schema_cls.model_json_schema()}
        prompt = user
        last_err = None
        for _ in range(retries + 1):
            resp = await self.create(
                node, model=model, max_tokens=max_tokens, system=system,
                messages=[{"role": "user", "content": prompt}],
                tools=[tool], tool_choice={"type": "tool", "name": "submit"})
            block = next((b for b in resp.content if b.type == "tool_use"), None)
            if block is None:
                last_err = "tool call nahi mila"
            else:
                try:
                    return schema_cls.model_validate(block.input)
                except ValidationError as e:
                    last_err = str(e)
            prompt = f"{user}\n\nPichla jawab invalid tha ({last_err[:300]}). Schema follow karke dobara do."
        raise StructuredOutputError(f"{node}: valid output nahi mila ({last_err})")
