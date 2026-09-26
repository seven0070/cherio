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

## Skill review priority

`python -m cheerio skill-scores` ranks recent approved-skill successes and failures in the local 30-event window. The smoothed failure rate helps you decide what to fix first; it never edits or installs a skill automatically. This is a small recent sample, not a benchmark, and it scores runtime success/failure rather than answer quality. `fix-skill NAME` still needs recorded failure evidence, tests and an explicit terminal APPROVE for replacement.

## MCP per-agent scope

Each enabled MCP server may set `"agents": ["chat"]` or `["web"]` (or both). The default is chat only. Cheerio opens only servers assigned to the active agent and exposes only their exact `allowed_tools` names. This routes tools, not actions: an allowed tool can still have broad side effects, and the server's startup code itself runs with local privileges.

## Optional Cognee memory (experimental)

Cheerio's bounded SQLite journal stays the default. Cognee is off by default and is not part of `requirements.txt`. To try it, install `pip install "cognee[ollama]"` in Cheerio's activated Python environment, run local Ollama (`ollama pull llama3.1:8b` and `ollama pull nomic-embed-text:latest`), set `CHEERIO_COGNEE_ENABLED=1`, and run `python -m cheerio cognee add "A note I deliberately want remembered"`. Use `python -m cheerio cognee search "question"` or ask the chat agent to search saved notes. No chat content is ingested automatically. The adapter fixes both LLM and embedding providers to local Ollama, sets telemetry off, and stores Cognee's own data under `%USERPROFILE%\.cheerio\cognee_system` and `cognee_data`. It rejects conflicting provider settings instead of silently falling back to a cloud API. Do not add passwords or sensitive notes. Cognee may use significant disk, RAM and CPU, and graph building can be slow; its search may still miss or misstate facts. The local SQLite journal's `memory forget` does not delete Cognee's separate data, and this preview has no per-note Cognee deletion UI. Review the separate data directories before removing them. No actual Cognee/Ollama/Windows run was performed; tests use a fake Cognee API. Source: https://docs.cognee.ai/guides/local-setup and https://docs.cognee.ai/python-api/.

## Local model/API discovery (draft)

`python -m cheerio models` checks the standard loopback ports for Ollama, LM Studio and llama.cpp-compatible servers, plus a configured `CHEERIO_API_BASE`. It asks each reachable `/v1/models` endpoint for a model list. For Ollama models it also reads `/api/show` for declared tool, vision and embedding capabilities and context length. Other providers' listed models show `unknown` unless tested. `--probe` makes a short, real tool-call generation request for *local* models only, which may load models and take time; a failed probe is inconclusive. `--scan-folder "C:\Models"` searches only that explicit folder for GGUF names, skipping hidden and symlink directories; finding a file does not mean it can run or has a known capability. This is not a full-PC file search.

A configured remote API is skipped unless `--remote` is set. That only lists remote models and may send its configured key to the configured HTTPS endpoint; it does not test or select a paid remote model. `--endpoint URL` adds an endpoint without forwarding the configured key to it. Provider names are host/port hints, not proofs; a key's prefix is never used as proof of provider. Commands never print keys. The CLI does **not** yet automatically select a model or support native non-OpenAI-compatible APIs such as Anthropic/Gemini. Use `--model` and `--api-base` to choose from the list. Remote model discovery can still disclose your IP and incur provider activity; use only endpoints you trust.

## Local Model Passport and task router (draft)

Run `python -m cheerio passport refresh` to inspect up to 20 local models listed by the loopback endpoints. It runs three small generation calls per model: a tool-call request, a JSON-format request, and one arithmetic question. The results are local evidence, not general reasoning scores or a benchmark; a failure may reflect timeout, unsupported request options, model loading or a genuine failure. Vision remains untested/unknown. Speed in tokens/second is shown only when the server reports output-token usage. This may load models and use your CPU/GPU. Passports and explicit feedback are stored in `%USERPROFILE%\.cheerio\passports.json` (or `CHEERIO_PASSPORT_DB`). No automatic background scanning, paid-provider exams, screenshots, or private prompt uploads.

