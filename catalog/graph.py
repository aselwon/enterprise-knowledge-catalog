from collections import deque

from catalog.db import connection


class AssetNotFound(ValueError):
    pass


def require_asset(conn, asset_id):
    row = conn.execute("SELECT id,kind,name,description FROM assets WHERE id=%s", (asset_id,)).fetchone()
    if not row:
        raise AssetNotFound(asset_id)
    return row


def neighbors(asset_id: str, direction="both", kind=None):
    with connection() as conn:
        asset = require_asset(conn, asset_id)
        edges = conn.execute("""SELECT * FROM edges
            WHERE ((%s IN ('both','outgoing') AND source_id=%s)
                OR (%s IN ('both','incoming') AND target_id=%s))
              AND (%s::text IS NULL OR kind=%s)
            ORDER BY kind,source_id,target_id""",
                             (direction, asset_id, direction, asset_id, kind, kind)).fetchall()
        ids = sorted({e[k] for e in edges for k in ("source_id", "target_id")} - {asset_id})
        nodes = conn.execute("SELECT id,kind,name,description FROM assets WHERE id=ANY(%s) ORDER BY id",
                             (ids,)).fetchall()
    return {"asset": asset, "nodes": nodes, "edges": edges}


def join_path(source: str, target: str, max_depth=3):
    if not 1 <= max_depth <= 3:
        raise ValueError("max_depth must be between 1 and 3")
    with connection() as conn:
        for asset_id in [source, target]:
            if require_asset(conn, asset_id)["kind"] != "table":
                raise ValueError("Join paths require table assets")
        if source == target:
            return {"found": True, "nodes": [source], "edges": [], "length": 0}
        queue = deque([(source, [source], [])])
        visited = {source}
        while queue:
            current, nodes, path = queue.popleft()
            if len(path) >= max_depth:
                continue
            adjacent = conn.execute("""SELECT * FROM edges WHERE kind='join'
                AND (source_id=%s OR target_id=%s) ORDER BY source_id,target_id""",
                                    (current, current)).fetchall()
            for edge in adjacent:
                next_id = edge["target_id"] if edge["source_id"] == current else edge["source_id"]
                if next_id in visited:
                    continue
                new_path = path + [edge]
                new_nodes = nodes + [next_id]
                if next_id == target:
                    return {"found": True, "nodes": new_nodes, "edges": new_path, "length": len(new_path)}
                visited.add(next_id)
                queue.append((next_id, new_nodes, new_path))
    return {"found": False, "nodes": [], "edges": [], "length": None}
