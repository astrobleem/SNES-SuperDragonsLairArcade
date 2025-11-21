# Generated DirkSimple event XMLs

This directory contains XML chapters produced from `tools/game.lua` using the Lua-to-XML converter in `tools/game_lua_to_xml.py`. The files mirror the DirkSimple scene table so the SNES pipeline can ingest the same branching and timing data that `game.lua` uses at runtime.

## Regenerating
Run the converter to rebuild the XML set after editing `game.lua`:

```
python3 tools/game_lua_to_xml.py --input tools/game.lua --output-dir data/events
```

Each sequence in the `scenes` table becomes a `<chapter>` file named `scene_sequence.xml` with the timing windows, checkpoints, and branching destinations defined in the Lua source.
