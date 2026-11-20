"""Native Groq REST Client via httpx.
Direct HTTP call to Groq OpenAI-compatible API (api.groq.com/openai/v1).
Lightweight, super-fast, supports tool use and Anthropic-compatible client interface: client.messages.create(**kw).
"""
import asyncio
import copy
import json
import logging
import os
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)

GROQ_API_BASE = "https://api.groq.com/openai/v1/chat/completions"


def _clean_schema(schema: Any) -> Any:
    """Cleans schema for JSON Schema compatibility."""
    if not isinstance(schema, dict):
        return schema
    schema_copy = copy.deepcopy(schema)
    defs = {}
    if "$defs" in schema_copy:
        defs.update(schema_copy.pop("$defs"))
    if "definitions" in schema_copy:
        defs.update(schema_copy.pop("definitions"))

    def _walk(node: Any) -> Any:
        if isinstance(node, dict):
            node_dict = dict(node)
            if "$ref" in node_dict:
                ref = node_dict.pop("$ref")
                target_key = ref.split("/")[-1]
                if target_key in defs:
                    resolved = _walk(copy.deepcopy(defs[target_key]))
                    if isinstance(resolved, dict):
                        node_dict.update(resolved)
            cleaned = {}
            for k, v in node_dict.items():
                if k in ("title", "$schema", "$defs", "definitions"):
                    continue
                cleaned[k] = _walk(v)
            return cleaned
        elif isinstance(node, list):
            return [_walk(x) for x in node]
        return node

    return _walk(schema_copy)


def _to_groq_tools(tools: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    """Convert Anthropic tools to OpenAI / Groq tools format."""
    if not tools:
        return None
    groq_tools = []
    for t in tools:
        if "name" in t:
            raw_schema = t.get("input_schema") or t.get("parameters") or {}
            cleaned_schema = _clean_schema(raw_schema)
            if not isinstance(cleaned_schema, dict):
                cleaned_schema = {"type": "object", "properties": {}}
            if not cleaned_schema.get("type"):
                cleaned_schema["type"] = "object"
            groq_tools.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": cleaned_schema
                }
            })
    return groq_tools if groq_tools else None


