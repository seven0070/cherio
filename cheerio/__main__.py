"""CLI: python -m cheerio chat | web [task...]"""
from __future__ import annotations

import argparse
import sys

from .agents import build_general_agent, build_web_agent
from .config import build_model, resolve_model_config


def chat_loop(agent):
    print("Cheerio general agent. Memory is kept for this session. Type /exit to quit.")
    first = True
    while True:
        try:
            task = input("\nyou > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not task:
            continue
        if task in ("/exit", "/quit"):
            break
        answer = agent.run(task, reset=first)  # reset=False keeps earlier turns in memory
        first = False
        print(f"\ncheerio > {answer}")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cheerio", description="Cheerio AGI base layer")
    parser.add_argument("mode", choices=["chat", "web"], help="chat = general agent, web = web-browsing agent")
    parser.add_argument("task", nargs="*", help="for web mode: the task (otherwise asked interactively)")
    parser.add_argument("--model", help="model id, e.g. llama3.1:8b or gpt-4o-mini")
    parser.add_argument("--api-base", help="OpenAI-compatible endpoint URL")
    parser.add_argument("--api-key", help="API key for the endpoint")
    args = parser.parse_args(argv)

    config = resolve_model_config(model=args.model, api_base=args.api_base, api_key=args.api_key)
    print(f"model: {config['model_id']}  endpoint: {config['api_base']}")
    model = build_model(config)

    if args.mode == "chat":
        chat_loop(build_general_agent(model))
    else:
        agent = build_web_agent(model)
        task = " ".join(args.task).strip()
        if not task:
            task = input("web task > ").strip()
        if task:
            print(f"\ncheerio > {agent.run(task)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
