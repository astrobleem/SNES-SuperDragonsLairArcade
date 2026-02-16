# Scene Transition Tracer Algorithm

## Context

The Super Dragon's Lair Arcade project uses a chapter-based event system where XML scene data (sourced from the DirkSimple game data repository) is converted to 65816 assembly event tables by `tools/xmlsceneparser.py`. Each chapter contains a set of events -- direction inputs, checkpoints, sequence markers, and a special `Event.chapter` event that defines the default timeout behavior. Events carry result handlers that chain to the next chapter when triggered, forming a directed graph of gameplay paths through each scene.

**The problem**: Scenes are self-contained subgraphs. Within a scene, chapters chain to each other via `EventResult.playchapter` results. But the final chapter of each scene -- the *terminal chapter* -- has its `Event.chapter` result set to `EventResult.none`, meaning the game simply stops when the scene completes. Without explicit cross-scene transitions, the player reaches the terminal chapter and the game halts.

**The solution**: The file `data/scene_transitions.json` provides a mapping from terminal chapter names to the next scene's `_start_alive` entry chapter. During assembly generation, `tools/xmlsceneparser.py` reads this JSON (via the `-scene_transitions` flag, invoked by the Makefile) and overrides the terminal `Event.chapter` result from `EventResult.none` to `EventResult.playchapter` with the appropriate target scene.

For example, the entry:

```json
"snake_room_seq5": "bower_start_alive"
```

causes the generated `snake_room_seq5.events` data to contain:

```asm
.dw Event.chapter.CLS.PTR, $0000, $004b, EventResult.playchapter, bower_start_alive, 516, 0
```

instead of the original `EventResult.none`.

The key challenge is **identifying which chapter is the terminal** for each scene. Some scenes have obvious `exit_room` chapters, but many do not. The scene transition tracer algorithm solves this by automatically tracing the success path through each scene's chapter graph.


## Event Data Format

Each chapter's event data (in `data/chapters/<name>/chapter.data`) consists of a table of event entries, each 7 words (14 bytes):

```
.dw Event.TYPE.CLS.PTR, $startframe, $endframe, EventResult.RESULT, TARGET, arg0, arg1
```

| Field | Description |
|-------|-------------|
| `Event.TYPE.CLS.PTR` | Event class: `chapter`, `direction_generic`, `checkpoint`, `seq_generic`, etc. |
| `$startframe` | Chapter-relative start frame (16-bit) |
| `$endframe` | Chapter-relative end frame (16-bit) |
| `EventResult.RESULT` | `playchapter`, `restartchapter`, `lastcheckpoint`, or `none` |
| `TARGET` | Assembly label of the target chapter, or `none` |
| `arg0` | Event-specific: direction mask (`JOY_DIR_LEFT`, etc.), `0` for attract mode, sequence number |
| `arg1` | Event-specific secondary argument |

The table is terminated by `.dw 0`.


## Event Classification

Understanding event types is essential for tracing:

### `Event.chapter` -- Default/Timeout Path

Every chapter has exactly one `Event.chapter` entry. It defines what happens when the player does nothing (the video plays to the end without correct input). In most gameplay chapters, this leads to a death sequence. In transition chapters (`_start_alive`, `_enter_room`), it chains to the next chapter in the scene.

### `Event.direction_generic` with `arg0=0` -- Attract Mode Auto-Play

The DirkSimple XML data includes attract mode events marked with `automacro="action"` and `type="action"`. Since `"action"` is not in `xmlsceneparser.py`'s `direction_lut`, it converts to `direction_generic` with `arg0=0` (no joystick direction). These events represent the **canonical correct input** for each chapter -- the path the game follows during attract mode demo playback.

Example from `snake_room_seq2.events`:
```asm
.dw Event.direction_generic.CLS.PTR, $002f, $0040, EventResult.playchapter, snake_room_seq3, 0, 0
```

### `Event.direction_generic` with Specific Direction -- Player Input

