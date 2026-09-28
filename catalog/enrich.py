from datetime import datetime, timedelta
from pathlib import Path

from pydantic import AwareDatetime, BaseModel, model_validator

from catalog.db import connection


class QueryEvent(BaseModel):
    query_id: str
    occurred_at: AwareDatetime
    asset_ids: list[str]
    team: str


class QueryHistory(BaseModel):
    as_of: AwareDatetime
    queries: list[QueryEvent]

    @model_validator(mode="after")
    def unique_queries(self):
        ids = [q.query_id for q in self.queries]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate query_id in history")
        return self


def enrich(path: str | Path, as_of: datetime | None = None):
    history = QueryHistory.model_validate_json(Path(path).read_text())
    clock = as_of or history.as_of
    if clock.tzinfo is None:
        raise ValueError("as_of must include timezone")
    window = clock - timedelta(days=7)
    with connection() as conn:
        tables = {a["id"] for a in conn.execute("SELECT id FROM assets WHERE kind='table'")}
        unknown = {i for event in history.queries for i in event.asset_ids} - tables
        if unknown:
            raise ValueError(f"Unknown table references: {sorted(unknown)}")
        signals = {i: {"count": 0, "last_seen": None, "teams": set()} for i in tables}
        for event in history.queries:
            if event.occurred_at > clock:
                continue
            for asset_id in set(event.asset_ids):
                signal = signals[asset_id]
                signal["last_seen"] = max(signal["last_seen"] or event.occurred_at, event.occurred_at)
                if window <= event.occurred_at:
                    signal["count"] += 1
                    signal["teams"].add(event.team)
        for asset_id, signal in signals.items():
            conn.execute("""INSERT INTO usage_signals VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT (asset_id) DO UPDATE SET query_count_7d=excluded.query_count_7d,
                last_seen=excluded.last_seen,user_teams=excluded.user_teams,
                unused=excluded.unused,as_of=excluded.as_of""",
                         (asset_id, signal["count"], signal["last_seen"], sorted(signal["teams"]),
                          signal["count"] == 0, clock))
    return {"tables": len(signals), "unused": sum(s["count"] == 0 for s in signals.values()),
            "as_of": clock.isoformat()}
