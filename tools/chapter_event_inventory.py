#!/usr/bin/env python3
"""Generate the chapter event inventory markdown file.

The script scans Dragon's Lair chapter XMLs for referenced event types and
compares them against the event object implementations under
``src/object/event``. It writes the refreshed report to
``data/chapter_event_inventory.md``.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

REPO_ROOT = Path(__file__).resolve().parent.parent
EVENT_DIR = REPO_ROOT / "src" / "object" / "event"
EVENT_DATA_DIR = REPO_ROOT / "data" / "events"
OUTPUT_PATH = REPO_ROOT / "data" / "chapter_event_inventory.md"


def normalize_event_name(name: str) -> str:
    """Normalize an event name for comparison.

    Hyphens are converted to underscores and generic handlers drop their suffix
    so ``direction_generic`` counts toward ``direction`` coverage.
    """

    cleaned = name.replace("-", "_")
    if cleaned.endswith("_generic"):
        cleaned = cleaned[: -len("_generic")]
    return cleaned


def collect_event_classes() -> List[str]:
    """Return all concrete event class names under ``src/object/event``.

    The list is deduplicated across header/implementation pairs and excludes
    the abstract base, templates, and inheritance helper.
    """

    names: Set[str] = set()
    for path in EVENT_DIR.glob("Event.*"):
        if path.suffix not in {".h", ".65816"}:
            continue

        stem = path.stem
        if not stem.startswith("Event."):
            continue

        name = stem.split(".", 1)[1]
        if name in {"template"}:
            continue
        if name.startswith("abstract"):
            continue

        names.add(name)

    return sorted(names)


def collect_referenced_events() -> Dict[str, Set[str]]:
    """Map referenced event types to the chapters that use them."""

    referenced: Dict[str, Set[str]] = defaultdict(set)
    for xml_path in EVENT_DATA_DIR.glob("*.xml"):
        tree = ET.parse(xml_path)
        root = tree.getroot()
        chapter_name = root.get("name") or xml_path.stem

        for event in root.findall(".//event"):
            event_type = event.get("type")
            if not event_type:
                continue
            referenced[event_type].add(chapter_name)

    return referenced


def render_markdown(
    chapters_analyzed: int,
    referenced_events: Dict[str, Set[str]],
    implemented_classes: List[str],
) -> str:
    implemented_normalized = {normalize_event_name(name) for name in implemented_classes}
    referenced_missing = {
        event_type: chapters
        for event_type, chapters in referenced_events.items()
        if normalize_event_name(event_type) not in implemented_normalized
    }

    lines: List[str] = [
        "# Chapter Script Event Inventory",
        "",
        (
            "This file summarizes the event types referenced in chapter script "
            "resources and compares them with the currently implemented event objects."
        ),
        "",
        "## Summary",
        "",
        f"- Chapters analyzed: {chapters_analyzed}",
        f"- Unique event types referenced: {len(referenced_events)}",
        f"- Implemented event object types: {len(implemented_classes)}",
        f"- Referenced event types not yet implemented: {len(referenced_missing)}",
        "",
        "## Implemented event object types",
        "",
    ]

    for name in implemented_classes:
        lines.append(f"- {name}")

    lines.append("")
    lines.append("## Referenced chapter event types not implemented")
    lines.append("")

    if referenced_missing:
        for event_type, chapters in sorted(referenced_missing.items()):
            scenes = ", ".join(sorted(chapters))
            lines.append(f"- **{event_type}** – {scenes}")
    else:
        lines.append("- None – every referenced event type has an implementation.")

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    implemented_classes = collect_event_classes()
    referenced_events = collect_referenced_events()
    chapters_analyzed = len(list(EVENT_DATA_DIR.glob("*.xml")))

    markdown = render_markdown(chapters_analyzed, referenced_events, implemented_classes)
    OUTPUT_PATH.write_text(markdown, encoding="utf-8")


if __name__ == "__main__":
    main()
