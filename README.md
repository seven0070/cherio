# Cheerio AGI

Cheerio's base layer, built on [smolagents](https://github.com/huggingface/smolagents). Everything Cheerio becomes gets built on top of the `cheerio` package: model configuration, ready agents, and a small CLI. Two agents work today:

- **General agent** (`chat`): chats, searches the web, reads pages, checks Wikipedia, and runs Python to work things out.
- **Web agent** (`web`): browses the web to complete a research task you give it.

This is a foundation, not AGI yet. It works with any OpenAI-compatible model endpoint that supports tool calling: local Ollama (free) by default, or the OpenAI API and similar providers.

## Run on Windows (PowerShell)

Install Python 3.10 or newer, then in this folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

**Option A: local Ollama (free, no API key)**

Install [Ollama](https://ollama.com/download/windows), pull a model with tool calling, then run:

```powershell
ollama pull llama3.1:8b
python -m cheerio chat
python -m cheerio web "latest news on small language models"
```

**Option B: OpenAI API (usage may cost money)**

```powershell
$env:CHEERIO_API_BASE = "https://api.openai.com/v1"
$env:CHEERIO_MODEL = "gpt-4o-mini"
$env:CHEERIO_API_KEY = "YOUR_KEY"
python -m cheerio chat
```

Other providers work when they expose an OpenAI-compatible chat API **with tool calling**. Set `CHEERIO_API_BASE`, `CHEERIO_MODEL`, and `CHEERIO_API_KEY` (or pass `--api-base`, `--model`, `--api-key`). Never commit your key.

In chat mode the agent remembers the session until you quit with `/exit`. Run the key-free tests with:

```powershell
python -m unittest discover -s tests -v
```

## Building on the base layer

Future features import the foundation instead of rewiring it:

```python
import cheerio

model = cheerio.build_model(cheerio.resolve_model_config())
agent = cheerio.build_general_agent(model)   # or build_web_agent(model)
```

New capabilities plug in as extra smolagents tools or new agent builders in `cheerio/agents.py`.

## Source and license

Built on [smolagents](https://github.com/huggingface/smolagents) by Hugging Face (Apache-2.0). The earlier v1 starter was inspired by [awesome-llm-apps / Function Tools Agent](https://github.com/Shubhamsaboo/awesome-llm-apps/tree/main/ai_agent_framework_crash_course/openai_sdk_crash_course/3_tool_using_agent/3_1_function_tools) by Shubham Saboo (MIT); it was replaced by this smolagents base layer and lives in git history. This repository is under the MIT License in `LICENSE`.

## Self-building skills (stage 1, experimental)

Cheerio can draft a small, **reviewed** Python tool from your request using the configured model (local Ollama by default). For example:

```powershell
python -m cheerio skill "turn a Celsius number into Fahrenheit"
```

It shows the exact generated code and runs the generated input/expected tests in isolated short-lived Python processes. **Nothing is saved on a test failure.** Inspect the code and results. Type `APPROVE` at the terminal prompt to save and enable it; any other input leaves it unsaved. A model cannot set this approval. Skills live in `%USERPROFILE%\.cheerio\skills\` (override with `CHEERIO_SKILLS_DIR`), as JSON with code and test cases. Existing skills are loaded as smolagents tools the next time `chat` starts. To disable one, remove its JSON file while Cheerio is stopped. Nothing changes the core code or main branch automatically.

Stage 1 deliberately permits only a tiny subset of Python: a single `def name(text): return ...` with approved basic builtins, no imports, attribute access, file/network/process APIs, loops, or overwrite of an existing skill. The validator rejects other code; each call runs in a fresh process with a three-second timeout and output/input limits. **This is not a security boundary against malicious code:** Python and the existing general agent's `PythonInterpreterTool` are not OS-sandboxed, especially on Windows. Do not use untrusted prompts/code on a machine with sensitive files; run Cheerio under a separate low-privilege user or a proper container if hostile input is possible. Test expectations are model-generated, so passing them does not prove correctness. This initial form is meant for short, pure text transformations, not arbitrary new system powers. No skill is installed or executed during draft generation before tests, and failures need manual correction and rerun.

## Local memory (stage 2 preview)

Cheerio writes the latest chat request and answer to a local SQLite journal in `%USERPROFILE%\.cheerio\memory.sqlite3` (override with `CHEERIO_MEMORY_DB`). At the next chat turn, a bounded excerpt of recent tasks and skill outcomes is passed to the model as **untrusted history**, not as instructions. The database keeps at most 500 events, with each request/outcome capped at 1000 characters. This is a basic recent-history journal, not semantic search or a reliable long-term personal profile. It is local and may contain sensitive chat content in plain text; protect your Windows user account and don't sync this DB publicly. Review and erase entries with `python -m cheerio memory show`, `python -m cheerio memory forget ID`, or `python -m cheerio memory forget all`. It is not connected to any cloud service or shared across machines. The optional journal and skill events are intended to feed later reviewable improvement proposals; Cheerio does not silently change skills or its own code.

## Review-only skill improvement (stage 3 preview)

Approved skill calls now record success or failure in local memory. To suggest a replacement **only after a recorded failure**, run `python -m cheerio fix-skill SKILL_NAME`. It sends the current skill and recent failure summaries to your configured model. If the candidate preserves earlier tests and passes all tests, Cheerio writes `SKILL_NAME.proposal.json` (not loaded on startup), displays the new code and test results, and asks for terminal `APPROVE` to replace the installed skill. Without that exact terminal input, the approved skill does not change. This does not run continuously, auto-diagnose root causes, or prove that a candidate is safe/correct. Don't put secrets into failure messages. The proposed replacement remains limited to the same expression-only language; no core source files are edited.

## Core-change suggestions (stage 4 preview)

`python -m cheerio propose-core` reads up to 30 recent local journal events and asks your configured model for one small core improvement idea. It stores a JSON review note under `%USERPROFILE%\.cheerio\proposals\`. The note includes the model's reason, target file, suggested change, test plan and risk. It is **not a patch or a GitHub PR**, and nothing edits the source, pushes a branch or contacts GitHub. Treat the note as untrusted model output. If you like an idea, a developer still needs to implement and test it in a separate branch, then open a PR for your review. This deliberate stop protects the core until a proper isolated code-development workflow exists. The four layers are connected only in this limited sense: chat and skill outcomes feed local history; failures can prompt human-requested skill fixes; accumulated history can prompt a human-requested core-change suggestion. There is no autonomous always-on self-modification loop.

## Local document search (RAG preview)

Explicitly index a folder with `python -m cheerio rag index "C:\Users\you\Documents\Notes"`, then use `python -m cheerio rag search "question or keywords"` or ask Cheerio in chat. `rag forget FOLDER` removes a folder's indexed text. Only `.txt`, `.md`, `.rst`, `.csv`, `.json` UTF-8 files are read (up to 2 MB each, 1000 files per folder); hidden/symlink folders are skipped. The local SQLite FTS5 index lives in `%USERPROFILE%\.cheerio\rag.sqlite3` (override `CHEERIO_RAG_DB`) and remains on your machine unless you point a model at a cloud endpoint. Search results show file paths and excerpts for checking sources. This is keyword RAG, not embeddings or a PDF/Office reader; similar wording may be missed. Re-run indexing after document changes. Indexed content is plain text, so protect that DB and review the folder before indexing. Retrieved text is untrusted data, not an instruction to follow.

## MCP servers (opt-in)

Install `pip install "smolagents[mcp,toolkit,openai]>=1.26" "mcp>=1.9,<2" "websockets>=13"` to use MCP. The current smolagents 1.26 MCP adapter does not yet work with MCP SDK 2.x; pin 1.x until upstream supports 2.x. Cheerio reads `%USERPROFILE%\.cheerio\mcp.json` (override `CHEERIO_MCP_CONFIG`) when chat starts. No file means no MCP connection. Example:

```json
{"servers": [{"name": "my-local-server", "enabled": true, "transport": "stdio", "command": "python", "args": ["C:\\path\\to\\server.py"], "env": {}, "allowed_tools": ["search"]}]}
```

For a remote server use `"transport": "streamable-http"` and `"url": "https://example.com/mcp"` instead of command/args/env; keep `allowed_tools` with exact tool names. Only explicitly enabled entries with an explicit tool allowlist start; disabled entries do nothing. Chat fails closed if an enabled server cannot connect or tool names clash; connections close on exit. Stdio launches a local process and MCP tools may read, write, send or run code with your privileges. Only configure servers you trust and review their tools and access before enabling them. Do not put passwords in the JSON file; use environment variables or a local secret manager. This is configuration-driven execution, not a sandbox or tool-by-tool approval gate. No live server was used in the key-free test suite.

## Optional local semantic search

Keep the keyword-only RAG default. To add semantic search, run Ollama locally, `ollama pull embeddinggemma`, then `python -m cheerio rag embed` after indexing folders. `python -m cheerio rag hybrid "question"` combines keyword and vector ranks. To let chat use hybrid search, set `CHEERIO_RAG_SEMANTIC=1` before starting it. Set `CHEERIO_EMBED_MODEL` to change the local Ollama embedding model, then rebuild vectors. All embeddings stay in the same local SQLite DB; the code contacts only `127.0.0.1:11434`. Reindexing or forgetting any folder clears vectors to avoid stale references; re-run `rag embed`. This is a simple full scan/cosine search, not ANN, and will slow down on large indexes. If Ollama is unavailable, chat falls back to keyword search. Use a local chat model too if documents must never leave the device.

## Optional corrective retrieval

Set `CHEERIO_RAG_CORRECTIVE=1` to check source/query word overlap and retry a weak match once with terms from the original query. The tool marks weak evidence so the agent can say it doesn't know. This is a cheap lexical quality proxy, not an LLM judge or proof the answer is right. It performs at most two local retrieval passes; it never web-searches private document text.
