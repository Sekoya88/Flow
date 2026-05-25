from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .tools.flow_agents import register_flow_agent_tools
from .tools.flow_skills import register_flow_skill_tools
from .tools.flow_knowledge import register_flow_knowledge_tools
from .tools.flow_memory import register_flow_memory_tools
from .tools.flow_kg import register_flow_kg_tools
from .tools.flow_workspace import register_flow_workspace_tools
from .tools.flow_digest import register_flow_digest_tools
from .tools.github_actions import register_github_tools
from .tools.obsidian_vault import register_obsidian_tools
from .tools.huggingface import register_huggingface_tools
from .tools.arxiv import register_arxiv_tools
from .tools.web_research import register_web_research_tools
from .resources.agent_list import register_agent_list_resource
from .resources.skill_catalog import register_skill_catalog_resource
from .resources.workspace_snapshot import register_workspace_snapshot_resource
from .prompts.research_digest import register_research_digest_prompt

mcp = FastMCP("Flow MCP")

# Core Flow capabilities
register_flow_agent_tools(mcp)
register_flow_skill_tools(mcp)
register_flow_knowledge_tools(mcp)
register_flow_memory_tools(mcp)
register_flow_kg_tools(mcp)

# Workspace overview + execution history
register_flow_workspace_tools(mcp)

# Research digest (arXiv + HuggingFace)
register_flow_digest_tools(mcp)

# External integrations
register_github_tools(mcp)
register_obsidian_tools(mcp)
register_huggingface_tools(mcp)
register_arxiv_tools(mcp)
register_web_research_tools(mcp)

# Resources (structured workspace context)
register_agent_list_resource(mcp)
register_skill_catalog_resource(mcp)
register_workspace_snapshot_resource(mcp)

# Prompt templates
register_research_digest_prompt(mcp)
