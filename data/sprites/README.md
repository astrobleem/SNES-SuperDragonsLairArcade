# Sprite prompts overview

The `.gfx_sprite` files in this folder are compiled animation assets referenced by the game's `SpriteAnimationLUT`, so prompt authors can align replacements with in-game usage.

- `left_arrow.gfx_sprite` / `right_arrow.gfx_sprite`: HUD arrows that blink as quick-time cues to dodge hazards or pivot directions, echoing Dragon's Lair reactions.
- `up_arrow.gfx_sprite`: Upward cue that flashes to prompt leaps onto ledges, grabs onto ropes, or other rising actions.
- `down_arrow.gfx_sprite`: Downward cue that pulses to signal ducking under blades, sliding away from strikes, or dropping through openings.
- `turbo.gfx_sprite`: Former racing callout; unused for Dragon's Lair and should be left unreferenced.
- `brake.gfx_sprite`: Former racing warning; unused for Dragon's Lair and should be left unreferenced.
- `dashboard.gfx_sprite`: HUD dashboard overlay framing gauges without hiding the road.
- `super.gfx_sprite`: HUD burst effect when the super state is active.
- `steering_wheel.normal/left/right.gfx_sprite`: Legacy racing wheel trio that is not required for Dragon's Lair scenes; keep unused.
- `life_car.gfx_sprite` / `life_counter.gfx_sprite`: Life icon row and counter that scroll upward after a timer, replacing cars with Dirk head icons.
- `points.normal.gfx_sprite`: Falling score popup for standard points.
- `points.extra.gfx_sprite`: Faster falling bonus points popup that precedes the bang burst.
- `bang.gfx_sprite`: Burst effect that appears after extra bonus points trigger.

Use these notes to craft Dragon's Lair–style visual prompts or replacements that match gameplay context.
