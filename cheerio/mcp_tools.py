"""Opt-in MCP configuration and lifecycle for a local Cheerio chat session."""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
import json
import os
from pathlib import Path
from urllib.parse import urlparse


def config_path():
    return Path(os.environ.get("CHEERIO_MCP_CONFIG", str(Path.home() / ".cheerio" / "mcp.json")))


def load_servers(path=None):
    """Reject unsafe or surprising config rather than silently activating servers."""
    path = Path(path) if path is not None else config_path()
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {"servers"} or not isinstance(data["servers"], list):
        raise ValueError("MCP config must contain a servers list")
    if len(data["servers"]) > 5:
        raise ValueError("At most 5 MCP servers")
    result = []
    for entry in data["servers"]:
        if not isinstance(entry, dict) or not set(entry) <= {"name", "enabled", "transport", "url", "command", "args", "env", "allowed_tools", "agents"}:
            raise ValueError("Unknown MCP server configuration")
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip() or len(name) > 60:
            raise ValueError("Each MCP server needs a short name")
        if entry.get("enabled") is not True:
            continue
        allowed = entry.get("allowed_tools")
        if not isinstance(allowed, list) or not allowed or len(allowed) > 20 or not all(isinstance(x, str) and x.strip() for x in allowed) or len(set(allowed)) != len(allowed):
            raise ValueError("Enabled MCP servers need an explicit allowed_tools list (up to 20 names)")
        agents = entry.get("agents", ["chat"])
        if not isinstance(agents, list) or not agents or not set(agents) <= {"chat", "web"}:
            raise ValueError("MCP agents must be chat and/or web")
        transport = entry.get("transport")
        if transport == "streamable-http":
            if set(entry) - {"name", "enabled", "transport", "url", "allowed_tools", "agents"}:
                raise ValueError("HTTP MCP servers accept only a URL")
            url = entry.get("url")
            parsed = urlparse(url) if isinstance(url, str) else None
            if not parsed or parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
                raise ValueError("Invalid HTTP MCP URL")
            result.append((name, {"url": url, "transport": transport}, allowed, agents))
        elif transport == "stdio":
            if set(entry) - {"name", "enabled", "transport", "command", "args", "env", "allowed_tools", "agents"}:
                raise ValueError("Invalid stdio MCP configuration")
            command, args, env = entry.get("command"), entry.get("args", []), entry.get("env", {})
            if not isinstance(command, str) or not command.strip() or not isinstance(args, list) or not all(isinstance(a, str) for a in args):
                raise ValueError("Invalid stdio command or arguments")
            if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
                raise ValueError("Invalid stdio environment")
            result.append((name, {"command": command, "args": args, "env": env}, allowed, agents))
        else:
            raise ValueError("Supported MCP transports: streamable-http or stdio")
    if len({name for name, _, _, _ in result}) != len(result):
        raise ValueError("Duplicate MCP server names")
    return result


@contextmanager
def connect_mcp_servers(path=None, agent="chat"):
    """Start explicitly enabled servers, keep sessions alive, and close on exit."""
    if agent not in {"chat", "web"}:
        raise ValueError("Unknown MCP agent")
    servers = [(name, params, allowed) for name, params, allowed, agents in load_servers(path) if agent in agents]
    if not servers:
        yield []
        return
    try:
        from smolagents import MCPClient
        from mcp import StdioServerParameters
    except ImportError as exc:
        raise RuntimeError("Install smolagents[mcp] to enable MCP servers") from exc
    with ExitStack() as stack:
        tools = []
        for name, params, allowed in servers:
            if "command" in params:
                params = StdioServerParameters(command=params["command"], args=params["args"], env={**os.environ, **params["env"]})
            client_tools = stack.enter_context(MCPClient(params, structured_output=False))
            selected = [t for t in client_tools if t.name in allowed]
            missing = set(allowed) - {t.name for t in selected}
            if missing:
                raise ValueError(f"MCP server {name} lacks configured tools: {sorted(missing)}")
            tools.extend(selected)
        names = [t.name for t in tools]
        if len(names) != len(set(names)):
            raise ValueError("MCP tools have duplicate names; disable conflicting servers")
        yield tools