Events with `arg0` set to `JOY_DIR_LEFT`, `JOY_DIR_RIGHT`, `JOY_DIR_UP`, or `JOY_DIR_DOWN` represent actual joystick inputs. Some of these lead to the correct next chapter (success), while others lead to death sequences (wrong input). The correct direction event targets the same chapter as the attract mode event.

### `Event.checkpoint` -- Save Point

Checkpoints mark positions where the player respawns after death. They always have `EventResult.none` and do not participate in transitions.


## Algorithm: Tracing Success Paths

The tracer walks the chapter graph starting from a scene's entry point, following the canonical correct path at each chapter until it reaches a terminal.

### Step 1: Parse Chapter Data

Read all `data/chapters/*/chapter.data` files. For each chapter, extract the event entries into structured records:

```python
{
    'type': 'chapter' | 'direction_generic' | 'checkpoint' | ...,
    'startframe': '0x002f',
    'endframe': '0x0040',
    'result': 'playchapter' | 'none' | 'lastcheckpoint' | 'restartchapter',
    'target': 'snake_room_seq3',
    'arg0': '0' | 'JOY_DIR_LEFT' | 'JOY_DIR_RIGHT' | ...,
    'arg1': '0'
}
```

### Step 2: At Each Chapter, Determine the Next Chapter

The algorithm uses a strict priority order to decide which event's target to follow:

**Priority 1 -- Attract Mode Events (`arg0=0`)**

If the chapter contains any `Event.direction_generic` entries with `arg0=0` and `result=playchapter`, follow the first one. These are the DirkSimple attract mode auto-play events and represent the authoritative correct path.

This handles the majority of gameplay chapters. For example, in `snake_room_seq2`:
- Attract mode (`arg0=0`) points to `snake_room_seq3` (correct)
- Direction (`JOY_DIR_LEFT`) points to `snake_room_seq7` (death)
- Chapter default also points to `snake_room_seq7` (timeout death)

The tracer follows `snake_room_seq3`.

**Priority 2 -- Non-Default Direction Events (Latest Startframe)**

If no attract mode events exist, examine direction events (`direction_generic` with specific `arg0` values like `JOY_DIR_LEFT`). Filter out any events whose target matches the chapter default target (since the default is typically death/timeout). Among the remaining candidates, select the one with the **latest startframe**.

The latest-startframe heuristic works because Dragon's Lair typically presents multiple input windows per chapter, and the later window is often the decisive correct input.

**Priority 3 -- Chapter Default**

If no direction events exist at all, follow the `Event.chapter` default target. This handles transition chapters (`_start_alive` -> `_enter_room` -> first gameplay chapter) that have no player input, only automatic chaining.

**Priority 4 -- Terminal**

If the `Event.chapter` has `EventResult.none` and no direction events provide an alternative, the chapter is terminal. Stop tracing.

### Step 3: Death Filtering

When using Priority 2, the algorithm must distinguish success targets from death targets among direction events. Death chapters are filtered by name patterns. Chapters with names containing any of these substrings are considered death paths:

- `death`, `dead`, `game_over`, `crush`, `crash`, `miss`, `fire`, `trap`
- `burn`, `fall`, `eaten`, `captured`, `killed`, `drown`, `poison`

If all non-default direction targets are death chapters, the chapter is treated as a dead end (the tracer would have already found the terminal via another branch).

### Step 4: Cycle Detection

The tracer maintains a visited set to prevent infinite loops. If a chapter has already been visited, tracing stops. A maximum depth limit (default 50) provides an additional safety bound.


## Two Categories of Terminal Chapters

The Dragon's Lair chapter data reveals two distinct patterns for scene-ending chapters:

### Category 1: `exit_room` Chapters

Fifteen scenes have chapters explicitly named `{scene}_exit_room`. These are unambiguous terminal markers: they contain only an `Event.chapter` and an `Event.checkpoint`, with the chapter event originally having `EventResult.none` (overridden by `scene_transitions.json`).

