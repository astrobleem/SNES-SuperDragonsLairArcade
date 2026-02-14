#!/usr/bin/env python3
"""Generate XML event files from DirkSimple game.lua.

Reads the scene data and scene_manager.rows from game.lua and generates
one XML file per scene+sequence (chapter), matching the format expected
by xmlsceneparser.py.

Usage:
    python3 tools/lua_scene_exporter.py --input data/game.lua --outfolder data/events
"""

import argparse
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logging.basicConfig(level=logging.INFO, format='%(message)s')

Token = Union[str, int, float, bool, None, Tuple[str, str]]


# ============ Time conversion functions matching game.lua ============

def laserdisc_frame_to_ms(frame: float) -> float:
    return (frame / 23.976) * 1000.0


def time_laserdisc_frame(frame: float) -> float:
    return laserdisc_frame_to_ms(frame) - 6297.0


def time_laserdisc_noseek() -> float:
    return -1.0


def time_to_ms(seconds: float, ms: float) -> float:
    return seconds * 1000 + ms


# ============ Name abbreviation ============
# wla-dx has a 63-byte limit on .include paths. With the path structure
# .include "data/chapters/{NAME}/chapter.script" (41 chars overhead),
# chapter names must be <= 22 chars. ALL scene names abbreviated to <= 4 chars,
# all long sequence names abbreviated to <= 17 chars. Max: 4 + 1 + 17 = 22.

SCENE_ABBREVS = {
    'alice_room': 'alrm',
    'attract_mode': 'atmd',
    'black_knight': 'bknt',
    'bower': 'bowr',
    'bubbling_cauldron': 'bcld',
    'catwalk_bats': 'cwbt',
    'crypt_creeps': 'cc',
    'crypt_creeps_reversed': 'ccr',
    'electric_cage_and_geyser': 'ecag',
    'falling_platform_long': 'fpl',
    'falling_platform_long_reversed': 'fplr',
    'falling_platform_short': 'fps',
    'fire_room': 'firm',
    'flaming_ropes': 'flrp',
    'flaming_ropes_reversed': 'flrr',
    'flattening_staircase': 'fstc',
    'flying_horse': 'fh',
    'flying_horse_reversed': 'fhr',
    'giant_bat': 'gbat',
    'giddy_goons': 'gg',
    'grim_reaper': 'gr',
    'grim_reaper_reversed': 'grr',
    'introduction': 'intr',
    'lizard_king': 'lzkg',
    'mudmen': 'mudm',
    'robot_knight': 'rk',
    'robot_knight_reversed': 'rkr',
    'rolling_balls': 'rbal',
    'smithee': 'sm',
    'smithee_reversed': 'smr',
    'snake_room': 'snkr',
    'tentacle_room': 'tntr',
    'the_dragons_lair': 'tdl',
    'throne_room': 'thrn',
    'tilting_room': 'tltr',
    'underground_river': 'ugr',
    'vestibule': 'vest',
    'wind_room': 'wndr',
    'yellow_brick_road': 'ybr',
    'yellow_brick_road_reversed': 'ybrr',
}

# Sequence-level abbreviations for names > 17 chars
SEQ_ABBREVS = {
    'fight_off_one_before_swarm': 'fight_b4_swarm',     # 26->14
    'squeeze_to_death_by_door': 'sq_death_door',         # 24->13
    'overpowered_by_skulls': 'skull_overpower',          # 21->15
    'kills_first_tentacle': 'kill_1st_tent',             # 20->13
    'attacked_second_hand': 'atk_2nd_hand',              # 20->12
    'left_tentacle_grabs': 'left_tent_grab',             # 19->14
    'jump_to_weapon_rack': 'jmp_weap_rack',              # 19->13
    'attacked_first_hand': 'atk_1st_hand',               # 19->12
    'captured_by_ghouls': 'ghoul_capture',               # 18->13
    'electrified_throne': 'elec_throne',                 # 18->11
    'small_ball_crushes': 'sm_ball_crush',               # 18->13
}

