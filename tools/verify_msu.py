#!/usr/bin/env python3
"""
Verify .msu binary file consistency with current chapter.id files.
Reads the MSU header, pointer table, and chapter entries, comparing
chapter IDs and frame counts against the on-disk chapter data.
"""

import os
import struct
import sys

HEADER_SIZE = 0x20
POINTER_SIZE = 4

# Key chapter IDs to inspect in detail
SPOTLIGHT_IDS = {
    # Attract mode (WORKING)
    7: "attract_mode_attract_movie",
    8: "attract_mode_insert_coins",
    9: "attract_mode_start_alive",
    10: "attract_mode_start_dead",
    # Introduction scene (BROKEN - higher IDs)
    251: "introduction_castle_exterior",
    252: "introduction_exit_room",
    253: "introduction_start_alive",
    254: "introduction_start_dead",
    # Snake room (BROKEN)
    378: "snake_room_start_alive",
    379: "snake_room_start_dead",
    # Vestibule (BROKEN)
    468: "vestibule_start_alive",
    469: "vestibule_start_dead",
}


def read_u8(f):
    return struct.unpack('<B', f.read(1))[0]


def read_u16(f):
    return struct.unpack('<H', f.read(2))[0]


def read_u32(f):
    return struct.unpack('<I', f.read(4))[0]


def read_u24(f):
    data = f.read(3)
    return data[0] | (data[1] << 8) | (data[2] << 16)


def load_chapter_ids(chapters_dir):
    """Scan data/chapters/ for chapter.id.NNN files, return {name: id} and {id: name}."""
    name_to_id = {}
    id_to_name = {}
    if not os.path.isdir(chapters_dir):
        print(f"WARNING: chapters dir not found: {chapters_dir}")
        return name_to_id, id_to_name
    for dirname in os.listdir(chapters_dir):
        dirpath = os.path.join(chapters_dir, dirname)
        if not os.path.isdir(dirpath):
            continue
        for fname in os.listdir(dirpath):
            if fname.startswith("chapter.id"):
                suffix = fname.split("chapter.id")[-1].lstrip('.')
                try:
                    cid = int(suffix)
                    name_to_id[dirname] = cid
                    id_to_name[cid] = dirname
                except ValueError:
                    pass
    return name_to_id, id_to_name


def count_frames_on_disk(chapters_dir, chapter_name):
    """Count .tiles files in a chapter directory (= number of source frames)."""
    dirpath = os.path.join(chapters_dir, chapter_name)
    if not os.path.isdir(dirpath):
        return -1
    return sum(1 for f in os.listdir(dirpath) if f.endswith('.tiles'))


