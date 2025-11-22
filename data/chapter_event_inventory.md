# Chapter Script Event Inventory

This file summarizes the event types referenced in chapter script resources and compares them with the currently implemented event objects.

## Summary

- Chapters analyzed: 516
- Unique event types referenced: 2
- Chapter markers referenced: 118
- Implemented event object types: 34
- Referenced entries without implemented handlers: 0

## Implemented event object types

- accelerate
- brake
- change_dash
- chapter
- checkpoint
- confirm
- crypt_creeps_encounter
- cutscene
- direction_generic
- direction_left
- direction_right
- falling_platform_phase
- flaming_ropes_hazard
- flaming_ropes_route
- flying_horse_collision
- flying_horse_lane
- giddy_goons_grapple
- giddy_goons_swarm
- hide_dash
- hide_sunscreen
- rolling_balls_ball
- rolling_balls_crush
- room_transition
- seq_generic
- shake
- show_help
- target
- tentacle_room_grab
- tentacle_room_path
- throne_room_state
- tilting_room_navigation
- touch
- underground_river_chain
- underground_river_phase

## Chapter marker → event handler mapping

| Chapter marker | Generic handler | Notes |
| --- | --- | --- |
| enter_room*, start_* | room_transition | Transition id passed as handler argument |
| seq* | seq_generic | Sequence id derived from the numeric suffix |
| exit_room, game_over | cutscene | Uses the cutscene template-defined helpers |

## Referenced chapter event types not implemented

- None – every referenced event type has an implementation.
