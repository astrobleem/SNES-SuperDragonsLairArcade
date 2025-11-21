"""Convert DirkSimple game.lua scenes into per-sequence XML chapters.

This script mirrors the timing helpers in ``tools/game.lua`` and reuses the
Lua parser from ``game_lua_to_json.py`` to expand the ``scenes`` table. Each
sequence becomes a chapter XML that follows ``data/events/README.md`` so it can
feed the original RoadBlaster/Dragon's Lair conversion tooling.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Iterable, Mapping, MutableMapping, Optional, Tuple
import xml.etree.ElementTree as ET

from game_lua_to_json import parse_scenes

# Timing helpers duplicated from tools/game.lua
FRAME_RATE = 23.976


def laserdisc_frame_to_ms(frame: float) -> float:
    return (frame / FRAME_RATE) * 1000.0


def time_laserdisc_frame(frame: float) -> float:
    return laserdisc_frame_to_ms(frame) - 6297.0


def time_laserdisc_noseek() -> int:
    return -1


def time_to_ms(*parts: float) -> float:
    if len(parts) == 2:
        seconds, milliseconds = parts
        return (seconds * 1000.0) + milliseconds
    if len(parts) == 3:
        minutes, seconds, milliseconds = parts
        return ((minutes * 60.0) + seconds) * 1000.0 + milliseconds
    raise ValueError(f"Unsupported time_to_ms arity: {len(parts)}")


TimingFnMap = {
    "laserdisc_frame_to_ms": laserdisc_frame_to_ms,
    "time_laserdisc_frame": time_laserdisc_frame,
    "time_laserdisc_noseek": time_laserdisc_noseek,
    "time_to_ms": time_to_ms,
}


# XML helpers

def ms_to_parts(ms: float) -> Tuple[int, int, int]:
    if ms < 0:
        ms = 0
    total_ms = int(round(ms))
    minutes, remainder = divmod(total_ms, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return minutes, seconds, milliseconds


def append_timeline(parent: ET.Element, start_ms: float, end_ms: Optional[float] = None) -> None:
    timeline = ET.SubElement(parent, "timeline")
    min_start, sec_start, ms_start = ms_to_parts(start_ms)
    ET.SubElement(
        timeline,
        "timestart",
        {
            "min": str(min_start),
            "second": str(sec_start),
            "ms": str(ms_start),
        },
    )
    if end_ms is not None:
        min_end, sec_end, ms_end = ms_to_parts(end_ms)
        ET.SubElement(
            timeline,
            "timeend",
            {
                "min": str(min_end),
                "second": str(sec_end),
                "ms": str(ms_end),
            },
        )


def add_params(parent: ET.Element, params: Mapping[str, object]) -> None:
    params_elem = ET.SubElement(parent, "params")
    for key, value in params.items():
        if isinstance(value, bool):
            value_int = 1 if value else 0
            ET.SubElement(params_elem, "int", {"key": key, "value": str(value_int)})
        elif isinstance(value, (int, float)):
            ET.SubElement(params_elem, "int", {"key": key, "value": str(int(value))})
        else:
            ET.SubElement(params_elem, "str", {"key": key, "value": str(value)})


def indent(elem: ET.Element, level: int = 0) -> None:
    """Pretty-print helper for ElementTree (Python 3.8 compatible)."""

    indent_str = "\n" + (level * "\t")
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent_str + "\t"
        for child in elem:
            indent(child, level + 1)
        if not child.tail or not child.tail.strip():  # type: ignore[name-defined]
            child.tail = indent_str
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = indent_str


# Conversion logic

def chapter_name(scene: str, sequence: str) -> str:
    return f"{scene}_{sequence}"


def resolve_next(scene: str, sequences: Iterable[str], destination: Optional[object]) -> Optional[str]:
    if not isinstance(destination, str):
        return None
    if destination in sequences:
        return chapter_name(scene, destination)
    return destination


def build_chapter(scene: str, sequence: str, data: MutableMapping[str, object], known_sequences: Iterable[str]) -> ET.Element:
    start_time = float(data.get("start_time", 0))
    timeout = data.get("timeout", {}) or {}
    assert isinstance(timeout, Mapping)
    duration = float(timeout.get("when", 0))
    end_time = start_time + duration if duration else start_time

    chapter = ET.Element("chapter", {"name": chapter_name(scene, sequence)})
    append_timeline(chapter, start_time, end_time)

    params: Dict[str, object] = {}
    if data.get("kills_player"):
        params["kills_player"] = 1
    if params:
        add_params(chapter, params)
    else:
        ET.SubElement(chapter, "params")

    ET.SubElement(chapter, "macros")

    events_elem = ET.SubElement(chapter, "events")
    # Chapter entry checkpoint
    checkpoint = ET.SubElement(events_elem, "event", {"type": "checkpoint"})
    append_timeline(checkpoint, start_time)

    actions = data.get("actions", []) or []
    if isinstance(actions, list):
        for index, action in enumerate(actions, start=1):
            if not isinstance(action, Mapping):
                continue
            input_type = action.get("input")
            if not isinstance(input_type, str):
                continue
            action_start = start_time + float(action.get("from", 0))
            action_end = start_time + float(action.get("to", action.get("from", 0)))

            event = ET.SubElement(
                events_elem,
                "event",
                {
                    "type": "direction",
                    "automacro": input_type,
                    "label": f"action-{index}",
                },
            )
            append_timeline(event, action_start, action_end)

            params_elem = ET.SubElement(event, "params")
            ET.SubElement(params_elem, "str", {"key": "type", "value": input_type})
            points = action.get("points")
            if isinstance(points, (int, float)):
                ET.SubElement(params_elem, "int", {"key": "score", "value": str(int(points))})

            next_dest = resolve_next(scene, known_sequences, action.get("nextsequence"))
            if next_dest:
                result = ET.SubElement(event, "result", {"value": "0"})
                ET.SubElement(result, "playchapter", {"name": next_dest})

    next_seq = resolve_next(scene, known_sequences, timeout.get("nextsequence"))
    if next_seq:
        result = ET.SubElement(chapter, "result")
        ET.SubElement(result, "playchapter", {"name": next_seq})

    return chapter


def write_chapter(path: Path, element: ET.Element) -> None:
    indent(element)
    tree = ET.ElementTree(element)
    path.write_text(ET.tostring(element, encoding="unicode"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert tools/game.lua scenes into XML chapters")
    parser.add_argument("--input", default="tools/game.lua", help="Path to the game.lua source")
    parser.add_argument("--output-dir", required=True, help="Directory to write XML chapters")
    args = parser.parse_args()

    scenes = parse_scenes(Path(args.input).read_text())

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for scene_name, scene_data in scenes.items():
        if not isinstance(scene_data, Mapping):
            continue
        sequences = [name for name in scene_data.keys() if isinstance(name, str)]
        for sequence_name, sequence_data in scene_data.items():
            if not isinstance(sequence_data, MutableMapping):
                continue
            chapter = build_chapter(scene_name, sequence_name, sequence_data, sequences)
            write_chapter(output_dir / f"{chapter_name(scene_name, sequence_name)}.xml", chapter)


if __name__ == "__main__":
    main()
