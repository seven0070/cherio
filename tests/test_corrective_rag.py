import unittest
from cheerio.corrective_rag import corrective_search, quality

class CorrectiveTests(unittest.TestCase):
    def test_strong_one_call(self):
        calls=[]
        def retrieve(q, limit):
            calls.append(q); return [{'path':'x','position':0,'excerpt':'canine veterinarian appointment'}]
        report=corrective_search('canine appointment', retriever=retrieve)
        self.assertEqual(len(calls),1)
        self.assertFalse(report['weak'])

    def test_weak_retry_bounded(self):
        calls=[]
        def retrieve(q, limit):
            calls.append(q); return [{'path':'x','position':0,'excerpt':'unrelated text'}]
        report=corrective_search('Where did the veterinarian appointment happen today', retriever=retrieve)
        self.assertLessEqual(len(calls),2)
        self.assertTrue(report['weak'])
        self.assertTrue(report['retried'])
