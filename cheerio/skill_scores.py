"""Local outcome counts to prioritize which approved skill needs review."""
from __future__ import annotations

from collections import defaultdict
from .memory import Memory


def rank_skills(memory=None, limit=10):
    memory = memory or Memory()
    counts = defaultdict(lambda: {'success': 0, 'failure': 0, 'last_failure': None})
    for event in memory.recent(30, kinds=['skill_used', 'skill_use_failed', 'skill_failed']):
        name = event['request']
        if event['kind'] == 'skill_used':
            counts[name]['success'] += 1
        else:
            counts[name]['failure'] += 1
            if counts[name]['last_failure'] is None:
                counts[name]['last_failure'] = event['outcome'][:200]
    rows = [{'name': name, **data, 'failure_rate': round((data['failure'] + 1)/(data['success'] + data['failure'] + 2), 3)} for name, data in counts.items()]
    return sorted(rows, key=lambda r: (-r['failure_rate'], -r['failure'], r['name']))[:max(1, min(limit, 25))]
