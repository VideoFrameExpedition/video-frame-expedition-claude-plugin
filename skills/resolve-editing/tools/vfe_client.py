"""Minimal client for the vfe-vision MCP server (streamable HTTP), standard library only.

The skill's tools call the application directly so that long results (boxes, images) land in
files instead of the conversation. Only read-only tools are used (get_reframe, get_frames,
get_cut_points, get_video...). The address comes from ``VFE_MCP_URL`` or defaults to the local
application (``run.bat``, port 8765). For an application on another computer, its access token
comes from ``VFE_MCP_TOKEN`` (sent as ``Authorization: Bearer``; the application does not ask
for one from its own computer).
"""

from __future__ import annotations

import json
import os
import urllib.request

DEFAULT_URL = "http://127.0.0.1:8765/mcp"


class ToolError(RuntimeError):
    """The tool answered with an error (unknown video, no subject in the range...)."""


class Client:
    def __init__(self, url: str | None = None, timeout: float = 120.0) -> None:
        self.url = url or os.environ.get("VFE_MCP_URL") or DEFAULT_URL
        self.token = os.environ.get("VFE_MCP_TOKEN") or None
        self.timeout = timeout
        self.session: str | None = None
        self._next = 0
        self._post(
            {
                "jsonrpc": "2.0",
                "id": self._id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "vfe-resolve-editing-tools", "version": "1"},
                },
            }
        )
        self._post(
            {"jsonrpc": "2.0", "method": "notifications/initialized"}, expect=False
        )

    def _id(self) -> int:
        self._next += 1
        return self._next

    def _post(self, message: dict, expect: bool = True) -> dict | None:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        request = urllib.request.Request(
            self.url, data=json.dumps(message).encode(), headers=headers, method="POST"
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            self.session = response.headers.get("Mcp-Session-Id") or self.session
            body = response.read().decode("utf-8")
            content_type = response.headers.get("Content-Type", "")
        if not expect:
            return None
        if "text/event-stream" in content_type:
            for line in body.splitlines():
                if line.startswith("data:"):
                    answer = json.loads(line[5:].strip())
                    if answer.get("id") == message.get("id"):
                        return answer
            raise RuntimeError("no answer in the event stream")
        return json.loads(body)

    def raw(self, name: str, arguments: dict) -> list[dict]:
        """The tool's content parts (text and images), or ToolError."""
        answer = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._id(),
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        if "error" in answer:
            raise ToolError(json.dumps(answer["error"], ensure_ascii=False))
        result = answer["result"]
        if result.get("isError"):
            raise ToolError(
                " ".join(p.get("text", "") for p in result.get("content", []))
            )
        return result.get("content", [])

    def call(self, name: str, arguments: dict):
        """The tool's answer decoded from JSON when it is JSON, else its text."""
        answer = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._id(),
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        if "error" in answer:
            raise ToolError(json.dumps(answer["error"], ensure_ascii=False))
        result = answer["result"]
        text = "".join(
            p.get("text", "")
            for p in result.get("content", [])
            if p.get("type") == "text"
        )
        if result.get("isError"):
            raise ToolError(text)
        structured = result.get("structuredContent")
        if isinstance(structured, dict):
            return (
                structured["result"] if list(structured) == ["result"] else structured
            )
        try:
            return json.loads(text)
        except ValueError:
            return text
