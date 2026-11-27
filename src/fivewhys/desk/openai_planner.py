"""One Responses API call proposes native function calls to the desk's MCP client."""
from __future__ import annotations

import asyncio
import http.client
import json
import os
from time import monotonic

from .vocabulary import relevant_vocabulary


def secret_value():
    value = os.environ["OPENAI_API_KEY"].strip()
    for prefix in ("export OPENAI_API_KEY=", "OPENAI_API_KEY=", "Bearer "):
        if value.startswith(prefix):
            value = value[len(prefix):].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in (chr(34), chr(39)):
        value = value[1:-1].strip()
    return value


def classify_error(error):
    code = error.get("code")
    known = {"insufficient_quota", "model_not_found", "invalid_api_key", "rate_limit_exceeded",
             "unsupported_parameter", "invalid_organization", "invalid_project", "ip_not_authorized"}
    if code in known:
        return code
    message = str(error.get("message") or "").lower()
    for signals, label in [
        (("missing scopes", "insufficient permissions", "insufficient scope"), "missing_permissions"),
        (("incorrect api key", "invalid api key", "invalid bearer", "invalid token"), "invalid_api_key"),
        (("revoked", "deactivated", "disabled"), "credential_or_account_inactive"),
        (("ip allowlist", "ip address"), "ip_restriction"),
        (("organization", "organisation", "project"), "organization_or_project_access"),
    ]:
        if any(signal in message for signal in signals):
            return label
    return "provider_rejection_unspecified"


class OpenAIPlanner:
    def __init__(self):
        self.model = os.getenv("FIVEWHYS_OPENAI_MODEL") or "gpt-4.1-mini"
        self.last_usage = {}
        self.provider_status = None
        self.error_code = None

    async def __call__(self, question, tools):
        self.last_usage = {}
        self.provider_status = None
        self.error_code = None
        start = monotonic()
        response = await asyncio.to_thread(self._post, {
            "model": self.model, "store": False, "max_output_tokens": 500,
            "instructions": (
                "Plan evidence collection for a synthetic order-service incident. "
                "Call each of the three supplied read-only tools exactly once, using the "
                "question to choose the order. Search logs with one specific English technical "
                "term or exact error code. Search prior reports with relevant terminology. "
                "The corpus glossary is for search vocabulary only. Choose narrow queries. "
                "Omit optional arguments if unsure; do not answer the question yourself."
            ),
            "input": json.dumps({"question": question, "historical_glossary": relevant_vocabulary(question)},
                                ensure_ascii=False),
            "tools": [{"type":"function", "name":tool["name"], "description":tool["description"],
                       "parameters":tool["inputSchema"], "strict":False} for tool in tools],
            "tool_choice": "required", "parallel_tool_calls": True,
        })
        if response.get("status") != "completed":
            raise ValueError("Incomplete OpenAI response")
        calls = [item for item in response["output"] if item["type"] == "function_call"]
        usage = response["usage"]
        self.last_usage = {
            "backend":"OpenAI Responses API", "model":response["model"], "request_id":response["id"],
            "prompt_tokens":usage["input_tokens"], "completion_tokens":usage["output_tokens"],
            "call_ids":[item["call_id"] for item in calls], "elapsed_ms":round((monotonic()-start)*1000, 1),
        }
        return [{"tool":item["name"], "input":json.loads(item["arguments"])} for item in calls]

    def _post(self, payload):
        key = secret_value()
        if not key:
            raise ValueError("OPENAI_API_KEY is missing")
        connection = http.client.HTTPSConnection("api.openai.com", timeout=25)
        try:
            connection.request("POST", "/v1/responses", body=json.dumps(payload).encode(),
                               headers={"Authorization":f"Bearer {key}", "Content-Type":"application/json"})
            response = connection.getresponse()
            self.provider_status = response.status
            body = response.read(1_000_001)
            if len(body) > 1_000_000:
                raise ValueError("Oversized response")
            parsed = json.loads(body)
            if response.status != 200:
                self.error_code = classify_error(parsed.get("error") or {})
                raise RuntimeError(f"OpenAI HTTP {response.status}")
            return parsed
        finally:
            connection.close()