Scenes with `exit_room` terminals:
- `introduction_exit_room`
- `vestibule_exit_room`
- `bower_exit_room`
- `throne_room_exit_room`
- `tilting_room_exit_room`
- `tentacle_room_exit_room`
- `wind_room_exit_room`
- `giddy_goons_exit_room`
- `rolling_balls_exit_room`
- `underground_river_exit_room`
- `flaming_ropes_exit_room`
- `flying_horse_exit_room`
- `crypt_creeps_exit_room`
- `alice_room_exit_room`
- `falling_platform_long_exit_room` (alternate path into `mudmen`)

### Category 2: Success-Path `seq` Chapters

Fourteen scenes lack `exit_room` chapters entirely. Their terminals are `{scene}_seqN` chapters that the tracer discovers by following correct inputs from the scene's `_start_alive` entry point through the chain of gameplay chapters.

Scenes with traced `seq` terminals:
- `snake_room_seq5`
- `fire_room_seq6`
- `catwalk_bats_seq7`
- `mudmen_seq15`
- `bubbling_cauldron_seq7`
- `giant_bat_seq7`
- `robot_knight_seq10`
- `smithee_seq7`
- `smithee_reversed_seq9`
- `grim_reaper_seq6`
- `yellow_brick_road_seq15`
- `black_knight_seq6`
- `lizard_king_seq14`
- `the_dragons_lair_seq19`

These are only discoverable by running the tracer algorithm. Without it, building `scene_transitions.json` for a new game requires manually playing through every scene to find the final chapter.


## Python Script Reference

The following standalone Python script implements the tracer algorithm. It can be adapted for any DirkSimple-derived FMV game.