`python -m cheerio passport list` shows saved results; `passport route TASK` shows which local tool-calling model the simple router would choose without sending TASK to a model. For an actual one-shot web task use `python -m cheerio web "your task" --auto-model`. The router scores the tiny exam, speed and feedback, refuses models that failed the tool-call request, and prints the choice before running. `passport feedback ENDPOINT MODEL good|bad` adds your explicit result; Cheerio does not infer answer quality from a run. Code/chat categories use a basic keyword heuristic, not a learned task classifier. Chat's interactive sessions still use your manually configured model. If no tested local tool-capable model exists, routing fails closed; use explicit `--model`/`--api-base` rather than silently switching providers. This is a first-pass Passport + Router, not proof it has found the best model for every task.

## v0.1 consolidated candidate (not released)

This branch collects the drafts #3-#15 in one review branch. Nothing has been merged to `main`. The project still requires an actual Windows/Ollama test before a release.

Run `python -m cheerio setup` to check Ollama and show models already installed on this PC. It reports NVIDIA VRAM and RAM as context, but does not recommend or download any model. Pick one from the numbered list; Cheerio saves the choice in `%USERPROFILE%\.cheerio\settings.json`. If none is installed, choose and install a model yourself, then rerun setup. A model is not bundled in the candidate. Run `python -m cheerio passport refresh` to test its tool calling before relying on it.

Optional OmniRoute gateway: start/configure OmniRoute separately and set `CHEERIO_GATEWAY_MODE=omniroute` and `CHEERIO_OMNIROUTE_KEY` to its **local endpoint key**. For `chat` and `web`, Cheerio preflights `http://127.0.0.1:20128/v1/models`; if it responds with a model catalog, Cheerio uses `model=auto` through the gateway. If it is unreachable or no gateway key is present, Cheerio falls back to the saved Ollama model **before** running the task. It does not replay an in-flight task or silently retry after a tool action. A successful catalog lookup does not guarantee the gateway can complete a request. Upstream provider credentials and privacy/cost controls remain OmniRoute's separate responsibility. An explicit CLI model/endpoint overrides gateway mode. Do not combine gateway mode with Passport `--auto-model`; use one router at a time. Cloud routes may send your prompts to cloud providers.

