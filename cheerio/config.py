"""Model configuration: any OpenAI-compatible chat endpoint with tool calling."""
from __future__ import annotations

import os

DEFAULT_API_BASE = "http://localhost:11434/v1"  # local Ollama
DEFAULT_API_KEY = "ollama"  # Ollama ignores the key; any placeholder works
DEFAULT_MODEL = "llama3.1:8b"  # pick any Ollama model with tool calling


def resolve_model_config(model=None, api_base=None, api_key=None, env=None):
    """Resolve model settings. Precedence: CLI args > CHEERIO_* env > OPENAI_* env > defaults."""
    env = os.environ if env is None else env
    return {
        "model_id": model or env.get("CHEERIO_MODEL") or env.get("OPENAI_MODEL") or DEFAULT_MODEL,
        "api_base": api_base or env.get("CHEERIO_API_BASE") or env.get("OPENAI_BASE_URL") or DEFAULT_API_BASE,
        "api_key": api_key or env.get("CHEERIO_API_KEY") or env.get("OPENAI_API_KEY") or DEFAULT_API_KEY,
    }


def build_model(config):
    """Create the smolagents model client for the resolved config."""
    from smolagents import OpenAIServerModel

    return OpenAIServerModel(
        model_id=config["model_id"],
        api_base=config["api_base"],
        api_key=config["api_key"],
    )
