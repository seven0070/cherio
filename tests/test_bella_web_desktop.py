import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from bella.core import Store
from bella.web_desktop import Bridge, make_handler


class WebDesktopTests(unittest.TestCase):
    def test_local_chat_crud_and_task_state(self):
        with tempfile.TemporaryDirectory() as folder:
            bridge = Bridge(data=Path(folder)/'bella.db', asset_dir=Path(folder))
            saved = bridge.action('chats/save', {'title':'Private', 'messages':[{'role':'user','content':'hello'}]})
            ident = saved['id']
            self.assertEqual(bridge.action('chats/list', {})['chats'][0]['messages'][0]['content'], 'hello')
            bridge.action('chats/pin', {'id': ident, 'pinned': True})
            bridge.action('chats/rename', {'id': ident, 'title': 'Renamed'})
            self.assertTrue(bridge.action('chats/list', {})['chats'][0]['pinned'])
            self.assertEqual(bridge.action('chats/list', {})['chats'][0]['title'], 'Renamed')
            proposed = bridge.action('task/propose', {'goal':'reason locally'})['task']
            self.assertEqual(proposed['state'], 'pending')
            # Refreshing state during a running task must not mark it interrupted.
            with Store(bridge.data, recover=False) as store:
                store.transition(proposed['id'], 'pending', 'running')
            with patch('bella.web_desktop.local_models', return_value=[]):
                self.assertEqual(bridge.action('state', {})['tasks'][0]['state'], 'running')
            bridge.action('chats/delete', {'id':ident})
            self.assertEqual(bridge.action('chats/list', {})['chats'], [])

    def test_frozen_handoff_is_disabled_before_task_transition(self):
        with tempfile.TemporaryDirectory() as folder:
            bridge = Bridge(data=Path(folder)/'bella.db', asset_dir=Path(folder))
            task = bridge.action('task/propose', {'goal':'reason locally'})['task']
            with patch('bella.web_desktop.sys.frozen', True, create=True):
                with self.assertRaisesRegex(ValueError, 'cannot propose'):
                    bridge.action('task/propose', {'goal':'unavailable'})
                with patch('bella.web_desktop.local_models', return_value=[]):
                    self.assertFalse(bridge.action('state', {})['handoff_available'])
                with self.assertRaisesRegex(ValueError, 'source install'):
                    bridge.action('task/approve', {'id':task['id']})
            with bridge.store() as store:
                self.assertEqual(store.task(task['id'])['state'], 'pending')

    def test_large_local_chat_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            assets=Path(folder)
            bridge=Bridge(data=assets/'bella.db', asset_dir=assets)
            server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(bridge))
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            try:
                content='x'*12000
                body=json.dumps({'title':'Long chat','messages':[{'role':'user','content':content[i:i+6000]} for i in (0,6000)]})
                connection=HTTPConnection('127.0.0.1',server.server_port)
                headers={'Content-Type':'application/json','Host':f'127.0.0.1:{server.server_port}','Origin':f'http://127.0.0.1:{server.server_port}','X-Bella-Session':bridge.token}
                connection.request('POST','/api/chats/save',body,headers)
                response=connection.getresponse()
                self.assertEqual(response.status,200)
                self.assertIn('id',json.loads(response.read()))
                connection.close()
            finally:
                server.shutdown();server.server_close()

    def test_http_session_origin_host_and_static_path(self):
        with tempfile.TemporaryDirectory() as folder:
            assets=Path(folder)
            (assets/'index.html').write_text('Bella')
            bridge=Bridge(data=assets/'bella.db', asset_dir=assets)
            server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(bridge))
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            try:
                def request(path, token=None, host=None, origin=None):
                    connection=HTTPConnection('127.0.0.1',server.server_port)
                    headers={'Content-Type':'application/json','Host':host or f'127.0.0.1:{server.server_port}'}
                    if token:headers['X-Bella-Session']=token
                    if origin:headers['Origin']=origin
                    connection.request('POST',path,'{}',headers)
                    response=connection.getresponse()
                    code=response.status;response.read();connection.close();return code
                self.assertEqual(request('/api/task/propose'),403)
                self.assertEqual(request('/api/task/propose',bridge.token,host='evil.example'),403)
                self.assertEqual(request('/api/task/propose',bridge.token,origin='http://evil.example'),403)
                self.assertEqual(request('/api/task/propose',bridge.token),400)
                connection=HTTPConnection('127.0.0.1',server.server_port)
                connection.request('GET','/%2e%2e/secrets')
                response=connection.getresponse();self.assertEqual(response.status,404);response.read();connection.close()
            finally:
                server.shutdown();server.server_close()

if __name__ == '__main__': unittest.main()
