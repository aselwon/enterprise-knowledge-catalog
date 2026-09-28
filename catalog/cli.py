import argparse
import json
import os
from pathlib import Path

from catalog.enrich import enrich
from catalog.evaluate import evaluate
from catalog.ingest import ingest
from catalog.search import search


def main():
    parser = argparse.ArgumentParser(description="Offline metadata pipeline and retrieval evaluation")
    sub = parser.add_subparsers(dest="command", required=True)
    for command, default in [("ingest", "fixtures/warehouse.json"),
                             ("enrich", "fixtures/query_history.json")]:
        sub.add_parser(command).add_argument("--file", default=default)
    query = sub.add_parser("search")
    query.add_argument("query")
    query.add_argument("--kind", choices=["dataset", "table", "column"])
    evaluation = sub.add_parser("eval")
    evaluation.add_argument("--golden", default="fixtures/golden_queries.json")
    evaluation.add_argument("--output", default="reports/eval.json")
    evaluation.add_argument("--min-recall", type=float, default=0.90)
    evaluation.add_argument("--min-mrr", type=float, default=0.85)
    evaluation.add_argument("--max-p95-ms", type=float, default=500)
    sub.add_parser("bootstrap")
    args = parser.parse_args()
    if os.getenv("MOCK_MODE", "true").lower() != "true":
        parser.error("This MVP supports MOCK_MODE=true only; no live warehouse connector")
    if args.command == "ingest":
        result = ingest(args.file)
    elif args.command == "enrich":
        result = enrich(args.file)
    elif args.command == "bootstrap":
        result = {"ingest": ingest("fixtures/warehouse.json"),
                  "enrich": enrich("fixtures/query_history.json")}
    elif args.command == "search":
        result = search(args.query, kind=args.kind)
    else:
        result = evaluate(args.golden)
        result["passed"] = (result["recall_at_5"] >= args.min_recall
                            and result["mrr_at_5"] >= args.min_mrr
                            and result["p95_latency_ms"] <= args.max_p95_ms)
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({k: v for k, v in result.items() if k != "details"}, indent=2))
        raise SystemExit(0 if result["passed"] else 1)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
