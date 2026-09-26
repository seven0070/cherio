"""Bounded local retrieval retry, with source scores rather than model-made certainty."""
from __future__ import annotations

import re
from .rag import search

STOP = {'the', 'and', 'for', 'this', 'that', 'what', 'where', 'when', 'with', 'from', 'about', 'your', 'does', 'have'}


def _terms(text):
    return {t for t in re.findall(r'\w+', text.lower()) if len(t) > 2 and t not in STOP}


def quality(query, items):
    """Keyword overlap proxy, not a relevance judgment or answer correctness score."""
    terms = _terms(query)
    if not terms or not items:
        return 0.0
    return max(len(terms & _terms(item['excerpt'])) / len(terms) for item in items)


def corrective_search(query, db=None, retriever=None):
    """At most two local retrieval calls. Return evidence and honest weakness flag."""
    retriever = retriever or (lambda q, n: search(q, db=db, limit=n))
    first = retriever(query, 5)
    score = quality(query, first)
    if score >= 0.5:
        return {'results': first, 'quality': score, 'retried': False, 'weak': False}
    terms = list(dict.fromkeys(t for t in re.findall(r'\w+', query.lower()) if len(t) > 2 and t not in STOP))
    # Try the rarest-looking long keywords, never invent new external terms.
    retry_query = ' '.join(sorted(terms, key=len, reverse=True)[:4])
    if not retry_query or retry_query == query.lower().strip():
        return {'results': first, 'quality': score, 'retried': False, 'weak': True}
    second = retriever(retry_query, 5)
    combined = list({(x['path'], x['position']): x for x in first + second}.values())[:8]
    score = quality(query, combined)
    return {'results': combined, 'quality': score, 'retried': True, 'weak': score < 0.5}