def _to_groq_messages(system: Optional[str], messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert Anthropic format messages into OpenAI/Groq chat format."""
    out = []
    if system:
        out.append({"role": "system", "content": str(system)})

    for m in messages:
        role = m.get("role")
        raw_content = m.get("content")

        if isinstance(raw_content, str):
            out.append({"role": role, "content": raw_content})
        elif isinstance(raw_content, list):
            text_parts = []
            tool_calls = []
            tool_results = []

            for b in raw_content:
                if isinstance(b, dict):
                    b_type = b.get("type")
                    if b_type == "text":
                        text_parts.append(b.get("text", ""))
                    elif b_type == "tool_use":
                        inp = b.get("input", {})
                        tool_calls.append({
                            "id": b.get("id") or f"call_{b.get('name', 'tool')}",
                            "type": "function",
                            "function": {
                                "name": b.get("name", ""),
                                "arguments": json.dumps(inp) if isinstance(inp, dict) else str(inp)
                            }
                        })
                    elif b_type == "tool_result":
                        tool_results.append(b)
                    else:
                        text_parts.append(str(b))
                else:
                    b_type = getattr(b, "type", None)
                    if b_type == "text":
                        text_parts.append(getattr(b, "text", ""))
                    elif b_type == "tool_use":
                        inp = getattr(b, "input", {})
                        tool_calls.append({
                            "id": getattr(b, "id", None) or f"call_{getattr(b, 'name', 'tool')}",
                            "type": "function",
                            "function": {
                                "name": getattr(b, "name", ""),
                                "arguments": json.dumps(inp) if isinstance(inp, dict) else str(inp)
                            }
                        })
                    elif b_type == "tool_result":
                        tool_results.append(b)
                    else:
                        text_parts.append(str(b))

            if role == "assistant":
                msg = {"role": "assistant"}
                if text_parts:
                    msg["content"] = "\n".join(text_parts)
                if tool_calls:
                    msg["tool_calls"] = tool_calls
                out.append(msg)
            elif tool_results:
                for tr in tool_results:
                    tid = tr.get("tool_use_id") if isinstance(tr, dict) else getattr(tr, "tool_use_id", "call_1")
                    content = tr.get("content") if isinstance(tr, dict) else getattr(tr, "content", "")
                    out.append({
                        "role": "tool",
                        "tool_call_id": tid,
                        "content": json.dumps(content) if isinstance(content, (dict, list)) else str(content)
                    })
            else:
                out.append({"role": role, "content": "\n".join(text_parts) if text_parts else ""})

    return out


class GroqClient:
    """Direct Groq REST API async client returning Anthropic-compatible SimpleNamespace."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.messages = self

    async def create(self, **kw) -> SimpleNamespace:
        raw_model = kw.get("model", "qwen/qwen3.8-27b")
        model = raw_model
        if "gemini" in model or "claude" in model:
            model = "qwen/qwen3.8-27b"

        system = kw.get("system", "")
        raw_messages = kw.get("messages", [])
        tools = kw.get("tools")
        tool_choice = kw.get("tool_choice")
        max_tokens = kw.get("max_tokens", 2000)

        api_key = self.api_key or os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set.")

        messages = _to_groq_messages(system, raw_messages)
        groq_tools = _to_groq_tools(tools)

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.2
        }

        if groq_tools:
            payload["tools"] = groq_tools
            if tool_choice:
                if isinstance(tool_choice, dict) and tool_choice.get("type") == "tool":
                    payload["tool_choice"] = {
                        "type": "function",
                        "function": {"name": tool_choice["name"]}
                    }
                elif tool_choice == "auto":
                    payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        data = None
        max_retries = 6
        async with httpx.AsyncClient(timeout=60.0) as client:
            for attempt in range(max_retries):
                resp = await client.post(GROQ_API_BASE, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    break
                elif resp.status_code == 429 and attempt < max_retries - 1:
                    wait_sec = 14.0
                    try:
                        err_json = resp.json()
                        msg = err_json.get("error", {}).get("message", "")
                        import re
                        m = re.search(r"try again in ([0-9.]+)s", msg)
                        if m:
                            wait_sec = float(m.group(1)) + 1.0
                    except Exception:
                        pass
                    logger.warning(f"Groq rate limit 429. Waiting {wait_sec:.1f}s before retry {attempt + 1}/{max_retries}...")
                    await asyncio.sleep(wait_sec)
                elif resp.status_code == 400 and "tool_use_failed" in resp.text and payload.get("tools"):
                    # Model hallucinated bad tool XML or invalid schema -> retry with explicit nudging
                    logger.warning("Groq tool call validation failed (model emitted bad XML syntax). Retrying with schema reminder...")
                    payload["messages"].append({
                        "role": "user",
                        "content": "CRITICAL: Call tools strictly using JSON parameters matching tool schemas (e.g. read_webpage with {\"url\": \"...\"}). Do not output raw XML."
                    })
                    continue
                else:
                    err_text = resp.text
                    logger.error(f"Groq API error {resp.status_code}: {err_text}")
                    raise RuntimeError(f"Groq API error ({resp.status_code}): {err_text}")

        content_blocks = []
        stop_reason = "end_turn"

        choices = data.get("choices", [])
        if choices:
            msg = choices[0].get("message", {})
            c_text = msg.get("content")
            if c_text:
                content_blocks.append(SimpleNamespace(type="text", text=c_text))

            t_calls = msg.get("tool_calls", [])
            if t_calls:
                stop_reason = "tool_use"
                for tc in t_calls:
                    fn = tc.get("function", {})
                    fn_name = fn.get("name", "")
                    raw_args = fn.get("arguments", "{}")
                    if isinstance(raw_args, str):
                        try:
                            args_dict = json.loads(raw_args)
                        except Exception:
                            args_dict = {}
                    else:
                        args_dict = raw_args
                    content_blocks.append(
                        SimpleNamespace(
                            type="tool_use",
                            id=tc.get("id") or f"call_{fn_name}",
                            name=fn_name,
                            input=args_dict
                        )
                    )

        usage_meta = data.get("usage", {})
        usage_ns = SimpleNamespace(
            input_tokens=usage_meta.get("prompt_tokens", 0),
            output_tokens=usage_meta.get("completion_tokens", 0)
        )

        return SimpleNamespace(
            content=content_blocks,
            stop_reason=stop_reason,
            usage=usage_ns
        )
