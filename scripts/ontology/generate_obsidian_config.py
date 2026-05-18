"""Generate .obsidian/ configuration for the ontology vault."""

from __future__ import annotations

import json
from pathlib import Path


_COLOR_PALETTE = [
    "#3b82f6", "#ef4444", "#f59e0b", "#8b5cf6", "#ec4899",
    "#06b6d4", "#84cc16", "#f97316", "#6366f1", "#14b8a6",
    "#e11d48", "#a855f7", "#0ea5e9", "#d946ef", "#22c55e",
    "#eab308", "#64748b", "#fb923c", "#2dd4bf", "#c084fc",
    "#f43f5e", "#38bdf8", "#4ade80", "#facc15", "#a78bfa",
    "#fb7185", "#34d399", "#fbbf24", "#818cf8", "#2563eb",
    "#dc2626", "#059669", "#d97706", "#7c3aed", "#db2777",
    "#0891b2", "#65a30d", "#ea580c", "#4f46e5", "#10b981",
]


def _domain_color(domain: str, index: int) -> str:
    return _COLOR_PALETTE[index % len(_COLOR_PALETTE)]


def _hex_to_rgb(hex_color: str) -> int:
    h = hex_color.lstrip("#")
    return int(h, 16)


def _generate_graph_css(domains: list[str]) -> str:
    lines = ["/* Ontology Graph — domain-based tag coloring */", ""]
    for i, domain in enumerate(sorted(domains)):
        color = _domain_color(domain, i)
        lines.append(f'.graph-view.color-fill-tag[data-tag="{domain}"] {{ color: {color}; }}')
    lines.append("")
    lines.append("/* Process bottleneck severity */")
    lines.append('.graph-view.color-fill-tag[data-tag="process"] { color: #f59e0b; }')
    return "\n".join(lines)


def write_obsidian_config(output_dir: Path, domains: list[str]) -> None:
    obsidian_dir = output_dir / ".obsidian"
    snippets_dir = obsidian_dir / "snippets"
    snippets_dir.mkdir(parents=True, exist_ok=True)

    (snippets_dir / "ontology-graph.css").write_text(
        _generate_graph_css(domains), encoding="utf-8"
    )

    (obsidian_dir / "appearance.json").write_text(
        json.dumps({
            "accentColor": "#3b82f6",
            "enabledCssSnippets": ["ontology-graph"],
        }, indent=2),
        encoding="utf-8",
    )

    (obsidian_dir / "community-plugins.json").write_text(
        json.dumps(["dataview", "obsidian-charts", "ontology-explorer"], indent=2),
        encoding="utf-8",
    )

    color_groups = [
        {"query": "tag:#process", "color": {"a": 1, "rgb": _hex_to_rgb("#f59e0b")}},
    ]
    for i, domain in enumerate(sorted(domains)):
        color = _domain_color(domain, i)
        color_groups.append({
            "query": f"tag:#{domain}",
            "color": {"a": 1, "rgb": _hex_to_rgb(color)},
        })

    (obsidian_dir / "graph.json").write_text(
        json.dumps({
            "collapse-filter": False,
            "search": "",
            "showTags": True,
            "showAttachments": False,
            "hideUnresolved": False,
            "showOrphans": True,
            "collapse-color-groups": False,
            "colorGroups": color_groups,
            "collapse-display": False,
            "showArrow": True,
            "textFadeMultiplier": 0,
            "nodeSizeMultiplier": 1.1,
            "lineSizeMultiplier": 1,
            "collapse-forces": True,
            "centerStrength": 0.5,
            "repelStrength": 10,
            "linkStrength": 1,
            "linkDistance": 250,
            "scale": 1,
            "close": False,
        }, indent=2),
        encoding="utf-8",
    )

    (obsidian_dir / "app.json").write_text(
        json.dumps({
            "showLineNumber": True,
            "strictLineBreaks": False,
            "readableLineLength": True,
        }, indent=2),
        encoding="utf-8",
    )
