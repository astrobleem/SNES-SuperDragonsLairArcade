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

## Adding New Sprites

To add a new sprite (e.g., `down_arrow`) to the system, you must complete both the **Asset** and **Code** steps. The system does not automatically detect or use new sprites just by their presence in this folder.

### 1. Asset Requirements
- Create a directory named `<sprite_name>.gfx_sprite` in `data/sprites/`.
- Place your frame images (PNG, GIF, BMP) inside this directory. They should be sorted alphabetically for the animation order.
- The build system (Makefile) will automatically compile this folder into a `.animation` file during the build.
- *Note: The `.txt` files in this directory are for documentation/AI-prompting purposes only and are not used by the build system.*

### 2. Code Requirements
You must implement the sprite logic and register it in the engine:
1.  **Implementation**: Create `src/object/sprite/<sprite_name>.65816` (assembly logic) and `src/object/sprite/<sprite_name>.h` (header). You can copy `left_arrow.65816` as a template.
2.  **Registration**:
    - Open `src/object/sprite/abstract.Sprite.h`.
    - Add your sprite to the `SpriteAnimationLUT` table.
    - Add a `SPRITE_ANIMATION <sprite_name>` macro call.

Once both assets and code are in place, the sprite can be spawned and used in the game.
