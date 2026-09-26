"""Cheerio's small OpenAI-compatible chat agent with explicit function tools."""

import json
import os
from typing import Any

from openai import OpenAI


TOOLS = [
    {"type": "function", "function": {"name": "add_numbers", "description": "Add two numbers.", "parameters": {"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}}, "required": ["a", "b"]}}},
    {"type": "function", "function": {"name": "multiply_numbers", "description": "Multiply two numbers.", "parameters": {"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}}, "required": ["a", "b"]}}},
    {"type": "function", "function": {"name": "convert_temperature", "description": "Convert between Celsius and Fahrenheit.", "parameters": {"type": "object", "properties": {"temperature": {"type": "number"}, "from_unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}, "to_unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}}, "required": ["temperature", "from_unit", "to_unit"]}}},
]

SYSTEM = ("You are Cheerio, a helpful general chat assistant. Use a tool for calculations "
          "or temperature conversions. Only claim actions you actually performed. "
          "Ask the user before proposing any external side effect.")


def run_tool(name: str, arguments: str) -> str:
    try:
        args = json.loads(arguments)
        if not isinstance(args, dict):
            raise ValueError("Expected an object")
        if name in ("add_numbers", "multiply_numbers"):
            a, b = args["a"], args["b"]
            if type(a) not in (int, float) or type(b) not in (int, float):
                raise ValueError("Expected numbers")
            return str(a + b if name == "add_numbers" else a * b)
        if name == "convert_temperature":
            value = args["temperature"]
            if type(value) not in (int, float):
                raise ValueError("Expected a number")
            source, target = args["from_unit"].lower(), args["to_unit"].lower()
            if source not in ("celsius", "fahrenheit") or target not in ("celsius", "fahrenheit"):
                raise ValueError("Only Celsius and Fahrenheit are supported")
            result = value if source == target else value * 9 / 5 + 32 if source == "celsius" else (value - 32) * 5 / 9
            return f"{result:.2f} {target}"
        raise ValueError("Unknown tool")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return f"Tool error: {exc}"


def answer(client: Any, model: str, messages: list[dict[str, Any]]) -> str:
    """Run at most five tool rounds so an errant model cannot loop forever."""
    for _ in range(5):
        response = client.chat.completions.create(model=model, messages=messages, tools=TOOLS)
        message = response.choices[0].message
        calls = message.tool_calls or []
        if not calls:
            text = message.content or ""
            messages.append({"role": "assistant", "content": text})
            return text
        messages.append({"role": "assistant", "content": message.content, "tool_calls": [
            {"id": call.id, "type": "function", "function": {"name": call.function.name, "arguments": call.function.arguments}}
            for call in calls
        ]})
        for call in calls:
            messages.append({"role": "tool", "tool_call_id": call.id, "content": run_tool(call.function.name, call.function.arguments)})
    return "Stopped after five tool rounds. Try a smaller request."


def main() -> None:
    model = os.getenv("CHEERIO_MODEL", "gpt-4o-mini")
    base_url = os.getenv("CHEERIO_BASE_URL")
    api_key = os.getenv("CHEERIO_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key and base_url and (base_url.startswith("http://localhost:") or base_url.startswith("http://127.0.0.1:")):
        api_key = "local"
    if not api_key:
        raise SystemExit("Set CHEERIO_API_KEY (or OPENAI_API_KEY); local Ollama needs CHEERIO_BASE_URL.")
    client = OpenAI(api_key=api_key, base_url=base_url or None)
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM}]
    print(f"Cheerio ({model}). Type /exit to quit.")
    try:
        while True:
            prompt = input("You: ").strip()
            if prompt.lower() in ("/exit", "/quit"):
                break
            if not prompt:
                continue
            messages.append({"role": "user", "content": prompt})
            try:
                print("Cheerio:", answer(client, model, messages))
            except Exception as exc:
                messages.pop()  # discard the failed user turn
                print(f"Request failed: {exc}")
    except (EOFError, KeyboardInterrupt):
        print("\nBye")


if __name__ == "__main__":
    main()