def main():
    # Determine paths
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    msu_path = os.path.join(project_dir, "build", "SuperDragonsLairArcade.msu")
    sfc_msu_path = os.path.join(project_dir, "distribution", "SuperDragonsLairArcade.msu")
    chapters_dir = os.path.join(project_dir, "data", "chapters")

    # Use sfc dir copy if build copy doesn't exist
    if not os.path.isfile(msu_path):
        msu_path = sfc_msu_path
    if not os.path.isfile(msu_path):
        print(f"ERROR: .msu file not found at {msu_path}")
        sys.exit(1)

    print(f"MSU file: {msu_path}")
    print(f"MSU size: {os.path.getsize(msu_path):,} bytes")
    print(f"Chapters dir: {chapters_dir}")
    print()

    # Load chapter.id mapping from disk
    name_to_id, id_to_name = load_chapter_ids(chapters_dir)
    max_disk_id = max(id_to_name.keys()) if id_to_name else -1
    print(f"On-disk chapter.id files: {len(id_to_name)}")
    print(f"On-disk max chapter ID: {max_disk_id}")
    print()

    with open(msu_path, 'rb') as f:
        # ---- Header ----
        magic = f.read(6).decode('ascii', errors='replace')
        title = f.read(21).decode('ascii', errors='replace').rstrip()
        bpp_code = read_u8(f)
        fps = read_u8(f)
        chapter_count = read_u16(f)
        padding = read_u8(f)

        bpp_map = {4: 2, 5: 4, 6: 8}
        bpp = bpp_map.get(bpp_code, f"?({bpp_code})")

        print("=== MSU HEADER ===")
        print(f"Magic: {magic!r}")
        print(f"Title: {title!r}")
        print(f"BPP code: {bpp_code} (= {bpp} bpp)")
        print(f"FPS: {fps}")
        print(f"Chapter count: {chapter_count}")
        print(f"Padding byte: 0x{padding:02X}")
        print()

        # Compare chapter counts
        expected_count = max_disk_id + 1 if max_disk_id >= 0 else 0
        if chapter_count != expected_count:
            print(f"*** MISMATCH: MSU chapter count={chapter_count}, expected={expected_count} (max_id+1)")
        else:
            print(f"Chapter count matches expected ({expected_count})")
        print()

        # ---- Pointer table ----
        print("=== POINTER TABLE (spotlight chapters) ===")
        mismatches = 0
        spotlight_results = {}

        for cid in sorted(SPOTLIGHT_IDS.keys()):
            expected_name = SPOTLIGHT_IDS[cid]
            if cid >= chapter_count:
                print(f"  ID {cid:3d} ({expected_name}): OUT OF RANGE (chapter_count={chapter_count})")
                mismatches += 1
                continue

            # Read pointer for this chapter
            f.seek(HEADER_SIZE + cid * POINTER_SIZE)
            ptr = read_u32(f)

            # Seek to chapter data
            f.seek(ptr)
            ch_id_byte = read_u8(f)
            frame_count = read_u24(f)

            # Check ID byte (ROM compares low byte only)
            expected_low = cid & 0xFF
            id_match = "OK" if ch_id_byte == expected_low else f"MISMATCH (got 0x{ch_id_byte:02X}, expected 0x{expected_low:02X})"
            if ch_id_byte != expected_low:
                mismatches += 1

            # Check frames on disk
            disk_frames = count_frames_on_disk(chapters_dir, expected_name)
            # msu1blockwriter adds 2 duplicate frames at end
            expected_msu_frames = disk_frames + 2 if disk_frames > 0 else 0
            frames_match = ""
            if disk_frames >= 0:
                if frame_count == expected_msu_frames:
                    frames_match = f" (disk={disk_frames}+2 ✓)"
                else:
                    frames_match = f" (disk={disk_frames}+2={expected_msu_frames}, MISMATCH!)"
                    mismatches += 1
            else:
                frames_match = " (no disk data)"

            # Actual disk name for this ID
            actual_name = id_to_name.get(cid, "???")
            name_note = "" if actual_name == expected_name else f" [disk name: {actual_name}]"

            print(f"  ID {cid:3d}: ptr=0x{ptr:08X}, id_byte=0x{ch_id_byte:02X} {id_match}, frames={frame_count}{frames_match}{name_note}")
            spotlight_results[cid] = (ptr, ch_id_byte, frame_count)

        print()

        # ---- Full scan: check ALL chapters for ID byte mismatches ----
        print("=== FULL SCAN: checking all chapter ID bytes ===")
        full_mismatches = 0
        empty_count = 0
        total_frames = 0

        for cid in range(chapter_count):
            f.seek(HEADER_SIZE + cid * POINTER_SIZE)
            ptr = read_u32(f)

            f.seek(ptr)
            ch_id_byte = read_u8(f)
            frame_count = read_u24(f)

            expected_low = cid & 0xFF

            if ch_id_byte == 0xFF and frame_count == 0:
                # Dummy/empty chapter slot
                empty_count += 1
                continue

            total_frames += frame_count

            if ch_id_byte != expected_low:
                name = id_to_name.get(cid, "???")
                print(f"  MISMATCH at ID {cid:3d} ({name}): id_byte=0x{ch_id_byte:02X}, expected=0x{expected_low:02X}, frames={frame_count}, ptr=0x{ptr:08X}")
                full_mismatches += 1

        print(f"\nFull scan: {chapter_count} slots, {chapter_count - empty_count} populated, {empty_count} empty/dummy")
        print(f"Total frames in MSU: {total_frames}")
        print(f"ID byte mismatches: {full_mismatches}")
        print()

        # ---- Check for duplicate pointers (multiple IDs pointing to same data) ----
        print("=== DUPLICATE POINTER CHECK ===")
        ptr_to_ids = {}
        for cid in range(chapter_count):
            f.seek(HEADER_SIZE + cid * POINTER_SIZE)
            ptr = read_u32(f)
            if ptr not in ptr_to_ids:
                ptr_to_ids[ptr] = []
            ptr_to_ids[ptr].append(cid)

        dupes = {ptr: ids for ptr, ids in ptr_to_ids.items() if len(ids) > 1}
        # Filter out dummy pointer (many empty IDs point to dummy)
        # Find dummy pointer (it's at dummyChapterOffset position)
        dummy_ids = [ids for ptr, ids in dupes.items() if len(ids) > 10]  # dummy has many
        non_dummy_dupes = {ptr: ids for ptr, ids in dupes.items() if len(ids) <= 10}

        if dummy_ids:
            print(f"  Dummy chapter pointer: {len(dummy_ids[0])} empty IDs (expected)")
        if non_dummy_dupes:
            for ptr, ids in sorted(non_dummy_dupes.items()):
                names = [id_to_name.get(i, '???') for i in ids]
                print(f"  DUPLICATE: ptr=0x{ptr:08X} shared by IDs {ids} ({names})")
        else:
            print(f"  No unexpected duplicate pointers")
        print()

        # ---- Summary ----
        print("=== SUMMARY ===")
        if full_mismatches == 0 and mismatches == 0:
            print("ALL CHECKS PASSED - MSU file is consistent with chapter.id files")
        else:
            print(f"ISSUES FOUND: {full_mismatches} full-scan mismatches, {mismatches} spotlight mismatches")
            print("Consider rebuilding the .msu file")


if __name__ == "__main__":
    main()
