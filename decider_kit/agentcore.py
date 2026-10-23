"""Amazon Bedrock AgentCore features for the agent: Memory and Gateway, with the decider in the loop.

Turn them on in `agent/features.yaml` (the /new-agent interview asks); `./kit deploy` adds them to
the AgentCore project and deploys them with the runtime. The runtime then gets these environment
variables, set by the AgentCore CDK constructs:

    MEMORY_<NAME>_ID                    an AgentCore Memory (name upper-cased, - and . become _)
    AGENTCORE_GATEWAY_<NAME>_URL        an AgentCore Gateway's MCP endpoint
    AGENTCORE_GATEWAY_<NAME>_AUTH_TYPE  AWS_IAM | CUSTOM_JWT | NONE

Running locally after a deploy, the same values are read from submission/deployment.json, so
`./kit demo` uses the deployed Memory and Gateway too. With neither, memory falls back to an
in-process list and the gateway to no tools, so the agent still runs.

How the decider works with them (each is one decision pattern)
    Memory  + #context-memory: AgentCore Memory returns candidate records for a request; the
            decider decides which are relevant enough to put in the prompt, and whether a new
            message is worth storing at all (small talk never reaches Memory).
    Gateway + #tool-selection: the gateway can expose many tools (Lambda, OpenAPI, MCP servers,
            web search, knowledge bases); the decider picks the one for this request and the
            agent only sees that one.
    Gateway + #guardrails: gateway tools pass through the same InterventionHandler as local ones.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from .config import ROOT, settings


def _token(name: str) -> str:
    return re.sub(r"[-.]", "_", name.upper())


def _deployed() -> dict[str, Any]:
    p = ROOT / "submission" / "deployment.json"
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def memory_id(name: str | None = None) -> str | None:
    """The AgentCore Memory id: MEMORY_<NAME>_ID (any one if no name), else the last deploy's."""
    if name:
        v = os.environ.get(f"MEMORY_{_token(name)}_ID")
        if v:
            return v
    else:
        for k, v in os.environ.items():
            if k.startswith("MEMORY_") and k.endswith("_ID") and v:
                return v
    mems = _deployed().get("memories") or {}
    return mems.get(name) if name else next(iter(mems.values()), None)


def gateway_url(name: str | None = None) -> tuple[str, str] | None:
    """(url, auth_type) of an AgentCore Gateway: AGENTCORE_GATEWAY_<NAME>_URL, else the last deploy's."""
    keys = [f"AGENTCORE_GATEWAY_{_token(name)}_URL"] if name else [
        k for k in os.environ if k.startswith("AGENTCORE_GATEWAY_") and k.endswith("_URL")]
    for k in keys:
        if os.environ.get(k):
            return os.environ[k], os.environ.get(k[:-4] + "_AUTH_TYPE", "AWS_IAM")
    gws = _deployed().get("gateways") or {}
    g = gws.get(name) if name else next(iter(gws.values()), None)
    return (g["url"], g.get("auth_type", "AWS_IAM")) if g else None


class AgentCoreMemoryStore:
    """Candidates from AgentCore Memory for DeciderMemory, and a place to store what it keeps.

        store = AgentCoreMemoryStore(actor_id="customer-42", session_id=session_id)
        mem = DeciderMemory(Decider())
        notes = mem.recall(user_message, store.candidates(user_message))
        if mem.maybe_store(user_message, []):
            store.save(user_message)

    `candidates` searches the memory's long-term records (extracted by its strategies, such as
    SEMANTIC facts and USER_PREFERENCE) plus anything saved in this process. `save` writes an
    event; AgentCore's strategies turn events into long-term records within about a minute.
    Without a memory id (no AgentCore Memory yet), it keeps notes in this process only.
    """

    def __init__(self, actor_id: str = "user", session_id: str = "default", name: str | None = None,
                 namespaces: list[str] | None = None, top_k: int = 8):
        self.id = memory_id(name)
        self.actor_id, self.session_id, self.top_k = actor_id, session_id, top_k
        self.namespaces = namespaces or ["/users/{actorId}/facts", "/users/{actorId}/preferences"]
        self.local: list[str] = []
        self._c = None
        if self.id:
            import boto3

            self._c = boto3.client("bedrock-agentcore", region_name=settings().aws_region)

    @property
    def enabled(self) -> bool:
        return self._c is not None

    def candidates(self, query: str) -> list[str]:
        out: list[str] = []
        if self._c:
            for ns in self.namespaces:
                ns = ns.replace("{actorId}", self.actor_id).replace("{sessionId}", self.session_id)
                try:
                    r = self._c.retrieve_memory_records(memoryId=self.id, namespace=ns,
                                                        searchCriteria={"searchQuery": query[:1000], "topK": self.top_k})
                except Exception as e:  # noqa: BLE001  (a missing namespace or a throttle must not break the turn)
                    print(f"[memory] retrieve {ns}: {type(e).__name__}: {e}")
                    continue
                for rec in r.get("memoryRecordSummaries", []):
                    t = (rec.get("content") or {}).get("text")
                    if t and t not in out:
                        out.append(t)
        return out + [m for m in self.local if m not in out]

    def save(self, text: str, role: str = "USER") -> None:
        self.local.append(text)
        if self._c:
            self._c.create_event(memoryId=self.id, actorId=self.actor_id, sessionId=self.session_id,
                                 eventTimestamp=time.time(),
                                 payload=[{"conversational": {"content": {"text": text[:9000]}, "role": role}}])


def gateway_client(name: str | None = None) -> Any:
    """A started Strands MCPClient for an AgentCore Gateway, or None if there is no gateway.

    AWS_IAM gateways are signed with your AWS credentials (mcp-proxy-for-aws); NONE gateways
    are called directly. Pass `gateway_tools(client)` to ToolSelector or an Agent.
    """
    found = gateway_url(name)
    if not found:
        return None
    url, auth = found
    from mcp.client.streamable_http import streamablehttp_client
    from strands.tools.mcp.mcp_client import MCPClient

    if auth == "AWS_IAM":
        from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client

        client = MCPClient(lambda: aws_iam_streamablehttp_client(url, aws_service="bedrock-agentcore",
                                                                 aws_region=settings().aws_region))
    elif auth == "NONE":
        client = MCPClient(lambda: streamablehttp_client(url))
    else:
        raise RuntimeError(f"gateway auth {auth}: use the AgentCore CLI's generated client for CUSTOM_JWT gateways")
    client.start()
    return client


def gateway_tools(client: Any, include_builtin: bool = False) -> list[Any]:
    """Every tool behind the gateway (follows pagination). Each has a tool_spec with a description.

    The gateway's own semantic tool search (`x_amz_bedrock_agentcore_search`) is left out unless
    `include_builtin`: with the decider choosing the tool, it is one more option to confuse.
    """
    tools: list[Any] = []
    token = None
    while True:
        page = client.list_tools_sync(pagination_token=token)
        tools.extend(t for t in page if include_builtin or not t.tool_name.startswith("x_amz_bedrock_agentcore_"))
        token = getattr(page, "pagination_token", None)
        if not token:
            return tools
