# Sprite prompts overview

The `.gfx_sprite` files in this folder are compiled animation assets referenced by the game's `SpriteAnimationLUT`, so prompt authors can align replacements with in-game usage.

- `left_arrow.gfx_sprite` / `right_arrow.gfx_sprite`: HUD arrows that blink to signal turns.
- `turbo.gfx_sprite`: HUD callout that pulses when turbo is armed.
- `brake.gfx_sprite`: HUD warning that flashes when braking is required.
- `dashboard.gfx_sprite`: HUD dashboard overlay framing gauges without hiding the road.
- `super.gfx_sprite`: HUD burst effect when the super state is active.
- `steering_wheel.normal/left/right.gfx_sprite`: Three-frame steering wheel states showing neutral, left lean, and right lean inputs.
- `life_car.gfx_sprite` / `life_counter.gfx_sprite`: Life icon row and counter that scroll upward after a timer, replacing cars with Dirk head icons.
- `points.normal.gfx_sprite`: Falling score popup for standard points.
- `points.extra.gfx_sprite`: Faster falling bonus points popup that precedes the bang burst.
- `bang.gfx_sprite`: Burst effect that appears after extra bonus points trigger.

Use these notes to craft Dragon's Lair–style visual prompts or replacements that match gameplay context.
