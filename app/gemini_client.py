"""Native Gemini REST Client via httpx.
Direct HTTP call to Google Generative Language API without LiteLLM.
Lightweight, super-fast startup, zero heavy dependencies.
Implements the Anthropic-compatible client interface: client.messages.create(**kw).
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

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _inline_defs(schema: Any) -> Any:
    """Inlines $defs/definitions and removes $ref, title, $schema for Gemini OpenAPI 3.0 compatibility."""
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


def _to_gemini_tools(tools: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    """Anthropic format tools [{'name': ..., 'description': ..., 'input_schema': ...}]
    ko Gemini function_declarations format me convert karta hai.
    """
    if not tools:
        return None
    declarations = []
    for t in tools:
        if "name" in t:
            raw_schema = t.get("input_schema") or t.get("parameters") or {}
            cleaned_schema = _inline_defs(raw_schema)
            if not isinstance(cleaned_schema, dict):
                cleaned_schema = {"type": "object", "properties": {}}
            if not cleaned_schema.get("type"):
                cleaned_schema["type"] = "object"
            declarations.append({
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": cleaned_schema
            })
    if declarations:
        return [{"function_declarations": declarations}]
    return None


def _to_gemini_contents(system: Optional[str], messages: List[Dict[str, Any]]) -> (Optional[Dict[str, Any]], List[Dict[str, Any]]):
    """Anthropic system + messages ko Gemini system_instruction + contents me badalta hai."""
    system_instruction = None
    if system:
        system_instruction = {
            "parts": [{"text": str(system)}]
        }

    contents = []
    for m in messages:
        role = m.get("role")
        raw_content = m.get("content")

        gemini_role = "model" if role in ("assistant", "model") else "user"

        parts = []
        if isinstance(raw_content, str):
            if raw_content:
                parts.append({"text": raw_content})
        elif isinstance(raw_content, list):
            for b in raw_content:
                if isinstance(b, dict):
                    b_type = b.get("type")
                    if b_type == "text":
                        parts.append({"text": b.get("text", "")})
                    elif b_type == "tool_use":
                        inp = b.get("input", {})
                        if isinstance(inp, str):
                            try:
                                inp = json.loads(inp)
                            except Exception:
                                inp = {}
                        parts.append({
                            "functionCall": {
                                "name": b.get("name", ""),
                                "args": inp
                            }
                        })
                    elif b_type == "tool_result":
                        tool_name = b.get("name") or b.get("tool_name") or "tool"
                        res_content = b.get("content", "")
                        if isinstance(res_content, (dict, list)):
                            res_payload = {"result": res_content}
                        else:
                            res_payload = {"result": str(res_content)}
                        parts.append({
                            "functionResponse": {
                                "name": tool_name,
                                "response": res_payload
                            }
                        })
                    else:
                        parts.append({"text": str(b)})
                else:
                    b_type = getattr(b, "type", None)
                    if b_type == "text":
                        parts.append({"text": getattr(b, "text", "")})
                    elif b_type == "tool_use":
                        inp = getattr(b, "input", {})
                        parts.append({
                            "functionCall": {
                                "name": getattr(b, "name", ""),
                                "args": inp
                            }
                        })
                    elif b_type == "tool_result":
                        tool_name = getattr(b, "name", None) or "tool"
                        res_content = getattr(b, "content", "")
                        parts.append({
                            "functionResponse": {
                                "name": tool_name,
                                "response": {"result": str(res_content)}
                            }
                        })
                    else:
                        parts.append({"text": str(b)})

        if parts:
            contents.append({
                "role": gemini_role,
                "parts": parts
            })

    return system_instruction, contents


class GeminiClient:
    """Direct Gemini REST API async client jo Anthropic format ke objects return karta hai."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.messages = self

    async def create(self, **kw) -> SimpleNamespace:
        raw_model = kw.get("model", "gemini-2.5-flash")
        model = raw_model.replace("gemini/", "")
        if "gemini-1.5" in model:
            model = model.replace("gemini-1.5", "gemini-2.5")
        elif "claude" in model:
            model = "gemini-2.5-flash"

        system = kw.get("system", "")
        raw_messages = kw.get("messages", [])
        tools = kw.get("tools")
        tool_choice = kw.get("tool_choice")
        max_tokens = kw.get("max_tokens", 2000)

        api_key = self.api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")

        system_instruction, contents = _to_gemini_contents(system, raw_messages)
        gemini_tools = _to_gemini_tools(tools)

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": 0.2
            }
        }
        if system_instruction:
            payload["system_instruction"] = system_instruction
        if gemini_tools:
            payload["tools"] = gemini_tools

        if tool_choice and gemini_tools:
            if isinstance(tool_choice, dict) and tool_choice.get("type") == "tool":
                payload["toolConfig"] = {
                    "functionCallingConfig": {
                        "mode": "ANY",
                        "allowedFunctionNames": [tool_choice["name"]]
                    }
                }
            elif tool_choice == "auto":
                payload["toolConfig"] = {
                    "functionCallingConfig": {"mode": "AUTO"}
                }

        url = f"{GEMINI_API_BASE}/{model}:generateContent?key={api_key}"

        data = None
        max_retries = 3
        async with httpx.AsyncClient(timeout=60.0) as client:
            for attempt in range(max_retries):
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    break
                elif resp.status_code == 429 and attempt < max_retries - 1:
                    wait_sec = 4.0 * (2 ** attempt)
                    logger.warning(f"Gemini rate limit 429 hit. Waiting {wait_sec}s before retry {attempt + 1}/{max_retries}...")
                    await asyncio.sleep(wait_sec)
                else:
                    err_text = resp.text
                    logger.error(f"Gemini API error {resp.status_code}: {err_text}")
                    raise RuntimeError(f"Gemini API error ({resp.status_code}): {err_text}")

        content_blocks = []
        stop_reason = "end_turn"

        candidates = data.get("candidates", [])
        if candidates:
            candidate = candidates[0]
            finish_reason = candidate.get("finishReason", "STOP")
            if finish_reason == "MAX_TOKENS":
                stop_reason = "max_tokens"

            parts = candidate.get("content", {}).get("parts", [])
            for p in parts:
                if "text" in p and p["text"]:
                    content_blocks.append(SimpleNamespace(type="text", text=p["text"]))
                elif "functionCall" in p:
                    stop_reason = "tool_use"
                    fn_call = p["functionCall"]
                    fn_name = fn_call.get("name", "")
                    fn_args = fn_call.get("args", {})
                    content_blocks.append(
                        SimpleNamespace(
                            type="tool_use",
                            id=f"call_{fn_name}",
                            name=fn_name,
                            input=fn_args
                        )
                    )

        usage_meta = data.get("usageMetadata", {})
        usage_ns = SimpleNamespace(
            input_tokens=usage_meta.get("promptTokenCount", 0),
            output_tokens=usage_meta.get("candidatesTokenCount", 0)
        )

        return SimpleNamespace(
            content=content_blocks,
            stop_reason=stop_reason,
            usage=usage_ns
        )
