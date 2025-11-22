# Dragon's Lair chapter XMLs

This directory now tracks the curated Dragon's Lair chapter XMLs used by the SNES toolchain. The legacy RoadBlaster iPhone XML dumps and the auxiliary Lua-to-XML generator scripts were removed to avoid confusion; the files checked in here are the authoritative descriptors consumed by the conversion tools.

# Event XML Reference

Each file mirrors the format produced by the classic iPhone XML scene dumps so the legacy tooling (for example, `xmlsceneparser.py` and the frame/audio extraction steps) can recreate chapters or alternate XMLs without guessing at tag semantics.

## Chapter layout
- **Root `<chapter>`**: Optional `name` attribute; otherwise the filename defines the chapter name.
- **`<timeline>`**: Required start/end bounds for the clip. Times are split into `min`, `second`, and `ms` attributes so they can be mapped directly to frame counts when chopping source video.
- **`<params>`**: Key/value pairs that configure how the engine should treat the clip (for example, `controller`, `cockpit`, `level`, debug switches). Keys are stored as `<int>` or `<str>` tags with `key`/`value` attributes.
- **`<macros>`**: Optional macro overrides scoped to the chapter; when present they shadow any global macros loaded elsewhere in the pipeline.
- **`<events>`**: Input windows and helpers that occur between `timestart` and `timeend`. Common event types include:
  - `checkpoint`: Marks respawn points; usually paired with the chapter entry timestamp.
  - `direction`: Records required controller direction (`type`), score reward, and failure branch via `<result>`.
  - `confirm`: Waits for a start/confirm input before branching to another chapter.
  - `hide-dash`: UI helper to hide the HUD during prerendered sequences.
  - Other game-specific helpers follow the same structure: a `<timeline>`, optional `<params>`, and one or more `<result>` branches chosen by `value`.
- **`<result>`**: Defines the chapter that should play next when the chapter finishes or when an event branch is taken. Branches use `<playchapter name="..."/>` to jump forward; a single `<result>` outside of `<events>` acts as the default completion path.

## Timing conventions
- All `timestart`/`timeend` elements use **minute/second/millisecond** attributes instead of absolute frame counts. The original conversion scripts multiply these into frame indexes using the clip FPS (23.9777 in `xmlsceneparser.py`).
- Individual events often re-state their own `<timeline>` window inside the chapter range so the tooling can trim per-input snippets or build MSU-1 frame folders with matching offsets.

## Recreating alternate XMLs
1. Export or hand-author XMLs in this layout for each chapter you want to feed into the conversion tools.
2. Run `xmlsceneparser.py` with the XML file, output folder, and optional video/audio inputs. It will:
   - Generate `chapter.script`/`chapter.include` references.
   - Slice frames/audio for the chapter when media is provided.
   - Copy any already-converted frame binaries if you point `convertedoutfolder`/`convertedframefolder` at an existing build.
3. Feed the extracted frames into the usual `gracon.py` → `animationWriter.py`/`msu1blockwriter.py` pipeline.

This documentation should be enough to rebuild the Dragon's Lair event XMLs—or author new ones—using the original tooling without needing to reverse-engineer the individual files.