MAX_CHAPTER_NAME = 22  # 63 - 41 overhead


def abbreviate_scene(scene_name: str) -> str:
    """Abbreviate a scene name."""
    return SCENE_ABBREVS.get(scene_name, scene_name)


def abbreviate_seq(seq_name: str) -> str:
    """Abbreviate a sequence name."""
    return SEQ_ABBREVS.get(seq_name, seq_name)


def make_chapter_name(scene_name: str, seq_name: str) -> str:
    """Create an abbreviated chapter name from scene + sequence."""
    name = f'{abbreviate_scene(scene_name)}_{abbreviate_seq(seq_name)}'
    if len(name) > MAX_CHAPTER_NAME:
        raise ValueError(
            f'Chapter name too long ({len(name)} > {MAX_CHAPTER_NAME}): {name} '
            f'(from {scene_name}_{seq_name}). Add abbreviation entries.'
        )
    return name


# ============ Lua preprocessing ============

def strip_comments(text: str) -> str:
    """Remove Lua single-line and multi-line comments."""
    # Remove multi-line comments --[[ ... ]]
    text = re.sub(r'--\[\[.*?\]\]', '', text, flags=re.DOTALL)
    # Remove single-line comments
    return "\n".join(line.split("--", 1)[0] for line in text.splitlines())


def preprocess_functions(text: str) -> str:
    """Evaluate Lua function calls to numeric values."""

    # time_laserdisc_noseek() — no args
    text = text.replace('time_laserdisc_noseek()', str(time_laserdisc_noseek()))

    # Only match function CALLS with numeric arguments, not function definitions
    # Pattern: function_name( digits/commas/spaces/dots/minus )

    # time_to_ms(S, MS) or time_to_ms(S, MS, X) — 3rd arg ignored by Lua
    def eval_time_to_ms(m: re.Match) -> str:
        args = m.group(1).split(',')
        s = float(args[0].strip())
        ms = float(args[1].strip())
        return str(time_to_ms(s, ms))
    text = re.sub(r'time_to_ms\(([\d\s,.\-]+)\)', eval_time_to_ms, text)

    # time_laserdisc_frame(N)
    def eval_time_laserdisc_frame(m: re.Match) -> str:
        frame = float(m.group(1).strip())
        return str(time_laserdisc_frame(frame))
    text = re.sub(r'time_laserdisc_frame\(([\d\s.\-]+)\)', eval_time_laserdisc_frame, text)

    # laserdisc_frame_to_ms(N)
    def eval_laserdisc_frame_to_ms(m: re.Match) -> str:
        frame = float(m.group(1).strip())
        return str(laserdisc_frame_to_ms(frame))
    text = re.sub(r'laserdisc_frame_to_ms\(([\d\s.\-]+)\)', eval_laserdisc_frame_to_ms, text)

    # Evaluate simple arithmetic: number +/- number
    # Require whitespace before the operator to avoid matching unary minus
    for _ in range(50):
        new_text = re.sub(
            r'(-?\d+\.?\d*(?:e[+-]?\d+)?)\s+([+-])\s*(\d+\.?\d*(?:e[+-]?\d+)?)',
            lambda m: str(
                float(m.group(1)) + float(m.group(3)) if m.group(2) == '+'
                else float(m.group(1)) - float(m.group(3))
            ),
            text, count=1
        )
        if new_text == text:
            break
        text = new_text

    return text


# ============ Tokenizer ============