```python
#!/usr/bin/env python3
"""
Scene Transition Tracer

Traces success paths through chapter event data to identify terminal chapters
for each scene. Used to generate scene_transitions.json for FMV games built
on the DirkSimple XML data format.

Usage:
    python trace_scene_terminals.py --chapters-dir data/chapters --scenes SCENE1 SCENE2 ...
"""

import os
import re
import sys
import json
import argparse


def parse_chapter_data(chapters_dir):
    """Parse all chapter.data files into a dict of chapter_name -> [events]."""
    chapters = {}
    for direntry in os.listdir(chapters_dir):
        data_path = os.path.join(chapters_dir, direntry, 'chapter.data')
        if not os.path.isfile(data_path):
            continue
        events = []
        with open(data_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('.dw Event.'):
                    parts = [p.strip() for p in line[4:].split(',')]
                    if len(parts) >= 7:
                        # Extract type from Event.TYPE.CLS.PTR
                        event_type = parts[0].replace('Event.', '').replace('.CLS.PTR', '')
                        events.append({
                            'type': event_type,
                            'startframe': parts[1],
                            'endframe': parts[2],
                            'result': parts[3].replace('EventResult.', ''),
                            'target': parts[4],
                            'arg0': parts[5],
                            'arg1': parts[6],
                        })
        if events:
            # Use the label from the first line of the file (before .events:)
            chapters[direntry] = events
    return chapters


def is_death_chapter(name):
    """Heuristic: does this chapter name suggest a death/failure path?"""
    death_keywords = [
        'death', 'dead', 'game_over', 'crush', 'crash', 'miss',
        'fire', 'trap', 'burn', 'fall', 'eaten', 'captured',
        'killed', 'drown', 'poison', 'lose', 'gameover',
    ]
    name_lower = name.lower()
    return any(kw in name_lower for kw in death_keywords)


def startframe_to_int(sf_str):
    """Convert a startframe string like '$002f' or '0' to integer."""
    sf_str = sf_str.strip()
    if sf_str.startswith('$'):
        return int(sf_str[1:], 16)
    elif sf_str.startswith('0x'):
        return int(sf_str, 16)
    else:
        return int(sf_str)


def trace_success_path(chapters, start, max_depth=50):
    """
    Trace the success path from a starting chapter.

    Returns a list of chapter names representing the path taken,
    ending at the terminal chapter.

    Priority at each chapter:
      1. Attract mode events (direction_generic with arg0=0)
      2. Non-default direction events (latest startframe, excluding deaths)
      3. Chapter default target
      4. Terminal (no further path)
    """
    path = []
    visited = set()
    current = start

    while current and current not in visited and len(path) < max_depth:
        visited.add(current)
        path.append(current)

        if current not in chapters:
            break

        events = chapters[current]

        # Classify events
        ch_target = None
        ch_result = None
        attract_targets = []
        direction_events = []

        for e in events:
            if e['type'] == 'chapter':
                ch_result = e['result']
                ch_target = e['target'] if e['result'] == 'playchapter' else None
            elif e['type'] == 'direction_generic' and e['result'] == 'playchapter' and e['target'] != 'none':
                if e['arg0'] == '0':
                    attract_targets.append(e['target'])
                else:
                    direction_events.append((e['startframe'], e['target']))

        # De-duplicate attract targets preserving order
        attract_targets = list(dict.fromkeys(attract_targets))

        # Priority 1: attract mode events
        if attract_targets:
            current = attract_targets[0]

        # Priority 2: non-default direction events
        elif direction_events:
            # Group by target, keeping latest startframe per target
            target_frames = {}
            for sf, target in direction_events:
                sf_int = startframe_to_int(sf)
                if target not in target_frames or sf_int > target_frames[target]:
                    target_frames[target] = sf_int

            # Filter out default (death) target and death-named chapters
            non_default = {
                t: sf for t, sf in target_frames.items()
                if t != ch_target and not is_death_chapter(t)
            }

            if non_default:
                # Pick the target with the latest startframe
                current = max(non_default.items(), key=lambda x: x[1])[0]
            elif ch_target:
                current = ch_target
            else:
                break

        # Priority 3: chapter default
        elif ch_result == 'playchapter' and ch_target:
            current = ch_target

        # Priority 4: terminal
        else:
            break

    return path


def find_terminal(chapters, start):
    """Trace success path and return the terminal chapter name."""
    path = trace_success_path(chapters, start)
    return path[-1] if path else None


def generate_scene_transitions(chapters, scene_order):
    """
    Generate a scene_transitions dict mapping terminal chapters to next scenes.

    Args:
        chapters: dict from parse_chapter_data()
        scene_order: list of (scene_name, start_chapter) tuples in order

    Returns:
        dict of terminal_chapter -> next_start_chapter
    """
    transitions = {}

    for i, (scene_name, start_chapter) in enumerate(scene_order):
        terminal = find_terminal(chapters, start_chapter)
        if terminal is None:
            print(f"WARNING: Could not trace scene '{scene_name}' from '{start_chapter}'",
                  file=sys.stderr)
            continue

        # Determine next scene target
        if i + 1 < len(scene_order):
            next_scene_name, next_start = scene_order[i + 1]
            transitions[terminal] = next_start
            print(f"  {scene_name}: {start_chapter} -> ... -> {terminal} => {next_start}")
        else:
            print(f"  {scene_name}: {start_chapter} -> ... -> {terminal} (final scene)")

    return transitions


def main():
    parser = argparse.ArgumentParser(description='Trace scene terminals for FMV games')
    parser.add_argument('--chapters-dir', required=True,
                        help='Path to data/chapters/ directory')
    parser.add_argument('--output', '-o', default=None,
                        help='Output JSON file (default: stdout)')
    parser.add_argument('--scene-order', default=None,
                        help='JSON file with scene order: [["scene", "start_chapter"], ...]')
    parser.add_argument('--trace', default=None,
                        help='Trace a single chapter and print path')
    args = parser.parse_args()

    chapters = parse_chapter_data(args.chapters_dir)
    print(f"Parsed {len(chapters)} chapters", file=sys.stderr)

    if args.trace:
        path = trace_success_path(chapters, args.trace)
        print(f"Success path from {args.trace} ({len(path)} chapters):")
        for i, ch in enumerate(path):
            marker = " [TERMINAL]" if i == len(path) - 1 else ""
            print(f"  {i+1}. {ch}{marker}")
        return

    if args.scene_order:
        with open(args.scene_order, 'r') as f:
            scene_order = json.load(f)
    else:
        print("ERROR: --scene-order or --trace required", file=sys.stderr)
        sys.exit(1)

    transitions = generate_scene_transitions(chapters, scene_order)

    output_json = json.dumps(transitions, indent=2)
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output_json + '\n')
        print(f"Wrote {len(transitions)} transitions to {args.output}", file=sys.stderr)
    else:
        print(output_json)


if __name__ == '__main__':
    main()
```


