# Source scripts overview

This directory holds the engine- and flow-control scripts that wire the core states of the Super Dragon's Lair arcade project. The scripts are written in the project's custom assembler-style DSL and typically create objects, configure rendering layers, and transition between chapters or levels.

## File guide
- `main.script` bootstraps MSU1 state, loads persisted scores, and spawns the MSU1 management script for later scenes.
- `msu1.script` uploads the MSU1 sample pack, shows the MSU1 splash background, and transitions to `logo_intro` when the player continues.
- `logo_intro.script` handles the post-MSU1 splash transition by briefly showing the logo background, fading back to black, and spawning the title sequence.
- `title_screen.script` builds the title presentation (logo zoom, palette rotation, intro sound effects) and hands off to `level1` after user input and cleanup.
- `hall_of_fame.script` renders the high-score list, plays the attract-track audio, and waits for user dismissal before returning to the MSU1 intro.
- `level_complete.script` shows chapter completion text, displays the player's score, and branches to the next level script after user confirmation.
- `score_entry.script` runs the post-game name entry sequence, persists the high-score table, and returns to the MSU1 intro sequence.
- `none.script` is a placeholder that currently errors if invoked.

## Theming and canonical content review
- The title screen currently triggers sound effects named `SAMPLE.0.SHURIKEN` and `SAMPLE.0.TECHNIQUE`, which evoke martial-arts imagery rather than a "lair" fantasy theme. Consider swapping these for cues like a dragon roar or sword clash to reinforce the setting.
- No other out-of-theme elements (e.g., steering wheels, turbo boosts, racetrack references) are present in the root scripts; if future scans reveal unused assets tied to such concepts, mark them as deprecated and remove references.

## Conventions for downstream directories
- Keep new scripts focused on lair-appropriate imagery (dragons, dungeon traps, medieval weapons, arcane effects) and avoid modern racing or vehicular motifs.
- When adding new assets or identifiers, prefer descriptive names that match the fantasy tone, and document any temporary placeholders so they can be replaced later.
