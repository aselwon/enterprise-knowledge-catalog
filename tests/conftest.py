import pytest
from fastapi.testclient import TestClient

from catalog.api import app
from catalog.enrich import enrich
from catalog.ingest import ingest


@pytest.fixture(scope="session", autouse=True)
def seeded_catalog():
    ingest("fixtures/warehouse.json")
    enrich("fixtures/query_history.json")


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