## Dragon's Lair Scene Order (Reference)

The following table lists all 29 Dragon's Lair scenes in order, showing the entry chapter, traced terminal chapter, and the next scene's target.

| # | Scene | Entry Chapter | Terminal Chapter | Next Target |
|---|-------|---------------|------------------|-------------|
| 1 | introduction | `introduction_start_alive` | `introduction_exit_room` | `vestibule_start_alive` |
| 2 | vestibule | `vestibule_start_alive` | `vestibule_exit_room` | `snake_room_start_alive` |
| 3 | snake_room | `snake_room_start_alive` | `snake_room_seq5` | `bower_start_alive` |
| 4 | bower | `bower_start_alive` | `bower_exit_room` | `fire_room_start_alive` |
| 5 | fire_room | `fire_room_start_alive` | `fire_room_seq6` | `throne_room_start_alive` |
| 6 | throne_room | `throne_room_start_alive` | `throne_room_exit_room` | `tilting_room_start_alive` |
| 7 | tilting_room | `tilting_room_start_alive` | `tilting_room_exit_room` | `tentacle_room_start_alive` |
| 8 | tentacle_room | `tentacle_room_start_alive` | `tentacle_room_exit_room` | `wind_room_start_alive` |
| 9 | wind_room | `wind_room_start_alive` | `wind_room_exit_room` | `giddy_goons_start_alive` |
| 10 | giddy_goons | `giddy_goons_start_alive` | `giddy_goons_exit_room` | `catwalk_bats_start_alive` |
| 11 | catwalk_bats | `catwalk_bats_start_alive` | `catwalk_bats_seq7` | `mudmen_start_alive` |
| 11b | (alternate) | `falling_platform_long_*` | `falling_platform_long_exit_room` | `mudmen_start_alive` |
| 12 | mudmen | `mudmen_start_alive` | `mudmen_seq15` | `rolling_balls_start_alive` |
| 13 | rolling_balls | `rolling_balls_start_alive` | `rolling_balls_exit_room` | `underground_river_start_alive` |
| 14 | underground_river | `underground_river_start_alive` | `underground_river_exit_room` | `flaming_ropes_start_alive` |
| 15 | flaming_ropes | `flaming_ropes_start_alive` | `flaming_ropes_exit_room` | `flying_horse_start_alive` |
| 16 | flying_horse | `flying_horse_start_alive` | `flying_horse_exit_room` | `bubbling_cauldron_start_alive` |
| 17 | bubbling_cauldron | `bubbling_cauldron_start_alive` | `bubbling_cauldron_seq7` | `giant_bat_start_alive` |
| 18 | giant_bat | `giant_bat_start_alive` | `giant_bat_seq7` | `crypt_creeps_start_alive` |
| 19 | crypt_creeps | `crypt_creeps_start_alive` | `crypt_creeps_exit_room` | `alice_room_start_alive` |
| 20 | alice_room | `alice_room_start_alive` | `alice_room_exit_room` | `robot_knight_start_alive` |
| 21 | robot_knight | `robot_knight_start_alive` | `robot_knight_seq10` | `smithee_start_alive` |
| 22 | smithee | `smithee_start_alive` | `smithee_seq7` | `smithee_reversed_start_alive` |
| 23 | smithee_reversed | `smithee_reversed_start_alive` | `smithee_reversed_seq9` | `grim_reaper_start_alive` |
| 24 | grim_reaper | `grim_reaper_start_alive` | `grim_reaper_seq6` | `yellow_brick_road_start_alive` |
| 25 | yellow_brick_road | `yellow_brick_road_start_alive` | `yellow_brick_road_seq15` | `black_knight_start_alive` |
| 26 | black_knight | `black_knight_start_alive` | `black_knight_seq6` | `lizard_king_start_alive` |
| 27 | lizard_king | `lizard_king_start_alive` | `lizard_king_seq14` | `the_dragons_lair_start_alive` |
| 28 | the_dragons_lair | `the_dragons_lair_start_alive` | `the_dragons_lair_seq19` | `title_screen` |
| 28b | (alternate end) | | `the_dragons_lair_endgame` | `title_screen` |
| 29 | attract_mode | `attract_mode_start_alive` | *(loops internally)* | *(no transition)* |


