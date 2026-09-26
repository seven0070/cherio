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
