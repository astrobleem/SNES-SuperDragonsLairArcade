# Source Scripts Overview

This directory holds the engine- and flow-control scripts that wire the core states of the Super Dragon's Lair arcade project. The scripts are written in the project's custom assembler-style DSL and typically create objects, configure rendering layers, and transition between chapters or levels.

## Game Flow

```
boot.65816 → main.script → msu1.script → losers.script → logo_intro.script
  → title_screen.script → level1.script → [chapter gameplay] → ... → level9.script
```

## File Guide
- `main.script` — Bootstraps MSU-1 state, loads persisted scores, resets hardware, and spawns the MSU-1 management script.
- `msu1.script` — Uploads the MSU-1 sample pack, shows the MSU-1 splash background, and transitions to the losers screen.
- `losers.script` — Credits/losers screen shown after MSU-1 init; transitions to logo intro.
- `logo_intro.script` — Post-splash transition: briefly shows the logo background, fades to black, and spawns the title screen.
- `title_screen.script` — Full menu system with Start Game, Options (High Scores, Attract Mode, Sound Test, Scene Select). Handles player navigation, fades, and transitions to gameplay.
- `level1.script` through `level9.script` — Level entry points. Each creates a starting chapter Script and dies. Example: `level1.script` spawns `introduction_start_alive`.
- `hall_of_fame.script` — Renders the high-score list, plays attract-track audio, waits for user dismissal.
- `level_complete.script` — Shows chapter completion text, displays score, branches to next level.
- `score_entry.script` — Post-game name entry sequence, persists high-score table.
- `none.script` — Placeholder that errors if invoked.

## Chapter System

Each level is composed of **chapters** — short video segments with timed events. Chapters are defined by XML files in `data/events/` and converted to assembly by `tools/xmlsceneparser.py`.

- **29 scenes** across 9 levels (selectable from Scene Select menu)
- **516 total chapters** with events for direction prompts, checkpoints, room transitions, sequences, and more
- **36+ event classes** handle gameplay: `direction_generic`, `checkpoint`, `room_transition`, `seq_generic`, `cutscene`, etc.

Chapter transitions happen via `EventResult.playchapter` — when a player input succeeds or an event timeout triggers, the current chapter creates the next chapter Script, which kills the old chapter via `killOthers(isChapter)`.

## Title Screen Menu

The title screen provides:
- **Main menu** (state 0): ARCADE MODE, BOSS RUSH, OOPS,ALL TRAPS!, OPTIONS
- **Options submenu** (state 1): HIGH SCORES, SOUND TEST, SCENE SELECT
- **Sound test** (state 2): L/R selects sample 0-5, A plays it
- **Scene select** (state 3): L/R selects scene 1-29, A launches it

## Asset Theming Notes
- Dragon's Lair themed sound effects (`dl_accept`, `dl_buzz`, `dl_credit`) exist in `data/sounds/` as WAVs but are not yet registered in the SPC build due to sample RAM constraints.
- Legacy RoadBlaster identifiers remain in some code (`SAMPLE.0.SHURIKEN`, `SAMPLE.0.TECHNIQUE`) — these are functional placeholders.
- Legacy sprites (brake, dashboard, steering wheels) are unused by Dragon's Lair scenes; keep unreferenced.
