# Cheerio AGI

A small starting point for a chat agent with function tools. This is not AGI, a desktop automation tool, or an autonomous agent yet. It can chat, add, multiply, and convert Celsius/Fahrenheit. It does not access files, websites, or your PC. Conversation history lasts only until you quit.

## Run on Windows (PowerShell)

Install Python 3.10 or newer, then in this folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Pick one provider:

**OpenAI API** (requires an API key; usage may cost money):

```powershell
$env:CHEERIO_MODEL = "gpt-4o-mini"
$env:CHEERIO_API_KEY = "YOUR_KEY"
python agent.py
```

**Local Ollama** (no API key; install Ollama separately and download a model that supports tool calling):

```powershell
ollama pull qwen2.5:3b
$env:CHEERIO_BASE_URL = "http://localhost:11434/v1"
$env:CHEERIO_MODEL = "qwen2.5:3b"
python agent.py
```

Other providers work when they expose an OpenAI-compatible chat completions API **with tool calling**. Set `CHEERIO_BASE_URL`, `CHEERIO_MODEL`, and `CHEERIO_API_KEY`. Compatibility depends on the provider/model; arbitrary model APIs will not work as-is. `OPENAI_API_KEY` also works in place of `CHEERIO_API_KEY`. The example `.env.example` is documentation only: this program reads environment variables, not `.env` automatically. Never commit your key.

Type `/exit` to quit. Run the local, key-free tests with `python -m unittest discover -s tests -v`.

## Source and license

Inspired by the function-tool pattern in [awesome-llm-apps / Function Tools Agent](https://github.com/Shubhamsaboo/awesome-llm-apps/tree/main/ai_agent_framework_crash_course/openai_sdk_crash_course/3_tool_using_agent/3_1_function_tools) by Shubham Saboo (MIT licensed). The small agent loop and tests here are a fresh implementation, not a copy of its OpenAI Agents SDK files. This repository is under the MIT License in `LICENSE`.
