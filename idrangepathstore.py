#!/bin/python3
from pathlib import Path
from typing import Optional, Tuple
import bisect
import json

# Written by Claude.ai Opus 4 and then modified by hand

class IDRangePathStore:
    """Store Paths keyed by SuttaCentral IDs which may be segment ranges."""
    
    def __init__(self):
        # Dictionary mapping appid to list of (lower_segment, upper_segment, path) tuples
        # Kept sorted by lower_segment for efficient binary search
        self._ranges: dict[str, list[tuple[tuple[int, ...], tuple[int, ...], Path]]] = {}
        self._plain: dict[str, Path] = {}
    
    def to_json(self, paths_relative_to: Path) -> str:
        return json.dumps({
            "ranges": {
                appid: [
                    [
                        self._segment_to_string(lower),
                        self._segment_to_string(upper),
                        str(path.relative_to(paths_relative_to))
                    ]
                    for lower, upper, path in ranges
                ]
                for appid, ranges in self._ranges.items()
            },
            "plain": {
                id_str: str(path.relative_to(paths_relative_to))
                for id_str, path in self._plain.items()
            }
        })

    def load_data_from_json(self, json_data: str, paths_relative_to: Path) -> None:
        """WARNING: Overwrites existing data and does no validation!"""
        data = json.loads(json_data)
        self._ranges = {
            appid: [
                (self._string_to_segment(lower), self._string_to_segment(upper), paths_relative_to.joinpath(path))
                for lower, upper, path in ranges
            ]
            for appid, ranges in data["ranges"].items()
        }
        self._plain = {
            id_str: paths_relative_to.joinpath(path)
            for id_str, path in data["plain"].items()
        }
    
    def add(self, lower_id: str, upper_id: str, path: Path) -> None:
        """
        Add a new range with associated path.
        
        Args:
            lower_id: Lower bound ID (e.g., "app:1.2.3")
            upper_id: Upper bound ID (e.g., "app:2.0.0")
            path: Path object to associate with this range
            
        Raises:
            ValueError: If range is invalid or overlaps with existing range
        """
        if ":" not in lower_id or lower_id == upper_id or not upper_id:
            self._plain[lower_id] = path
            return
        lower_appid, lower_segment = self._parse_id(lower_id)
        upper_appid, upper_segment = self._parse_id(upper_id)
        
        if lower_appid != upper_appid:
            raise ValueError(f"App IDs must match: {lower_appid} != {upper_appid}")
        
        if not self._segment_less_than_or_equal(lower_segment, upper_segment):
            raise ValueError(f"Lower segment must be <= upper segment: {lower_id} > {upper_id}")
        
        # Check for overlaps with existing ranges
        if lower_appid in self._ranges:
            ranges = self._ranges[lower_appid]
            
            # Find where this range would be inserted
            insert_pos = bisect.bisect_left(ranges, (lower_segment, upper_segment, None))
            
            # Check the range before the insertion point (if exists)
            if insert_pos > 0:
                prev_lower, prev_upper, _ = ranges[insert_pos - 1]
                if self._segment_less_than_or_equal(prev_lower, upper_segment) and \
                   self._segment_less_than_or_equal(lower_segment, prev_upper):
                    raise ValueError(
                        f"Range {lower_id}-{upper_id} overlaps with existing range "
                        f"{lower_appid}:{self._segment_to_string(prev_lower)}-"
                        f"{lower_appid}:{self._segment_to_string(prev_upper)}"
                    )
            
            # Check the range at the insertion point (if exists)
            if insert_pos < len(ranges):
                next_lower, next_upper, _ = ranges[insert_pos]
                if self._segment_less_than_or_equal(lower_segment, next_upper) and \
                   self._segment_less_than_or_equal(next_lower, upper_segment):
                    raise ValueError(
                        f"Range {lower_id}-{upper_id} overlaps with existing range "
                        f"{lower_appid}:{self._segment_to_string(next_lower)}-"
                        f"{lower_appid}:{self._segment_to_string(next_upper)}"
                    )
        
        # Add the new range, keeping the list sorted
        if lower_appid not in self._ranges:
            self._ranges[lower_appid] = []
        
        # Insert in sorted order by lower_segment
        bisect.insort(self._ranges[lower_appid], (lower_segment, upper_segment, path))
    
    def get(self, key_id: str) -> Optional[Path]:
        """
        Get the Path associated with the range containing the given ID.
        
        Args:
            key_id: ID to search for (e.g., "app:1.5.0")
            
        Returns:
            Path object if ID is within a stored range, None otherwise
        """
        if key_id in self._plain:
            return self._plain[key_id]
        if ':' not in key_id:
            return None
        appid, segment = self._parse_id(key_id)
        
        if appid not in self._ranges:
            return None
        
        # Binary search for the range that might contain this segment
        ranges = self._ranges[appid]
        
        # Find the rightmost range whose lower bound is <= segment
        left, right = 0, len(ranges)
        while left < right:
            mid = (left + right) // 2
            if self._segment_less_than_or_equal(ranges[mid][0], segment):
                left = mid + 1
            else:
                right = mid
        
        # Check the found range and the one before it
        for i in range(max(0, left - 1), min(len(ranges), left + 1)):
            lower, upper, path = ranges[i]
            if (self._segment_less_than_or_equal(lower, segment) and 
                self._segment_less_than_or_equal(segment, upper)):
                return path
        
        return None
    
    def _parse_id(self, id_str: str) -> Tuple[str, Tuple[int, ...]]:
        """Parse an ID into appid and segment tuple."""
        try:
            appid, segment_str = id_str.split(':', 1)
            segment_parts = self._string_to_segment(segment_str)
            return appid, segment_parts
        except (ValueError, AttributeError):
            raise ValueError(f"Invalid ID format: {id_str}")
    
    def _segment_less_than_or_equal(self, v1: Tuple[int, ...], v2: Tuple[int, ...]) -> bool:
        """Compare two segment tuples."""
        # Pad shorter segment with zeros for comparison
        max_len = max(len(v1), len(v2))
        v1_padded = v1 + (0,) * (max_len - len(v1))
        v2_padded = v2 + (0,) * (max_len - len(v2))
        return v1_padded <= v2_padded
    
    def _segment_to_string(self, segment: Tuple[int, ...]) -> str:
        """Convert segment tuple back to string."""
        return '.'.join(str(v) for v in segment)
    
    def _string_to_segment(self, segment_str: str) -> Tuple[int, ...]:
        """Convert string to segment tuple."""
        return tuple(int(part) for part in segment_str.split('.'))


