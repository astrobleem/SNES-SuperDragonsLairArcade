#!/usr/bin/env python3
"""Super Dragon's Lair - MSU Data Generator GUI.

Tkinter wrapper around tools/generate_msu_data.py that provides a visual
interface for converting Daphne laserdisc source data (.m2v/.ogg) into
MSU-1 files (.msu + .pcm + manifest.xml).
"""

import os
import re
import sys
import glob
import signal
import subprocess
import threading
import time
import tkinter as tk
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from tkinter import simpledialog
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Path resolution — import defaults from tools/paths.py
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = PROJECT_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))

try:
    from paths import (
        DAPHNE_FRAMEFILE,
        DAPHNE_CONTENT,
        FFMPEG,
        DISTRIBUTION,
        BUILD_DIR,
    )
    DEFAULT_FRAMEFILE = str(DAPHNE_FRAMEFILE)
    DEFAULT_CONTENT = str(DAPHNE_CONTENT)
    DEFAULT_FFMPEG = str(FFMPEG)
except ImportError:
    DEFAULT_FRAMEFILE = str(PROJECT_ROOT / "data" / "laserdisc" / "framefile" / "dlcdrom.TXT")
    DEFAULT_CONTENT = str(PROJECT_ROOT / "data" / "laserdisc" / "DLCDROM")
    DEFAULT_FFMPEG = "ffmpeg"
    DISTRIBUTION = PROJECT_ROOT / "distribution"
    BUILD_DIR = PROJECT_ROOT / "build"

GENERATE_SCRIPT = TOOLS_DIR / "generate_msu_data.py"
MANIFEST_SCRIPT = TOOLS_DIR / "generate_manifest.py"
CHAPTERS_DIR = PROJECT_ROOT / "data" / "chapters"
CONVERTER_DIR = PROJECT_ROOT / "converter"

# Add converter dir to path for preview/segments imports
if str(CONVERTER_DIR) not in sys.path:
    sys.path.insert(0, str(CONVERTER_DIR))

SCENE_PREFIXES = {
    'introduction': 'intr_', 'vestibule': 'vest_', 'snake_room': 'snkr_',
    'bower': 'bowr_', 'fire_room': 'firm_', 'throne_room': 'thrn_',
    'tilting_room': 'tltr_', 'tentacle_room': 'tntr_', 'wind_room': 'wndr_',
    'giddy_goons': 'gg_', 'catwalk_bats': 'cwbt_', 'mudmen': 'mudm_',
    'rolling_balls': 'rbal_', 'underground_river': 'ugr_', 'flaming_ropes': 'flrp_',
    'flying_horse': 'fh_', 'bubbling_cauldron': 'bcld_', 'giant_bat': 'gbat_',
    'crypt_creeps': 'cc_', 'alice_room': 'alrm_', 'robot_knight': 'rk_',
    'smithee': 'sm_', 'smithee_reversed': 'smr_', 'grim_reaper': 'gr_',
    'yellow_brick_road': 'ybr_', 'black_knight': 'bknt_', 'lizard_king': 'lzkg_',
    'the_dragons_lair': 'tdl_', 'attract_mode': 'atmd_',
}

TARGET_FPS = 24000.0 / 1001.0  # ~23.976 fps
EVENTS_DIR = PROJECT_ROOT / "data" / "events"

# Direction event colors for timeline strip and arrow overlay
DIR_COLORS = {
    'left':   '#e8c840',  # gold
    'right':  '#40a8e8',  # blue
    'up':     '#60d060',  # green
    'down':   '#e86040',  # red/orange
    'action': '#c060e0',  # purple
}

# Arrow positions on the 256x192 SNES screen (center of arrow)
DIR_POSITIONS = {
    'left':   (60, 80),
    'right':  (160, 80),
    'up':     (110, 36),
    'down':   (110, 156),
    'action': (120, 80),
}


@dataclass
class ChapterEvent:
    """A direction event parsed from a chapter XML file."""
    direction: str       # 'left', 'right', 'up', 'down', 'action'
    start_frame: int     # chapter-relative
    end_frame: int       # chapter-relative
    label: str           # 'direction-1' = correct, others = death traps
    target: str          # result chapter name
    result_type: str = 'playchapter'  # 'playchapter', 'none', 'lastcheckpoint', etc.


@dataclass
class ChapterMeta:
    """Chapter-level context needed for XML round-tripping and Lua export."""
    chapter_name: str
    chapter_start_ms: float       # absolute ms from XML <timeline><timestart>
    chapter_end_ms: float         # absolute ms from XML <timeline><timeend>
    chapter_start_frame: Optional[int]  # laserdisc frame attr (may be absent)
    default_result_type: str      # 'playchapter', 'lastcheckpoint', etc.
    default_result_target: str    # target chapter name or ''
    non_direction_events: list    # raw XML strings for checkpoint etc. (preserved verbatim)


def _parse_time_ms(el) -> float:
    """Parse min/second(or sec)/ms attributes from a time element into total ms."""
    return (int(el.get("min", "0")) * 60000
            + int(el.get("second", el.get("sec", "0"))) * 1000
            + int(el.get("ms", "0")))


def _detect_result(result_el) -> Tuple[str, str]:
    """Detect result type and target from a <result> element.

    Returns (result_type, target_name). For elements like <playchapter name="x"/>,
    returns ('playchapter', 'x'). For <lastcheckpoint/>, returns ('lastcheckpoint', '').
    For <none name="x"/>, returns ('none', 'x').
    """
    if result_el is None:
        return ('none', '')
    for child in result_el:
        name = child.get("name", "")
        return (child.tag, name)
    return ('none', '')


def _parse_chapter_events(chapter_name: str) -> Tuple[List[ChapterEvent], Optional[ChapterMeta]]:
    """Parse direction events and chapter metadata from a chapter's XML file.

    Returns (events, meta). If the XML doesn't exist or has no timeline,
    returns ([], None).
    """
    xml_path = EVENTS_DIR / f"{chapter_name}.xml"
    if not xml_path.exists():
        return ([], None)

    try:
        tree = ET.parse(str(xml_path))
    except ET.ParseError:
        return ([], None)

    root = tree.getroot()

    # Chapter timeline
    ch_tl = root.find("timeline")
    if ch_tl is None:
        return ([], None)
    ch_start_el = ch_tl.find("timestart")
    ch_end_el = ch_tl.find("timeend")
    if ch_start_el is None:
        return ([], None)

    ch_start_ms = _parse_time_ms(ch_start_el)
    ch_end_ms = _parse_time_ms(ch_end_el) if ch_end_el is not None else ch_start_ms

    # Laserdisc frame attribute (optional)
    ch_start_frame = None
    frame_attr = ch_start_el.get("frame")
    if frame_attr is not None:
        try:
            ch_start_frame = int(frame_attr)
        except ValueError:
            pass

    # Chapter-level default result
    ch_result_el = root.find("result")
    default_result_type, default_result_target = _detect_result(ch_result_el)

    events_el = root.find("events")

    # Collect non-direction events as raw XML strings
    non_direction_events = []
    results = []

    if events_el is not None:
        for ev in events_el.findall("event"):
            if ev.get("type") != "direction":
                # Preserve non-direction events verbatim
                non_direction_events.append(
                    ET.tostring(ev, encoding="unicode"))
                continue

            # Direction type
            direction = "action"
            params = ev.find("params")
            if params is not None:
                for s in params.findall("str"):
                    if s.get("key") == "type":
                        direction = s.get("value", "action")

            # Event timeline (absolute timestamps)
            ev_tl = ev.find("timeline")
            if ev_tl is None:
                continue
            ev_start = ev_tl.find("timestart")
            ev_end = ev_tl.find("timeend")
            if ev_start is None or ev_end is None:
                continue

            start_ms = _parse_time_ms(ev_start)
            end_ms = _parse_time_ms(ev_end)

            # Convert to chapter-relative frames
            start_frame = max(0, int((start_ms - ch_start_ms) / 1000.0 * TARGET_FPS))
            end_frame = max(0, int((end_ms - ch_start_ms) / 1000.0 * TARGET_FPS))

            # Label and result
            label = ev.get("label", "")
            result_type, target = _detect_result(ev.find("result"))

            results.append(ChapterEvent(
                direction=direction,
                start_frame=start_frame,
                end_frame=end_frame,
                label=label,
                target=target,
                result_type=result_type,
            ))

    meta = ChapterMeta(
        chapter_name=chapter_name,
        chapter_start_ms=ch_start_ms,
        chapter_end_ms=ch_end_ms,
        chapter_start_frame=ch_start_frame,
        default_result_type=default_result_type,
        default_result_target=default_result_target,
        non_direction_events=non_direction_events,
    )

    return (results, meta)


# Phase weights for overall progress (renormalized when phases skipped)
PHASE_WEIGHTS = {
    "1":  40,   # Extract video
    "1b": 10,   # Extract audio
    "1c":  2,   # Copy PCM
    "2":  40,   # Convert tiles
    "3":   8,   # Package .msu
}

# Regex patterns for parsing subprocess output
RE_PHASE = re.compile(r"^--- (Phase \S+): (.+?) ---$")
RE_PROGRESS = re.compile(r"^\[\s*(\d+)/(\d+)\]")
RE_ERROR = re.compile(r"^ERROR", re.IGNORECASE)
RE_WARN = re.compile(r"^WARN", re.IGNORECASE)


