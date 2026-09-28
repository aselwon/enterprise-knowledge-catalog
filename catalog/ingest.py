import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from catalog.db import connection, migrate


class Asset(BaseModel):
    id: str = Field(min_length=1)
    kind: Literal["dataset", "table", "column"]
    name: str = Field(min_length=1)
    data_type: str
    description: str
    domain: str
    parent_id: str | None = None
    owners: list[str] = []
    tags: list[str] = []


class Edge(BaseModel):
    source_id: str
    target_id: str
    kind: Literal["lineage", "join", "same_concept"]
    description: str
    source_column: str | None = None
    target_column: str | None = None


class Definition(BaseModel):
    term: str
    definition: str
    asset_ids: list[str]


class Warehouse(BaseModel):
    assets: list[Asset]
    edges: list[Edge]
    definitions: list[Definition]

    @model_validator(mode="after")
    def valid_references(self):
        assets = {a.id: a for a in self.assets}
        if len(assets) != len(self.assets):
            raise ValueError("Duplicate asset ID")
        for asset in self.assets:
            expected = {"table": "dataset", "column": "table"}.get(asset.kind)
            parent = assets.get(asset.parent_id)
            if expected and (not parent or parent.kind != expected):
                raise ValueError(f"Invalid parent for {asset.id}")
            if asset.kind == "dataset" and asset.parent_id is not None:
                raise ValueError("Dataset must be a root")
        edge_keys = set()
        for edge in self.edges:
            key = (edge.source_id, edge.target_id, edge.kind)
            if key in edge_keys or edge.source_id == edge.target_id:
                raise ValueError("Duplicate edge or self edge")
            edge_keys.add(key)
            if edge.source_id not in assets or edge.target_id not in assets:
                raise ValueError("Unknown edge endpoint")
            if edge.kind == "join":
                for table_id, column in [(edge.source_id, edge.source_column),
                                         (edge.target_id, edge.target_column)]:
                    if assets[table_id].kind != "table" or not column:
                        raise ValueError("Join requires tables and columns")
                    child = assets.get(f"{table_id}.{column}")
                    if not child or child.parent_id != table_id:
                        raise ValueError("Unknown join column")
        terms = [d.term for d in self.definitions]
        if len(terms) != len(set(terms)):
            raise ValueError("Duplicate glossary term")
        if any(i not in assets for d in self.definitions for i in d.asset_ids):
            raise ValueError("Unknown definition asset")
        return self


def ingest(path: str | Path):
    warehouse = Warehouse.model_validate_json(Path(path).read_text())
    migrate()
    glossary = {}
    for definition in warehouse.definitions:
        for asset_id in definition.asset_ids:
            glossary.setdefault(asset_id, []).append(f"{definition.term} {definition.definition}")
    with connection() as conn:
        for asset in warehouse.assets:
            values = asset.model_dump()
            values["terms"] = " ".join(glossary.get(asset.id, []))
            values["tag_text"] = " ".join(asset.tags)
            conn.execute("""
                INSERT INTO assets
                  (id,kind,name,data_type,description,domain,parent_id,owners,tags,search_document)
                VALUES (%(id)s,%(kind)s,%(name)s,%(data_type)s,%(description)s,%(domain)s,
                        %(parent_id)s,%(owners)s,%(tags)s,
                  setweight(to_tsvector('english', replace(%(name)s, '_', ' ')), 'A') ||
                  setweight(to_tsvector('english', %(tag_text)s || ' ' || %(terms)s), 'B') ||
                  setweight(to_tsvector('english', %(description)s), 'C'))
                ON CONFLICT (id) DO UPDATE SET
                  kind=excluded.kind,name=excluded.name,data_type=excluded.data_type,
                  description=excluded.description,domain=excluded.domain,
                  parent_id=excluded.parent_id,owners=excluded.owners,tags=excluded.tags,
                  search_document=excluded.search_document
            """, values)
        for edge in warehouse.edges:
            conn.execute("""
                INSERT INTO edges VALUES (%(source_id)s,%(target_id)s,%(kind)s,
                    %(description)s,%(source_column)s,%(target_column)s)
                ON CONFLICT (source_id,target_id,kind) DO UPDATE SET
                    description=excluded.description,source_column=excluded.source_column,
                    target_column=excluded.target_column
            """, edge.model_dump())
        for definition in warehouse.definitions:
            conn.execute("""INSERT INTO business_definitions VALUES (%s,%s)
                ON CONFLICT (term) DO UPDATE SET definition=excluded.definition""",
                         (definition.term, definition.definition))
            conn.execute("DELETE FROM definition_assets WHERE term=%s", (definition.term,))
            for asset_id in definition.asset_ids:
                conn.execute("INSERT INTO definition_assets VALUES (%s,%s)",
                             (definition.term, asset_id))
    return {"assets": len(warehouse.assets), "tables": sum(a.kind == "table" for a in warehouse.assets),
            "edges": len(warehouse.edges), "definitions": len(warehouse.definitions)}


if __name__ == "__main__":
    print(json.dumps(ingest("fixtures/warehouse.json")))
