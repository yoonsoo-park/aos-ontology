"""Serialize OntologyGraph to _meta/graph.json + _meta/metrics/*.json."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .graph_model import OntologyGraph
from .metrics import MetricsAdapter


def write_graph(
    graph: OntologyGraph,
    output_dir: Path,
    metrics_adapter: MetricsAdapter | None = None,
    process_keys: list[str] | None = None,
) -> dict[str, int]:
    meta_dir = output_dir / "_meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    graph_path = meta_dir / "graph.json"
    graph_path.write_text(
        json.dumps(graph.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    stats = {
        "nodes": len(graph.nodes),
        "edges": len(graph.edges),
        "metrics_files": 0,
    }

    if metrics_adapter and process_keys:
        metrics_dir = meta_dir / "metrics"
        metrics_dir.mkdir(parents=True, exist_ok=True)

        for process_key in process_keys:
            stage_metrics = metrics_adapter.fetch_metrics(process_key)
            if not stage_metrics:
                continue

            overlay = {
                "process_key": process_key,
                "adapter": metrics_adapter.adapter_name(),
                "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "stages": {
                    sm.stage_key: sm.to_dict()
                    for sm in stage_metrics
                },
            }

            metrics_path = metrics_dir / f"{process_key}.json"
            metrics_path.write_text(
                json.dumps(overlay, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            stats["metrics_files"] += 1

    return stats
