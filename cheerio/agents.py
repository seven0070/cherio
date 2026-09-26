"""Cheerio's ready agents. Future capabilities plug in here as tools or new agents."""
from __future__ import annotations


def build_general_agent(model, max_steps=8, extra_tools=()):
    """Everyday agent: answers questions, searches, reads pages, runs Python."""
    from smolagents import (
        DuckDuckGoSearchTool,
        PythonInterpreterTool,
        ToolCallingAgent,
        VisitWebpageTool,
        WikipediaSearchTool,
    )

    from .skills import load_skills
    from .rag import build_rag_tool

    return ToolCallingAgent(
        tools=[
            DuckDuckGoSearchTool(max_results=5),
            VisitWebpageTool(max_output_length=8000),
            WikipediaSearchTool(),
            PythonInterpreterTool(),
            *load_skills(),
            build_rag_tool(),
            *extra_tools,
        ],
        model=model,
        max_steps=max_steps,
    )


def build_web_agent(model, max_steps=10):
    """Web agent: digs through the web to complete a research task."""
    from smolagents import DuckDuckGoSearchTool, ToolCallingAgent, VisitWebpageTool

    return ToolCallingAgent(
        tools=[
            DuckDuckGoSearchTool(max_results=8),
            VisitWebpageTool(max_output_length=12000),
        ],
        model=model,
        max_steps=max_steps,
    )
