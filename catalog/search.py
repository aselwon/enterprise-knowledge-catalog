"""Lexical candidate gate with bounded, inspectable usage boosts."""
import math

from catalog.db import connection


def search(query: str, limit=10, kind=None, domain=None, team=None):
    with connection() as conn:
        rows = conn.execute("""
            WITH q AS (SELECT websearch_to_tsquery('english', %s) AS terms)
            SELECT a.id,a.kind,a.name,a.data_type,a.description,a.domain,a.parent_id,a.owners,a.tags,
              ts_rank_cd(a.search_document,q.terms,32) AS lexical,
              coalesce(u.query_count_7d,0) AS query_count_7d,u.last_seen,
              coalesce(u.user_teams,'{}') AS user_teams,u.unused,
              CASE WHEN u.last_seen IS NULL THEN 0.0 ELSE
                exp(-greatest(0,extract(epoch FROM (u.as_of-u.last_seen)))/86400.0/14) END AS recency
            FROM assets a CROSS JOIN q LEFT JOIN usage_signals u
              ON u.asset_id = CASE WHEN a.kind='column' THEN a.parent_id ELSE a.id END
            WHERE a.search_document @@ q.terms
              AND (%s::text IS NULL OR a.kind=%s)
              AND (%s::text IS NULL OR a.domain=%s)
        """, (query, kind, kind, domain, domain)).fetchall()
    for row in rows:
        lexical = float(row.pop("lexical"))
        popularity = min(1.0, math.log1p(row["query_count_7d"]) / math.log1p(100))
        recency = float(row.pop("recency"))
        affinity = float(bool(team and team in row["user_teams"]))
        components = {"lexical": 0.70 * lexical, "popularity": 0.18 * popularity,
                      "recency": 0.08 * recency, "team_affinity": 0.04 * affinity}
        row["score"] = sum(components.values())
        row["explanation"] = {
            "matched_by": "PostgreSQL english full-text (name A, tags/glossary B, description C)",
            "components": components,
            "features": {"lexical": lexical, "popularity": popularity,
                         "recency": recency, "team_affinity": affinity},
            "usage_scope": "parent table" if row["kind"] == "column" else "asset",
        }
    rows.sort(key=lambda row: (-row["score"], row["id"]))
    return rows[:limit]
