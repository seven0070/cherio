"""Key-free tests: no model API or network needed."""
import unittest

import cheerio


class FakeModel(__import__("smolagents.models", fromlist=["Model"]).Model):
    """Stand-in model that immediately calls final_answer. No network."""

    def __init__(self, answer="done"):
        self.answer = answer

    def generate(self, messages, stop_sequences=None, response_format=None, tools_to_call_from=None, **kwargs):
        from smolagents.models import ChatMessage, ChatMessageToolCall, ChatMessageToolCallFunction, MessageRole

        return ChatMessage(
            role=MessageRole.ASSISTANT,
            tool_calls=[
                ChatMessageToolCall(
                    id="call_1",
                    type="function",
                    function=ChatMessageToolCallFunction(name="final_answer", arguments={"answer": self.answer}),
                )
            ],
        )


class ConfigTests(unittest.TestCase):
    def test_defaults_point_at_local_ollama(self):
        cfg = cheerio.resolve_model_config(env={})
        self.assertEqual(cfg["api_base"], "http://localhost:11434/v1")
        self.assertEqual(cfg["model_id"], cheerio.DEFAULT_MODEL)
        self.assertTrue(cfg["api_key"])

    def test_env_overrides(self):
        env = {"CHEERIO_MODEL": "qwen2.5:3b", "CHEERIO_API_BASE": "http://x/v1", "CHEERIO_API_KEY": "k"}
        cfg = cheerio.resolve_model_config(env=env)
        self.assertEqual((cfg["model_id"], cfg["api_base"], cfg["api_key"]), ("qwen2.5:3b", "http://x/v1", "k"))

    def test_cli_beats_env_and_openai_fallback(self):
        env = {"CHEERIO_MODEL": "a", "OPENAI_API_KEY": "sk-openai"}
        cfg = cheerio.resolve_model_config(model="b", env=env)
        self.assertEqual(cfg["model_id"], "b")
        self.assertEqual(cfg["api_key"], "sk-openai")


class AgentTests(unittest.TestCase):
    def _model(self):
        return cheerio.build_model({"model_id": "m", "api_base": "http://127.0.0.1:9/v1", "api_key": "x"})

    def test_general_agent_tools(self):
        agent = cheerio.build_general_agent(self._model())
        names = set(agent.tools.keys())
        self.assertIn("web_search", names)
        self.assertIn("visit_webpage", names)
        self.assertIn("python_interpreter", names)
        self.assertIn("final_answer", names)

    def test_web_agent_tools(self):
        agent = cheerio.build_web_agent(self._model())
        names = set(agent.tools.keys())
        self.assertIn("web_search", names)
        self.assertIn("visit_webpage", names)
        self.assertNotIn("python_interpreter", names)

    def test_agent_runs_end_to_end_with_fake_model(self):
        agent = cheerio.build_general_agent(FakeModel(answer="pong"), max_steps=2)
        self.assertEqual(agent.run("ping"), "pong")


if __name__ == "__main__":
    unittest.main()
