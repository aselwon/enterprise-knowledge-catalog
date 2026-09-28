from catalog.db import connection
from catalog.graph import join_path
from catalog.search import search


def context_pack(query: str, limit=5, team=None):
    ranked = search(query, limit=limit, kind="table", team=team)
    ids = [a["id"] for a in ranked]
    with connection() as conn:
        definitions = conn.execute("""SELECT d.term,d.definition,
            array_agg(da.asset_id ORDER BY da.asset_id) AS asset_ids
            FROM business_definitions d JOIN definition_assets da USING(term)
            WHERE da.asset_id=ANY(%s) GROUP BY d.term,d.definition ORDER BY d.term""", (ids,)).fetchall()
        columns = conn.execute("""SELECT id,parent_id,name,data_type FROM assets
            WHERE kind='column' AND parent_id=ANY(%s) ORDER BY id""", (ids,)).fetchall()
    tables = [{"id": a["id"], "description": a["description"], "score": a["score"],
               "owners": a["owners"], "unused": a["unused"],
               "columns": [{"name": c["name"], "type": c["data_type"]}
                           for c in columns if c["parent_id"] == a["id"]][:12]} for a in ranked]
    joins = []
    bridge_ids = set()
    for i, source in enumerate(ids):
        for target in ids[i + 1:]:
            path = join_path(source, target)
            if path["found"]:
                joins.append(path)
                bridge_ids.update(set(path["nodes"]) - set(ids))
    with connection() as conn:
        bridges = conn.execute("SELECT id,description FROM assets WHERE id=ANY(%s) ORDER BY id",
                               (sorted(bridge_ids),)).fetchall()
    return {"query": query, "tables": tables, "definitions": definitions,
            "joins": joins, "bridge_tables": bridges,
            "constraints": {"max_tables": limit, "max_join_hops": 3,
                            "max_columns_per_table": 12, "metadata_only": True}}
