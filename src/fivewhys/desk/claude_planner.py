"""Use Anthropic Messages tool_use blocks as proposals for validated MCP calls."""
import os
from time import monotonic

import anthropic

from .vocabulary import relevant_vocabulary


class ClaudePlanner:
    def __init__(self, client, model):
        self.client = client
        self.model = model
        self.last_usage = {}
        self.provider_status = None
        self.error_code = None

    async def __call__(self, question, tools):
        import json
        self.last_usage = {}
        self.provider_status = None
        self.error_code = None
        started = monotonic()
        try:
            msg = await self.client.messages.create(
                model=self.model, max_tokens=1024,
                system=("Plan evidence collection for the order-service incident. In one response, "
                        "call each of the three supplied tools exactly once. Choose order and arguments "
                        "from the user question. Search logs using a distinctive technical term; "
                        "use the glossary as vocabulary for retrieval. Do not answer the incident yourself."),
                messages=[{"role":"user", "content":json.dumps(
                    {"question":question, "glossary":relevant_vocabulary(question)}, ensure_ascii=False)}],
                tools=[{"name":t["name"], "description":t["description"], "input_schema":t["inputSchema"]}
                       for t in tools],
            )
        except anthropic.APIStatusError as exc:
            self.provider_status = exc.status_code
            self.error_code = type(exc).__name__
            raise
        self.provider_status = 200
        blocks = [block for block in msg.content if block.type == "tool_use"]
        self.last_usage = {"model":msg.model, "backend":"Anthropic Messages API", "request_id":msg.id,
                           "prompt_tokens":msg.usage.input_tokens, "completion_tokens":msg.usage.output_tokens,
                           "stop_reason":msg.stop_reason, "call_ids":[b.id for b in blocks],
                           "elapsed_ms":round((monotonic()-started)*1000, 1)}
        if msg.stop_reason != "tool_use":
            raise ValueError("Claude did not complete its tool plan")
        return [{"tool":b.name, "input":b.input} for b in blocks]


async def available_model(client):
    configured = os.getenv("FIVEWHYS_MODEL")
    if configured:
        return configured
    models = [m.id async for m in client.models.list(limit=100)]
    for family in ("haiku", "sonnet"):
        for model in models:
            if family in model:
                return model
    raise ValueError("No listed Haiku or Sonnet model; configure FIVEWHYS_MODEL")
