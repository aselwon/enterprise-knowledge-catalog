CREATE TABLE IF NOT EXISTS assets (
    id text PRIMARY KEY,
    kind text NOT NULL CHECK (kind IN ('dataset', 'table', 'column')),
    name text NOT NULL,
    data_type text NOT NULL,
    description text NOT NULL,
    domain text NOT NULL,
    parent_id text REFERENCES assets(id) DEFERRABLE INITIALLY DEFERRED,
    owners text[] NOT NULL DEFAULT '{}',
    tags text[] NOT NULL DEFAULT '{}',
    search_document tsvector NOT NULL
);
CREATE INDEX IF NOT EXISTS assets_search_gin ON assets USING gin(search_document);
CREATE INDEX IF NOT EXISTS assets_parent_idx ON assets(parent_id);
CREATE TABLE IF NOT EXISTS edges (
    source_id text NOT NULL REFERENCES assets(id),
    target_id text NOT NULL REFERENCES assets(id),
    kind text NOT NULL CHECK (kind IN ('lineage', 'join', 'same_concept')),
    description text NOT NULL,
    source_column text,
    target_column text,
    PRIMARY KEY (source_id, target_id, kind),
    CHECK (source_id <> target_id),
    CHECK (kind <> 'join' OR (source_column IS NOT NULL AND target_column IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS edges_target_idx ON edges(target_id);
CREATE TABLE IF NOT EXISTS usage_signals (
    asset_id text PRIMARY KEY REFERENCES assets(id),
    query_count_7d integer NOT NULL DEFAULT 0 CHECK (query_count_7d >= 0),
    last_seen timestamptz,
    user_teams text[] NOT NULL DEFAULT '{}',
    unused boolean NOT NULL DEFAULT true,
    as_of timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS business_definitions (
    term text PRIMARY KEY,
    definition text NOT NULL
);
CREATE TABLE IF NOT EXISTS definition_assets (
    term text NOT NULL REFERENCES business_definitions(term),
    asset_id text NOT NULL REFERENCES assets(id),
    PRIMARY KEY (term, asset_id)
);
