"""The incident desk's three read-only capabilities on the shared MCP server."""

from __future__ import annotations

import json
import os
import sys
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError


class DeskError(Exception):
    def __init__(self, reason: str, detail: str = ""):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


class StrictRecord(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


Text = Annotated[str, Field(min_length=1, max_length=2048)]
Query = Annotated[str, Field(min_length=1, max_length=200)]
PositiveID = Annotated[int, Field(gt=0)]


class PastQuery(StrictRecord):
    query: Query
    k: int = Field(default=4, ge=1, le=8)


class ScopedPastQuery(PastQuery):
    doc: Text
    section: Literal["근본 원인"]


class LogQuery(StrictRecord):
    query: Query
    service: Literal["order-service", "api-gateway", "mysql"] | None = None
    level: Literal["INFO", "WARN", "ERROR", "FATAL"] | None = None
    limit: int = Field(default=5, ge=1, le=15)


class ChangeQuery(StrictRecord):
    pass


class Log(StrictRecord):
    id: PositiveID
    ts: Text
    service: Text
    level: Text
    component: Text
    message: Text


class Change(StrictRecord):
    id: PositiveID
    ts: Text
    service: Text
    kind: Text
    description: Text


class Document(StrictRecord):
    doc: Text
    section: Text
    text: Text
    score: float = Field(allow_inf_nan=False)


class Call(StrictRecord):
    tool: str
    input: dict


INPUTS = {
    "search_past_incidents": PastQuery,
    "search_logs": LogQuery,
    "list_change_events": ChangeQuery,
}
OUTPUTS = {
    "search_past_incidents": TypeAdapter(list[Document]),
    "search_logs": TypeAdapter(list[Log]),
    "list_change_events": TypeAdapter(list[Change]),
}


@asynccontextmanager
async def desk_session():
    server = StdioServerParameters(
        command=sys.executable,
        env={name: os.environ[name] for name in ("DESK_EMBEDDING_URL",) if name in os.environ},
        args=["-m", "fivewhys.cli", "mcp-serve", "--scenario", "db_pool_exhaustion", "--seed", "42"],
    )
    async with stdio_client(server) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            yield session


async def discover(session) -> list[dict]:
    await session.initialize()
    listed = await session.list_tools()
    specs = []
    for tool in listed.tools:
        if tool.name in INPUTS:
            specs.append({
                "name": tool.name,
                "description": tool.description or "",
                # Advertise the desk's tighter bounds on the actual discovery result.
                "inputSchema": INPUTS[tool.name].model_json_schema(),
            })
    if {s["name"] for s in specs} != set(INPUTS):
        raise DeskError("tool_error")
    return specs


def validate_plan(raw: list[dict]) -> list[dict]:
    if type(raw) is not list or len(raw) != len(INPUTS):
        raise DeskError("invalid_plan")
    calls = []
    try:
        for entry in raw:
            call = Call.model_validate(entry)
            arguments = INPUTS[call.tool].model_validate(call.input).model_dump(exclude_none=True)
            if "query" in arguments and not arguments["query"].strip():
                raise DeskError("invalid_plan")
            calls.append({"tool": call.tool, "input": arguments})
    except (ValidationError, KeyError) as error:
        raise DeskError("invalid_plan") from error
    if {call["tool"] for call in calls} != set(INPUTS):
        raise DeskError("invalid_plan")
    return calls


async def read_rows(session, call, result_hook=None) -> list[dict]:
    name, args = call["tool"], call["input"]
    response = await session.call_tool(name, args)
    if getattr(response, "is_error", getattr(response, "isError", False)):
        raise DeskError("tool_error")
    if len(response.content) != 1 or response.content[0].type != "text":
        raise DeskError("invalid_result")
    payload = response.content[0].text
    if len(payload) > 64_000:
        raise DeskError("invalid_result")
    try:
        rows = json.loads(payload)
    except ValueError as error:
        raise DeskError("invalid_result") from error
    if result_hook:
        rows = result_hook(name, rows)
    limit = args.get("limit", args.get("k", 32))
    if type(rows) is not list or len(rows) > limit:
        raise DeskError("invalid_result")
    try:
        return [row.model_dump() for row in OUTPUTS[name].validate_python(rows)]
    except ValidationError as error:
        raise DeskError("invalid_result") from error
