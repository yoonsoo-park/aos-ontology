"""Minimal YAML-like frontmatter parser. No external dependencies."""

from __future__ import annotations

import re


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown text.

    Returns (frontmatter_dict, body_text).
    """
    if not text.startswith("---"):
        return {}, text

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text

    fm_raw = parts[1].strip()
    body = parts[2].strip()
    return _parse_yaml_simple(fm_raw), body


def _parse_yaml_simple(raw: str) -> dict:
    result: dict = {}
    lines = raw.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue

        match = re.match(r"^(\w[\w_]*)\s*:\s*(.*)", line)
        if not match:
            i += 1
            continue

        key = match.group(1)
        value_str = match.group(2).strip()

        if value_str == "" and i + 1 < len(lines) and lines[i + 1].startswith("  "):
            items, i = _parse_nested_list(lines, i + 1)
            result[key] = items
        elif value_str.startswith("[") and value_str.endswith("]"):
            result[key] = _parse_inline_list(value_str)
        elif value_str.startswith('"') and value_str.endswith('"'):
            result[key] = value_str[1:-1]
        elif value_str.lower() in ("true", "false"):
            result[key] = value_str.lower() == "true"
        elif re.match(r"^-?\d+$", value_str):
            result[key] = int(value_str)
        elif re.match(r"^-?\d+\.\d+$", value_str):
            result[key] = float(value_str)
        else:
            result[key] = value_str
        i += 1

    return result


def _parse_inline_list(value_str: str) -> list:
    inner = value_str[1:-1].strip()
    if not inner:
        return []
    return [item.strip() for item in inner.split(",")]


def _parse_nested_list(lines: list[str], start: int) -> tuple[list, int]:
    items: list = []
    i = start
    current_item: dict | None = None

    while i < len(lines):
        line = lines[i]
        if not line.startswith("  "):
            break

        stripped = line.strip()
        if stripped.startswith("- "):
            if current_item is not None:
                items.append(current_item)

            kv = stripped[2:].strip()
            kv_match = re.match(r"^(\w[\w_]*)\s*:\s*(.*)", kv)
            if kv_match:
                current_item = {kv_match.group(1): _coerce_value(kv_match.group(2).strip())}
            else:
                items.append(_coerce_value(kv))
                current_item = None
        elif current_item is not None:
            kv_match = re.match(r"^\s+(\w[\w_]*)\s*:\s*(.*)", stripped)
            if kv_match:
                current_item[kv_match.group(1)] = _coerce_value(kv_match.group(2).strip())
        i += 1

    if current_item is not None:
        items.append(current_item)
    return items, i - 1


def _coerce_value(v: str):
    if v.startswith('"') and v.endswith('"'):
        return v[1:-1]
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    if re.match(r"^-?\d+$", v):
        return int(v)
    return v
