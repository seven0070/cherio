import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from cheerio.mcp_tools import load_servers, connect_mcp_servers

class MCPTests(unittest.TestCase):
    def test_absent_disabled_and_enabled(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'mcp.json'
            self.assertEqual(load_servers(path), [])
            path.write_text(json.dumps({'servers':[{'name':'local', 'enabled':False,'transport':'stdio','command':'test'}]}))
            self.assertEqual(load_servers(path), [])
            with connect_mcp_servers(path) as tools:
                self.assertEqual(tools, [])
            path.write_text(json.dumps({'servers':[{'name':'local','enabled':True,'transport':'streamable-http','url':'http://localhost:8000/mcp','allowed_tools':['search']}]}))
            self.assertEqual(load_servers(path)[0][0], 'local')

    def test_reject_unexpected_and_credentials(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'mcp.json'
            for server in [{'name':'bad','enabled':True,'transport':'streamable-http','url':'http://u:p@example.com','allowed_tools':['search']}, {'name':'bad','enabled':True,'transport':'stdio','command':'x','allowed_tools':['search'],'surprise':'y'}]:
                path.write_text(json.dumps({'servers':[server]}))
                with self.assertRaises(ValueError): load_servers(path)
