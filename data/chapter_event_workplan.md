# Chapter Event Implementation Work Plan

This work plan groups the 95 unmapped chapter markers from `data/chapter_event_inventory.md` by their chapter contexts and outlines how to implement their handlers under `src/object/event/`.

## Template leverage and new class scaffolding
- **Cutscene-friendly markers** can extend `Event.cutscene` with new cutscene identifiers and arguments rather than introducing new assembly code. Candidates include the attract mode intro, passive deaths (e.g., burns, falls, poison), and narrative transitions (e.g., throne interactions).
- **Reusable chapter templates** should branch from `Event.template` or `abstract.Event` to encapsulate repeated behaviors inside a chapter:
  - **RollingBalls**: shared collision/spawn handling for colored balls and crush outcomes.
  - **UndergroundRiver**: parameterized rapid/boulder/whirlpool stages with shared timing and chain-grab fail states.
  - **TentacleRoom**: branching inputs for multiple escape routes versus tentacle grabs.
  - **FallingPlatform**: long/short platform phases with shared jump sets and landing resolution.
- **Bespoke logic** is required where player control or physics adjustments differ from existing templates (e.g., steering on flying horse, alternating electrified floor/sword states, multi-actor giddy goons fights).

## Chapter grouping and handler plan

### Attract Mode
- **Markers**: `mode_attract_movie`, `mode_insert_coins`.
- **Plan**: Map both to new cutscene entries via `Event.cutscene` (no new class) to trigger the attract/coin sequences.

### Introduction
- **Markers**: `introduction_castle_exterior`.
- **Plan**: Add a `cutscene` entry with chapter-specific script id; no bespoke code needed.

### Rolling Balls
- **Markers**: `balls_blue_ball`, `balls_green_ball`, `balls_orange_ball`, `balls_purple_ball`, `balls_red_ball`, `big_ball_crushes`, `pit_in_ground`, `small_ball_crushes`.
- **Plan**: Introduce `Event.rolling_balls_ball` (parameterized color) and `Event.rolling_balls_crush` (big/small) classes for spawn and collision resolution. `pit_in_ground` can reuse `Event.cutscene` if purely cinematic; otherwise, add a flag to the crush handler for pit-specific animation.

### Underground River
- **Markers**: `bounce_to_chain`, `river_boulders_crash`, `river_boulders_crash2`, `river_boulders_crash3`, `river_boulders_crash4`, `river_first_boulders`, `river_first_rapids`, `river_first_whirlpools`, `river_fourth_boulders`, `river_fourth_rapids`, `river_fourth_whirlpools`, `river_miss_chain`, `river_rapids_crash`, `river_second_boulders`, `river_second_rapids`, `river_second_whirlpools`, `river_third_boulders`, `river_third_rapids`, `river_third_whirlpools`, `river_whirlpools_crash`.
- **Plan**: Build `Event.underground_river_phase` (phase enum covering rapids/boulders/whirlpools across first–fourth) to share timer, knockback, and camera shake logic. Layer `Event.underground_river_chain` for chain-target interactions (`bounce_to_chain`, `river_miss_chain`). Crashes can be cutscene variants triggered from the phase handler.

### Alice Room
- **Markers**: `burned_to_death`, `room_drinks_potion`.
- **Plan**: Use a `cutscene` entry for the potion animation. If burns are scripted, map to `cutscene`; if tied to player hazard checks, add `Event.alice_room_fire` with a damage trigger reused by the dragon fire variant below.

### Flying Horse
- **Markers**: `burned_to_death`, `hit_brick_wall`, `horse_brick_wall`, `horse_fifth_fire`, `horse_fourth_fire`, `horse_hit_pillar`, `horse_second_fire`, `horse_third_fire`.
- **Plan**: Create `Event.flying_horse_lane` (parameterized fire index) to manage timing of consecutive fire obstacles. Add `Event.flying_horse_collision` for wall/pillar impacts, emitting `cutscene` results. Reuse `alice_room_fire` logic if burn handling is shared.

### Tentacle Room
- **Markers**: `death_by_door`, `jump_to_door`, `jump_to_stairs`, `jump_to_table`, `kills_first_tentacle`, `left_tentacle_grabs`, `squeeze_to_death`, `to_weapon_rack`, `two_front_war`.
- **Plan**: Implement `Event.tentacle_room_path` (door/stairs/table/weapon rack options) for branching direction prompts. Add `Event.tentacle_room_grab` for `left_tentacle_grabs` and `squeeze_to_death/death_by_door` resolutions. `two_front_war` and `kills_first_tentacle` can be state flags within the path handler; death outcomes can fall back to `cutscene` entries.