def tokenize(content: str) -> List[Token]:
    tokens: List[Token] = []
    i = 0
    while i < len(content):
        ch = content[i]
        if ch.isspace():
            i += 1
            continue

        if ch in "{}=,":
            tokens.append(ch)
            i += 1
            continue

        # Strings: double or single quoted
        if ch in ('"', "'"):
            quote = ch
            j = i + 1
            value_chars: List[str] = []
            while j < len(content):
                if content[j] == "\\":
                    if j + 1 < len(content):
                        value_chars.append(content[j + 1])
                        j += 2
                        continue
                if content[j] == quote:
                    break
                value_chars.append(content[j])
                j += 1
            tokens.append("".join(value_chars))
            i = j + 1
            continue

        # Numbers: integer or float, possibly negative
        if ch.isdigit() or (ch == '.' and i + 1 < len(content) and content[i + 1].isdigit()) or \
           (ch == '-' and i + 1 < len(content) and (content[i + 1].isdigit() or content[i + 1] == '.')):
            j = i + 1
            has_dot = (ch == '.')
            while j < len(content) and (content[j].isdigit() or (content[j] == '.' and not has_dot)):
                if content[j] == '.':
                    has_dot = True
                j += 1
            # Handle scientific notation (e.g. 1.23e-4)
            if j < len(content) and content[j] in ('e', 'E'):
                j += 1
                if j < len(content) and content[j] in ('+', '-'):
                    j += 1
                while j < len(content) and content[j].isdigit():
                    j += 1
                has_dot = True  # treat as float
            numstr = content[i:j]
            if has_dot:
                tokens.append(float(numstr))
            else:
                tokens.append(int(numstr))
            i = j
            continue

        # Identifiers and keywords
        if ch.isalpha() or ch == '_':
            j = i + 1
            while j < len(content) and (content[j].isalnum() or content[j] == '_'):
                j += 1
            ident = content[i:j]
            if ident == "true":
                tokens.append(True)
            elif ident == "false":
                tokens.append(False)
            elif ident == "nil":
                tokens.append(None)
            else:
                tokens.append(("IDENT", ident))
            i = j
            continue

        # Skip unrecognized characters (parentheses, brackets, etc.)
        i += 1

    return tokens


# ============ Parser ============

def parse_value(tokens: List[Token], position: int) -> Tuple[Any, int]:
    tok = tokens[position]
    if tok == "{":
        return parse_table(tokens, position)
    if isinstance(tok, tuple) and tok[0] == "IDENT":
        return tok[1], position + 1
    return tok, position + 1


def parse_table(tokens: List[Token], position: int) -> Tuple[Any, int]:
    assert tokens[position] == "{"
    position += 1
    entries: List[Any] = []
    keyed = False

    while position < len(tokens) and tokens[position] != "}":
        if tokens[position] == ",":
            position += 1
            continue

        # Check for key = value (identifier key)
        if (position + 1 < len(tokens) and tokens[position + 1] == "=" and
                isinstance(tokens[position], tuple) and tokens[position][0] == "IDENT"):
            key = tokens[position][1]
            position += 2  # skip key and =
            value, position = parse_value(tokens, position)
            entries.append((key, value))
            keyed = True
        else:
            value, position = parse_value(tokens, position)
            entries.append(value)

        if position < len(tokens) and tokens[position] == ",":
            position += 1

    position += 1  # consume closing brace

    if keyed:
        table: Dict[str, Any] = {}
        for entry in entries:
            if isinstance(entry, tuple) and len(entry) == 2:
                key, value = entry
                table[str(key)] = value
        return table, position

    return entries, position


# ============ Scene parsing ============

def parse_scenes(lua_text: str) -> Dict[str, Any]:
    """Parse the scenes table from preprocessed Lua text."""
    match = re.search(r'scenes\s*=\s*\{', lua_text)
    if not match:
        raise ValueError("Could not locate scenes table in Lua source")

    brace_start = lua_text.find("{", match.start())
    tokens = tokenize(lua_text[brace_start:])
    scenes, _ = parse_table(tokens, 0)
    if not isinstance(scenes, dict):
        raise ValueError("Scenes table did not parse into a dictionary")
    return scenes


