import json
import math
import statistics
import time
from pathlib import Path

from catalog.search import search


def evaluate(golden_path="fixtures/golden_queries.json", repeats=3):
    cases = json.loads(Path(golden_path).read_text())
    if len(cases) < 25 or repeats < 1:
        raise ValueError("Evaluation needs >=25 queries and >=1 repeats")
    measurements, details = [], []
    for case in cases:
        expected = set(case["expected"])
        if not expected:
            raise ValueError("Each golden query needs expected assets")
        search(case["query"], limit=5, kind=case.get("kind"))  # warm-up, excluded from timing
        for _ in range(repeats):
            start = time.perf_counter()
            results = search(case["query"], limit=5, kind=case.get("kind"))
            measurements.append((time.perf_counter() - start) * 1000)
        ids = [r["id"] for r in results]
        hits = expected.intersection(ids)
        reciprocal_rank = next((1 / (i + 1) for i, item in enumerate(ids) if item in expected), 0)
        details.append({**case, "retrieved": ids, "recall_at_5": len(hits) / len(expected),
                        "reciprocal_rank_at_5": reciprocal_rank})
    latencies = sorted(measurements)
    return {"queries": len(cases), "timed_requests": len(latencies), "cutoff": 5,
            "recall_at_5": statistics.mean(d["recall_at_5"] for d in details),
            "mrr_at_5": statistics.mean(d["reciprocal_rank_at_5"] for d in details),
            "p95_latency_ms": latencies[math.ceil(0.95 * len(latencies)) - 1],
            "latency_scope": "warm retrieval including a fresh DB connection; excludes HTTP",
            "details": details}
