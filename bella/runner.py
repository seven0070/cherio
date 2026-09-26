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
        from cheerio.agents import build_general_agent
        from cheerio.config import build_model, resolve_model_config
        model = build_model(resolve_model_config())
        answer = build_general_agent(model).run(request["goal"])
    print(json.dumps({"task_id": request["task_id"], "result": str(answer)}))


if __name__ == "__main__":
    main()