def parse_scene_manager_rows(lua_text: str) -> List[List[str]]:
    """Parse scene_manager.rows table from Lua text."""
    match = re.search(r'rows\s*=\s*\{', lua_text)
    if not match:
        raise ValueError("Could not locate scene_manager.rows table")

    brace_start = lua_text.find("{", match.start())
    tokens = tokenize(lua_text[brace_start:])
    rows, _ = parse_table(tokens, 0)

    if not isinstance(rows, list):
        raise ValueError("rows did not parse into a list")

    return rows


# ============ Scene order ============

def build_scene_order(rows: List[List[str]]) -> Dict[str, str]:
    """Build deterministic scene progression from rows.

    Iterates rows top-to-bottom, columns left-to-right, skipping duplicates.
    Returns dict mapping scene_name -> next_scene_name.
    Introduction is always first; the_dragons_lair exit -> title_screen.
    """
    # Flatten rows left-to-right, row-by-row, skipping duplicates
    linear: List[str] = []
    seen: set = set()
    for row in rows:
        if not isinstance(row, list):
            continue
        for scene in row:
            if scene not in seen:
                linear.append(scene)
                seen.add(scene)

    # Build next-scene mapping
    order: Dict[str, str] = {}

    # Introduction -> first scene in rows
    if linear:
        order['introduction'] = linear[0]

    # Each scene -> next scene in linear order
    for i in range(len(linear) - 1):
        order[linear[i]] = linear[i + 1]

    # Last scene (the_dragons_lair) -> title_screen (endgame)
    if linear:
        order[linear[-1]] = 'title_screen'

    # attract_mode -> title_screen
    order['attract_mode'] = 'title_screen'

    return order


# ============ Result derivation ============

def derive_chapter_result(scene_name: str, sequence: Dict, scene_order: Dict[str, str]) -> Tuple[str, str]:
    """Derive the chapter-level <result> for a sequence timeout."""
    timeout = sequence.get('timeout', {})
    if not isinstance(timeout, dict):
        return ('none', 'none')

    next_seq = timeout.get('nextsequence')
    kills = sequence.get('kills_player', False)
    interrupt = timeout.get('interrupt')

    if interrupt:
        if interrupt == 'game_over_complete':
            return ('lastcheckpoint', 'none')
        elif interrupt == 'start_game':
            return ('playchapter', 'title_screen')
        else:
            return ('lastcheckpoint', 'none')
    elif next_seq:
        return ('playchapter', make_chapter_name(scene_name, next_seq))
    elif kills:
        return ('lastcheckpoint', 'none')
    else:
        # Scene exit — find next scene
        next_scene = scene_order.get(scene_name)
        if next_scene:
            # title_screen is an assembly Script, not a generated chapter
            if next_scene == 'title_screen':
                return ('playchapter', 'title_screen')
            return ('playchapter', make_chapter_name(next_scene, 'start_alive'))
        else:
            return ('lastcheckpoint', 'none')


def derive_action_result(scene_name: str, action: Dict) -> Tuple[str, str]:
    """Derive the <result> for an event action."""
    interrupt = action.get('interrupt')
    next_seq = action.get('nextsequence')

    if interrupt:
        if interrupt == 'start_game':
            return ('playchapter', 'title_screen')
        elif interrupt == 'game_over_complete':
            return ('lastcheckpoint', 'none')
        else:
            return ('none', 'none')
    elif next_seq:
        return ('playchapter', make_chapter_name(scene_name, next_seq))
    else:
        return ('none', 'none')


# ============ XML generation ============

