#!/usr/bin/env python3
"""
segments.py - Per-chapter quality settings for SDLA MSU converter

Allows different chapters (or chapter groups) to use different dithering,
palette count, and max tile settings. Provides lookup by chapter name,
split/delete operations for the GUI, and JSON serialization.
"""

import json
from dataclasses import dataclass, asdict
from typing import List, Optional


@dataclass
class Segment:
    """Quality settings for one time range (used for chapter-level overrides)."""
    start_time: float       # seconds, inclusive
    end_time: float         # seconds, exclusive
    dither_method: str      # 'none', 'floyd-steinberg', 'ordered'
    num_palettes: int       # 1-8
    max_tiles: int          # 1-384
    grayscale: bool = False
    shared_palette: bool = False


class SegmentList:
    """Manages an ordered list of non-overlapping, contiguous segments."""

    MIN_SEGMENT_DURATION = 0.1  # seconds

    def __init__(self, segments: Optional[List[Segment]] = None):
        if segments:
            self.segments = list(segments)
        else:
            self.segments = []

    @classmethod
    def create_default(cls, duration: float, dither_method: str = 'floyd-steinberg',
                       num_palettes: int = 8, max_tiles: int = 384,
                       grayscale: bool = False,
                       shared_palette: bool = False) -> 'SegmentList':
        """Create a SegmentList with one segment covering the full duration."""
        seg = Segment(
            start_time=0.0,
            end_time=max(duration, 0.1),
            dither_method=dither_method,
            num_palettes=num_palettes,
            max_tiles=max_tiles,
            grayscale=grayscale,
            shared_palette=shared_palette,
        )
        return cls([seg])

    def settings_for_time(self, t: float) -> Optional[Segment]:
        """Return the segment containing time t, or None if out of range."""
        for seg in self.segments:
            if seg.start_time <= t < seg.end_time:
                return seg
        # Edge case: t exactly equals the last segment's end_time
        if self.segments and t >= self.segments[-1].end_time:
            return self.segments[-1]
        return None

    def settings_for_frame(self, frame_index: int, fps: float,
                           start_offset: float = 0.0) -> Optional[Segment]:
        """Return the segment for a given frame index.

        Args:
            frame_index: 0-based frame number
            fps: frames per second
            start_offset: video start time offset
        """
        t = start_offset + frame_index / fps
        return self.settings_for_time(t)

    def segment_index_for_time(self, t: float) -> int:
        """Return the index of the segment containing time t."""
        for i, seg in enumerate(self.segments):
            if seg.start_time <= t < seg.end_time:
                return i
        # Edge case: at or past end
        if self.segments:
            return len(self.segments) - 1
        return 0

    def split_at(self, t: float) -> Optional[int]:
        """Split the segment containing time t into two halves with identical settings.

        Returns the index of the new (right) segment, or None if the split
        would create a segment shorter than MIN_SEGMENT_DURATION.
        """
        idx = self.segment_index_for_time(t)
        seg = self.segments[idx]

        # Check minimum duration on both halves
        left_dur = t - seg.start_time
        right_dur = seg.end_time - t
        if left_dur < self.MIN_SEGMENT_DURATION or right_dur < self.MIN_SEGMENT_DURATION:
            return None

        # Create two segments with the same settings
        left = Segment(
            start_time=seg.start_time,
            end_time=t,
            dither_method=seg.dither_method,
            num_palettes=seg.num_palettes,
            max_tiles=seg.max_tiles,
            grayscale=seg.grayscale,
            shared_palette=seg.shared_palette,
        )
        right = Segment(
            start_time=t,
            end_time=seg.end_time,
            dither_method=seg.dither_method,
            num_palettes=seg.num_palettes,
            max_tiles=seg.max_tiles,
            grayscale=seg.grayscale,
            shared_palette=seg.shared_palette,
        )

        self.segments[idx] = left
        self.segments.insert(idx + 1, right)
        return idx + 1

    def delete_segment(self, idx: int) -> bool:
        """Delete segment at idx by merging it into a neighbor.

        Merges into left neighbor if possible, otherwise right neighbor.
        Returns False if only one segment remains (cannot delete).
        """
        if len(self.segments) <= 1:
            return False
        if idx < 0 or idx >= len(self.segments):
            return False

        removed = self.segments.pop(idx)

        if idx > 0:
            # Merge into left neighbor
            self.segments[idx - 1].end_time = removed.end_time
        else:
            # No left neighbor -- merge into new first segment (expand its start)
            self.segments[0].start_time = removed.start_time

        return True

    def update_duration(self, new_duration: float):
        """Clamp or extend segments when duration changes."""
        if not self.segments:
            return

        new_duration = max(new_duration, 0.1)

        # Remove segments that start beyond the new duration
        self.segments = [s for s in self.segments if s.start_time < new_duration]

        if not self.segments:
            self.segments = [Segment(
                start_time=0.0, end_time=new_duration,
                dither_method='floyd-steinberg',
                num_palettes=8, max_tiles=384,
            )]
            return

        # Clamp the last segment's end_time
        self.segments[-1].end_time = new_duration

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps([asdict(s) for s in self.segments], indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'SegmentList':
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        for d in data:
            d.setdefault('grayscale', False)
            d.setdefault('shared_palette', False)
        segments = [Segment(**d) for d in data]
        return cls(segments)

    @classmethod
    def from_json_file(cls, path: str) -> 'SegmentList':
        """Load from a JSON file."""
        with open(path, 'r') as f:
            return cls.from_json(f.read())

    def __len__(self):
        return len(self.segments)
