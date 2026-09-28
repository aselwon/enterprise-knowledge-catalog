import os
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from psycopg import OperationalError

from catalog.context import context_pack
from catalog.db import connection
from catalog.graph import AssetNotFound, join_path, neighbors
from catalog.search import search

app = FastAPI(title="Enterprise Knowledge Catalog", version="0.1.0")
Text = Annotated[str, Query(min_length=1, max_length=300, pattern=r"\S")]


@app.exception_handler(OperationalError)
def database_unavailable(request, exc):
    return JSONResponse(status_code=503, content={"detail": "Catalog database unavailable"})


@app.exception_handler(AssetNotFound)
def unknown_asset(request, exc):
    return JSONResponse(status_code=404, content={"detail": "Asset not found"})


@app.get("/health")
def health():
    with connection() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok", "mock_mode": os.getenv("MOCK_MODE", "true").lower() == "true"}


@app.get("/api/search")
def search_api(q: Text, limit: Annotated[int, Query(ge=1, le=50)] = 10,
               kind: Literal["dataset", "table", "column"] | None = None,
               domain: Annotated[str | None, Query(max_length=100)] = None,
               team: Annotated[str | None, Query(max_length=100)] = None):
    return {"query": q, "results": search(q, limit, kind, domain, team)}


@app.get("/api/graph/neighbors")
def neighbors_api(asset_id: Text, direction: Literal["both", "incoming", "outgoing"] = "both",
                  kind: Literal["lineage", "join", "same_concept"] | None = None):
    return neighbors(asset_id, direction, kind)


@app.get("/api/graph/join-path")
def join_path_api(source: Text, target: Text, max_depth: Annotated[int, Query(ge=1, le=3)] = 3):
    try:
        return join_path(source, target, max_depth)
    except AssetNotFound:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/context")
def context_api(q: Text, limit: Annotated[int, Query(ge=1, le=5)] = 5,
                team: Annotated[str | None, Query(max_length=100)] = None):
    return context_pack(q, limit, team)