## Integration with the Build System

The Makefile invokes `xmlsceneparser.py` with the scene transitions file:

```makefile
$(chapterscripts): $(chapterfolder)%/chapter.$(chapterscript):$(eventfolder)%.$(scripteventxml) $(datadir)/scene_transitions.json
	$(xmlchapterconverter) -infile $< -outfolder $(chapterfolder) -scene_transitions $(datadir)/scene_transitions.json
```

In `xmlsceneparser.py`, the `writeEventFile` function loads the JSON and applies overrides:

```python
scene_transitions = {}
transitions_file = options.get('scene_transitions')
if transitions_file and os.path.exists(transitions_file):
    import json
    with open(transitions_file, 'r') as f:
        scene_transitions = json.load(f)

# When writing each event line:
if event.type == 'chapter' and chapterLabel in scene_transitions:
    result = 'playchapter'
    resultname = scene_transitions[chapterLabel]
```

This means the `scene_transitions.json` file is the single source of truth for cross-scene linking. Regenerating it (via the tracer algorithm) and rebuilding is all that is needed to update scene flow.


## Applying to Space Ace

Space Ace uses the same DirkSimple XML data format and can reuse the tracer algorithm with the following adaptations.

### Step 1: Convert XML Chapters

Run `xmlsceneparser.py` against all Space Ace XML event files (from the DirkSimple `spaceace` data set) to generate `chapter.data` files:

```bash
for xml in data/events/*.xml; do
    python3 tools/xmlsceneparser.py -infile "$xml" -outfolder data/chapters
done
```

### Step 2: Run the Tracer

Use `trace_scene_terminals.py` to trace each scene:

```bash
python3 tools/trace_scene_terminals.py \
    --chapters-dir data/chapters \
    --trace spaceace_scene1_start_alive
```

### Step 3: Determine Scene Order

Space Ace has a fixed scene sequence, similar to Dragon's Lair. Create a `scene_order.json` file listing scenes in play order:

```json
[
    ["scene1", "scene1_start_alive"],
    ["scene2", "scene2_start_alive"],
    ...
]
```

### Step 4: Generate Transitions

```bash
python3 tools/trace_scene_terminals.py \
    --chapters-dir data/chapters \
    --scene-order scene_order.json \
    -o data/scene_transitions.json
```

### Step 5: Handle Space Ace-Specific Mechanics

Space Ace has gameplay mechanics that Dragon's Lair does not:

**Energize/Deenergize branching**: Space Ace allows the player to "energize" (transform from Dexter into Ace) at certain moments. This creates branching paths where the Dexter path and Ace path diverge and may rejoin at different points. The tracer must be run separately for each branch:

- Trace the Dexter (default) path through each scene
- Trace the Ace (energized) path through scenes that support it
- Both paths may have different terminal chapters but should map to the same next scene

In practice, this means some scenes may have **two entries** in `scene_transitions.json`:

```json
{
    "scene5_dexter_seq8": "scene6_start_alive",
    "scene5_ace_seq12": "scene6_start_alive"
}
```

**Skill level variants**: Some Space Ace scenes only appear at certain difficulty levels (Cadet, Captain, Ace). The tracer operates on the chapter data regardless of skill level. Skill-level filtering is handled at the level script layer (which scenes to include in each difficulty's level scripts), not in the transition map.

**Energize events in XML**: Look for event types like `energize` or parameters indicating transformation. These may need to be mapped to custom event classes in the assembly, but they do not affect the tracer's ability to find terminals -- the tracer follows the attract mode path, which always takes the canonical route through each scene.


## Applying to Cliff Hanger

Cliff Hanger (Stern Electronics, 1983) is based on scenes from Hayao Miyazaki's *Lupin III: The Castle of Cagliostro*. If DirkSimple-format XML data exists for Cliff Hanger, the same tracer pipeline applies.

### Key Differences from Dragon's Lair

**Linear narrative structure**: Cliff Hanger follows the movie's plot in sequence. Scenes are more linear than Dragon's Lair's randomly-ordered rooms. The scene order follows the film's narrative:

1. Car chase on the cliff road
2. Entering the castle
3. Rooftop escape
4. Underground waterway
5. Clock tower confrontation
6. Final escape

**Different event vocabulary**: Cliff Hanger's XML data may use different event type names. The tracer's event classification step may need adjustment:

- Look for the attract mode marker (likely still `automacro="action"` with `type="action"`, producing `arg0=0`)
- If the XML uses different conventions for auto-play events, update the `arg0=0` check accordingly
- Direction events should still follow the same pattern (`type="left"`, `type="right"`, etc.)

**Fewer branching paths**: Cliff Hanger is simpler than Dragon's Lair with fewer wrong-input alternatives per scene. The tracer may find shorter paths with fewer decision points, making manual verification easier.

### Adaptation Steps

1. **Obtain XML data**: Source Cliff Hanger chapter XMLs from DirkSimple or equivalent game data repository.

2. **Audit event types**: Before running `xmlsceneparser.py`, check what event types appear in the XML. If new types are found (e.g., `punch`, `kick` for Cliff Hanger's combat system), add normalization rules to `__normalize_type()` in `xmlsceneparser.py`.

3. **Convert and trace**: Follow the same convert-then-trace pipeline as Dragon's Lair and Space Ace.

4. **Verify against gameplay**: Cross-reference traced terminals against known Cliff Hanger gameplay guides or video playthroughs. The linear narrative makes this straightforward -- each scene should have exactly one terminal leading to the next narrative beat.

5. **Handle game-specific end conditions**: Cliff Hanger may have different endgame handling (victory screen, credits sequence). Map the final scene's terminal to the appropriate post-game chapter or title screen.


## Troubleshooting

### Tracer stops at an unexpected chapter

If the tracer terminates at a chapter that is clearly not the scene's end:

- **Missing attract mode events**: Not all DirkSimple XMLs include attract mode data for every chapter. Check the XML source for `automacro="action"` entries. If absent, the tracer falls back to direction events (Priority 2).
- **All direction targets are deaths**: If every non-default direction event leads to a death chapter, the death filter removes all candidates. Relax the death keyword list or manually inspect the chapter.
- **Chapter data not generated**: Ensure `xmlsceneparser.py` has been run for all XML files. Missing `chapter.data` files cause the tracer to stop at the first reference to an unparsed chapter.

### Multiple possible terminals for a scene

Some scenes have alternate success paths (e.g., `falling_platform_long_exit_room` as an alternate route into `mudmen`). The tracer follows one path deterministically, but you may need to add additional entries to `scene_transitions.json` manually for alternate routes.

### Cycle detected

If the tracer reports a cycle, the chapter graph contains a loop (e.g., a scene that can be replayed). This is normal for `attract_mode` which loops between `attract_mode_attract_movie` and `attract_mode_insert_coins`. Looping scenes do not need transitions.
