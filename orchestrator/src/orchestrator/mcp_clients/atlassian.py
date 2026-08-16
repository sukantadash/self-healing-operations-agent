"""Client for the Atlassian MCP server (Jira + Confluence)."""

from __future__ import annotations

from typing import Any

from .base import BaseMCPClient

DEFAULT_URL = "http://mcp-atlassian:8000/mcp"


class AtlassianClient(BaseMCPClient):
    def __init__(self) -> None:
        super().__init__("MCP_ATLASSIAN_URL", DEFAULT_URL)

    async def create_jira_issue(self, project_key: str, summary: str, description: str, issue_type: str = "Task", **extra: Any) -> Any:
        return await self.call_tool(
            "create_jira_issue",
            project_key=project_key,
            summary=summary,
            description=description,
            issue_type=issue_type,
            **extra,
        )

    async def create_confluence_page(self, space_key: str, title: str, body: str, parent_id: str | None = None) -> Any:
        kwargs: dict[str, Any] = {"space_key": space_key, "title": title, "body": body}
        if parent_id:
            kwargs["parent_id"] = parent_id
        return await self.call_tool("create_confluence_page", **kwargs)
