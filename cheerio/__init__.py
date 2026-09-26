"""Cheerio AGI - base layer.

Everything Cheerio becomes builds on this package: model configuration,
ready agents, and a small CLI. Built on smolagents.
"""
from .config import DEFAULT_API_BASE, DEFAULT_API_KEY, DEFAULT_MODEL, build_model, resolve_model_config
from .agents import build_general_agent, build_web_agent

__all__ = [
    "DEFAULT_API_BASE",
    "DEFAULT_API_KEY",
    "DEFAULT_MODEL",
    "build_model",
    "resolve_model_config",
    "build_general_agent",
    "build_web_agent",
]
__version__ = "0.2.0"
