import os
import shutil

mapping = {
    'falling_platform_long_third_jump_set': 'fall_plat_long_jump3',
    'falling_platform_short_crash_landing': 'fall_plat_short_crash',
    'falling_platform_short_fell_to_death': 'fall_plat_short_death',
    'giddy_goons_fight_off_one_before_swarm': 'goons_fight_one_swarm',
    'tentacle_room_squeeze_to_death_by_door': 'tentacle_squeeze_death',
    'underground_river_fourth_whirlpools': 'ug_river_whirl4',
    'underground_river_second_whirlpools': 'ug_river_whirl2',
    'yellow_brick_road_reversed_enter_room': 'ybr_rev_enter',
    'yellow_brick_road_reversed_game_over': 'ybr_rev_gameover',
    'yellow_brick_road_reversed_start_alive': 'ybr_rev_alive',
    'yellow_brick_road_reversed_start_dead': 'ybr_rev_dead',
    'falling_platform_long_reversed_seq2': 'fall_plat_long_rev_seq2',
    'falling_platform_long_reversed_seq3': 'fall_plat_long_rev_seq3',
    'falling_platform_long_reversed_seq4': 'fall_plat_long_rev_seq4',
    'falling_platform_long_reversed_seq5': 'fall_plat_long_rev_seq5',
    'falling_platform_long_reversed_seq6': 'fall_plat_long_rev_seq6',
    'falling_platform_long_reversed_seq7': 'fall_plat_long_rev_seq7',
    'falling_platform_long_reversed_seq8': 'fall_plat_long_rev_seq8',
    'falling_platform_long_reversed_start_alive': 'fall_plat_long_rev_alive',
    'falling_platform_long_reversed_start_dead': 'fall_plat_long_rev_dead',
    'falling_platform_long_second_jump_set': 'fall_plat_long_jump2',
    'electric_cage_and_geyser_enter_room': 'elec_cage_enter',
    'electric_cage_and_geyser_start_alive': 'elec_cage_alive',
    'electric_cage_and_geyser_start_dead': 'elec_cage_dead',
    'falling_platform_long_crash_landing': 'fall_plat_long_crash',
    'falling_platform_long_fell_to_death': 'fall_plat_long_death',
    'falling_platform_long_reversed_enter_room': 'fall_plat_long_rev_enter',
    'falling_platform_long_reversed_game_over': 'fall_plat_long_rev_gameover',
    'crypt_creeps_overpowered_by_skulls': 'crypt_creeps_skulls_death',
    'underground_river_second_boulders': 'ug_river_boulder2',
    'underground_river_third_boulders': 'ug_river_boulder3',
    'underground_river_third_whirlpools': 'ug_river_whirl3',
    'underground_river_whirlpools_crash': 'ug_river_whirl_crash',
    'yellow_brick_road_reversed_seq10': 'ybr_rev_seq10',
    'yellow_brick_road_reversed_seq11': 'ybr_rev_seq11',
    'yellow_brick_road_reversed_seq12': 'ybr_rev_seq12',
    'yellow_brick_road_reversed_seq14': 'ybr_rev_seq14',
    'yellow_brick_road_reversed_seq15': 'ybr_rev_seq15',
    'yellow_brick_road_reversed_seq16': 'ybr_rev_seq16',
    'yellow_brick_road_reversed_seq17': 'ybr_rev_seq17',
    'yellow_brick_road_reversed_seq17': 'ybr_rev_seq17',
    'yellow_brick_road_reversed_seq18': 'ybr_rev_seq18',
    'tentacle_room_left_tentacle_grabs': 'tentacle_left_grab',
    'underground_river_boulders_crash': 'ug_river_boulder_crash',
    'underground_river_boulders_crash2': 'ug_river_boulder_crash2',
    'underground_river_boulders_crash3': 'ug_river_boulder_crash3',
    'underground_river_boulders_crash4': 'ug_river_boulder_crash4',
    'underground_river_bounce_to_chain': 'ug_river_bounce_chain',
    'underground_river_first_boulders': 'ug_river_boulder1',
    'underground_river_first_whirlpools': 'ug_river_whirl1',
    'underground_river_fourth_boulders': 'ug_river_boulder4',
    'flying_horse_reversed_start_alive': 'fly_horse_rev_alive',
    'flying_horse_reversed_start_dead': 'fly_horse_rev_dead',
    'grim_reaper_reversed_start_alive': 'grim_reaper_rev_alive',
    'robot_knight_reversed_enter_room': 'robot_knight_rev_enter',
    'robot_knight_reversed_start_alive': 'robot_knight_rev_alive',
    'robot_knight_reversed_start_dead': 'robot_knight_rev_dead',
    'rolling_balls_small_ball_crushes': 'roll_ball_small_crush',
    'tentacle_room_jump_to_weapon_rack': 'tentacle_jump_rack',
    'tentacle_room_kills_first_tentacle': 'tentacle_kill_first',
    'falling_platform_short_missed_jump': 'fall_plat_short_miss',
    'falling_platform_short_start_alive': 'fall_plat_short_alive',
    'falling_platform_short_start_dead': 'fall_plat_short_dead',
    'flaming_ropes_reversed_enter_room': 'flame_rope_rev_enter',
    'flaming_ropes_reversed_game_over': 'flame_rope_rev_gameover',
    'flaming_ropes_reversed_start_alive': 'flame_rope_rev_alive',
    'flaming_ropes_reversed_start_dead': 'flame_rope_rev_dead',
    'flattening_staircase_start_alive': 'flat_stair_alive',
    'flying_horse_reversed_enter_room': 'fly_horse_rev_enter',
    'crypt_creeps_reversed_start_dead': 'crypt_creeps_rev_dead',
    'electric_cage_and_geyser_game_over': 'elec_cage_gameover',
    'falling_platform_long_enter_room': 'fall_plat_long_enter',
    'falling_platform_long_missed_jump': 'fall_plat_long_miss',
    'falling_platform_long_start_alive': 'fall_plat_long_alive',
    'falling_platform_long_start_dead': 'fall_plat_long_dead',
    'falling_platform_short_enter_room': 'fall_plat_short_enter',
    'falling_platform_short_exit_room': 'fall_plat_short_exit',
    'falling_platform_short_game_over': 'fall_plat_short_gameover',
    'crypt_creeps_attacked_first_hand': 'crypt_creeps_atk_hand1',
    'crypt_creeps_attacked_second_hand': 'crypt_creeps_atk_hand2',
    'crypt_creeps_reversed_enter_room': 'crypt_creeps_rev_enter',
    'crypt_creeps_reversed_start_alive': 'crypt_creeps_rev_alive'
import os
import shutil

mapping = {
    'falling_platform_long_third_jump_set': 'fall_plat_long_jump3',
    'falling_platform_short_crash_landing': 'fall_plat_short_crash',
    'falling_platform_short_fell_to_death': 'fall_plat_short_death',
    'giddy_goons_fight_off_one_before_swarm': 'goons_fight_one_swarm',
    'tentacle_room_squeeze_to_death_by_door': 'tentacle_squeeze_death',
    'underground_river_fourth_whirlpools': 'ug_river_whirl4',
    'underground_river_second_whirlpools': 'ug_river_whirl2',
    'yellow_brick_road_reversed_enter_room': 'ybr_rev_enter',
    'yellow_brick_road_reversed_game_over': 'ybr_rev_gameover',
    'yellow_brick_road_reversed_start_alive': 'ybr_rev_alive',
    'yellow_brick_road_reversed_start_dead': 'ybr_rev_dead',
    'falling_platform_long_reversed_seq2': 'fall_plat_long_rev_seq2',
    'falling_platform_long_reversed_seq3': 'fall_plat_long_rev_seq3',
    'falling_platform_long_reversed_seq4': 'fall_plat_long_rev_seq4',
    'falling_platform_long_reversed_seq5': 'fall_plat_long_rev_seq5',
    'falling_platform_long_reversed_seq6': 'fall_plat_long_rev_seq6',
    'falling_platform_long_reversed_seq7': 'fall_plat_long_rev_seq7',
    'falling_platform_long_reversed_seq8': 'fall_plat_long_rev_seq8',
    'falling_platform_long_reversed_start_alive': 'fall_plat_long_rev_alive',
    'falling_platform_long_reversed_start_dead': 'fall_plat_long_rev_dead',
    'falling_platform_long_second_jump_set': 'fall_plat_long_jump2',
    'electric_cage_and_geyser_enter_room': 'elec_cage_enter',
    'electric_cage_and_geyser_start_alive': 'elec_cage_alive',
    'electric_cage_and_geyser_start_dead': 'elec_cage_dead',
    'falling_platform_long_crash_landing': 'fall_plat_long_crash',
    'falling_platform_long_fell_to_death': 'fall_plat_long_death',
    'falling_platform_long_reversed_enter_room': 'fall_plat_long_rev_enter',
    'falling_platform_long_reversed_game_over': 'fall_plat_long_rev_gameover',
    'crypt_creeps_overpowered_by_skulls': 'crypt_creeps_skulls_death',
    'underground_river_second_boulders': 'ug_river_boulder2',
    'underground_river_third_boulders': 'ug_river_boulder3',
    'underground_river_third_whirlpools': 'ug_river_whirl3',
    'underground_river_whirlpools_crash': 'ug_river_whirl_crash',
    'yellow_brick_road_reversed_seq10': 'ybr_rev_seq10',
    'yellow_brick_road_reversed_seq11': 'ybr_rev_seq11',
    'yellow_brick_road_reversed_seq12': 'ybr_rev_seq12',
    'yellow_brick_road_reversed_seq14': 'ybr_rev_seq14',
    'yellow_brick_road_reversed_seq15': 'ybr_rev_seq15',
    'yellow_brick_road_reversed_seq16': 'ybr_rev_seq16',
    'yellow_brick_road_reversed_seq17': 'ybr_rev_seq17',
    'yellow_brick_road_reversed_seq17': 'ybr_rev_seq17',
    'yellow_brick_road_reversed_seq18': 'ybr_rev_seq18',
    'tentacle_room_left_tentacle_grabs': 'tentacle_left_grab',
    'underground_river_boulders_crash': 'ug_river_boulder_crash',
    'underground_river_boulders_crash2': 'ug_river_boulder_crash2',
    'underground_river_boulders_crash3': 'ug_river_boulder_crash3',
    'underground_river_boulders_crash4': 'ug_river_boulder_crash4',
    'underground_river_bounce_to_chain': 'ug_river_bounce_chain',
    'underground_river_first_boulders': 'ug_river_boulder1',
    'underground_river_first_whirlpools': 'ug_river_whirl1',
    'underground_river_fourth_boulders': 'ug_river_boulder4',
    'flying_horse_reversed_start_alive': 'fly_horse_rev_alive',
    'flying_horse_reversed_start_dead': 'fly_horse_rev_dead',
    'grim_reaper_reversed_start_alive': 'grim_reaper_rev_alive',
    'robot_knight_reversed_enter_room': 'robot_knight_rev_enter',
    'robot_knight_reversed_start_alive': 'robot_knight_rev_alive',
    'robot_knight_reversed_start_dead': 'robot_knight_rev_dead',
    'rolling_balls_small_ball_crushes': 'roll_ball_small_crush',
    'tentacle_room_jump_to_weapon_rack': 'tentacle_jump_rack',
    'tentacle_room_kills_first_tentacle': 'tentacle_kill_first',
    'falling_platform_short_missed_jump': 'fall_plat_short_miss',
    'falling_platform_short_start_alive': 'fall_plat_short_alive',
    'falling_platform_short_start_dead': 'fall_plat_short_dead',
    'flaming_ropes_reversed_enter_room': 'flame_rope_rev_enter',
    'flaming_ropes_reversed_game_over': 'flame_rope_rev_gameover',
    'flaming_ropes_reversed_start_alive': 'flame_rope_rev_alive',
    'flaming_ropes_reversed_start_dead': 'flame_rope_rev_dead',
    'flattening_staircase_start_alive': 'flat_stair_alive',
    'flying_horse_reversed_enter_room': 'fly_horse_rev_enter',
    'crypt_creeps_reversed_start_dead': 'crypt_creeps_rev_dead',
    'electric_cage_and_geyser_game_over': 'elec_cage_gameover',
    'falling_platform_long_enter_room': 'fall_plat_long_enter',
    'falling_platform_long_missed_jump': 'fall_plat_long_miss',
    'falling_platform_long_start_alive': 'fall_plat_long_alive',
    'falling_platform_long_start_dead': 'fall_plat_long_dead',
    'falling_platform_short_enter_room': 'fall_plat_short_enter',
    'falling_platform_short_exit_room': 'fall_plat_short_exit',
    'falling_platform_short_game_over': 'fall_plat_short_gameover',
    'crypt_creeps_attacked_first_hand': 'crypt_creeps_atk_hand1',
    'crypt_creeps_attacked_second_hand': 'crypt_creeps_atk_hand2',
    'crypt_creeps_reversed_enter_room': 'crypt_creeps_rev_enter',
    'crypt_creeps_reversed_start_alive': 'crypt_creeps_rev_alive'
}

events_dir = 'data/events'
chapters_dir = 'data/chapters'
include_file = 'data/chapters/chapter.include'

import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rename long paths in events and chapters.")
    parser.parse_args()

    # Rename XMLs
    for long_name, short_name in mapping.items():
        old_xml = os.path.join(events_dir, long_name + '.xml')
        new_xml = os.path.join(events_dir, short_name + '.xml')
        if os.path.exists(old_xml):
            print(f"Renaming {old_xml} to {new_xml}")
            os.rename(old_xml, new_xml)
        
        # Remove old chapter dir if exists
        old_chap_dir = os.path.join(chapters_dir, long_name)
        if os.path.exists(old_chap_dir):
            print(f"Removing {old_chap_dir}")
            shutil.rmtree(old_chap_dir)

    # Update chapter.include
    if os.path.exists(include_file):
        with open(include_file, 'r') as f:
            content = f.read()
        
        for long_name, short_name in mapping.items():
            if long_name in content:
                print(f"Replacing {long_name} with {short_name}")
                content = content.replace(long_name, short_name)

        with open(include_file, 'w') as f:
            f.write(content)
        print(f"Updated {include_file}")

    # Check for remaining long paths
    if os.path.exists(include_file):
        with open(include_file, 'r') as f:
            lines = f.readlines()
        
        found_unmapped = False
        for i, line in enumerate(lines):
            line = line.strip()
            if line.startswith('.include "'):
                path = line.split('"')[1]
                if len(path) > 60:
                    # Check if it was already renamed (should be short now)
                    # If it's still long, it means we missed it.
                    print(f"Unmapped long path at line {i+1}: {path} (Len: {len(path)})")
                    found_unmapped = True

        if found_unmapped:
            print("Please add mappings for the above paths.")