Run `python -m cheerio update` to *check* the latest stable GitHub release. It prints a release link for review, but **never downloads or installs an update**. This is not an auto-updater. Keep `%USERPROFILE%\.cheerio\` when updating, and back it up before any major version change.

Windows candidate CI builds a zipped executable at `.github/workflows/windows-candidate.yml`. `packaging/build-windows.ps1` does the same locally. It is an unverified candidate artifact, **not an installer** and not a GitHub Release; packaging dependencies and optional Cognee/MCP integrations still need validation on a real Windows PC. The earlier documentation's local-only claims apply only when the selected backend is local.

## Experimental local review gate (separate draft)

New `skill` and `fix-skill` proposals run their existing deterministic tests, then ask the selected *local Ollama* model for an advisory JSON review of the candidate and test results. A fixed policy stops on failed tests, asks for more verification on uncertainty, concerns, added-test suggestions or an unavailable review, and offers terminal `APPROVE` only for a clean result. `APPROVE` is still required to save or replace a skill; model text never approves a write. The review is not a security proof, and an untested model can miss a flaw. The local review accepts only Ollama on loopback port 11434 and refuses redirects; do not put a proxy that forwards to cloud models on that port. A remote model or OmniRoute configuration makes this gate unavailable, rather than sending source code or test inputs to a cloud provider. This preview does not run Foreman or TypeSafe, does not supervise Cheerio's web/chat agents, and does not turn a core proposal into code.

## Intelligence preview (separate draft, not a model upgrade)

`python -m cheerio web "task" --smart-route` uses a simple word-count/keyword heuristic and an explicitly chosen local Ollama model. It does not measure task difficulty or model intelligence. For hard web tasks only, `--allow-cloud` with separately configured `CHEERIO_GATEWAY_MODE=omniroute` and `CHEERIO_OMNIROUTE_KEY` may route the whole task through OmniRoute's `auto` model; this can send the task and subsequent tool context to a cloud provider and may cost money. There is no per-step switch or retry after an agent has used tools. Easy tasks stay local. Without the explicit cloud flag, no gateway is contacted by this routing mode. If an explicit provider/model environment is set, smart routing refuses to override it. Keep one router per run.

`--think-harder` on `chat` or `web` adds a fixed planning checklist before the run and asks a local Ollama model for an advisory caveat check after the answer. It neither verifies facts nor replays actions to repair mistakes; the agent's answer remains unchanged. With a remote or gateway endpoint the extra calls are refused. This is not a general self-correcting reasoner.

Cheerio's existing web tools can search and open live pages during tasks, but they do not guarantee current or accurately cited facts. `python -m cheerio world refresh` is an explicit fetch of BBC World RSS headlines and links into `%USERPROFILE%\.cheerio\world_digest.json`, timestamped and marked unverified. It is not a daily background task, full-article ingestion, or automatically inserted model memory. Check the linked article before relying on a headline.

`python -m cheerio preferences set KEY VALUE`, `preferences show`, and `preferences forget KEY` store only explicitly supplied short notes under `%USERPROFILE%\.cheerio\preferences.json`. Chat sees them as untrusted context; it does not infer preferences from conversations. `memory forget` and `preferences forget` are separate stores. Do not save passwords or tokens. These changes are an experimental harness preview, not a claim to have increased the underlying model's intelligence. ZCode (https://github.com/zai-org/ZCode) was evaluated but not imported: it is a separate TypeScript/Node coding workbench, not a Cheerio Python dependency.

## Bella: conversational front end (prototype)

Bella lives in this repository as a separate Python package. She is the clearly artificial conversational front end; Cheerio remains the tool-running worker. The design is inspired by the user's role split, not copied from the unlicensed Jackywine/Bella project. Bella is non-romantic and non-sexual, encourages real relationships, and presses for concrete next steps without pretending to be human or claiming work she has not done.

On Windows, after installing Cheerio's requirements and a local Ollama model, run from this repository root:

```powershell
py -m cheerio bella
```

Bella uses local Ollama `llama3.2` for conversation (`ollama pull llama3.2` first); Cheerio uses its own `CHEERIO_MODEL`, `CHEERIO_API_BASE`, and normal installation. Bella's chat does not dispatch work automatically. `/task GOAL` creates a pending request, `/approve ID` runs it through Cheerio, `/tasks` displays status, and `/cancel ID` cancels a pending request. Cheerio's own approval gates are separate and must not be bypassed. `/remember NOTE`, `/notes`, and `/forget ID` provide opt-in local notes. Bella stores notes and results in `~/.cheerio/bella.sqlite3` (or `BELLA_DB`), next to Cheerio local state. Completed handoffs are also journaled to Cheerio memory and Bella reads explicit Cheerio preferences as context. Chat history is not persisted. The handoff is a JSON `bella.cheerio.task.v1` envelope passed over stdin to a local subprocess, with result JSON returned to Bella. See `bella/core.py` and `bella/worker.py` for the contract. The Windows candidate launcher also accepts `Cheerio.exe bella` after packaging, but this still needs real Windows smoke testing.

This is a CLI prototype, not a shipped voice or expressive interface, and not yet a broad autonomous personal assistant. The bridge is not a security sandbox: Cheerio tools can have side effects, and failures or timeouts may have left work partly done. Verify before retrying. No Bella code or assets were taken from Jackywine/Bella. Tests run with `python -m unittest discover -s tests -v`.
