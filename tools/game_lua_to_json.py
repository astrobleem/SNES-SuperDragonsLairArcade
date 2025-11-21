"""Convert the DirkSimple `game.lua` scenes table into JSON.

This parser evaluates the helper timing functions used in `tools/game.lua`
(`time_to_ms`, `time_laserdisc_frame`, etc.) and expands the full `scenes`
table into plain Python data before serializing it as JSON. Use it to inspect
or feed the Dragon's Lair scene timings into other pipelines without pulling
in a Lua runtime.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple, Union

Token = Union[str, int, float, bool, None, Tuple[str, str]]


# Timing helpers mirrored from tools/game.lua
# Laserdisc frame rate for the Dragon's Lair source.
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


FUNCTIONS: Dict[str, Callable[..., Any]] = {
    "laserdisc_frame_to_ms": laserdisc_frame_to_ms,
    "time_laserdisc_frame": time_laserdisc_frame,
    "time_laserdisc_noseek": time_laserdisc_noseek,
    "time_to_ms": time_to_ms,
}


@dataclass
class ParserState:
    tokens: List[Token]
    position: int = 0

    def current(self) -> Token:
        return self.tokens[self.position]

    def advance(self) -> None:
        self.position += 1

    def expect(self, value: Token) -> None:
        if self.current() != value:
            raise ValueError(
                f"Expected token {value!r} at position {self.position}, found {self.current()!r}"
            )
        self.advance()


# Lexing


def strip_comments(text: str) -> str:
    return "\n".join(line.split("--", 1)[0] for line in text.splitlines())


def tokenize(content: str) -> List[Token]:
    tokens: List[Token] = []
    i = 0
    while i < len(content):
        ch = content[i]
        if ch.isspace():
            i += 1
            continue

        if ch in "{}=,()+-":
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
            has_dot = False
            while j < len(content):
                if content[j].isdigit():
                    j += 1
                    continue
                if content[j] == "." and not has_dot:
                    has_dot = True
                    j += 1
                    continue
                break
            number_str = content[i:j]
            tokens.append(float(number_str) if "." in number_str else int(number_str))
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

        i += 1  # skip anything unrecognized

    return tokens


# Parsing


def parse_value(state: ParserState) -> Any:
    tok = state.current()

    if tok == "{":
        return parse_table(state)
    if tok == "(":
        state.advance()
        value = parse_expression(state)
        state.expect(")")
        return value
    if tok == "-":
        state.advance()
        return -parse_value(state)
    if isinstance(tok, tuple) and tok[0] == "IDENT":
        return parse_identifier_or_call(state)

    state.advance()
    return tok


def parse_identifier_or_call(state: ParserState) -> Any:
    ident = state.current()
    assert isinstance(ident, tuple) and ident[0] == "IDENT"
    name = ident[1]
    state.advance()

    if state.position < len(state.tokens) and state.current() == "(":
        state.advance()
        args: List[Any] = []
        while state.position < len(state.tokens) and state.current() != ")":
            args.append(parse_expression(state))
            if state.current() == ",":
                state.advance()
        state.expect(")")
        func = FUNCTIONS.get(name)
        if func is None:
            return {"function": name, "args": args}
        return func(*args)

    return name


def parse_expression(state: ParserState) -> Any:
    value = parse_term(state)
    while state.position < len(state.tokens) and state.current() in {"+", "-"}:
        op = state.current()
        state.advance()
        rhs = parse_term(state)
        if not isinstance(value, (int, float)) or not isinstance(rhs, (int, float)):
            raise ValueError(
                f"Cannot apply operator {op!r} to non-numeric values: {value!r}, {rhs!r}"
            )
        value = value + rhs if op == "+" else value - rhs
    return value


def parse_term(state: ParserState) -> Any:
    return parse_value(state)


def parse_table(state: ParserState) -> Any:
    state.expect("{")
    entries: List[Any] = []
    keyed = False

    while state.position < len(state.tokens) and state.current() != "}":
        if state.current() == ",":
            state.advance()
            continue

        if (state.position + 1 < len(state.tokens)) and (state.tokens[state.position + 1] == "="):
            key_token = state.current()
            key = key_token[1] if isinstance(key_token, tuple) else key_token
            state.advance()  # key
            state.advance()  # equals
            value = parse_expression(state)
            entries.append((key, value))
            keyed = True
        else:
            entries.append(parse_expression(state))

        if state.position < len(state.tokens) and state.current() == ",":
            state.advance()

    state.expect("}")

    if keyed:
        table: Dict[str, Any] = {}
        for entry in entries:
            if isinstance(entry, tuple) and len(entry) == 2:
                key, value = entry
                table[str(key)] = value
        return table

    return entries


# Driver


def parse_scenes(lua_text: str) -> Dict[str, Any]:
    cleaned = strip_comments(lua_text)
    match = re.search(r"scenes\s*=\s*{", cleaned)
    if not match:
        raise ValueError("Could not locate scenes table in Lua source")

    brace_start = cleaned.find("{", match.start())
    tokens = tokenize(cleaned[brace_start:])
    state = ParserState(tokens)
    scenes = parse_table(state)
    if not isinstance(scenes, dict):
        raise ValueError("Scenes table did not parse into a dictionary")
    return scenes


def main() -> None:
    parser = argparse.ArgumentParser(description="Expand tools/game.lua scenes into JSON")
    parser.add_argument("--input", default="tools/game.lua", help="Path to the game.lua source")
    parser.add_argument("--output", required=True, help="Destination JSON path")
    parser.add_argument("--indent", type=int, default=2, help="Indent level for JSON output")
    args = parser.parse_args()

    lua_text = Path(args.input).read_text()
    scenes = parse_scenes(lua_text)
    Path(args.output).write_text(json.dumps(scenes, indent=args.indent, sort_keys=True))


if __name__ == "__main__":
    main()
