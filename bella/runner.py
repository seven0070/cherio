"""Isolated process that loads Cheerio locally and emits one result to Bella."""
import contextlib
import io
import json
import sys


def main():
    checkout = sys.argv[1]
    request = json.load(sys.stdin)
    sys.path.insert(0, checkout)
    # Importing and agent execution can print chatter. Keep stdout machine-readable.
    with contextlib.redirect_stdout(sys.stderr):
        from smolagents import ToolCallingAgent
        from cheerio.config import build_model, resolve_model_config
        # A model-only worker, not the general agent: no Python, browser, skills or MCP tools.
        # Force loopback even when CHEERIO_API_BASE or OPENAI_BASE_URL points to a remote provider.
        config = resolve_model_config(api_base="http://127.0.0.1:11434/v1", api_key="ollama", env={})
        model = build_model(config)
        answer = ToolCallingAgent(tools=[], model=model, max_steps=3).run(
            "You are Cheerio. Sanath is your owner and boss. Bella is the primary assistant, and you are her assistant; Sanath can direct you directly. Answer using reasoning only. You have no tools or access to live facts. "
            "Do not claim to have executed any task. Request: " + request["goal"]
        )
    print(json.dumps({"task_id": request["task_id"], "result": str(answer)}))


if __name__ == "__main__":
    main()
