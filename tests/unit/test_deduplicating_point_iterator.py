"""Unit tests for DeduplicatingPointIterator."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from typing import Iterator, Dict, Any

from microweldr.generators.deduplicating_point_iterator import (
    DeduplicatingPointIterator,
    WeldTypeEnum,
    iterate_points_from_file_deduplicated,
)


class TestWeldTypeEnum:
    """Test the WeldTypeEnum functionality."""

    def test_enum_values(self):
        """Test that enum values are correct integers."""
        assert WeldTypeEnum.NORMAL == 0
        assert WeldTypeEnum.FRANGIBLE == 1
        assert WeldTypeEnum.STOP == 2
        assert WeldTypeEnum.PIPETTE == 3

    def test_from_string_normal(self):
        """Test conversion from normal weld type string."""
        assert WeldTypeEnum.from_string("normal") == WeldTypeEnum.NORMAL
        assert WeldTypeEnum.from_string("NORMAL") == WeldTypeEnum.NORMAL
        assert WeldTypeEnum.from_string("Normal") == WeldTypeEnum.NORMAL

    def test_from_string_frangible(self):
        """Test conversion from frangible weld type string."""
        assert WeldTypeEnum.from_string("frangible") == WeldTypeEnum.FRANGIBLE
        assert WeldTypeEnum.from_string("FRANGIBLE") == WeldTypeEnum.FRANGIBLE
        assert WeldTypeEnum.from_string("Frangible") == WeldTypeEnum.FRANGIBLE

    def test_from_string_stop(self):
        """Test conversion from stop weld type string."""
        assert WeldTypeEnum.from_string("stop") == WeldTypeEnum.STOP
        assert WeldTypeEnum.from_string("STOP") == WeldTypeEnum.STOP

    def test_from_string_pipette(self):
        """Test conversion from pipette weld type string."""
        assert WeldTypeEnum.from_string("pipette") == WeldTypeEnum.PIPETTE
        assert WeldTypeEnum.from_string("PIPETTE") == WeldTypeEnum.PIPETTE

    def test_from_string_unknown_defaults_to_normal(self):
        """Test that unknown weld types default to normal."""
        assert WeldTypeEnum.from_string("unknown") == WeldTypeEnum.NORMAL
        assert WeldTypeEnum.from_string("") == WeldTypeEnum.NORMAL
        assert WeldTypeEnum.from_string("weird_type") == WeldTypeEnum.NORMAL

    def test_to_string(self):
        """Test conversion back to string."""
        assert WeldTypeEnum.NORMAL.to_string() == "normal"
        assert WeldTypeEnum.FRANGIBLE.to_string() == "frangible"
        assert WeldTypeEnum.STOP.to_string() == "stop"
        assert WeldTypeEnum.PIPETTE.to_string() == "pipette"


class TestDeduplicatingPointIterator:
    """Test the DeduplicatingPointIterator functionality."""

    def test_init_default_precision(self):
        """Test initialization with default precision."""
        iterator = DeduplicatingPointIterator()
        assert iterator.precision_mm == 0.1
        assert len(iterator.seen_coordinates) == 0

    def test_init_custom_precision(self):
        """Test initialization with custom precision."""
        iterator = DeduplicatingPointIterator(precision_mm=0.05)
        assert iterator.precision_mm == 0.05
        assert len(iterator.seen_coordinates) == 0

    def test_round_coordinate_default_precision(self):
        """Test coordinate rounding with default 0.1mm precision."""
        iterator = DeduplicatingPointIterator()

        # Test exact multiples
        assert iterator._round_coordinate(1.0) == 1.0
        assert iterator._round_coordinate(1.1) == 1.1

        # Test rounding down
        assert iterator._round_coordinate(1.04) == 1.0
        assert iterator._round_coordinate(1.14) == 1.1

        # Test rounding up (Python uses banker's rounding - .5 rounds to nearest even)
        assert iterator._round_coordinate(1.06) == 1.1
        assert abs(iterator._round_coordinate(1.16) - 1.2) < 1e-10

        # Test negative values
        assert iterator._round_coordinate(-1.04) == -1.0
        assert iterator._round_coordinate(-1.06) == -1.1

    def test_round_coordinate_custom_precision(self):
        """Test coordinate rounding with custom precision."""
        iterator = DeduplicatingPointIterator(precision_mm=0.05)

        assert iterator._round_coordinate(1.02) == 1.0
        assert iterator._round_coordinate(1.03) == 1.05
        assert iterator._round_coordinate(1.07) == 1.05
        assert iterator._round_coordinate(1.08) == 1.1

    def test_get_coordinate_key(self):
        """Test coordinate key generation."""
        iterator = DeduplicatingPointIterator()

        # Test normal weld - use values that round cleanly
        key = iterator._get_coordinate_key(1.2, 2.6, "normal")
        assert abs(key[0] - 1.2) < 1e-10
        assert abs(key[1] - 2.6) < 1e-10
        assert key[2] == WeldTypeEnum.NORMAL

        # Test frangible weld
        key = iterator._get_coordinate_key(1.2, 2.6, "frangible")
        assert abs(key[0] - 1.2) < 1e-10
        assert abs(key[1] - 2.6) < 1e-10
        assert key[2] == WeldTypeEnum.FRANGIBLE

        # Test same coordinates, different weld types should have different keys
        key1 = iterator._get_coordinate_key(1.0, 2.0, "normal")
        key2 = iterator._get_coordinate_key(1.0, 2.0, "frangible")
        assert key1 != key2
        assert key1[0] == key2[0]  # Same x
        assert key1[1] == key2[1]  # Same y
        assert key1[2] != key2[2]  # Different weld type

    @patch("microweldr.generators.deduplicating_point_iterator.PointIteratorFactory")
    def test_iterate_points_no_duplicates(self, mock_factory):
        """Test iteration with no duplicate points."""
        # Mock the underlying iterator
        mock_iterator = Mock()
        mock_iterator.iterate_points.return_value = [
            {"x": 1.0, "y": 2.0, "weld_type": "normal", "path_id": "path1"},
            {"x": 3.0, "y": 4.0, "weld_type": "frangible", "path_id": "path2"},
            {"x": 5.0, "y": 6.0, "weld_type": "normal", "path_id": "path3"},
        ]
        mock_factory.create_iterator.return_value = mock_iterator

        iterator = DeduplicatingPointIterator()
        file_path = Path("test.dxf")

        points = list(iterator.iterate_points(file_path))

        assert len(points) == 3
        assert points[0] == {
            "x": 1.0,
            "y": 2.0,
            "weld_type": "normal",
            "path_id": "path1",
        }
        assert points[1] == {
            "x": 3.0,
            "y": 4.0,
            "weld_type": "frangible",
            "path_id": "path2",
        }
        assert points[2] == {
            "x": 5.0,
            "y": 6.0,
            "weld_type": "normal",
            "path_id": "path3",
        }

    @patch("microweldr.generators.deduplicating_point_iterator.PointIteratorFactory")
    def test_iterate_points_with_exact_duplicates(self, mock_factory):
        """Test iteration with exact duplicate points."""
        # Mock the underlying iterator with duplicates
        mock_iterator = Mock()
        mock_iterator.iterate_points.return_value = [
            {"x": 1.0, "y": 2.0, "weld_type": "normal", "path_id": "path1"},
            {
                "x": 1.0,
                "y": 2.0,
                "weld_type": "normal",
                "path_id": "path2",
            },  # Exact duplicate
            {"x": 3.0, "y": 4.0, "weld_type": "frangible", "path_id": "path3"},
        ]
        mock_factory.create_iterator.return_value = mock_iterator

        iterator = DeduplicatingPointIterator()
        file_path = Path("test.dxf")

        points = list(iterator.iterate_points(file_path))

        # Should filter out the duplicate
        assert len(points) == 2
        assert points[0] == {
            "x": 1.0,
            "y": 2.0,
            "weld_type": "normal",
            "path_id": "path1",
        }
        assert points[1] == {
            "x": 3.0,
            "y": 4.0,
            "weld_type": "frangible",
            "path_id": "path3",
        }

    @patch("microweldr.generators.deduplicating_point_iterator.PointIteratorFactory")
    def test_iterate_points_with_rounded_duplicates(self, mock_factory):
        """Test iteration with points that become duplicates after rounding."""
        # Mock the underlying iterator with near-duplicates
        mock_iterator = Mock()
        mock_iterator.iterate_points.return_value = [
            {"x": 1.00, "y": 2.00, "weld_type": "normal", "path_id": "path1"},
            {
                "x": 1.04,
                "y": 2.03,
                "weld_type": "normal",
                "path_id": "path2",
            },  # Rounds to same
            {"x": 3.0, "y": 4.0, "weld_type": "frangible", "path_id": "path3"},
        ]
        mock_factory.create_iterator.return_value = mock_iterator

        iterator = DeduplicatingPointIterator()
        file_path = Path("test.dxf")

        points = list(iterator.iterate_points(file_path))

        # Should filter out the rounded duplicate
        assert len(points) == 2
        assert points[0] == {
            "x": 1.00,
            "y": 2.00,
            "weld_type": "normal",
            "path_id": "path1",
        }
        assert points[1] == {
            "x": 3.0,
            "y": 4.0,
            "weld_type": "frangible",
            "path_id": "path3",
        }

    @patch("microweldr.generators.deduplicating_point_iterator.PointIteratorFactory")
    def test_iterate_points_same_coords_different_weld_types(self, mock_factory):
        """Test that same coordinates with different weld types are NOT filtered."""
        # Mock the underlying iterator
        mock_iterator = Mock()
        mock_iterator.iterate_points.return_value = [
            {"x": 1.0, "y": 2.0, "weld_type": "normal", "path_id": "path1"},
            {
                "x": 1.0,
                "y": 2.0,
                "weld_type": "frangible",
                "path_id": "path2",
            },  # Same coords, different type
            {"x": 3.0, "y": 4.0, "weld_type": "normal", "path_id": "path3"},
        ]
        mock_factory.create_iterator.return_value = mock_iterator

        iterator = DeduplicatingPointIterator()
        file_path = Path("test.dxf")

        points = list(iterator.iterate_points(file_path))

        # Should NOT filter - different weld types allowed at same location
        assert len(points) == 3
        assert points[0]["weld_type"] == "normal"
        assert points[1]["weld_type"] == "frangible"
        assert points[2]["weld_type"] == "normal"

    @patch("microweldr.generators.deduplicating_point_iterator.PointIteratorFactory")
    def test_iterate_points_clears_seen_coordinates(self, mock_factory):
        """Test that seen coordinates are cleared for each new file."""
        # Mock the underlying iterator
        mock_iterator = Mock()
        mock_iterator.iterate_points.return_value = [
            {"x": 1.0, "y": 2.0, "weld_type": "normal", "path_id": "path1"},
        ]
        mock_factory.create_iterator.return_value = mock_iterator

        iterator = DeduplicatingPointIterator()
        file_path1 = Path("test1.dxf")
        file_path2 = Path("test2.dxf")

        # Process first file
        points1 = list(iterator.iterate_points(file_path1))
        assert len(points1) == 1
        assert len(iterator.seen_coordinates) == 1

        # Process second file - should clear seen coordinates
        points2 = list(iterator.iterate_points(file_path2))
        assert len(points2) == 1
        # Should have been cleared and repopulated
        assert len(iterator.seen_coordinates) == 1

    @patch("microweldr.generators.deduplicating_point_iterator.PointIteratorFactory")
    def test_iterate_points_complex_scenario(self, mock_factory):
        """Test a complex scenario with multiple types of duplicates."""
        # Mock the underlying iterator with a complex mix
        mock_iterator = Mock()
        mock_iterator.iterate_points.return_value = [
            {"x": 1.0, "y": 2.0, "weld_type": "normal", "path_id": "path1"},
            {
                "x": 1.04,
                "y": 2.03,
                "weld_type": "normal",
                "path_id": "path2",
            },  # Rounds to duplicate
            {
                "x": 1.0,
                "y": 2.0,
                "weld_type": "frangible",
                "path_id": "path3",
            },  # Same coords, diff type
            {"x": 3.0, "y": 4.0, "weld_type": "normal", "path_id": "path4"},
            {
                "x": 3.0,
                "y": 4.0,
                "weld_type": "normal",
                "path_id": "path5",
            },  # Exact duplicate
            {"x": 5.0, "y": 6.0, "weld_type": "stop", "path_id": "path6"},
        ]
        mock_factory.create_iterator.return_value = mock_iterator

        iterator = DeduplicatingPointIterator()
        file_path = Path("test.dxf")

        points = list(iterator.iterate_points(file_path))

        # Should have: original normal, frangible at same location, one normal at (3,4), stop
        assert len(points) == 4

        # Check the points we expect
        weld_types = [p["weld_type"] for p in points]
        assert "normal" in weld_types
        assert "frangible" in weld_types
        assert "stop" in weld_types

        # Check coordinates
        coords = [(p["x"], p["y"]) for p in points]
        assert (1.0, 2.0) in coords  # Should appear twice (normal + frangible)
        assert (3.0, 4.0) in coords  # Should appear once (duplicate filtered)
        assert (5.0, 6.0) in coords  # Should appear once


class TestIteratePointsFromFileDeduplicated:
    """Test the convenience function."""

    @patch(
        "microweldr.generators.deduplicating_point_iterator.DeduplicatingPointIterator"
    )
    def test_iterate_points_from_file_deduplicated(self, mock_dedup_class):
        """Test the convenience function calls the iterator correctly."""
        # Mock the deduplicating iterator
        mock_iterator = Mock()
        mock_iterator.iterate_points.return_value = [
            {"x": 1.0, "y": 2.0, "weld_type": "normal", "path_id": "path1"},
        ]
        mock_dedup_class.return_value = mock_iterator

        file_path = Path("test.dxf")
        config = Mock()

        points = list(iterate_points_from_file_deduplicated(file_path, config=config))

        # Should create iterator with default precision (0.1)
        mock_dedup_class.assert_called_once_with(precision_mm=0.1)

        # Should call iterate_points with correct arguments
        mock_iterator.iterate_points.assert_called_once_with(file_path, config=config)

        # Should return the points
        assert len(points) == 1
        assert points[0]["x"] == 1.0


if __name__ == "__main__":
    pytest.main([__file__])
