import tempfile
import unittest
from pathlib import Path
from cheerio.rag import index_folder, search
from cheerio.semantic_rag import build_vectors, semantic_search, hybrid_search

class SemanticTests(unittest.TestCase):
    def test_opt_in_hybrid_and_invalidation(self):
        with tempfile.TemporaryDirectory() as temp:
            root, db = Path(temp)/'docs', Path(temp)/'db.sqlite'
            root.mkdir()
            (root/'a.md').write_text('Canine veterinarian appointment')
            (root/'b.md').write_text('Blue bicycle repair')
            index_folder(root, db)
            self.assertEqual(search('dog', db), [])
            vectors = {'Canine veterinarian appointment':[1.,0.], 'Blue bicycle repair':[0.,1.]}
            fake = lambda text, model: vectors.get(text, [1.,0.])
            self.assertEqual(build_vectors(db, fake, 'test'), 2)
            self.assertIn('a.md', semantic_search('dog', db, embedder=fake, model='test')[0]['path'])
            self.assertIn('a.md', hybrid_search('dog', db, embedder=fake, model='test')[0]['path'])
            index_folder(root, db)
            self.assertEqual(semantic_search('dog', db, embedder=fake, model='test'), [])
