import json

import pytest

from catalog.evaluate import evaluate


def test_metrics_count_all_relevant_assets_and_rank_first_hit(tmp_path, monkeypatch):
    cases = [{"query": "example", "expected": ["table.a", "table.b"]}] * 25
    path = tmp_path / "golden.json"
    path.write_text(json.dumps(cases))
    monkeypatch.setattr("catalog.evaluate.search", lambda *args, **kwargs: [
        {"id": "table.other"}, {"id": "table.b"},
    ])
    report = evaluate(path, repeats=1)
    assert report["recall_at_5"] == pytest.approx(0.5)
    assert report["mrr_at_5"] == pytest.approx(0.5)
    assert report["timed_requests"] == 25


def test_metrics_missing_relevant_assets_score_zero(tmp_path, monkeypatch):
    path = tmp_path / "golden.json"
    path.write_text(json.dumps([{"query": "missing", "expected": ["table.a"]}] * 25))
    monkeypatch.setattr("catalog.evaluate.search", lambda *args, **kwargs: [])
    report = evaluate(path, repeats=1)
    assert report["recall_at_5"] == 0
    assert report["mrr_at_5"] == 0