class Tooltip:
    """Simple hover tooltip for tkinter widgets."""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, event=None):
        if self.tip_window:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw, text=self.text, justify=tk.LEFT,
            background="#ffffe0", relief=tk.SOLID, borderwidth=1,
            font=("Segoe UI", 9),
        )
        label.pack(ipadx=4, ipady=2)

    def _hide(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


class MSUGeneratorGUI:
    """Main application window."""

    def __init__(self, root):
        self.root = root
        self.root.title("Super Dragon's Lair - MSU Data Generator")
        self.root.geometry("900x650")
        self.root.minsize(750, 500)

        self.process = None
        self.worker_thread = None
        self.is_running = False
        self.cancelled = False
        self.start_time = None

        # Phase tracking for overall progress
        self.current_phase_key = None
        self.phase_progress = {}  # phase_key -> (current, total)
        self.active_weights = dict(PHASE_WEIGHTS)

        # Preview state
        self._chapter_frames = []       # sorted list of PNG paths for current chapter
        self._current_chapter_dir = None  # path to current chapter directory
        self._preview_path = None       # cached source PNG path for reconversion
        self._preview_timer = None      # debounce timer for quality changes
        self._scrub_timer = None        # debounce timer for scrubber
        self._updating_controls = False  # suppress feedback loops

        # Clip preview state
        self._clip_frames = []          # list of (src_pil, snes_pil) for animation
        self._clip_playing = False      # animation loop active
        self._clip_frame_idx = 0        # current animation frame
        self._clip_timer = None         # after() id for animation tick
        self._clip_cancel = None        # threading.Event to signal cancel

        # Segment state
        self._segment_list = None
        self._selected_segment_idx = 0

        # Event overlay state
        self._chapter_events = []  # List[ChapterEvent] for current chapter
        self._chapter_meta = None  # ChapterMeta for current chapter

        # Event editing state
        self._events_dirty = False
        self._selected_event_idx = -1
        self._drag_mode = None       # None | 'move' | 'resize_left' | 'resize_right'
        self._drag_start_x = 0
        self._drag_orig_start = 0
        self._drag_orig_end = 0

        self._build_ui()
        self._validate_all()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        outer = ttk.Frame(self.root, padding=8)
        outer.pack(fill=tk.BOTH, expand=True)

        # --- Scene / Chapter selector (shared, above tabs) ---
        nav_frame = ttk.Frame(outer)
        nav_frame.pack(fill=tk.X, pady=(0, 4))

        ttk.Label(nav_frame, text="Scene:").pack(side=tk.LEFT)
        scene_names = [
            "All Scenes",
            "introduction", "vestibule", "snake_room", "bower", "fire_room",
            "throne_room", "tilting_room", "tentacle_room", "wind_room",
            "giddy_goons", "catwalk_bats", "mudmen", "rolling_balls",
            "underground_river", "flaming_ropes", "flying_horse",
            "bubbling_cauldron", "giant_bat", "crypt_creeps", "alice_room",
            "robot_knight", "smithee", "smithee_reversed", "grim_reaper",
            "yellow_brick_road", "black_knight", "lizard_king",
            "the_dragons_lair", "attract_mode",
        ]
        self.scene_var = tk.StringVar(value="All Scenes")
        scene_cb = ttk.Combobox(nav_frame, textvariable=self.scene_var, width=24,
                                values=scene_names, state="readonly")
        scene_cb.pack(side=tk.LEFT, padx=(4, 0))
        scene_cb.bind("<<ComboboxSelected>>", lambda e: self._on_scene_changed())
        Tooltip(scene_cb, "Select a scene to browse its chapters")

        ttk.Label(nav_frame, text="Chapter:").pack(side=tk.LEFT, padx=(16, 0))
        self.chapter_var = tk.StringVar(value="")
        self.chapter_cb = ttk.Combobox(nav_frame, textvariable=self.chapter_var, width=30,
                                       state="readonly")
        self.chapter_cb.pack(side=tk.LEFT, padx=(4, 0))
        self.chapter_cb.bind("<<ComboboxSelected>>", lambda e: self._on_chapter_changed())
        Tooltip(self.chapter_cb, "Select a chapter to preview its frames")

        # --- Notebook tabs ---
        self.notebook = ttk.Notebook(outer)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self._build_editor_tab()
        self._build_generate_tab()

        # Arrow keys for single-frame stepping
        self.root.bind("<Left>", lambda e: self._step_frame(-1))
        self.root.bind("<Right>", lambda e: self._step_frame(1))
        self.root.bind("<Delete>", self._on_delete_key)

    def _build_editor_tab(self):
        """Build the Editor tab: preview, scrubber, events, segments."""
        tab = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(tab, text="Editor")

        # --- Preview Panels ---
        preview_frame = ttk.LabelFrame(tab, text="Preview", padding=5)
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        src_frame = ttk.Frame(preview_frame)
        src_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
        ttk.Label(src_frame, text="Source Frame").pack()
        self.src_canvas = tk.Canvas(src_frame, width=256, height=160, bg="black")
        self.src_canvas.pack(fill=tk.BOTH, expand=True)
        self.src_photo = None

        snes_frame = ttk.Frame(preview_frame)
        snes_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(4, 0))
        ttk.Label(snes_frame, text="SNES Reconstruction").pack()
        self.snes_canvas = tk.Canvas(snes_frame, width=256, height=160, bg="black")
        self.snes_canvas.pack(fill=tk.BOTH, expand=True)
        self.snes_photo = None

        # --- Scrubber ---
        scrubber_frame = ttk.Frame(tab)
        scrubber_frame.pack(fill=tk.X, pady=(0, 4))

        self.scrub_var = tk.DoubleVar(value=0.0)
        self.scrub_scale = ttk.Scale(scrubber_frame, from_=0, to=1,
                                     orient=tk.HORIZONTAL,
                                     variable=self.scrub_var,
                                     command=self._on_scrub)
        self.scrub_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.scrub_scale.configure(state=tk.DISABLED)

        self.clip_btn = ttk.Button(scrubber_frame, text="Preview Clip",
                                   command=self._toggle_clip, state=tk.DISABLED)
        self.clip_btn.pack(side=tk.RIGHT, padx=(0, 8))
        Tooltip(self.clip_btn,
                "Render ~2 seconds of converted frames from the\n"
                "current position and play back as animation.")

        self.scrub_label = ttk.Label(scrubber_frame, text="Frame 0 / 0", width=20,
                                     anchor=tk.E)
        self.scrub_label.pack(side=tk.RIGHT)

        # --- Quality Settings ---
        qual_frame = ttk.LabelFrame(tab, text="Quality", padding=4)
        qual_frame.pack(fill=tk.X, pady=(0, 4))

        qual_row1 = ttk.Frame(qual_frame)
        qual_row1.pack(fill=tk.X)

        ttk.Label(qual_row1, text="Dithering:").pack(side=tk.LEFT)
        self.dither_var = tk.StringVar(value="Floyd-Steinberg")
        dither_cb = ttk.Combobox(qual_row1, textvariable=self.dither_var, width=14,
                                 values=["None", "Floyd-Steinberg", "Ordered"],
                                 state="readonly")
        dither_cb.pack(side=tk.LEFT, padx=(4, 16))
        dither_cb.bind("<<ComboboxSelected>>", lambda e: self._on_quality_changed())
        Tooltip(dither_cb, "Dithering method for tile conversion")

        ttk.Label(qual_row1, text="Palettes:").pack(side=tk.LEFT)
        self.palettes_var = tk.StringVar(value="8")
        palettes_spin = ttk.Spinbox(qual_row1, from_=1, to=8, width=3,
                                    textvariable=self.palettes_var)
        palettes_spin.pack(side=tk.LEFT, padx=(4, 16))
        self.palettes_var.trace_add("write", lambda *_: self._on_quality_changed())
        Tooltip(palettes_spin, "Number of sub-palettes per frame (1-8)")

        ttk.Label(qual_row1, text="Max Tiles:").pack(side=tk.LEFT)
        self.max_tiles_var = tk.StringVar(value="512")
        tiles_spin = ttk.Spinbox(qual_row1, from_=1, to=512, width=4,
                                 textvariable=self.max_tiles_var)
        tiles_spin.pack(side=tk.LEFT, padx=(4, 16))
        self.max_tiles_var.trace_add("write", lambda *_: self._on_quality_changed())
        Tooltip(tiles_spin, "Maximum tiles per frame (VRAM limit)")

        self.grayscale_var = tk.BooleanVar(value=False)
        gs_cb = ttk.Checkbutton(qual_row1, text="Grayscale", variable=self.grayscale_var,
                                command=self._on_quality_changed)
        gs_cb.pack(side=tk.LEFT)
        Tooltip(gs_cb, "Convert frames to grayscale before processing")

        self.shared_palette_var = tk.BooleanVar(value=False)
        sp_cb = ttk.Checkbutton(qual_row1, text="Shared Palette",
                                variable=self.shared_palette_var,
                                command=self._on_quality_changed)
        sp_cb.pack(side=tk.LEFT, padx=(8, 0))
        Tooltip(sp_cb, "Use shared palette across all frames in each chapter to reduce swimming")

        ttk.Label(qual_row1, text="Palette:").pack(side=tk.LEFT, padx=(8, 0))
        self.palette_method_var = tk.StringVar(value="Tile-Aware")
        palette_cb = ttk.Combobox(qual_row1, textvariable=self.palette_method_var, width=10,
                                  values=["K-Means", "Tile-Aware"], state="readonly")
        palette_cb.pack(side=tk.LEFT, padx=(4, 0))
        palette_cb.bind("<<ComboboxSelected>>", lambda e: self._on_quality_changed())
        Tooltip(palette_cb, "Palette optimization method: K-Means (fast) or Tile-Aware (better quality)")

        # --- Event Timeline (multi-track) ---
        evt_outer = ttk.Frame(tab)
        evt_outer.pack(fill=tk.X, pady=(0, 2))
        ttk.Label(evt_outer, text="Events:").pack(side=tk.LEFT, padx=(0, 4), anchor=tk.N)
        self.evt_canvas = tk.Canvas(evt_outer, height=20, bg="#1a1a2e",
                                    highlightthickness=0)
        self.evt_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.evt_canvas.bind("<Configure>", lambda e: self._redraw_event_canvas())
        self.evt_canvas.bind("<Button-1>", self._on_evt_press)
        self.evt_canvas.bind("<B1-Motion>", self._on_evt_drag)
        self.evt_canvas.bind("<ButtonRelease-1>", self._on_evt_release)
        self.evt_canvas.bind("<Button-3>", self._on_evt_right_click)
        self.evt_canvas.bind("<Motion>", self._on_evt_hover)

        # Event button row
        evt_btn_frame = ttk.Frame(tab)
        evt_btn_frame.pack(fill=tk.X, pady=(0, 2))

        self.save_xml_btn = ttk.Button(evt_btn_frame, text="Save XML",
                                        command=self._save_events_xml,
                                        state=tk.DISABLED)
        self.save_xml_btn.pack(side=tk.LEFT, padx=(0, 5))
        Tooltip(self.save_xml_btn, "Save edited events back to XML")

        self.export_lua_btn = ttk.Button(evt_btn_frame, text="Export Lua",
                                          command=self._export_events_lua,
                                          state=tk.DISABLED)
        self.export_lua_btn.pack(side=tk.LEFT, padx=(0, 5))
        Tooltip(self.export_lua_btn, "Export events as DirkSimple game.lua format")

        self.evt_dirty_label = ttk.Label(evt_btn_frame, text="")
        self.evt_dirty_label.pack(side=tk.LEFT, padx=(10, 0))

        # --- Segments ---
        seg_frame = ttk.LabelFrame(tab, text="Segments", padding=4)
        seg_frame.pack(fill=tk.X, pady=(0, 4))

        self.seg_canvas = tk.Canvas(seg_frame, height=24, bg="#2b2b2b",
                                    highlightthickness=0)
        self.seg_canvas.pack(fill=tk.X, pady=(0, 4))
        self.seg_canvas.bind("<Button-1>", self._on_seg_canvas_click)
        self.seg_canvas.bind("<Configure>", lambda e: self._redraw_seg_canvas())

        seg_btn_frame = ttk.Frame(seg_frame)
        seg_btn_frame.pack(fill=tk.X)

        self.split_btn = ttk.Button(seg_btn_frame, text="Split Here",
                                    command=self._split_segment, state=tk.DISABLED)
        self.split_btn.pack(side=tk.LEFT, padx=(0, 5))
        Tooltip(self.split_btn,
                "Split the current segment at the scrubber position.\n"
                "Each segment can have its own quality settings.")

        self.delete_seg_btn = ttk.Button(seg_btn_frame, text="Delete Segment",
                                         command=self._delete_segment, state=tk.DISABLED)
        self.delete_seg_btn.pack(side=tk.LEFT, padx=(0, 5))
        Tooltip(self.delete_seg_btn,
                "Delete the selected segment, merging it\n"
                "into its left neighbor.")

        self.save_seg_btn = ttk.Button(seg_btn_frame, text="Save...",
                                        command=self._save_segments, state=tk.DISABLED)
        self.save_seg_btn.pack(side=tk.LEFT, padx=(0, 5))
        Tooltip(self.save_seg_btn, "Save segment layout and settings to a JSON file")

        self.load_seg_btn = ttk.Button(seg_btn_frame, text="Load...",
                                        command=self._load_segments)
        self.load_seg_btn.pack(side=tk.LEFT, padx=(0, 5))
        Tooltip(self.load_seg_btn, "Load segment layout and settings from a JSON file")

        self.seg_info_label = ttk.Label(seg_btn_frame, text="No segments")
        self.seg_info_label.pack(side=tk.LEFT, padx=(10, 0))

    def _build_generate_tab(self):
        """Build the Generate tab: source data, pipeline options, progress, log."""
        tab = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(tab, text="Generate")

        # --- Source Data ---
        src_frame = ttk.LabelFrame(tab, text="Source Data", padding=6)
        src_frame.pack(fill=tk.X, pady=(0, 4))

        self.framefile_var = tk.StringVar(value=DEFAULT_FRAMEFILE)
        self.content_var = tk.StringVar(value=DEFAULT_CONTENT)
        self.ffmpeg_var = tk.StringVar(value=DEFAULT_FFMPEG)

        self._path_row(src_frame, 0, "Framefile:", self.framefile_var,
                       self._browse_framefile, is_file=True,
                       tooltip="Daphne framefile (dlcdrom.TXT)")
        self._path_row(src_frame, 1, "Content:", self.content_var,
                       self._browse_content, is_file=False,
                       tooltip="Directory containing .m2v and .ogg segment files")
        self._path_row(src_frame, 2, "ffmpeg:", self.ffmpeg_var,
                       self._browse_ffmpeg, is_file=True,
                       tooltip="Path to ffmpeg executable (or just 'ffmpeg' if on PATH)")

        self.framefile_status = ttk.Label(src_frame, text="", width=2)
        self.framefile_status.grid(row=0, column=3, padx=(4, 0))
        self.content_status = ttk.Label(src_frame, text="", width=2)
        self.content_status.grid(row=1, column=3, padx=(4, 0))
        self.ffmpeg_status = ttk.Label(src_frame, text="", width=2)
        self.ffmpeg_status.grid(row=2, column=3, padx=(4, 0))

        for var in (self.framefile_var, self.content_var, self.ffmpeg_var):
            var.trace_add("write", lambda *_: self._validate_all())

        # --- Pipeline Options ---
        opt_frame = ttk.LabelFrame(tab, text="Pipeline Options", padding=6)
        opt_frame.pack(fill=tk.X, pady=(0, 4))

        row0 = ttk.Frame(opt_frame)
        row0.pack(fill=tk.X, pady=(0, 2))

        ttk.Label(row0, text="Workers:").pack(side=tk.LEFT)
        self.workers_var = tk.StringVar(value="8")
        workers_spin = ttk.Spinbox(row0, from_=1, to=32, width=4,
                                   textvariable=self.workers_var)
        workers_spin.pack(side=tk.LEFT, padx=(4, 16))
        Tooltip(workers_spin, "Number of parallel worker threads for tile conversion")

        self.clean_var = tk.BooleanVar(value=False)
        clean_cb = ttk.Checkbutton(row0, text="Clean (re-extract all)",
                                   variable=self.clean_var)
        clean_cb.pack(side=tk.LEFT)
        Tooltip(clean_cb, "Delete existing extracted frames before re-extracting from .m2v")

        row1 = ttk.Frame(opt_frame)
        row1.pack(fill=tk.X)

        ttk.Label(row1, text="Phases:").pack(side=tk.LEFT)
        self.phase_extract = tk.BooleanVar(value=True)
        self.phase_audio = tk.BooleanVar(value=True)
        self.phase_convert = tk.BooleanVar(value=True)
        self.phase_package = tk.BooleanVar(value=True)

        for text, var in [("Extract", self.phase_extract),
                          ("Audio", self.phase_audio),
                          ("Convert", self.phase_convert),
                          ("Package", self.phase_package)]:
            ttk.Checkbutton(row1, text=text, variable=var).pack(side=tk.LEFT, padx=(8, 0))

        self.manifest_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row1, text="Auto-manifest",
                        variable=self.manifest_var).pack(side=tk.LEFT, padx=(16, 0))

        # --- Generate / Cancel ---
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 4))

        self.generate_btn = ttk.Button(btn_frame, text="Generate",
                                       command=self._start_generation)
        self.generate_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.cancel_btn = ttk.Button(btn_frame, text="Cancel",
                                     command=self._cancel_generation, state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.LEFT)

        # --- Progress ---
        prog_frame = ttk.LabelFrame(tab, text="Progress", padding=6)
        prog_frame.pack(fill=tk.X, pady=(0, 4))

        self.phase_label = ttk.Label(prog_frame, text="Ready")
        self.phase_label.pack(fill=tk.X)

        bar_frame = ttk.Frame(prog_frame)
        bar_frame.pack(fill=tk.X, pady=(4, 0))

        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(bar_frame, variable=self.progress_var,
                                            maximum=100)
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.progress_pct = ttk.Label(bar_frame, text="0%", width=6, anchor=tk.E)
        self.progress_pct.pack(side=tk.LEFT, padx=(8, 0))

        self.progress_count = ttk.Label(bar_frame, text="", width=12, anchor=tk.E)
        self.progress_count.pack(side=tk.LEFT, padx=(4, 0))

        self.time_label = ttk.Label(prog_frame, text="")
        self.time_label.pack(fill=tk.X, pady=(2, 0))

        # --- Log Output ---
        log_frame = ttk.LabelFrame(tab, text="Log Output", padding=4)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        self.log_text = tk.Text(log_frame, wrap=tk.WORD, state=tk.DISABLED,
                                font=("Consolas", 9), height=10)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL,
                                  command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.log_text.tag_configure("error", foreground="#cc0000")
        self.log_text.tag_configure("warn", foreground="#cc8800")
        self.log_text.tag_configure("phase", foreground="#0066cc", font=("Consolas", 9, "bold"))
        self.log_text.tag_configure("success", foreground="#008800")

    def _path_row(self, parent, row, label, var, browse_cmd, is_file=True, tooltip=None):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, padx=(0, 4))
        entry = ttk.Entry(parent, textvariable=var)
        entry.grid(row=row, column=1, sticky=tk.EW, padx=(0, 4))
        parent.columnconfigure(1, weight=1)
        btn = ttk.Button(parent, text="Browse...", command=browse_cmd, width=8)
        btn.grid(row=row, column=2)
        if tooltip:
            Tooltip(entry, tooltip)

    # ------------------------------------------------------------------
    # Browse dialogs
    # ------------------------------------------------------------------
    def _browse_framefile(self):
        path = filedialog.askopenfilename(
            title="Select Daphne framefile",
            filetypes=[("Text files", "*.TXT *.txt"), ("All files", "*.*")],
            initialdir=str(Path(self.framefile_var.get()).parent)
            if Path(self.framefile_var.get()).parent.exists() else str(PROJECT_ROOT),
        )
        if path:
            self.framefile_var.set(path)

    def _browse_content(self):
        path = filedialog.askdirectory(
            title="Select Daphne content directory",
            initialdir=self.content_var.get()
            if Path(self.content_var.get()).exists() else str(PROJECT_ROOT),
        )
        if path:
            self.content_var.set(path)

    def _browse_ffmpeg(self):
        path = filedialog.askopenfilename(
            title="Select ffmpeg executable",
            filetypes=[("Executables", "*.exe"), ("All files", "*.*")],
        )
        if path:
            self.ffmpeg_var.set(path)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def _validate_all(self):
        ok = True

        # Framefile
        ff_path = Path(self.framefile_var.get())
        if ff_path.is_file():
            self.framefile_status.configure(text="OK", foreground="green")
        else:
            self.framefile_status.configure(text="X", foreground="red")
            ok = False

        # Content directory
        content_path = Path(self.content_var.get())
        if content_path.is_dir():
            has_m2v = any(content_path.glob("*.m2v"))
            if has_m2v:
                self.content_status.configure(text="OK", foreground="green")
            else:
                self.content_status.configure(text="?", foreground="orange")
                # Allow proceeding — .m2v files might be in subdirectories
        else:
            self.content_status.configure(text="X", foreground="red")
            ok = False

        # ffmpeg — check if it's accessible
        ffmpeg_val = self.ffmpeg_var.get().strip()
        if ffmpeg_val:
            ffmpeg_path = Path(ffmpeg_val)
            if ffmpeg_path.is_file() or ffmpeg_val == "ffmpeg":
                self.ffmpeg_status.configure(text="OK", foreground="green")
            else:
                self.ffmpeg_status.configure(text="?", foreground="orange")
        else:
            self.ffmpeg_status.configure(text="X", foreground="red")
            ok = False

        # Check other prerequisites
        if not GENERATE_SCRIPT.exists():
            ok = False
        if not CHAPTERS_DIR.exists():
            ok = False

        state = tk.NORMAL if (ok and not self.is_running) else tk.DISABLED
        self.generate_btn.configure(state=state)
        return ok

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------
    def _build_args(self):
        """Translate GUI state into CLI arguments for generate_msu_data.py."""
        args = [sys.executable, str(GENERATE_SCRIPT)]
        args += ["--workers", self.workers_var.get()]
        args += ["--framefile", self.framefile_var.get()]
        args += ["--content-root", self.content_var.get()]

        if self.clean_var.get():
            args.append("--clean")
        if not self.phase_extract.get():
            args.append("--skip-extract")
        if not self.phase_audio.get():
            args.append("--skip-audio")
        if not self.phase_convert.get():
            args.append("--skip-convert")
        if not self.phase_package.get():
            args.append("--skip-package")

        # Quality settings
        dither_map = {
            "None": "none",
            "Floyd-Steinberg": "floyd-steinberg",
            "Ordered": "ordered",
        }
        dither_val = dither_map.get(self.dither_var.get(), "floyd-steinberg")
        args += ["--dither", dither_val]

        args += ["--palettes", self.palettes_var.get()]
        args += ["--max-tiles", self.max_tiles_var.get()]

        if self.grayscale_var.get():
            args.append("--grayscale")
        if self.shared_palette_var.get():
            args.append("--shared-palette")

        args += ["--palette-method", self._get_palette_method()]

        # Scene filter
        scene_val = self.scene_var.get()
        if scene_val and scene_val != "All Scenes":
            args += ["--scene", scene_val]

        return args

    def _build_env(self):
        """Build environment for subprocess with FFMPEG and unbuffered output."""
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        ffmpeg_val = self.ffmpeg_var.get().strip()
        if ffmpeg_val and ffmpeg_val != "ffmpeg":
            env["FFMPEG"] = ffmpeg_val
        return env

    def _compute_active_weights(self):
        """Compute phase weights based on which phases are enabled."""
        self.active_weights = {}
        if self.phase_extract.get():
            self.active_weights["1"] = PHASE_WEIGHTS["1"]
        if self.phase_audio.get():
            self.active_weights["1b"] = PHASE_WEIGHTS["1b"]
        # 1c (copy) always runs if audio ran
        if self.phase_audio.get():
            self.active_weights["1c"] = PHASE_WEIGHTS["1c"]
        if self.phase_convert.get():
            self.active_weights["2"] = PHASE_WEIGHTS["2"]
        if self.phase_package.get():
            self.active_weights["3"] = PHASE_WEIGHTS["3"]
        if not self.active_weights:
            self.active_weights = {"1": 1}  # fallback

    def _start_generation(self):
        if self.is_running:
            return

        # Re-validate
        if not self._validate_all():
            messagebox.showerror("Validation Failed",
                                 "Please fix the highlighted paths before generating.")
            return

        # Check chapters dir
        if not CHAPTERS_DIR.exists():
            messagebox.showerror("Missing chapters",
                                 f"data/chapters/ not found.\n\n"
                                 f"Run 'make' first to build the ROM and generate chapter data.")
            return

        self.is_running = True
        self.cancelled = False
        self.start_time = time.time()
        self.current_phase_key = None
        self.phase_progress = {}
        self._compute_active_weights()

        self.generate_btn.configure(state=tk.DISABLED)
        self.cancel_btn.configure(state=tk.NORMAL)
        self.progress_var.set(0)
        self.progress_pct.configure(text="0%")
        self.progress_count.configure(text="")
        self.phase_label.configure(text="Starting...")
        self.time_label.configure(text="")

        # Clear log
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

        args = self._build_args()
        env = self._build_env()
        self._log(f"Command: {' '.join(args)}", tag="phase")

        self.worker_thread = threading.Thread(target=self._run_subprocess,
                                              args=(args, env), daemon=True)
        self.worker_thread.start()
        self._update_elapsed()

    def _run_subprocess(self, args, env):
        """Background thread: run subprocess and stream output."""
        try:
            self.process = subprocess.Popen(
                args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                env=env, cwd=str(PROJECT_ROOT),
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )

            for raw_line in self.process.stdout:
                if self.cancelled:
                    break
                line = raw_line.decode("utf-8", errors="replace").rstrip("\n\r")
                self.root.after(0, self._process_line, line)

            self.process.wait()
            rc = self.process.returncode

            if self.cancelled:
                self.root.after(0, self._on_cancelled)
            elif rc == 0:
                self.root.after(0, self._on_success)
            else:
                self.root.after(0, self._on_failure, rc)

        except Exception as e:
            self.root.after(0, self._on_error, str(e))
        finally:
            self.process = None

    def _process_line(self, line):
        """Parse a line of subprocess output and update UI."""
        # Phase header
        m = RE_PHASE.match(line)
        if m:
            phase_id = m.group(1).replace("Phase ", "")
            phase_desc = m.group(2)
            self.current_phase_key = phase_id
            self.phase_label.configure(text=f"Phase {phase_id}: {phase_desc}")
            self._log(line, tag="phase")
            return

        # Progress counter
        m = RE_PROGRESS.match(line)
        if m:
            current = int(m.group(1))
            total = int(m.group(2))
            if self.current_phase_key:
                self.phase_progress[self.current_phase_key] = (current, total)
            self._update_progress(current, total)
            # Determine tag
            tag = None
            if RE_ERROR.search(line):
                tag = "error"
            elif RE_WARN.search(line):
                tag = "warn"
            self._log(line, tag=tag)
            return

        # Error/warn lines
        if RE_ERROR.match(line):
            self._log(line, tag="error")
        elif RE_WARN.match(line):
            self._log(line, tag="warn")
        elif "Success!" in line or "Done!" in line:
            self._log(line, tag="success")
        else:
            self._log(line)

    def _update_progress(self, current, total):
        """Update overall progress bar based on phase weights."""
        # Compute overall percentage
        total_weight = sum(self.active_weights.values())
        if total_weight == 0:
            return

        completed = 0.0
        for key, weight in self.active_weights.items():
            if key in self.phase_progress:
                c, t = self.phase_progress[key]
                if t > 0:
                    completed += weight * (c / t)
                if key == self.current_phase_key:
                    break  # Don't count future phases as partially done
            elif self._phase_order(key) < self._phase_order(self.current_phase_key or "1"):
                completed += weight  # Previous phases are 100%

        pct = min(100.0, (completed / total_weight) * 100)
        self.progress_var.set(pct)
        self.progress_pct.configure(text=f"{pct:.0f}%")
        self.progress_count.configure(text=f"[{current}/{total}]")

    @staticmethod
    def _phase_order(key):
        order = {"1": 0, "1b": 1, "1c": 2, "1d": 3, "1e": 4, "2": 5, "3": 6}
        return order.get(key, 99)

    def _update_elapsed(self):
        """Periodically update elapsed/ETA display."""
        if not self.is_running:
            return
        elapsed = time.time() - self.start_time
        elapsed_str = self._format_time(elapsed)

        pct = self.progress_var.get()
        if pct > 2:
            eta = elapsed * (100 - pct) / pct
            eta_str = f"~{self._format_time(eta)}"
        else:
            eta_str = "calculating..."

        self.time_label.configure(text=f"Elapsed: {elapsed_str}  |  ETA: {eta_str}")
        self.root.after(1000, self._update_elapsed)

    @staticmethod
    def _format_time(seconds):
        m, s = divmod(int(seconds), 60)
        if m >= 60:
            h, m = divmod(m, 60)
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    def _log(self, message, tag=None):
        """Append a line to the log text widget."""
        self.log_text.configure(state=tk.NORMAL)
        if tag:
            self.log_text.insert(tk.END, message + "\n", tag)
        else:
            self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Completion handlers
    # ------------------------------------------------------------------
    def _on_success(self):
        self.progress_var.set(100)
        self.progress_pct.configure(text="100%")
        self.phase_label.configure(text="Complete!")
        elapsed = self._format_time(time.time() - self.start_time)
        self.time_label.configure(text=f"Elapsed: {elapsed}")
        self._log("Generation completed successfully!", tag="success")

        # Run manifest generation if enabled and package phase was active
        if self.manifest_var.get() and self.phase_package.get():
            self._run_manifest()

        self._generation_finished()

    def _on_failure(self, rc):
        self.phase_label.configure(text="Failed")
        self._log(f"Generation failed with exit code {rc}", tag="error")
        messagebox.showerror("Generation Failed",
                             f"generate_msu_data.py exited with code {rc}.\n\n"
                             f"Check the log output for details.")
        self._generation_finished()

    def _on_error(self, error_msg):
        self.phase_label.configure(text="Error")
        self._log(f"Error: {error_msg}", tag="error")
        messagebox.showerror("Error", f"An error occurred:\n\n{error_msg}")
        self._generation_finished()

    def _on_cancelled(self):
        self.phase_label.configure(text="Cancelled")
        self._log("Generation cancelled by user.", tag="warn")
        self._generation_finished()

    def _generation_finished(self):
        self.is_running = False
        self.generate_btn.configure(state=tk.NORMAL)
        self.cancel_btn.configure(state=tk.DISABLED)
        self._validate_all()

    def _run_manifest(self):
        """Run generate_manifest.py after successful generation."""
        if not MANIFEST_SCRIPT.exists():
            self._log("WARN: generate_manifest.py not found, skipping manifest generation",
                      tag="warn")
            return

        self._log("Generating manifest.xml...", tag="phase")
        try:
            result = subprocess.run(
                [sys.executable, str(MANIFEST_SCRIPT), str(DISTRIBUTION)],
                capture_output=True, text=True, cwd=str(PROJECT_ROOT),
            )
            for line in result.stdout.strip().splitlines():
                self._log(line, tag="success")
            if result.returncode != 0:
                for line in result.stderr.strip().splitlines():
                    self._log(line, tag="error")
        except Exception as e:
            self._log(f"Manifest generation error: {e}", tag="error")

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------
    def _cancel_generation(self):
        if not self.is_running or self.cancelled:
            return

        self.cancelled = True
        self._log("Cancelling...", tag="warn")

        if self.process and self.process.poll() is None:
            try:
                # On Windows, kill the entire process tree (including ffmpeg children)
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(self.process.pid)],
                    capture_output=True,
                )
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Chapter discovery and preview
    # ------------------------------------------------------------------
    def _discover_chapters(self, scene_name):
        """Return sorted list of chapter directory names for a scene."""
        if not CHAPTERS_DIR.exists():
            return []

        prefix = SCENE_PREFIXES.get(scene_name, "")
        if not prefix:
            return []

        chapters = []
        for d in sorted(CHAPTERS_DIR.iterdir()):
            if d.is_dir() and d.name.startswith(prefix):
                # Only include chapters that have extracted frames
                pngs = glob.glob(str(d / "*.gfx_video.png"))
                if pngs:
                    chapters.append(d.name)
        return chapters

    def _on_scene_changed(self):
        """Scene combobox changed: populate chapter list."""
        scene = self.scene_var.get()
        if scene == "All Scenes" or not scene:
            self.chapter_cb.configure(values=[])
            self.chapter_var.set("")
            self._clear_preview()
            return

        chapters = self._discover_chapters(scene)
        self.chapter_cb.configure(values=chapters)
        if chapters:
            self.chapter_var.set(chapters[0])
            self._on_chapter_changed()
        else:
            self.chapter_var.set("")
            self._clear_preview()
            self._log(f"No extracted frames found for scene '{scene}'")

    def _on_chapter_changed(self):
        """Chapter combobox changed: load frames and setup scrubber."""
        # Dirty guard: prompt to save before switching
        if self._events_dirty:
            answer = messagebox.askyesnocancel(
                "Save Changes?",
                "Event timeline has been modified. Save before switching?")
            if answer is None:  # Cancel
                return
            if answer:  # Yes
                self._save_events_xml()

        chapter = self.chapter_var.get()
        if not chapter:
            self._clear_preview()
            return

        chapter_dir = CHAPTERS_DIR / chapter
        if not chapter_dir.exists():
            self._clear_preview()
            return

        # Discover frame PNGs
        pngs = sorted(glob.glob(str(chapter_dir / "*.gfx_video.png")))
        if not pngs:
            self._log(f"No frames in {chapter}")
            self._clear_preview()
            return

        self._chapter_frames = pngs
        self._current_chapter_dir = str(chapter_dir)

        # Stop any running clip
        if self._clip_playing or self._clip_cancel is not None:
            self._stop_clip()

        # Setup scrubber
        num_frames = len(pngs)
        self.scrub_scale.configure(from_=0, to=max(num_frames - 1, 0),
                                   state=tk.NORMAL)
        self.clip_btn.configure(state=tk.NORMAL)
        self.scrub_var.set(0)
        self.scrub_label.configure(text=f"Frame 1 / {num_frames}")

        # Setup segments for this chapter
        duration = num_frames / TARGET_FPS
        from segments import SegmentList
        self._segment_list = SegmentList.create_default(
            duration,
            dither_method=self._get_dither_method(),
            num_palettes=self._get_palettes(),
            max_tiles=self._get_max_tiles(),
            grayscale=self.grayscale_var.get(),
            shared_palette=self.shared_palette_var.get(),
            palette_method=self._get_palette_method(),
        )
        self._selected_segment_idx = 0
        self.split_btn.configure(state=tk.NORMAL)
        self.delete_seg_btn.configure(state=tk.DISABLED)
        self.save_seg_btn.configure(state=tk.NORMAL)
        self._redraw_seg_canvas()
        self._update_seg_info()

        # Parse direction events from XML
        events, meta = _parse_chapter_events(chapter)
        self._chapter_events = events
        self._chapter_meta = meta
        self._selected_event_idx = -1
        self._events_dirty = False
        self._update_evt_dirty_label()
        self._redraw_event_canvas()

        # Show first frame
        self._show_frame(0)
        evt_count = len(self._chapter_events)
        correct = sum(1 for e in self._chapter_events if e.label == 'direction-1')
        evt_msg = f", {evt_count} events ({correct} correct)" if evt_count else ""
        self._log(f"Loaded {chapter}: {num_frames} frames{evt_msg}")

    def _clear_preview(self):
        """Clear preview canvases and reset scrubber."""
        if self._clip_playing or self._clip_cancel is not None:
            self._stop_clip()
        self._chapter_frames = []
        self._current_chapter_dir = None
        self._preview_path = None
        self.src_canvas.delete("all")
        self.snes_canvas.delete("all")
        self.scrub_scale.configure(state=tk.DISABLED)
        self.clip_btn.configure(state=tk.DISABLED)
        self.scrub_var.set(0)
        self.scrub_label.configure(text="Frame 0 / 0")
        self._segment_list = None
        self._chapter_events = []
        self._chapter_meta = None
        self._selected_event_idx = -1
        self._events_dirty = False
        self._update_evt_dirty_label()
        self.evt_canvas.delete("all")
        self.split_btn.configure(state=tk.DISABLED)
        self.delete_seg_btn.configure(state=tk.DISABLED)
        self.save_seg_btn.configure(state=tk.DISABLED)
        self.seg_canvas.delete("all")
        self.seg_info_label.configure(text="No segments")

    def _on_scrub(self, value):
        """Scrubber moved: show the frame at the new position."""
        if not self._chapter_frames:
            return
        # Stop any running clip when the user scrubs
        if self._clip_playing or self._clip_cancel is not None:
            self._stop_clip()

        idx = int(float(value))
        idx = max(0, min(idx, len(self._chapter_frames) - 1))
        self.scrub_label.configure(
            text=f"Frame {idx + 1} / {len(self._chapter_frames)}")

        # Auto-select segment at scrubber position
        if self._segment_list:
            t = idx / TARGET_FPS
            new_seg = self._segment_list.segment_index_for_time(t)
            if new_seg != self._selected_segment_idx:
                self._selected_segment_idx = new_seg
                self._load_segment_to_controls()
                self._redraw_seg_canvas()
                self._update_seg_info()

        # Update event timeline playhead
        self._redraw_event_canvas()

        # Debounce the actual frame display
        if self._scrub_timer is not None:
            self.root.after_cancel(self._scrub_timer)
        self._scrub_timer = self.root.after(50, self._show_frame, idx)

    def _show_frame(self, idx):
        """Display source frame and SNES reconstruction for frame index."""
        self._scrub_timer = None
        if idx < 0 or idx >= len(self._chapter_frames):
            return

        png_path = self._chapter_frames[idx]
        self._preview_path = png_path

        try:
            from PIL import Image, ImageTk

            # Source frame
            src_img = Image.open(png_path)
            self._display_on_canvas(self.src_canvas, src_img, "src_photo")

            # Draw direction arrow overlays on source canvas
            self._draw_event_overlay(idx)

            # SNES reconstruction: check for existing tile data
            base = png_path[:-4]  # remove .png
            tile_file = base + ".tiles"
            map_file = base + ".tilemap"
            pal_file = base + ".palette"

            if (os.path.isfile(tile_file) and os.path.isfile(map_file)
                    and os.path.isfile(pal_file)):
                from preview import preview_frame_files
                snes_img = preview_frame_files(tile_file, map_file, pal_file)
                self._display_on_canvas(self.snes_canvas, snes_img, "snes_photo")
            else:
                # No pre-converted data; run conversion in background
                self._reconvert_preview()
        except Exception as e:
            self._log(f"Preview error: {e}", tag="warn")

    def _display_on_canvas(self, canvas, pil_img, photo_attr):
        """Scale a PIL image to fit the canvas and display it centered."""
        from PIL import Image, ImageTk

        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        if cw <= 1 or ch <= 1:
            cw = int(canvas.cget("width"))
            ch = int(canvas.cget("height"))

        iw, ih = pil_img.size
        scale = min(cw / iw, ch / ih)
        new_w = max(1, int(iw * scale))
        new_h = max(1, int(ih * scale))

        if new_w != iw or new_h != ih:
            scaled = pil_img.resize((new_w, new_h), Image.NEAREST)
        else:
            scaled = pil_img

        photo = ImageTk.PhotoImage(scaled)
        setattr(self, photo_attr, photo)
        canvas.delete("all")
        canvas.create_image(cw // 2, ch // 2, image=photo)

    def _get_dither_method(self):
        """Map GUI dither string to CLI value."""
        mapping = {"None": "none", "Floyd-Steinberg": "floyd-steinberg",
                   "Ordered": "ordered"}
        return mapping.get(self.dither_var.get(), "floyd-steinberg")

    def _get_palettes(self):
        """Get current palette count as int."""
        try:
            return int(self.palettes_var.get())
        except (ValueError, tk.TclError):
            return 8

    def _get_max_tiles(self):
        """Get current max tiles as int."""
        try:
            return int(self.max_tiles_var.get())
        except (ValueError, tk.TclError):
            return 512

    def _get_palette_method(self):
        """Get current palette method as CLI string."""
        mapping = {"K-Means": "kmeans", "Tile-Aware": "tileaware"}
        return mapping.get(self.palette_method_var.get(), "tileaware")

    def _on_quality_changed(self):
        """Quality settings changed: update segment and reconvert preview."""
        if self._updating_controls:
            return

        # Write current widget values into the selected segment
        if self._segment_list and 0 <= self._selected_segment_idx < len(self._segment_list):
            seg = self._segment_list.segments[self._selected_segment_idx]
            seg.dither_method = self._get_dither_method()
            seg.grayscale = self.grayscale_var.get()
            seg.shared_palette = self.shared_palette_var.get()
            seg.num_palettes = self._get_palettes()
            seg.max_tiles = self._get_max_tiles()
            seg.palette_method = self._get_palette_method()
            self._redraw_seg_canvas()

        # Debounce reconversion
        if self._preview_timer is not None:
            self.root.after_cancel(self._preview_timer)
        self._preview_timer = self.root.after(300, self._reconvert_preview)

    def _reconvert_preview(self):
        """Re-convert the current preview frame with current quality settings."""
        self._preview_timer = None
        preview_path = self._preview_path
        if not preview_path or not os.path.isfile(preview_path):
            return
        if self.is_running:
            return

        num_palettes = self._get_palettes()
        max_tiles = self._get_max_tiles()
        dither_method = self._get_dither_method()
        grayscale = self.grayscale_var.get()
        palette_method = self._get_palette_method()

        if max_tiles < 1 or max_tiles > 512:
            return

        def _convert():
            try:
                from generate_msu_data import convert_frame_superfamiconv
                from preview import preview_frame_files

                ok, err = convert_frame_superfamiconv(
                    preview_path,
                    num_palettes=num_palettes,
                    dither_method=dither_method,
                    max_tiles=max_tiles,
                    grayscale=grayscale,
                    palette_method=palette_method,
                )
                if ok:
                    base = preview_path[:-4]
                    snes_img = preview_frame_files(
                        base + ".tiles", base + ".tilemap", base + ".palette")
                    self.root.after(0, self._display_on_canvas,
                                    self.snes_canvas, snes_img, "snes_photo")
            except Exception:
                pass

        threading.Thread(target=_convert, daemon=True).start()

    # ------------------------------------------------------------------
    # Arrow key frame stepping
    # ------------------------------------------------------------------
    def _step_frame(self, delta):
        """Advance or rewind the scrubber by delta frames."""
        if not self._chapter_frames:
            return
        # Stop any running clip
        if self._clip_playing or self._clip_cancel is not None:
            self._stop_clip()

        idx = int(self.scrub_var.get()) + delta
        idx = max(0, min(idx, len(self._chapter_frames) - 1))
        self.scrub_var.set(idx)
        self.scrub_label.configure(
            text=f"Frame {idx + 1} / {len(self._chapter_frames)}")

        # Auto-select segment
        if self._segment_list:
            t = idx / TARGET_FPS
            new_seg = self._segment_list.segment_index_for_time(t)
            if new_seg != self._selected_segment_idx:
                self._selected_segment_idx = new_seg
                self._load_segment_to_controls()
                self._redraw_seg_canvas()
                self._update_seg_info()

        # Update event timeline playhead
        self._redraw_event_canvas()

        # Show immediately (no debounce for arrow keys)
        if self._scrub_timer is not None:
            self.root.after_cancel(self._scrub_timer)
            self._scrub_timer = None
        self._show_frame(idx)

    # ------------------------------------------------------------------
    # Event timeline strip + arrow overlay
    # ------------------------------------------------------------------
    _EVT_TRACK_HEIGHT = 20  # pixels per event track

    def _resize_evt_canvas(self):
        """Resize event canvas height to fit one track per event."""
        n = max(1, len(self._chapter_events))
        h = n * self._EVT_TRACK_HEIGHT
        self.evt_canvas.configure(height=h)

    def _redraw_event_canvas(self):
        """Redraw the multi-track event timeline strip below the scrubber."""
        c = self.evt_canvas
        c.delete("all")
        if not self._chapter_events or not self._chapter_frames:
            self.evt_canvas.configure(height=self._EVT_TRACK_HEIGHT)
            return

        self._resize_evt_canvas()

        cw = c.winfo_width()
        if cw <= 1:
            cw = 400

        total_frames = len(self._chapter_frames)
        if total_frames <= 0:
            return

        th = self._EVT_TRACK_HEIGHT
        total_h = len(self._chapter_events) * th

        for i, ev in enumerate(self._chapter_events):
            y0 = i * th
            y1 = y0 + th

            # Track separator line
            if i > 0:
                c.create_line(0, y0, cw, y0, fill="#333355", width=1)

            x0 = int(ev.start_frame / total_frames * cw)
            x1 = int(ev.end_frame / total_frames * cw)
            x1 = max(x1, x0 + 2)  # minimum 2px wide
            color = DIR_COLORS.get(ev.direction, '#888888')
            # Death traps (label != 'direction-1') drawn dimmer
            if ev.label != 'direction-1':
                color = self._dim_color(color, 0.35)
            c.create_rectangle(x0, y0 + 1, x1, y1 - 1, fill=color, outline="")

            # Selection highlight
            if i == self._selected_event_idx:
                c.create_rectangle(x0, y0 + 1, x1, y1 - 1, fill="",
                                   outline="white", width=2)

            # Direction letter when wide enough
            if x1 - x0 > 14:
                letter = ev.direction[0].upper()
                mid_x = (x0 + x1) // 2
                mid_y = (y0 + y1) // 2
                c.create_text(mid_x, mid_y, text=letter,
                              fill="white", font=("Segoe UI", 8, "bold"))

        # Playhead line (spans all tracks)
        idx = int(self.scrub_var.get())
        px = int(idx / total_frames * cw)
        c.create_line(px, 0, px, total_h, fill="white", width=1)

    # ------------------------------------------------------------------
    # Event timeline interaction
    # ------------------------------------------------------------------
    def _evt_hit_test(self, px, py):
        """Hit-test pixel (x,y) on evt_canvas. Returns (event_index, zone).

        Each event occupies its own horizontal track. zone is 'left_edge',
        'right_edge', 'body', or 'none'.
        """
        if not self._chapter_events or not self._chapter_frames:
            return (-1, 'none')

        cw = self.evt_canvas.winfo_width()
        if cw <= 1:
            return (-1, 'none')
        total_frames = len(self._chapter_frames)
        if total_frames <= 0:
            return (-1, 'none')

        th = self._EVT_TRACK_HEIGHT
        track = int(py // th)
        if track < 0 or track >= len(self._chapter_events):
            return (-1, 'none')

        ev = self._chapter_events[track]
        x0 = int(ev.start_frame / total_frames * cw)
        x1 = int(ev.end_frame / total_frames * cw)
        x1 = max(x1, x0 + 2)

        EDGE_PX = 6
        if x0 <= px <= x1:
            if px <= x0 + EDGE_PX:
                return (track, 'left_edge')
            elif px >= x1 - EDGE_PX:
                return (track, 'right_edge')
            else:
                return (track, 'body')

        return (track, 'none')

    def _on_evt_hover(self, event):
        """Update cursor shape based on hover position."""
        idx, zone = self._evt_hit_test(event.x, event.y)
        if zone in ('left_edge', 'right_edge'):
            self.evt_canvas.configure(cursor="sb_h_double_arrow")
        elif zone == 'body':
            self.evt_canvas.configure(cursor="fleur")
        else:
            self.evt_canvas.configure(cursor="")

    def _on_evt_press(self, event):
        """Mouse button 1 pressed on event canvas: select + start drag."""
        idx, zone = self._evt_hit_test(event.x, event.y)
        self._selected_event_idx = idx
        if idx >= 0 and zone != 'none':
            ev = self._chapter_events[idx]
            if zone == 'left_edge':
                self._drag_mode = 'resize_left'
            elif zone == 'right_edge':
                self._drag_mode = 'resize_right'
            else:
                self._drag_mode = 'move'
            self._drag_start_x = event.x
            self._drag_orig_start = ev.start_frame
            self._drag_orig_end = ev.end_frame
        else:
            self._drag_mode = None
        self._redraw_event_canvas()

    def _on_evt_drag(self, event):
        """Mouse drag on event canvas: move or resize event."""
        if self._drag_mode is None or self._selected_event_idx < 0:
            return
        if not self._chapter_frames:
            return

        cw = self.evt_canvas.winfo_width()
        if cw <= 1:
            return
        total_frames = len(self._chapter_frames)

        dx_px = event.x - self._drag_start_x
        dx_frames = int(dx_px / cw * total_frames)
        ev = self._chapter_events[self._selected_event_idx]

        if self._drag_mode == 'move':
            new_start = self._drag_orig_start + dx_frames
            new_end = self._drag_orig_end + dx_frames
            span = self._drag_orig_end - self._drag_orig_start
            if new_start < 0:
                new_start = 0
                new_end = span
            if new_end > total_frames:
                new_end = total_frames
                new_start = total_frames - span
            ev.start_frame = new_start
            ev.end_frame = new_end
        elif self._drag_mode == 'resize_left':
            new_start = self._drag_orig_start + dx_frames
            new_start = max(0, min(new_start, ev.end_frame - 1))
            ev.start_frame = new_start
        elif self._drag_mode == 'resize_right':
            new_end = self._drag_orig_end + dx_frames
            new_end = max(ev.start_frame + 1, min(new_end, total_frames))
            ev.end_frame = new_end

        self._mark_events_dirty()
        self._redraw_event_canvas()

    def _on_evt_release(self, event):
        """Mouse button released: end drag."""
        self._drag_mode = None

    def _on_evt_right_click(self, event):
        """Right-click context menu on event canvas."""
        idx, zone = self._evt_hit_test(event.x, event.y)
        menu = tk.Menu(self.root, tearoff=0)

        if idx >= 0:
            self._selected_event_idx = idx
            self._redraw_event_canvas()
            ev = self._chapter_events[idx]

            # Change Direction submenu
            dir_menu = tk.Menu(menu, tearoff=0)
            for d in ('left', 'right', 'up', 'down', 'action'):
                label = f"{'> ' if d == ev.direction else '  '}{d.capitalize()}"
                dir_menu.add_command(
                    label=label,
                    command=lambda d=d: self._change_event_direction(idx, d))
            menu.add_cascade(label="Change Direction", menu=dir_menu)

            # Correct path toggle
            if ev.label == 'direction-1':
                menu.add_command(label="Mark as Death Trap",
                                 command=lambda: self._set_event_label(idx, False))
            else:
                menu.add_command(label="Mark as Correct Path",
                                 command=lambda: self._set_event_label(idx, True))

            menu.add_command(label="Set Target Chapter...",
                             command=lambda: self._edit_event_target(idx))
            menu.add_separator()
            menu.add_command(label="Delete Event",
                             command=lambda: self._delete_event(idx))
        else:
            # Add event submenu on empty space
            add_menu = tk.Menu(menu, tearoff=0)
            for d in ('left', 'right', 'up', 'down', 'action'):
                add_menu.add_command(
                    label=d.capitalize(),
                    command=lambda d=d: self._add_event(event.x, d))
            menu.add_cascade(label="Add Event", menu=add_menu)

        menu.post(event.x_root, event.y_root)

    def _on_delete_key(self, event):
        """Delete key pressed: remove selected event."""
        if self._selected_event_idx >= 0 and self._chapter_events:
            self._delete_event(self._selected_event_idx)

    # ------------------------------------------------------------------
    # Event CRUD operations
    # ------------------------------------------------------------------
    def _add_event(self, px, direction):
        """Add a new direction event centered at the clicked pixel position."""
        if not self._chapter_frames:
            return
        cw = self.evt_canvas.winfo_width()
        if cw <= 1:
            return
        total_frames = len(self._chapter_frames)

        center_frame = int(px / cw * total_frames)
        half_span = 7  # 15-frame default span
        start = max(0, center_frame - half_span)
        end = min(total_frames, center_frame + half_span + 1)

        # Auto-label: direction-{N+1}
        n = len(self._chapter_events) + 1
        label = f"direction-{n}"

        ev = ChapterEvent(
            direction=direction,
            start_frame=start,
            end_frame=end,
            label=label,
            target="",
            result_type="playchapter",
        )
        self._chapter_events.append(ev)
        self._selected_event_idx = len(self._chapter_events) - 1
        self._mark_events_dirty()
        self._redraw_event_canvas()

    def _delete_event(self, idx):
        """Delete event at index."""
        if 0 <= idx < len(self._chapter_events):
            self._chapter_events.pop(idx)
            self._selected_event_idx = -1
            self._mark_events_dirty()
            self._redraw_event_canvas()

    def _change_event_direction(self, idx, direction):
        """Change the direction of event at index."""
        if 0 <= idx < len(self._chapter_events):
            self._chapter_events[idx].direction = direction
            self._mark_events_dirty()
            self._redraw_event_canvas()
            # Refresh arrow overlay
            frame_idx = int(self.scrub_var.get())
            self._draw_event_overlay(frame_idx)

    def _set_event_label(self, idx, is_correct):
        """Toggle event between correct path (direction-1) and death trap."""
        if not (0 <= idx < len(self._chapter_events)):
            return
        if is_correct:
            # Demote any existing direction-1
            for i, ev in enumerate(self._chapter_events):
                if ev.label == 'direction-1':
                    ev.label = f'direction-{i + 1}'
            self._chapter_events[idx].label = 'direction-1'
        else:
            self._chapter_events[idx].label = f'direction-{idx + 1}'
        self._mark_events_dirty()
        self._redraw_event_canvas()

    def _edit_event_target(self, idx):
        """Edit target chapter name via dialog."""
        if not (0 <= idx < len(self._chapter_events)):
            return
        ev = self._chapter_events[idx]
        result = simpledialog.askstring(
            "Target Chapter",
            f"Target chapter for {ev.direction} event:",
            initialvalue=ev.target,
            parent=self.root)
        if result is not None:
            ev.target = result.strip()
            self._mark_events_dirty()

    # ------------------------------------------------------------------
    # Dirty state tracking
    # ------------------------------------------------------------------
    def _mark_events_dirty(self):
        """Mark events as modified."""
        self._events_dirty = True
        self._update_evt_dirty_label()

    def _clear_events_dirty(self):
        """Clear the modified flag."""
        self._events_dirty = False
        self._update_evt_dirty_label()

    def _update_evt_dirty_label(self):
        """Update the dirty indicator label and button states."""
        has_meta = self._chapter_meta is not None
        if self._events_dirty:
            self.evt_dirty_label.configure(text="* Modified", foreground="orange")
            self.save_xml_btn.configure(state=tk.NORMAL if has_meta else tk.DISABLED)
        else:
            if has_meta and self._chapter_events:
                self.evt_dirty_label.configure(text="Saved", foreground="green")
            else:
                self.evt_dirty_label.configure(text="")
            self.save_xml_btn.configure(state=tk.DISABLED)
        self.export_lua_btn.configure(
            state=tk.NORMAL if (has_meta and self._chapter_events) else tk.DISABLED)

    @staticmethod
    def _dim_color(hex_color: str, factor: float) -> str:
        """Dim a hex color by blending toward black."""
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        r = int(r * factor)
        g = int(g * factor)
        b = int(b * factor)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _draw_event_overlay(self, frame_idx):
        """Draw directional arrows on the source canvas for active events."""
        self.src_canvas.delete("event_overlay")
        if not self._chapter_events:
            return

        # Get canvas dimensions and image scale
        cw = self.src_canvas.winfo_width()
        ch_canvas = self.src_canvas.winfo_height()
        if cw <= 1 or ch_canvas <= 1:
            return

        # SNES frame is 256x192
        img_w, img_h = 256, 192
        scale = min(cw / img_w, ch_canvas / img_h)
        # Image is centered on canvas
        offset_x = (cw - img_w * scale) / 2
        offset_y = (ch_canvas - img_h * scale) / 2

        for ev in self._chapter_events:
            # Only show correct-path arrows (direction-1)
            if ev.label != 'direction-1':
                continue
            if not (ev.start_frame <= frame_idx < ev.end_frame):
                continue

            pos = DIR_POSITIONS.get(ev.direction)
            if pos is None:
                continue
            color = DIR_COLORS.get(ev.direction, '#e8c840')

            # Scale SNES coords to canvas coords
            cx = offset_x + pos[0] * scale
            cy = offset_y + pos[1] * scale
            sz = 14 * scale  # arrow size

            points = self._arrow_points(ev.direction, cx, cy, sz)
            if points:
                self.src_canvas.create_polygon(
                    points, fill=color, outline="white", width=1,
                    tags="event_overlay")

    @staticmethod
    def _arrow_points(direction, cx, cy, sz):
        """Return polygon points for an arrow triangle pointing in direction."""
        half = sz / 2
        if direction == 'left':
            return [cx - half, cy, cx + half, cy - half, cx + half, cy + half]
        elif direction == 'right':
            return [cx + half, cy, cx - half, cy - half, cx - half, cy + half]
        elif direction == 'up':
            return [cx, cy - half, cx - half, cy + half, cx + half, cy + half]
        elif direction == 'down':
            return [cx, cy + half, cx - half, cy - half, cx + half, cy - half]
        elif direction == 'action':
            # Diamond shape for action
            return [cx, cy - half, cx + half, cy, cx, cy + half, cx - half, cy]
        return None

    # ------------------------------------------------------------------
    # Save XML / Export Lua
    # ------------------------------------------------------------------
    @staticmethod
    def _ms_to_time_attrs(total_ms, frame=None):
        """Convert total ms to min/second/ms attribute dict."""
        total_ms = max(0, total_ms)
        minutes = int(total_ms // 60000)
        remainder = total_ms - minutes * 60000
        seconds = int(remainder // 1000)
        ms = int(remainder % 1000)
        d = {"min": str(minutes), "second": str(seconds), "ms": str(ms)}
        if frame is not None:
            d["frame"] = str(frame)
        return d

    def _save_events_xml(self):
        """Save edited events back to the chapter's XML file."""
        meta = self._chapter_meta
        if meta is None:
            return

        # Build XML tree
        root = ET.Element("chapter", name=meta.chapter_name)

        # Chapter timeline
        tl = ET.SubElement(root, "timeline")
        ts_attrs = self._ms_to_time_attrs(meta.chapter_start_ms,
                                           frame=meta.chapter_start_frame)
        ET.SubElement(tl, "timestart", **ts_attrs)
        te_attrs = self._ms_to_time_attrs(meta.chapter_end_ms)
        ET.SubElement(tl, "timeend", **te_attrs)

        ET.SubElement(root, "params")
        ET.SubElement(root, "macros")

        # Events
        events_el = ET.SubElement(root, "events")

        # Non-direction events (preserved verbatim)
        for raw_xml in meta.non_direction_events:
            try:
                parsed = ET.fromstring(raw_xml)
                events_el.append(parsed)
            except ET.ParseError:
                pass

        # Direction events from editor
        for ev in self._chapter_events:
            # Convert chapter-relative frames back to absolute ms
            abs_start_ms = meta.chapter_start_ms + ev.start_frame / TARGET_FPS * 1000
            abs_end_ms = meta.chapter_start_ms + ev.end_frame / TARGET_FPS * 1000

            ev_el = ET.SubElement(events_el, "event",
                                  type="direction", automacro="direction",
                                  label=ev.label)
            ev_tl = ET.SubElement(ev_el, "timeline")
            ET.SubElement(ev_tl, "timestart", **self._ms_to_time_attrs(abs_start_ms))
            ET.SubElement(ev_tl, "timeend", **self._ms_to_time_attrs(abs_end_ms))

            params = ET.SubElement(ev_el, "params")
            ET.SubElement(params, "str", key="type", value=ev.direction)

            result = ET.SubElement(ev_el, "result")
            if ev.result_type and ev.result_type != 'none':
                attrs = {"name": ev.target} if ev.target else {}
                ET.SubElement(result, ev.result_type, **attrs)
            elif ev.target:
                ET.SubElement(result, "none", name=ev.target)

        # Chapter-level result
        ch_result = ET.SubElement(root, "result")
        if meta.default_result_type:
            attrs = {"name": meta.default_result_target} if meta.default_result_target else {}
            ET.SubElement(ch_result, meta.default_result_type, **attrs)

        # Write with indentation
        ET.indent(root, space="\t")
        xml_path = EVENTS_DIR / f"{meta.chapter_name}.xml"
        tree = ET.ElementTree(root)
        tree.write(str(xml_path), encoding="unicode", xml_declaration=False)
        # Append trailing newline
        with open(str(xml_path), "a") as f:
            f.write("\n")

        self._clear_events_dirty()
        self._log(f"Saved events to {xml_path.name}", tag="success")

    def _export_events_lua(self):
        """Export current events as DirkSimple game.lua format in a dialog."""
        meta = self._chapter_meta
        if meta is None or not self._chapter_events:
            return

        # Derive sequence name by stripping scene prefix
        seq_name = meta.chapter_name
        for scene, prefix in SCENE_PREFIXES.items():
            if seq_name.startswith(prefix):
                seq_name = seq_name[len(prefix):]
                break

        # Build Lua text
        lines = []
        lines.append(f"    {seq_name} = {{")

        # start_time
        if meta.chapter_start_frame is not None:
            lines.append(f"        start_time = time_laserdisc_frame({meta.chapter_start_frame}),")
        else:
            lines.append(f"        start_time = time_laserdisc_noseek(),")

        # timeout (chapter default result)
        ch_end_rel_ms = meta.chapter_end_ms - meta.chapter_start_ms
        s = int(ch_end_rel_ms // 1000)
        ms = int(ch_end_rel_ms % 1000)
        target_seq = meta.default_result_target
        for scene, prefix in SCENE_PREFIXES.items():
            if target_seq.startswith(prefix):
                target_seq = target_seq[len(prefix):]
                break
        if target_seq:
            lines.append(f"        timeout = {{ when=time_to_ms({s}, {ms}), nextsequence=\"{target_seq}\" }},")
        else:
            lines.append(f"        timeout = {{ when=time_to_ms({s}, {ms}) }},")

        # actions
        lines.append(f"        actions = {{")
        for ev in self._chapter_events:
            direction_str = ev.direction
            if direction_str == 'action':
                direction_str = 'button'

            from_ms = ev.start_frame / TARGET_FPS * 1000
            to_ms = ev.end_frame / TARGET_FPS * 1000
            from_s = int(from_ms // 1000)
            from_rem = int(from_ms % 1000)
            to_s = int(to_ms // 1000)
            to_rem = int(to_ms % 1000)

            ev_target = ev.target
            for scene, prefix in SCENE_PREFIXES.items():
                if ev_target.startswith(prefix):
                    ev_target = ev_target[len(prefix):]
                    break

            target_part = f', nextsequence="{ev_target}"' if ev_target else ""
            lines.append(
                f"            {{ input=\"{direction_str}\", "
                f"from=time_to_ms({from_s}, {from_rem}), "
                f"to=time_to_ms({to_s}, {to_rem})"
                f"{target_part} }},")

        lines.append(f"        }}")
        lines.append(f"    }},")

        lua_text = "\n".join(lines)

        # Show in dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Lua Export — {meta.chapter_name}")
        dialog.geometry("600x400")
        dialog.transient(self.root)

        text = tk.Text(dialog, wrap=tk.NONE, font=("Consolas", 10))
        text.insert("1.0", lua_text)
        text.configure(state=tk.DISABLED)

        scrollbar = ttk.Scrollbar(dialog, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)

        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=8, pady=4)

        def copy_to_clipboard():
            dialog.clipboard_clear()
            dialog.clipboard_append(lua_text)
            copy_btn.configure(text="Copied!")
            dialog.after(1500, lambda: copy_btn.configure(text="Copy to Clipboard"))

        copy_btn = ttk.Button(btn_frame, text="Copy to Clipboard",
                               command=copy_to_clipboard)
        copy_btn.pack(side=tk.RIGHT)

    # ------------------------------------------------------------------
    # Clip preview (animated ~2s playback)
    # ------------------------------------------------------------------
    def _toggle_clip(self):
        """Start or stop the animated preview clip."""
        if self._clip_playing or self._clip_cancel is not None:
            self._stop_clip()
        else:
            self._start_clip()

    def _start_clip(self):
        """Render a short clip from the scrubber position and play it back."""
        if not self._chapter_frames or self.is_running:
            return

        CLIP_FRAMES = int(TARGET_FPS * 2)  # ~2 seconds
        start_idx = int(self.scrub_var.get())
        end_idx = min(start_idx + CLIP_FRAMES, len(self._chapter_frames))
        if end_idx <= start_idx:
            return

        frame_paths = self._chapter_frames[start_idx:end_idx]
        total = len(frame_paths)

        # Capture quality settings
        num_palettes = self._get_palettes()
        max_tiles = self._get_max_tiles()
        dither_method = self._get_dither_method()
        grayscale = self.grayscale_var.get()
        palette_method = self._get_palette_method()

        cancel = threading.Event()
        self._clip_cancel = cancel
        self._clip_frames = []
        self._clip_playing = False
        self.clip_btn.configure(text="Stop")
        self.phase_label.configure(text="Rendering preview clip...")
        self.progress_var.set(0)

        def _render():
            from concurrent.futures import ThreadPoolExecutor, as_completed

            results = [None] * total
            done = [0]

            def convert_one(idx, png_path):
                if cancel.is_set():
                    return idx, None, None
                try:
                    from PIL import Image
                    from generate_msu_data import convert_frame_superfamiconv
                    from preview import preview_frame_files

                    src = Image.open(png_path).copy()

                    ok, err = convert_frame_superfamiconv(
                        png_path,
                        num_palettes=num_palettes,
                        dither_method=dither_method,
                        max_tiles=max_tiles,
                        grayscale=grayscale,
                        palette_method=palette_method,
                    )
                    if ok:
                        base = png_path[:-4]
                        snes = preview_frame_files(
                            base + ".tiles", base + ".tilemap", base + ".palette")
                    else:
                        snes = src  # fallback
                    return idx, src, snes
                except Exception:
                    return idx, None, None

            try:
                workers = max(1, int(self.workers_var.get()))
            except (ValueError, tk.TclError):
                workers = 4

            try:
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    futures = {pool.submit(convert_one, i, p): i
                               for i, p in enumerate(frame_paths)}
                    for future in as_completed(futures):
                        if cancel.is_set():
                            pool.shutdown(wait=False, cancel_futures=True)
                            return
                        idx, src, snes = future.result()
                        if src is not None:
                            results[idx] = (src, snes)
                        done[0] += 1
                        pct = done[0] / total * 100
                        self.root.after(0, self._clip_render_progress,
                                        done[0], total, pct)

                if cancel.is_set():
                    return

                frames = [r for r in results if r is not None]
                if frames:
                    self.root.after(0, self._clip_play, frames)

            except Exception as e:
                self.root.after(0, self._log,
                                f"Clip render failed: {e}", "error")
            finally:
                self.root.after(0, self._clip_render_done)

        threading.Thread(target=_render, daemon=True).start()

    def _clip_render_progress(self, done, total, pct):
        """Update progress during clip rendering."""
        self.progress_var.set(pct)
        self.progress_pct.configure(text=f"{pct:.0f}%")
        self.phase_label.configure(text=f"Rendering clip: {done}/{total} frames")

    def _clip_render_done(self):
        """Clean up after clip render thread finishes."""
        if not self._clip_playing:
            self._clip_cancel = None
            self.clip_btn.configure(text="Preview Clip")
            self.phase_label.configure(text="Ready")
            self.progress_var.set(0)
            self.progress_pct.configure(text="0%")

    def _clip_play(self, frames):
        """Start animation playback of rendered clip frames."""
        self._clip_frames = frames
        self._clip_frame_idx = 0
        self._clip_playing = True
        self._clip_cancel = None
        self.phase_label.configure(text="Playing preview clip")
        self.progress_var.set(0)
        self.progress_pct.configure(text="")
        self._clip_tick()

    def _clip_tick(self):
        """Display the next animation frame and schedule the next tick."""
        if not self._clip_playing or not self._clip_frames:
            return

        idx = self._clip_frame_idx
        src_pil, snes_pil = self._clip_frames[idx]
        self._display_on_canvas(self.src_canvas, src_pil, "src_photo")
        self._display_on_canvas(self.snes_canvas, snes_pil, "snes_photo")

        self._clip_frame_idx = (idx + 1) % len(self._clip_frames)

        # ~24fps = 42ms per frame
        self._clip_timer = self.root.after(42, self._clip_tick)

    def _stop_clip(self):
        """Stop clip rendering or playback."""
        if self._clip_cancel is not None:
            self._clip_cancel.set()
            self._clip_cancel = None

        self._clip_playing = False
        if self._clip_timer is not None:
            self.root.after_cancel(self._clip_timer)
            self._clip_timer = None

        self._clip_frames = []
        self._clip_frame_idx = 0
        self.clip_btn.configure(text="Preview Clip")
        self.phase_label.configure(text="Ready")
        self.progress_var.set(0)
        self.progress_pct.configure(text="0%")

    # ------------------------------------------------------------------
    # Segment strip
    # ------------------------------------------------------------------
    _SEG_COLORS = ['#4a90d9', '#e07040', '#50b060', '#c050c0',
                   '#d0c040', '#40c0c0', '#d06080', '#8080c0']

    def _redraw_seg_canvas(self):
        """Redraw the colored segment strip."""
        c = self.seg_canvas
        c.delete("all")
        if not self._segment_list or len(self._segment_list) == 0:
            return

        cw = c.winfo_width()
        ch = c.winfo_height()
        if cw <= 1:
            cw = 400
        if ch <= 1:
            ch = 24

        total_dur = (self._segment_list.segments[-1].end_time
                     if self._segment_list.segments else 1.0)
        if total_dur <= 0:
            total_dur = 1.0

        for i, seg in enumerate(self._segment_list.segments):
            x0 = int(seg.start_time / total_dur * cw)
            x1 = int(seg.end_time / total_dur * cw)
            color = self._SEG_COLORS[i % len(self._SEG_COLORS)]
            c.create_rectangle(x0, 0, x1, ch, fill=color, outline="")

            if i == self._selected_segment_idx:
                c.create_rectangle(x0, 0, x1, ch, fill="", outline="white", width=2)

            mid_x = (x0 + x1) // 2
            if x1 - x0 > 16:
                c.create_text(mid_x, ch // 2, text=str(i + 1),
                              fill="white", font=("Segoe UI", 8, "bold"))

    def _update_seg_info(self):
        """Update segment info label."""
        if not self._segment_list or len(self._segment_list) == 0:
            self.seg_info_label.configure(text="No segments")
            return

        idx = self._selected_segment_idx
        total = len(self._segment_list)
        seg = self._segment_list.segments[idx]
        self.seg_info_label.configure(
            text=f"Segment {idx + 1}/{total}: "
                 f"{self._format_time(seg.start_time)} - {self._format_time(seg.end_time)}")

        self.delete_seg_btn.configure(
            state=tk.NORMAL if total > 1 else tk.DISABLED)

    def _on_seg_canvas_click(self, event):
        """Select the segment under the mouse click."""
        if not self._segment_list or len(self._segment_list) == 0:
            return

        cw = self.seg_canvas.winfo_width()
        if cw <= 1:
            return

        total_dur = (self._segment_list.segments[-1].end_time
                     if self._segment_list.segments else 1.0)
        click_time = event.x / cw * total_dur

        new_idx = self._segment_list.segment_index_for_time(click_time)
        if new_idx != self._selected_segment_idx:
            self._selected_segment_idx = new_idx
            self._load_segment_to_controls()
            self._redraw_seg_canvas()
            self._update_seg_info()

    def _load_segment_to_controls(self):
        """Load selected segment's settings into the quality widgets."""
        if not self._segment_list or self._selected_segment_idx >= len(self._segment_list):
            return

        seg = self._segment_list.segments[self._selected_segment_idx]

        self._updating_controls = True
        try:
            dither_map = {
                "none": "None",
                "floyd-steinberg": "Floyd-Steinberg",
                "ordered": "Ordered",
            }
            self.dither_var.set(dither_map.get(seg.dither_method, "Floyd-Steinberg"))
            self.palettes_var.set(str(seg.num_palettes))
            self.max_tiles_var.set(str(seg.max_tiles))
            self.grayscale_var.set(seg.grayscale)
            self.shared_palette_var.set(seg.shared_palette)
            pal_method_map = {"kmeans": "K-Means", "tileaware": "Tile-Aware"}
            self.palette_method_var.set(pal_method_map.get(seg.palette_method, "Tile-Aware"))
        finally:
            self._updating_controls = False

    def _split_segment(self):
        """Split the segment at the current scrubber position."""
        if not self._segment_list or not self._chapter_frames:
            return

        idx = int(self.scrub_var.get())
        split_time = idx / TARGET_FPS

        new_idx = self._segment_list.split_at(split_time)
        if new_idx is None:
            self._log("Cannot split: segment would be too short")
            return

        self._selected_segment_idx = new_idx
        self._load_segment_to_controls()
        self._redraw_seg_canvas()
        self._update_seg_info()
        self._log(f"Split at frame {idx + 1} ({len(self._segment_list)} segments)")

    def _delete_segment(self):
        """Delete the selected segment by merging into its neighbor."""
        if not self._segment_list:
            return

        idx = self._selected_segment_idx
        if not self._segment_list.delete_segment(idx):
            self._log("Cannot delete the last remaining segment")
            return

        self._selected_segment_idx = max(0, idx - 1)
        self._load_segment_to_controls()
        self._redraw_seg_canvas()
        self._update_seg_info()
        self._on_quality_changed()
        self._log(f"Deleted segment ({len(self._segment_list)} segments remaining)")

    def _save_segments(self):
        """Save segment layout to a JSON file."""
        if not self._segment_list:
            return

        # Default filename based on current chapter
        initial_name = "segments.json"
        chapter = self.chapter_var.get()
        if chapter:
            initial_name = f"{chapter}_segments.json"

        path = filedialog.asksaveasfilename(
            title="Save Segments",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            defaultextension=".json",
            initialfile=initial_name,
            initialdir=str(CHAPTERS_DIR) if CHAPTERS_DIR.exists() else str(PROJECT_ROOT),
        )
        if not path:
            return

        try:
            with open(path, "w") as f:
                f.write(self._segment_list.to_json())
            self._log(f"Saved {len(self._segment_list)} segment(s) to {Path(path).name}",
                      tag="success")
        except Exception as e:
            self._log(f"Save failed: {e}", tag="error")

    def _load_segments(self):
        """Load segment layout from a JSON file."""
        path = filedialog.askopenfilename(
            title="Load Segments",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=str(CHAPTERS_DIR) if CHAPTERS_DIR.exists() else str(PROJECT_ROOT),
        )
        if not path:
            return

        try:
            from segments import SegmentList
            loaded = SegmentList.from_json_file(path)
            if len(loaded) == 0:
                self._log("File contains no segments", tag="warn")
                return

            # If a chapter is loaded, clamp to its duration
            if self._chapter_frames:
                duration = len(self._chapter_frames) / TARGET_FPS
                loaded.update_duration(duration)

            self._segment_list = loaded
            self._selected_segment_idx = 0
            self._load_segment_to_controls()
            self._redraw_seg_canvas()
            self._update_seg_info()
            self.split_btn.configure(state=tk.NORMAL if self._chapter_frames else tk.DISABLED)
            self.save_seg_btn.configure(state=tk.NORMAL)
            self._log(f"Loaded {len(loaded)} segment(s) from {Path(path).name}",
                      tag="success")
        except Exception as e:
            self._log(f"Load failed: {e}", tag="error")

    # ------------------------------------------------------------------
    # Window close
    # ------------------------------------------------------------------
    def _on_close(self):
        if self._events_dirty:
            answer = messagebox.askyesnocancel(
                "Save Changes?",
                "Event timeline has been modified. Save before closing?")
            if answer is None:  # Cancel
                return
            if answer:  # Yes
                self._save_events_xml()

        if self.is_running:
            if not messagebox.askokcancel(
                "Generation in progress",
                "MSU data generation is still running.\n\n"
                "Cancel the generation and close?",
            ):
                return
            self._cancel_generation()
            # Give the subprocess a moment to die
            if self.worker_thread:
                self.worker_thread.join(timeout=3)

        self.root.destroy()


def main():
    root = tk.Tk()

    # Set window icon if available
    icon_path = PROJECT_ROOT / "converter" / "icon.ico"
    if icon_path.exists():
        root.iconbitmap(str(icon_path))

    MSUGeneratorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
