# Dragon's Lair Chapter XMLs

This directory contains the curated Dragon's Lair chapter XMLs (516 files) used by the SNES toolchain. These are derived from DirkSimple game data and are the authoritative descriptors consumed by the conversion tools.

# Event XML Reference

Each file defines one chapter with a timeline, events, and result branches.

## Chapter Layout
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

## Timing Conventions
- All `timestart`/`timeend` elements use **minute/second/millisecond** attributes instead of absolute frame counts. The conversion script (`xmlsceneparser.py`) multiplies these into frame indexes using the clip FPS (23.9777 fps).
- Individual events often re-state their own `<timeline>` window inside the chapter range so the tooling can trim per-input snippets or build MSU-1 frame folders with matching offsets.

## Conversion Pipeline
1. Export or hand-author XMLs in this layout for each chapter.
2. Run `xmlsceneparser.py` with the XML file. It generates:
   - `chapter.script` — assembly code (~10 bytes: CHAPTER macro + 24-bit pointer to event data + DIE)
   - `chapter.data` — event data table (7 words per event, terminated by `.dw 0`)
3. All chapter scripts aggregate into `data/chapters/chapter.include`; all data into `data/chapters/chapter_data.include`.
4. MSU-1 video data is generated separately via `tools/generate_msu_data.py`.

This documentation should be enough to rebuild the Dragon's Lair event XMLs — or author new ones — using the existing tooling without needing to reverse-engineer the individual files.
