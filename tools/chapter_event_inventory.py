#!/usr/bin/env python3
"""Generate the chapter event inventory markdown file.

The script scans Dragon's Lair chapter XMLs for referenced event types and
compares them against the event object implementations under
``src/object/event``. It writes the refreshed report to
``data/chapter_event_inventory.md``.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
EVENT_DIR = REPO_ROOT / "src" / "object" / "event"
EVENT_DATA_DIR = REPO_ROOT / "data" / "events"
OUTPUT_PATH = REPO_ROOT / "data" / "chapter_event_inventory.md"

# Mapping from chapter name suffixes to the generic event handler that powers
# them. The entries mirror the normalization performed in ``xmlsceneparser.py``
# so coverage stays aligned between documentation and conversion outputs.
MARKER_SUFFIX_MAP: Dict[str, str] = {
    "enter_room_upleft": "room_transition",
    "enter_room_left": "room_transition",
    "enter_room_right": "room_transition",
    "enter_room_up": "room_transition",
    "enter_room_down": "room_transition",
    "enter_room": "room_transition",
    "start_alive": "room_transition",
    "start_dead": "room_transition",
    "burned_to_death": "cutscene",
    "dragons_lair_endgame": "cutscene",
    "fall_to_death": "cutscene",
    "falls_to_death": "cutscene",
    "fell_to_death": "cutscene",
    "attacked_first_hand": "crypt_creeps_encounter",
    "attacked_second_hand": "crypt_creeps_encounter",
    "balls_blue_ball": "rolling_balls_ball",
    "balls_green_ball": "rolling_balls_ball",
    "balls_orange_ball": "rolling_balls_ball",
    "balls_purple_ball": "rolling_balls_ball",
    "balls_red_ball": "rolling_balls_ball",
    "big_ball_crushes": "rolling_balls_crush",
    "bounce_to_chain": "underground_river_chain",
    "captured_by_ghouls": "crypt_creeps_encounter",
    # The generic cutscene event template also defines dedicated classes for
    # exit/game-over stingers even though they are emitted from the cutscene
    # file rather than distinct assembly units.
    "exit_room": "cutscene",
    "game_over": "cutscene",
    "introduction_castle_exterior": "cutscene",
    "mode_attract_movie": "cutscene",
    "mode_insert_coins": "cutscene",
    "pit_in_ground": "cutscene",
    "creeps_enter_crypt": "crypt_creeps_encounter",
    "creeps_jumped_skulls": "crypt_creeps_encounter",
    "creeps_jumped_slime": "crypt_creeps_encounter",
    "crushed_by_hand": "crypt_creeps_encounter",
    "death_by_door": "tentacle_room_grab",
    "eaten_by_skulls": "crypt_creeps_encounter",
    "eaten_by_slime": "crypt_creeps_encounter",
    "flaming_ropes_rope1": "flaming_ropes_route",
    "flaming_ropes_rope2": "flaming_ropes_route",
    "flaming_ropes_rope3": "flaming_ropes_route",
    "goons_climbs_stairs": "giddy_goons_swarm",
    "hit_brick_wall": "flying_horse_collision",
    "horse_brick_wall": "flying_horse_collision",
    "horse_fifth_fire": "flying_horse_lane",
    "horse_fourth_fire": "flying_horse_lane",
    "horse_hit_pillar": "flying_horse_collision",
    "horse_second_fire": "flying_horse_lane",
    "horse_third_fire": "flying_horse_lane",
    "jump_to_door": "tentacle_room_path",
    "jump_to_stairs": "tentacle_room_path",
    "jump_to_table": "tentacle_room_path",
    "kill_upper_goons": "giddy_goons_swarm",
    "kills_first_goon": "giddy_goons_swarm",
    "kills_first_tentacle": "tentacle_room_path",
    "knife_in_back": "giddy_goons_grapple",
    "left_tentacle_grabs": "tentacle_room_grab",
    "long_crash_landing": "falling_platform_phase",
    "long_missed_jump": "falling_platform_phase",
    "one_before_swarm": "giddy_goons_swarm",
    "overpowered_by_skulls": "crypt_creeps_encounter",
    "river_boulders_crash": "underground_river_phase",
    "river_boulders_crash2": "underground_river_phase",
    "river_boulders_crash3": "underground_river_phase",
    "river_boulders_crash4": "underground_river_phase",
    "river_first_boulders": "underground_river_phase",
    "river_first_rapids": "underground_river_phase",
    "river_first_whirlpools": "underground_river_phase",
    "river_fourth_boulders": "underground_river_phase",
    "river_fourth_rapids": "underground_river_phase",
    "river_fourth_whirlpools": "underground_river_phase",
    "river_miss_chain": "underground_river_chain",
    "river_rapids_crash": "underground_river_phase",
    "river_second_boulders": "underground_river_phase",
    "river_second_rapids": "underground_river_phase",
    "river_second_whirlpools": "underground_river_phase",
    "river_third_boulders": "underground_river_phase",
    "river_third_rapids": "underground_river_phase",
    "river_third_whirlpools": "underground_river_phase",
    "river_whirlpools_crash": "underground_river_phase",
    "room_drinks_potion": "cutscene",
    "room_catches_fire": "cutscene",
    "room_electrified_floor": "throne_room_state",
    "room_electrified_sword": "throne_room_state",
    "room_electrified_throne": "throne_room_state",
    "room_first_jump": "throne_room_state",
    "room_jumps_back": "tilting_room_navigation",
    "room_jumps_forward": "tilting_room_navigation",
    "room_on_throne": "cutscene",
    "room_second_jump": "throne_room_state",
    "room_sucked_in": "cutscene",
    "room_wrong_door": "cutscene",
    "ropes_platform_sliding": "flaming_ropes_route",
    "ropes_burns_hands": "cutscene",
    "ropes_misses_landing": "cutscene",
    "second_jump_set": "falling_platform_phase",
    "short_crash_landing": "falling_platform_phase",
    "short_missed_jump": "falling_platform_phase",
    "shoves_off_edge": "giddy_goons_grapple",
    "small_ball_crushes": "rolling_balls_crush",
    "squeeze_to_death": "tentacle_room_grab",
    "swarm_of_goons": "giddy_goons_swarm",
    "third_jump_set": "falling_platform_phase",
    "to_weapon_rack": "tentacle_room_path",
    "two_front_war": "tentacle_room_path",
    "trapped_in_wall": "cutscene",
    "vestibule_stagger": "cutscene",
}

SEQ_MARKER_PATTERN = re.compile(r"_seq(\d+)$")


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


def extract_chapter_marker(chapter_name: str) -> Tuple[str, Optional[str]]:
    """Return the marker suffix for a chapter and its mapped handler.

    The function mirrors the suffix-driven normalization used by
    ``xmlsceneparser.py`` so markers like ``*_enter_room`` and ``*_seq5`` can be
    attributed to ``Event.room_transition`` and ``Event.seq_generic``
    respectively. Any suffix that fails to match a known pattern still returns
    a marker string (typically the trailing three tokens) so missing coverage is
    easy to report.
    """

    cleaned = chapter_name.replace("-", "_")

    # Check explicit suffixes first so more specific variants win before the
    # base ``enter_room``.
    for suffix in sorted(MARKER_SUFFIX_MAP, key=len, reverse=True):
        if cleaned.endswith(f"_{suffix}") or cleaned == suffix:
            return suffix, MARKER_SUFFIX_MAP[suffix]

    seq_match = SEQ_MARKER_PATTERN.search(cleaned)
    if seq_match:
        return f"seq{seq_match.group(1)}", "seq_generic"

    parts = cleaned.split("_")
    if len(parts) >= 3:
        fallback = "_".join(parts[-3:])
    elif len(parts) == 2:
        fallback = "_".join(parts[-2:])
    else:
        fallback = cleaned

    return fallback, None


def collect_chapter_markers() -> Dict[str, Dict[str, object]]:
    """Extract chapter markers and the chapters that reference them."""

    markers: Dict[str, Dict[str, object]] = {}
    for xml_path in EVENT_DATA_DIR.glob("*.xml"):
        tree = ET.parse(xml_path)
        root = tree.getroot()
        chapter_name = (root.get("name") or xml_path.stem).replace("-", "_")

        marker, handler = extract_chapter_marker(chapter_name)
        entry = markers.setdefault(marker, {"chapters": set(), "handler": handler})
        entry["chapters"].add(chapter_name)
        entry.setdefault("handler", handler)

    return markers


def render_markdown(
    chapters_analyzed: int,
    referenced_events: Dict[str, Set[str]],
    chapter_markers: Dict[str, Dict[str, object]],
    implemented_classes: List[str],
) -> str:
    implemented_normalized = {normalize_event_name(name) for name in implemented_classes}
    referenced_missing = {
        event_type: chapters
        for event_type, chapters in referenced_events.items()
        if normalize_event_name(event_type) not in implemented_normalized
    }

    marker_missing = {
        marker: info
        for marker, info in chapter_markers.items()
        if not info.get("handler")
        or normalize_event_name(str(info["handler"])) not in implemented_normalized
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
        f"- Chapter markers referenced: {len(chapter_markers)}",
        f"- Implemented event object types: {len(implemented_classes)}",
        (
            "- Referenced entries without implemented handlers: "
            f"{len(referenced_missing) + len(marker_missing)}"
        ),
        "",
        "## Implemented event object types",
        "",
    ]

    for name in implemented_classes:
        lines.append(f"- {name}")

    lines.append("")
    lines.append("## Chapter marker → event handler mapping")
    lines.append("")
    lines.append("| Chapter marker | Generic handler | Notes |")
    lines.append("| --- | --- | --- |")
    lines.append("| enter_room*, start_* | room_transition | Transition id passed as handler argument |")
    lines.append("| seq* | seq_generic | Sequence id derived from the numeric suffix |")
    lines.append("| exit_room, game_over | cutscene | Uses the cutscene template-defined helpers |")
    lines.append("")

    lines.append("## Referenced chapter event types not implemented")
    lines.append("")

    if referenced_missing or marker_missing:
        for event_type, chapters in sorted(referenced_missing.items()):
            scenes = ", ".join(sorted(chapters))
            lines.append(f"- **{event_type}** – {scenes}")
        for marker, info in sorted(marker_missing.items()):
            scenes = ", ".join(sorted(info["chapters"]))
            handler = info.get("handler")
            handler_note = f" (mapped to {handler})" if handler else ""
            lines.append(f"- **{marker}** – {scenes}{handler_note}")
    else:
        lines.append("- None – every referenced event type has an implementation.")

    lines.append("")
    return "\n".join(lines)


import argparse

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the chapter event inventory markdown file.")
    parser.parse_args()

    implemented_classes = collect_event_classes()
    referenced_events = collect_referenced_events()
    chapter_markers = collect_chapter_markers()
    chapters_analyzed = len(list(EVENT_DATA_DIR.glob("*.xml")))

    markdown = render_markdown(
        chapters_analyzed, referenced_events, chapter_markers, implemented_classes
    )
    OUTPUT_PATH.write_text(markdown, encoding="utf-8")


if __name__ == "__main__":
    main()