### Crypt Creeps
- **Markers**: `attacked_first_hand`, `attacked_second_hand`, `captured_by_ghouls`, `creeps_enter_crypt`, `creeps_jumped_skulls`, `creeps_jumped_slime`, `crushed_by_hand`, `eaten_by_skulls`, `eaten_by_slime`, `overpowered_by_skulls`.
- **Plan**: Create `Event.crypt_creeps_encounter` to manage hand/ghoul/skull/slime states with parameterized hazard type. Non-interactive death scenes (`captured_by_ghouls`, `overpowered_by_skulls`) can be `cutscene` entries triggered by the encounter handler.

### Giddy Goons
- **Markers**: `fall_to_death`, `goons_climbs_stairs`, `kill_upper_goons`, `kills_first_goon`, `knife_in_back`, `one_before_swarm`, `shoves_off_edge`, `swarm_of_goons`.
- **Plan**: Build `Event.giddy_goons_swarm` to manage multi-goon waves (`one_before_swarm`, `swarm_of_goons`, `kill_upper_goons`). Add `Event.giddy_goons_grapple` for shove/knife/fall outcomes, using `cutscene` for fall/knife cinematic beats. `goons_climbs_stairs` can reuse a `direction_*` cue with a goon-specific animation argument inside the swarm handler.

### Falling Platforms (Long/Short/Vestibule)
- **Markers**: `fell_to_death`, `long_crash_landing`, `long_missed_jump`, `second_jump_set`, `short_crash_landing`, `short_missed_jump`, `third_jump_set`, `vestibule_stagger`.
- **Plan**: Introduce `Event.falling_platform_phase` with a `length` flag (long/short/vestibule) to manage jump sets and landing checks. Miss/crash outcomes can call `cutscene`. `fell_to_death` can be a shared cutscene entry reused by both lengths.

### Tilting Room
- **Markers**: `falls_to_death`, `room_catches_fire`, `room_jumps_back`, `room_jumps_forward`, `room_wrong_door`.
- **Plan**: Add `Event.tilting_room_navigation` to drive branching movement prompts and state (`room_jumps_back/forward`, `room_wrong_door`). Fire/fall deaths can map to `cutscene` entries triggered when timers expire or wrong choices occur.

### Flaming Ropes
- **Markers**: `fall_to_death`, `flaming_ropes_rope1`, `flaming_ropes_rope2`, `flaming_ropes_rope3`, `ropes_burns_hands`, `ropes_misses_landing`, `ropes_platform_sliding`.
- **Plan**: Build `Event.flaming_ropes_route` (rope index 1–3) to control rope selection and sliding speed. Add `Event.flaming_ropes_hazard` for burns/missed landing, calling shared `fall_to_death` cutscene when appropriate.

### Throne Room
- **Markers**: `room_electrified_floor`, `room_electrified_sword`, `room_electrified_throne`, `room_first_jump`, `room_second_jump`, `room_on_throne`.
- **Plan**: Implement `Event.throne_room_state` managing alternating electrified floor/sword/throne hazards and jump prompts. Successful sequence leads to `room_on_throne` cutscene entry; failures trigger cutscene deaths.

### Wind Room
- **Markers**: `room_sucked_in`.
- **Plan**: Map to `cutscene` entry; no bespoke code unless wind physics are interactive, in which case add `Event.wind_room_pull` to manage movement slowdown before the cutscene.

### Bower
- **Markers**: `trapped_in_wall`.
- **Plan**: Use `cutscene` entry for the trap animation; no new class expected.

### Dragon's Lair Endgame
- **Markers**: `dragons_lair_endgame`.
- **Plan**: Add dedicated `Event.dragons_lair_endgame` handler for boss outro/cinematic triggers; can extend `Event.template` if purely scripted.

## Implementation order
1. **Cutscene mappings**: Add `Event.cutscene` entries for attract mode, introduction, wind room, bower, and all simple death/narrative markers (burn/fall/electrified/poison) to unblock non-interactive paths.
2. **Reusable chapter templates**: Implement `rolling_balls_*`, `underground_river_*`, `tentacle_room_*`, and `falling_platform_phase` to cover the largest marker clusters with shared code.
3. **Combat/physics-heavy chapters**: Add `crypt_creeps_encounter`, `giddy_goons_swarm/grapple`, `flying_horse_lane/collision`, and `throne_room_state`, which need bespoke timing and multi-actor handling.
4. **Remaining polish**: Wire cutscene fallbacks and integrate new handler args into chapter scripts, ensuring duplicated markers (e.g., `burned_to_death`, `fall_to_death`) reuse shared cutscene ids.
