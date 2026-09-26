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
