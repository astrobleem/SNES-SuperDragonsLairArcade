"""Extract simplified Dragon's Lair scene timing data from game.lua.

This exporter is intentionally limited to the subset of the DirkSimple
`game.lua` format used in tests. It reads the `scenes` table and emits a
textual `chapter.script` summary that preserves start/end times,
timeouts, actions, and single-frame flags.
"""

import argparse
import re
from pathlib import Path
from typing import Any, List, Tuple, Union

Token = Union[str, int, bool, None, Tuple[str, str]]


def strip_comments(text: str) -> str:
    """Remove Lua single-line comments."""
    return "\n".join(line.split("--", 1)[0] for line in text.splitlines())


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

        if ch == '"':
            j = i + 1
            value_chars: List[str] = []
            while j < len(content):
                if content[j] == "\\":
                    if j + 1 < len(content):
                        value_chars.append(content[j + 1])
                        j += 2
                        continue
                if content[j] == '"':
                    break
                value_chars.append(content[j])
                j += 1
            tokens.append("".join(value_chars))
            i = j + 1
            continue

        if ch.isdigit() or (ch == "-" and i + 1 < len(content) and content[i + 1].isdigit()):
            j = i + 1
            while j < len(content) and content[j].isdigit():
                j += 1
            tokens.append(int(content[i:j]))
            i = j
            continue

        if ch.isalpha() or ch == "_":
            j = i + 1
            while j < len(content) and (content[j].isalnum() or content[j] == "_"):
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

        # Skip unrecognized characters to keep parsing tolerant for the test subset.
        i += 1

    return tokens


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

        if position + 1 < len(tokens) and tokens[position + 1] == "=":
            key_token = tokens[position]
            key = key_token[1] if isinstance(key_token, tuple) else key_token
            position += 2
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
        table: dict[str, Any] = {}
        for entry in entries:
            if isinstance(entry, tuple) and len(entry) == 2:
                key, value = entry
                table[str(key)] = value
        return table, position

    return entries, position


def parse_scenes(lua_text: str) -> dict:
    cleaned = strip_comments(lua_text)
    match = re.search(r"scenes\s*=\s*{", cleaned)
    if not match:
        raise ValueError("Could not locate scenes table in Lua source")

    start = match.start()
    brace_start = cleaned.find("{", start)
    tokens = tokenize(cleaned[brace_start:])
    scenes, _ = parse_table(tokens, 0)
    if not isinstance(scenes, dict):
        raise ValueError("Scenes table did not parse into a dictionary")
    return scenes


def format_chapter_script(scenes: dict) -> str:
    lines: List[str] = ["# chapter.script generated from Lua scenes"]
    for scene_name in sorted(scenes.keys()):
        lines.append(f"scene {scene_name}")
        sequences = scenes[scene_name]
        if not isinstance(sequences, dict):
            continue
        for sequence_name in sorted(sequences.keys()):
            sequence = sequences[sequence_name]
            lines.append(f"  sequence {sequence_name}")
            start_time = sequence.get("start_time")
            lines.append(f"    start_time: {start_time}")
            if "end_time" in sequence:
                lines.append(f"    end_time: {sequence.get('end_time')}")

            timeout = sequence.get("timeout")
            if isinstance(timeout, dict):
                when = timeout.get("when")
                next_sequence = timeout.get("nextsequence")
                lines.append(f"    timeout: when={when} next={next_sequence}")

            lines.append(f"    is_single_frame: {bool(sequence.get('is_single_frame', False))}")

            actions = sequence.get("actions") or []
            if actions:
                lines.append("    actions:")
                for action in actions:
                    lines.append(
                        "      - input={input} from={from_time} to={to_time} next={next_seq} interrupt={interrupt}".format(
                            input=action.get("input"),
                            from_time=action.get("from"),
                            to_time=action.get("to"),
                            next_seq=action.get("nextsequence"),
                            interrupt=action.get("interrupt"),
                        )
                    )
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Export chapter.script summary from a Lua scenes file")
    parser.add_argument("--input", required=True, help="Path to game.lua source")
    parser.add_argument("--output", required=True, help="Destination path for chapter.script")
    args = parser.parse_args()

    lua_text = Path(args.input).read_text()
    scenes = parse_scenes(lua_text)
    output_text = format_chapter_script(scenes)
    Path(args.output).write_text(output_text)


if __name__ == "__main__":
    main()