# Example usage and tests by Gemini 2.5 Pro
if __name__ == "__main__":
    store = IDRangePathStore()
    p1 = Path("/files/np19/v2.5-v2.12")
    p2 = Path("/files/pc4/v1.1.7-v2.1.18")
    p3 = Path("/files/foo/v1.50-v3.1")
    p4 = Path("/files/bar/v1.0-v1.0")
    store.add("pli-tv-bu-vb-np19:2.5", "pli-tv-bu-vb-np19:2.12", p1)
    store.add("pli-tv-bu-vb-pc4:1.1.7", "pli-tv-bu-vb-pc4:2.1.18", p2)
    store.add("foo:1.50", "foo:3.1", p3)
    store.add("bar:1.0", "bar:1.0", p4) # A range with a single segment
    print("\n--- Testing successful gets ---")
    assert store.get("pli-tv-bu-vb-np19:2.7") == p1
    print('✅ Get "pli-tv-bu-vb-np19:2.7" -> OK')
    assert store.get("pli-tv-bu-vb-np19:2.5") == p1
    print('✅ Get "pli-tv-bu-vb-np19:2.5" (lower bound) -> OK')
    assert store.get("pli-tv-bu-vb-np19:2.12") == p1
    print('✅ Get "pli-tv-bu-vb-np19:2.12" (upper bound) -> OK')
    assert store.get("foo:2.24") == p3
    print('✅ Get "foo:2.24" -> OK')
    assert store.get("foo:3.1") == p3
    print('✅ Get "foo:3.1" (upper bound of 2-part segment) -> OK')
    assert store.get("bar:1.0") == p4
    print('✅ Get "bar:1.0" (single-segment range) -> OK')

    print("\n--- Testing unsuccessful gets ---")
    assert store.get("foo:4.0") is None
    print('✅ Get "foo:4.0" (out of range high) -> OK')
    assert store.get("foo:1.49") is None
    print('✅ Get "foo:1.49" (out of range low) -> OK')
    assert store.get("nonexistent-app:1.0") is None
    print('✅ Get "nonexistent-app:1.0" -> OK')

    print("\n--- Testing overlap detection ---")
    test_cases = [
        ("foo:2.0", "foo:2.50"),      # Case 1: New range is fully within an existing range
        ("foo:0.1", "foo:1.51"),      # Case 2: New range overlaps the start of an existing range
        ("foo:3.0", "foo:4.0"),       # Case 3: New range overlaps the end of an existing range
        ("foo:0.1", "foo:4.0"),       # Case 4: New range fully contains an existing range
    ]
    for lower, upper in test_cases:
        try:
            store.add(lower, upper, Path("/overlap"))
            print(f"❌ FAIL: Overlap for {lower}-{upper} was not detected.")
        except ValueError as e:
            print(f"✅ PASS: Caught expected overlap for {lower}-{upper}.")
            # print(f"   (Error: {e})")
    
    print("\nAll tests completed.")
