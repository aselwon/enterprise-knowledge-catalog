# Enterprise Knowledge Catalog

A mini knowledge catalog for agents: warehouse schema metadata is ingested into PostgreSQL, enriched with query history, searched with explainable lexical ranking, and returned as a compact context pack. The MVP runs fully offline on mock fixtures.

## Public demo

No public demo is currently available. Run the local Docker Compose stack below.

## Quick start

Requirements: Docker with Compose and `make`. From the repository root:

```bash
make demo
```

This builds images, starts the database/API/UI, runs fixture ingest, enrichment, and evaluation. Manual steps:

```bash
make up
make ingest
make enrich
make search
make eval
make test
make lint
```

Endpoints:

- UI: http://localhost:18092
- API/OpenAPI: http://localhost:18091/docs
- health: http://localhost:18091/health

`make eval` writes `reports/eval.json` and may exit with code 1 when metrics miss the CLI thresholds. `make down` removes containers and the network but keeps the named volume `catalog_data`. Full cleanup requires `docker compose down -v`.

Compose ports are configurable via `CATALOG_DB_PORT`, `CATALOG_API_PORT`, and `CATALOG_UI_PORT` (defaults 55440, 18091, 18092). Local development uses API port 8000 and the Vite UI port. After the first image/dependency fetch, runtime works offline.

## Local development

Backend requires Python 3.12+ and PostgreSQL 16. Start the database with `docker compose up -d db`, then:

```bash
uv sync --extra dev --frozen
export DATABASE_URL=postgresql://catalog:catalog@localhost:55440/catalog
export MOCK_MODE=true
uv run catalog bootstrap
uv run uvicorn catalog.api:app --reload --host 127.0.0.1 --port 8000
```

UI:

```bash
cd ui
npm ci
npm run dev
```

`make install` runs both install steps. Lockfiles are `uv.lock`, `requirements.lock` (hashed), and `ui/package-lock.json`. The app is mock/offline only; the CLI rejects any `MOCK_MODE` other than `true`. Fixtures live in `fixtures/`: warehouse schema, query history, and golden queries. No BigQuery/Snowflake accounts or API keys are required. The `catalog` / `catalog` credentials in `compose.yaml` are local demo credentials only.

## API

- `GET /api/search?q=monthly%20recurring%20revenue&limit=10&kind=table&domain=finance&team=analytics` — ranked `dataset` / `table` / `column` assets with score, usage signals, and `explanation`; limit 1–50.
- `GET /api/graph/neighbors?asset_id=...&direction=both&kind=join` — neighbors and edges; direction `incoming|outgoing|both`, kind `lineage|join|same_concept`.
- `GET /api/graph/join-path?source=...&target=...&max_depth=3` — join path between tables, at most 3 edges.
- `GET /api/context?q=monthly%20recurring%20revenue&limit=5&team=analytics` — agent context pack: up to 5 tables, 12 columns per table, definitions, join paths, and `bridge_tables`.

## Ranking and enrichment

Candidates pass a lexical gate: `search_document @@ websearch_to_tsquery('english', query)`. The document uses PostgreSQL FTS weights: name A, tags/glossary B, description C. Ranking uses `ts_rank_cd`, not true BM25:

```text
score = 0.70 * lexical
      + 0.18 * min(1, log1p(query_count_7d) / log1p(100))
      + 0.08 * recency
      + 0.04 * team_affinity
```

`recency = exp(-max(0, epoch(as_of-last_seen))/86400/14)`; affinity is 1 when the team is in `user_teams`. Popularity covers 7 days and is clipped; column signals inherit from the parent table. Ties sort by `id`.

The gate ensures popularity/recency cannot surface assets that failed the lexical match. `unused` means no usage in the 7-day window relative to `as_of`; future events are skipped. Enrichment upserts a full snapshot for every table, including zeros.

Ingest is idempotent: assets, edges, and glossary entries are upserted by key, and definition relations are rebuilt. There are no asset/edge deletions, so removing an item from the source snapshot does not delete it from the catalog.

## Graph and data model

Schema (`catalog/schema.sql`) includes `assets`, `edges`, `usage_signals`, `business_definitions`, and bridge table `definition_assets`. Assets are dataset/table/column with `parent_id`. Edges describe lineage, join, or same concept, plus join columns.

Neighbors respect source → target; `both` unions directions. Join path uses BFS; join edges are treated as undirected with depth limit 3. Context bridge tables are extra tables on paths between results; glossary is loaded via the bridge table.

## Evaluation

```bash
make eval
```

The CLI requires at least 25 golden queries, measures top-5, and writes `recall_at_5`, `mrr_at_5`, details, and p95 latency. Acceptance thresholds: recall ≥ 0.90, MRR@5 ≥ 0.85, p95 ≤ 500 ms. P95 covers a warm in-process search call with a fresh DB connection (no HTTP); warm-up is disabled. `make test` runs `docker compose exec -T api pytest -q`; locally use `uv run pytest` with the database up. `make lint` runs ruff.

## Architecture and trade-offs

Compose runs PostgreSQL, seed (`catalog bootstrap`), FastAPI, and a static React UI. Postgres FTS with a GIN index is simple and explainable, but does not solve synonyms and is not BM25. Explicit edges and BFS are easy to debug, but do not replace a graph engine at scale. Context-pack limits protect agent budget at the cost of completeness. `as_of` makes enrichment reproducible; popularity is a low-weight auxiliary signal.

## Limitations

No authentication/authorization, tenant isolation, live connectors, deletions from a synced snapshot, embeddings, true BM25, or production secrets. The demo is local, mock, and metadata-only.

The UI uses a clean futuristic navy-glass direction: deep navy background, translucent panels, cool cyan/lime accents, and a responsive catalog search layout.
