import json
from pathlib import Path

import pytest

from catalog.context import context_pack
from catalog.db import connection
from catalog.enrich import enrich
from catalog.evaluate import evaluate
from catalog.graph import join_path, neighbors
from catalog.ingest import Warehouse, ingest
from catalog.search import search


def test_fixture_size_integrity_and_idempotent_ingest():
    result = ingest("fixtures/warehouse.json")
    assert result["tables"] == 45
    with connection() as conn:
        counts = conn.execute("SELECT count(*) AS n,count(DISTINCT domain) AS domains FROM assets").fetchone()
        assert counts == {"n": 273, "domains": 3}
        assert conn.execute("SELECT count(*) AS n FROM edges").fetchone()["n"] == 31
    assert ingest("fixtures/warehouse.json") == result


def test_rejects_invalid_fixture_before_write():
    data = json.loads(Path("fixtures/warehouse.json").read_text())
    data["edges"][0]["source_column"] = "not_a_column"
    with pytest.raises(ValueError, match="Unknown join column"):
        Warehouse.model_validate(data)


def test_search_explanation_and_filters():
    results = search("monthly recurring revenue", kind="table", domain="finance", team="team-1")
    assert results[0]["id"] == "finance.subscriptions"
    for row in results:
        assert row["domain"] == "finance"
        assert row["kind"] == "table"
        assert row["score"] == pytest.approx(sum(row["explanation"]["components"].values()))
    assert search("xyznonexistent") == []
    assert search("the and or") == []
    assert search("'; DROP TABLE assets; --") == []
    assert search("tracking number", kind="column")[0]["id"] == "commerce.shipments.tracking_number"


def test_enrichment_idempotent_and_usage_boost():
    first = enrich("fixtures/query_history.json")
    second = enrich("fixtures/query_history.json")
    assert first == second
    assert first["unused"] >= 6
    with connection() as conn:
        customer = conn.execute("SELECT * FROM usage_signals WHERE asset_id='commerce.customers'").fetchone()
        assert customer["unused"] is True
        assert customer["last_seen"] is not None
        assert customer["query_count_7d"] == 0
    rows = search("revenue", kind="table")
    assert any(r["explanation"]["components"]["popularity"] > 0 for r in rows)
    with connection() as conn:
        conn.execute("UPDATE usage_signals SET query_count_7d=0,user_teams='{}',last_seen=NULL")
    try:
        baseline = {r["id"]: r["score"] for r in search("revenue", kind="table")}
    finally:
        enrich("fixtures/query_history.json")
    assert any(r["score"] > baseline[r["id"]] for r in rows)


def test_enrichment_window_duplicates_future_and_unknown(tmp_path):
    payload = {"as_of": "2026-09-27T12:00:00Z", "queries": [
        {"query_id": "boundary", "occurred_at": "2026-09-20T12:00:00Z",
         "asset_ids": ["commerce.orders", "commerce.orders"], "team": "sales"},
        {"query_id": "old", "occurred_at": "2026-09-20T11:59:59Z",
         "asset_ids": ["commerce.orders"], "team": "old"},
        {"query_id": "future", "occurred_at": "2026-09-28T12:00:00Z",
         "asset_ids": ["commerce.orders"], "team": "future"},
    ]}
    path = tmp_path / "history.json"
    path.write_text(json.dumps(payload))
    try:
        enrich(path)
        with connection() as conn:
            row = conn.execute("SELECT * FROM usage_signals WHERE asset_id='commerce.orders'").fetchone()
            assert row["query_count_7d"] == 1
            assert row["user_teams"] == ["sales"]
        payload["queries"][0]["asset_ids"] = ["unknown.table"]
        path.write_text(json.dumps(payload))
        with pytest.raises(ValueError, match="Unknown table"):
            enrich(path)
        with connection() as conn:
            assert conn.execute("SELECT query_count_7d FROM usage_signals WHERE asset_id='commerce.orders'").fetchone()["query_count_7d"] == 1
    finally:
        enrich("fixtures/query_history.json")


def test_graph_direction_and_bounded_shortest_join_path():
    lineage = neighbors("commerce.daily_sales", "incoming", "lineage")
    assert len(lineage["edges"]) == 2
    assert neighbors("commerce.daily_sales", "outgoing", "lineage")["edges"] == []
    path = join_path("finance.refunds", "commerce.customers")
    assert path["found"] is True and path["length"] == 3
    assert path["nodes"] == ["finance.refunds", "finance.payments", "commerce.orders", "commerce.customers"]
    assert join_path("finance.refunds", "commerce.customers", 2)["found"] is False
    assert join_path("commerce.customers", "finance.refunds")["length"] == 3
    assert join_path("commerce.daily_sales", "commerce.orders")["found"] is False
    assert join_path("commerce.orders", "commerce.orders")["length"] == 0
    with pytest.raises(ValueError):
        join_path("commerce.orders", "commerce.customers", 4)


def test_context_is_bounded_and_grounded():
    pack = context_pack("revenue")
    assert 1 <= len(pack["tables"]) <= 5
    assert pack["definitions"]
    known = {t["id"] for t in pack["tables"] + pack["bridge_tables"]}
    for path in pack["joins"]:
        assert path["length"] <= 3
        assert set(path["nodes"]) <= known
        assert all(e["source_column"] and e["target_column"] for e in path["edges"])
    assert all(len(t["columns"]) <= 12 for t in pack["tables"])
    assert context_pack("xyznonexistent")["tables"] == []


def test_context_includes_intermediate_tables_for_join_paths():
    pack = context_pack("refunds OR profiles")
    assert pack["joins"]
    referenced = {node for path in pack["joins"] for node in path["nodes"]}
    represented = {table["id"] for table in pack["tables"] + pack["bridge_tables"]}
    assert referenced <= represented
    assert "finance.payments" in {table["id"] for table in pack["bridge_tables"]}


@pytest.mark.parametrize("path", [
    "/api/search?q=", "/api/search?q=%20%20", "/api/search?q=orders&limit=51",
    "/api/search?q=orders&kind=invalid", "/api/context?q=orders&limit=6",
    "/api/graph/join-path?source=commerce.orders&target=commerce.customers&max_depth=4",
])
def test_api_validation(client, path):
    assert client.get(path).status_code == 422


def test_api_paths(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/api/search", params={"q": "GMV"}).json()["results"]
    assert client.get("/api/context", params={"q": "MRR"}).json()["tables"]
    assert client.get("/api/graph/neighbors", params={"asset_id": "missing"}).status_code == 404
    assert client.get("/api/graph/join-path", params={"source": "missing", "target": "commerce.orders"}).status_code == 404
    assert client.get("/api/graph/join-path", params={"source": "commerce", "target": "commerce.orders"}).status_code == 422


def test_golden_retrieval():
    report = evaluate()
    assert report["queries"] >= 25
    assert report["recall_at_5"] >= 0.90
    assert report["mrr_at_5"] >= 0.85
    assert report["p95_latency_ms"] < 500
