# Chapter Script Event Inventory

This file summarizes the event types referenced in chapter script resources and compares them with the currently implemented event objects.

## Summary

- Chapters analyzed: 516
- Unique event types referenced: 2
- Chapter markers referenced: 118
- Implemented event object types: 18
- Referenced entries without implemented handlers: 79

## Implemented event object types

- accelerate
- brake
- change_dash
- chapter
- checkpoint
- confirm
- cutscene
- direction_generic
- direction_left
- direction_right
- hide_dash
- hide_sunscreen
- room_transition
- seq_generic
- shake
- show_help
- target
- touch

## Chapter marker → event handler mapping

| Chapter marker | Generic handler | Notes |
| --- | --- | --- |
| enter_room*, start_* | room_transition | Transition id passed as handler argument |
| seq* | seq_generic | Sequence id derived from the numeric suffix |
| exit_room, game_over | cutscene | Uses the cutscene template-defined helpers |

## Referenced chapter event types not implemented

- **attacked_first_hand** – crypt_creeps_attacked_first_hand
- **attacked_second_hand** – crypt_creeps_attacked_second_hand
- **balls_blue_ball** – rolling_balls_blue_ball
- **balls_green_ball** – rolling_balls_green_ball
- **balls_orange_ball** – rolling_balls_orange_ball
- **balls_purple_ball** – rolling_balls_purple_ball
- **balls_red_ball** – rolling_balls_red_ball
- **big_ball_crushes** – rolling_balls_big_ball_crushes
- **bounce_to_chain** – underground_river_bounce_to_chain
- **captured_by_ghouls** – crypt_creeps_captured_by_ghouls
- **creeps_enter_crypt** – crypt_creeps_enter_crypt
- **creeps_jumped_skulls** – crypt_creeps_jumped_skulls
- **creeps_jumped_slime** – crypt_creeps_jumped_slime
- **crushed_by_hand** – crypt_creeps_crushed_by_hand
- **death_by_door** – tentacle_room_squeeze_to_death_by_door
- **eaten_by_skulls** – crypt_creeps_eaten_by_skulls
- **eaten_by_slime** – crypt_creeps_eaten_by_slime
- **flaming_ropes_rope1** – flaming_ropes_rope1
- **flaming_ropes_rope2** – flaming_ropes_rope2
- **flaming_ropes_rope3** – flaming_ropes_rope3
- **goons_climbs_stairs** – giddy_goons_climbs_stairs
- **hit_brick_wall** – flying_horse_hit_brick_wall
- **horse_brick_wall** – flying_horse_brick_wall
- **horse_fifth_fire** – flying_horse_fifth_fire
- **horse_fourth_fire** – flying_horse_fourth_fire
- **horse_hit_pillar** – flying_horse_hit_pillar
- **horse_second_fire** – flying_horse_second_fire
- **horse_third_fire** – flying_horse_third_fire
- **jump_to_door** – tentacle_room_jump_to_door
- **jump_to_stairs** – tentacle_room_jump_to_stairs
- **jump_to_table** – tentacle_room_jump_to_table
- **kill_upper_goons** – giddy_goons_kill_upper_goons
- **kills_first_goon** – giddy_goons_kills_first_goon
- **kills_first_tentacle** – tentacle_room_kills_first_tentacle
- **knife_in_back** – giddy_goons_knife_in_back
- **left_tentacle_grabs** – tentacle_room_left_tentacle_grabs
- **long_crash_landing** – falling_platform_long_crash_landing
- **long_missed_jump** – falling_platform_long_missed_jump
- **one_before_swarm** – giddy_goons_fight_off_one_before_swarm
- **overpowered_by_skulls** – crypt_creeps_overpowered_by_skulls
- **river_boulders_crash** – underground_river_boulders_crash
- **river_boulders_crash2** – underground_river_boulders_crash2
- **river_boulders_crash3** – underground_river_boulders_crash3
- **river_boulders_crash4** – underground_river_boulders_crash4
- **river_first_boulders** – underground_river_first_boulders
- **river_first_rapids** – underground_river_first_rapids
- **river_first_whirlpools** – underground_river_first_whirlpools
- **river_fourth_boulders** – underground_river_fourth_boulders
- **river_fourth_rapids** – underground_river_fourth_rapids
- **river_fourth_whirlpools** – underground_river_fourth_whirlpools
- **river_miss_chain** – underground_river_miss_chain
- **river_rapids_crash** – underground_river_rapids_crash
- **river_second_boulders** – underground_river_second_boulders
- **river_second_rapids** – underground_river_second_rapids
- **river_second_whirlpools** – underground_river_second_whirlpools
- **river_third_boulders** – underground_river_third_boulders
- **river_third_rapids** – underground_river_third_rapids
- **river_third_whirlpools** – underground_river_third_whirlpools
- **river_whirlpools_crash** – underground_river_whirlpools_crash
- **room_drinks_potion** – alice_room_drinks_potion
- **room_electrified_floor** – throne_room_electrified_floor
- **room_electrified_sword** – throne_room_electrified_sword
- **room_electrified_throne** – throne_room_electrified_throne
- **room_first_jump** – throne_room_first_jump
- **room_jumps_back** – tilting_room_jumps_back
- **room_jumps_forward** – tilting_room_jumps_forward
- **room_second_jump** – throne_room_second_jump
- **ropes_platform_sliding** – flaming_ropes_platform_sliding
- **second_jump_set** – falling_platform_long_second_jump_set
- **short_crash_landing** – falling_platform_short_crash_landing
- **short_missed_jump** – falling_platform_short_missed_jump
- **shoves_off_edge** – giddy_goons_shoves_off_edge
- **small_ball_crushes** – rolling_balls_small_ball_crushes
- **squeeze_to_death** – tentacle_room_squeeze_to_death
- **swarm_of_goons** – giddy_goons_swarm_of_goons
- **third_jump_set** – falling_platform_long_third_jump_set
- **to_weapon_rack** – tentacle_room_jump_to_weapon_rack
- **two_front_war** – tentacle_room_two_front_war
- **vestibule_stagger** – vestibule_stagger