def ms_to_attrs(total_ms: float) -> str:
    """Convert milliseconds to min/second/ms XML attributes."""
    if total_ms < 0:
        total_ms = 0
    total_ms = round(total_ms)
    minutes = int(total_ms // 60000)
    seconds = int((total_ms % 60000) // 1000)
    ms = int(total_ms % 1000)
    return f'min="{minutes}" second="{seconds}" ms="{ms}"'


# Diagonal inputs to skip — they're always redundant with individual direction actions in game.lua
DIAGONAL_INPUTS = {'downleft', 'downright', 'upleft', 'upright'}


def to_float(val: Any, default: float = 0.0) -> float:
    """Safely convert a parsed value to float."""
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def generate_xml(scene_name: str, seq_name: str, sequence: Dict, scene_order: Dict[str, str]) -> str:
    """Generate XML event file content for one chapter."""
    chapter_name = make_chapter_name(scene_name, seq_name)

    start_time = to_float(sequence.get('start_time', 0))
    timeout = sequence.get('timeout', {})
    if not isinstance(timeout, dict):
        timeout = {}
    timeout_when = to_float(timeout.get('when', 0))

    # Clamp noseek (-1) to 0 for XML times
    xml_start = max(0.0, start_time)
    xml_end = xml_start + timeout_when

    lines: List[str] = []
    lines.append(f'<chapter name="{chapter_name}">')
    lines.append(f'\t<timeline>')
    lines.append(f'\t\t<timestart {ms_to_attrs(xml_start)} />')
    lines.append(f'\t\t<timeend {ms_to_attrs(xml_end)} />')
    lines.append(f'\t</timeline>')

    # Params
    params_lines: List[str] = []
    if sequence.get('kills_player'):
        params_lines.append(f'\t\t<int key="kills_player" value="1" />')
    if sequence.get('cockpit'):
        params_lines.append(f'\t\t<int key="cockpit" value="1" />')
    if params_lines:
        lines.append(f'\t<params>')
        lines.extend(params_lines)
        lines.append(f'\t</params>')
    else:
        lines.append(f'\t<params />')

    # Macros (empty, kept for format compatibility)
    lines.append(f'\t<macros />')

    # Events
    lines.append(f'\t<events>')

    # Checkpoint event
    lines.append(f'\t\t<event type="checkpoint">')
    lines.append(f'\t\t\t<timeline>')
    lines.append(f'\t\t\t\t<timestart {ms_to_attrs(xml_start)} />')
    lines.append(f'\t\t\t</timeline>')
    lines.append(f'\t\t</event>')

    # Action events
    actions = sequence.get('actions')
    if isinstance(actions, list):
        label_counter = 0
        for action in actions:
            if not isinstance(action, dict):
                continue

            input_type = action.get('input', '')

            # Skip diagonal inputs (always redundant with individual directions)
            if input_type in DIAGONAL_INPUTS:
                continue

            label_counter += 1

            action_from = to_float(action.get('from', 0))
            action_to = to_float(action.get('to', 0))
            action_start = xml_start + action_from
            action_end = xml_start + action_to

            # Determine automacro attribute
            if input_type in ('left', 'right', 'up', 'down'):
                automacro = 'direction'
            elif input_type == 'action':
                automacro = 'action'
            elif input_type == 'start':
                automacro = 'start'
            else:
                automacro = 'direction'

            event_label = f'{automacro}-{label_counter}'

            lines.append(f'\t\t<event type="direction" automacro="{automacro}" label="{event_label}">')
            lines.append(f'\t\t\t<timeline>')
            lines.append(f'\t\t\t\t<timestart {ms_to_attrs(action_start)} />')
            lines.append(f'\t\t\t\t<timeend {ms_to_attrs(action_end)} />')
            lines.append(f'\t\t\t</timeline>')
            lines.append(f'\t\t\t<params>')
            lines.append(f'\t\t\t\t<str key="type" value="{input_type}" />')
            lines.append(f'\t\t\t</params>')

            # Action result
            result_type, result_name = derive_action_result(scene_name, action)
            if result_type != 'none' or result_name != 'none':
                if result_name and result_name != 'none':
                    lines.append(f'\t\t\t<result><{result_type} name="{result_name}" /></result>')
                else:
                    lines.append(f'\t\t\t<result><{result_type} /></result>')

            lines.append(f'\t\t</event>')

    lines.append(f'\t</events>')

    # Chapter-level result
    result_type, result_name = derive_chapter_result(scene_name, sequence, scene_order)
    if result_name and result_name != 'none':
        lines.append(f'\t<result><{result_type} name="{result_name}" /></result>')
    else:
        lines.append(f'\t<result><{result_type} /></result>')

    lines.append(f'</chapter>')

    return '\n'.join(lines) + '\n'


# ============ Main ============

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Generate XML event files from DirkSimple game.lua')
    parser.add_argument('--input', required=True, help='Path to game.lua')
    parser.add_argument('--outfolder', required=True, help='Output folder for XML files')
    args = parser.parse_args()

    lua_text = Path(args.input).read_text()

    # Preprocess: strip comments, evaluate function calls and arithmetic
    processed = strip_comments(lua_text)
    processed = preprocess_functions(processed)

    # Parse scenes table
    scenes = parse_scenes(processed)
    logging.info(f'Parsed {len(scenes)} scenes from game.lua')

    # Parse scene_manager.rows
    rows = parse_scene_manager_rows(processed)
    logging.info(f'Parsed {len(rows)} rows from scene_manager.rows')

    # Build scene order
    scene_order = build_scene_order(rows)
    logging.info(f'Scene order ({len(scene_order)} scenes):')
    # Print the linear order for verification
    current = 'introduction'
    chain: List[str] = [current]
    visited: set = {current}
    while current in scene_order:
        nxt = scene_order[current]
        if nxt in visited or nxt == 'title_screen':
            chain.append(nxt)
            break
        chain.append(nxt)
        visited.add(nxt)
        current = nxt
    logging.info('  ' + ' -> '.join(chain))

    # Create output folder
    outfolder = Path(args.outfolder)
    outfolder.mkdir(parents=True, exist_ok=True)

    # Track generated files
    generated_files: set = set()
    total = 0
    skipped = 0

    for scene_name in sorted(scenes.keys()):
        scene_data = scenes[scene_name]
        if not isinstance(scene_data, dict):
            continue
        for seq_name in sorted(scene_data.keys()):
            sequence = scene_data[seq_name]
            if not isinstance(sequence, dict):
                continue

            chapter_name = make_chapter_name(scene_name, seq_name)
            xml_content = generate_xml(scene_name, seq_name, sequence, scene_order)

            xml_path = outfolder / f'{chapter_name}.xml'
            xml_path.write_text(xml_content)
            generated_files.add(xml_path.name)
            total += 1

    logging.info(f'Generated {total} XML event files in {outfolder}')

    # Check for orphan XML files (exist on disk but not generated)
    existing_xmls = {f.name for f in outfolder.glob('*.xml')}
    orphans = existing_xmls - generated_files
    if orphans:
        logging.warning(f'{len(orphans)} orphan XML files not in game.lua:')
        for name in sorted(orphans):
            logging.warning(f'  {name}')

    # Verify all generated files have <result> elements
    missing_result = 0
    for xml_file in sorted(outfolder.glob('*.xml')):
        if xml_file.name not in generated_files:
            continue
        content = xml_file.read_text()
        # Check for chapter-level result (not event-level)
        # The last <result> before </chapter> should be the chapter result
        if content.count('<result>') < 1:
            logging.warning(f'Missing <result> in {xml_file.name}')
            missing_result += 1

    if missing_result:
        logging.warning(f'{missing_result} files missing <result> elements!')
    else:
        logging.info('All generated XML files have <result> elements.')

    # Summary
    logging.info(f'\nSummary:')
    logging.info(f'  Scenes: {len(scenes)}')
    logging.info(f'  Chapters generated: {total}')
    logging.info(f'  Orphan XMLs: {len(orphans)}')
    logging.info(f'  Missing results: {missing_result}')


if __name__ == "__main__":
    main()
