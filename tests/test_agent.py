import json
import unittest
from types import SimpleNamespace
from agent import answer, run_tool


def obj(**kwargs):
    return SimpleNamespace(**kwargs)


class FakeCompletions:
    def __init__(self):
        self.responses = [
            obj(choices=[obj(message=obj(content=None, tool_calls=[obj(id="1", function=obj(name="add_numbers", arguments=json.dumps({"a": 2, "b": 3})))]))]),
            obj(choices=[obj(message=obj(content="Five.", tool_calls=None))]),
        ]
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return self.responses.pop(0)


class AgentTests(unittest.TestCase):
    def test_tools(self):
        self.assertEqual(run_tool("add_numbers", '{"a":2,"b":3}'), "5")
        self.assertEqual(run_tool("multiply_numbers", '{"a":2,"b":3}'), "6")
        self.assertEqual(run_tool("convert_temperature", '{"temperature":0,"from_unit":"celsius","to_unit":"fahrenheit"}'), "32.00 fahrenheit")
        self.assertTrue(run_tool("unknown", "{}").startswith("Tool error:"))
        self.assertTrue(run_tool("add_numbers", '{"a":true,"b":3}').startswith("Tool error:"))

    def test_tool_call_roundtrip(self):
        completions = FakeCompletions()
        client = obj(chat=obj(completions=completions))
        messages = [{"role": "user", "content": "2+3?"}]
        self.assertEqual(answer(client, "test-model", messages), "Five.")
        self.assertEqual(completions.requests[1]["messages"][2]["content"], "5")
        self.assertEqual(messages[-1], {"role": "assistant", "content": "Five."})


if __name__ == "__main__":
    unittest.main()
