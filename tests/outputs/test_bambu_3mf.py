"""Tests for Bambu 3MF output generation and shared weld renderer."""

import tempfile
import zipfile
from pathlib import Path

from PIL import Image

from microweldr.core.events import Event, EventType, PathEvent
from microweldr.outputs.bambu_3mf_subscriber import Bambu3mfSubscriber
from microweldr.outputs.weld_renderer import (
    calculate_point_radius,
    calculate_transform,
    compute_bounds,
    render_weld_overview,
    transform_point,
)

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------


def make_test_points():
    """Create a small set of test weld points."""
    return [
        {"x": 0.0, "y": 0.0, "weld_type": "normal", "path_id": "path_1"},
        {"x": 10.0, "y": 0.0, "weld_type": "normal", "path_id": "path_1"},
        {"x": 10.0, "y": 10.0, "weld_type": "frangible", "path_id": "path_2"},
        {"x": 0.0, "y": 10.0, "weld_type": "frangible", "path_id": "path_2"},
    ]


def feed_points_to_subscriber(subscriber, points):
    """Send path/point events to a subscriber, then trigger processing_complete."""
    current_path_id = None
    for point in points:
        path_id = point["path_id"]
        if path_id != current_path_id:
            if current_path_id is not None:
                subscriber.handle_event(
                    PathEvent(action="path_complete", path_id=current_path_id)
                )
            subscriber.handle_event(PathEvent(action="path_start", path_id=path_id))
            current_path_id = path_id

        subscriber.handle_event(
            PathEvent(action="point_added", path_id=path_id, point=point)
        )

    if current_path_id is not None:
        subscriber.handle_event(
            PathEvent(action="path_complete", path_id=current_path_id)
        )

    subscriber.handle_event(
        Event(
            event_type=EventType.OUTPUT_GENERATION,
            timestamp=0.0,
            data={"action": "processing_complete"},
            source="test",
        )
    )


# ===========================================================================
# weld_renderer tests
# ===========================================================================


class TestComputeBounds:
    def test_basic(self):
        pts = [{"x": 1, "y": 2}, {"x": 5, "y": -3}]
        b = compute_bounds(pts)
        assert b["min_x"] == 1
        assert b["max_x"] == 5
        assert b["min_y"] == -3
        assert b["max_y"] == 2

    def test_single_point(self):
        b = compute_bounds([{"x": 7, "y": 7}])
        assert b["min_x"] == b["max_x"] == 7
        assert b["min_y"] == b["max_y"] == 7

    def test_empty(self):
        b = compute_bounds([])
        assert b["min_x"] is None


class TestCalculateTransform:
    def test_identity_on_empty_bounds(self):
        b = {"min_x": None, "min_y": None, "max_x": None, "max_y": None}
        scale, _ox, _oy = calculate_transform(b, 800, 600, 50)
        assert scale == 1.0

    def test_positive_scale(self):
        b = {"min_x": 0, "max_x": 100, "min_y": 0, "max_y": 100}
        scale, _ox, _oy = calculate_transform(b, 800, 600, 50)
        assert scale > 0

    def test_zero_range(self):
        b = {"min_x": 5, "max_x": 5, "min_y": 5, "max_y": 5}
        scale, _, _ = calculate_transform(b, 800, 600, 50)
        assert scale > 0


class TestCalculatePointRadius:
    def test_defaults(self):
        r = calculate_point_radius(10.0)
        assert 1 <= r <= 20

    def test_capped(self):
        r = calculate_point_radius(1000.0, weld_spot_diameter=10.0)
        assert r == 20

    def test_base_floor(self):
        r = calculate_point_radius(0.001, weld_spot_diameter=0.001, base_radius=2.0)
        assert r >= 2


class TestTransformPoint:
    def test_identity(self):
        assert transform_point(5.0, 10.0, 1.0, 0.0, 0.0) == (5, 10)

    def test_with_offset(self):
        assert transform_point(0.0, 0.0, 2.0, 100.0, 50.0) == (100, 50)


class TestRenderWeldOverview:
    def test_returns_image(self):
        img = render_weld_overview(make_test_points(), width=200, height=150)
        assert isinstance(img, Image.Image)
        assert img.size == (200, 150)

    def test_custom_title(self):
        img = render_weld_overview(
            make_test_points(), title="Test Title", show_legend=False
        )
        assert img.size == (800, 600)

    def test_empty_sequence(self):
        img = render_weld_overview([], width=100, height=100)
        assert isinstance(img, Image.Image)

    def test_single_point(self):
        pts = [{"x": 5.0, "y": 5.0, "weld_type": "normal"}]
        img = render_weld_overview(pts, width=100, height=100)
        assert isinstance(img, Image.Image)


# ===========================================================================
# Bambu3mfSubscriber tests
# ===========================================================================


class TestBambu3mfSubscriber:
    def _make_gcode_file(self, tmp_dir: Path) -> Path:
        """Write a minimal gcode file and return its path."""
        gcode_path = tmp_dir / "test.gcode"
        gcode_path.write_text(
            "; Generated by MicroWeldr\nG28\nG1 X100 Y100 F3000\nM84\n",
            encoding="utf-8",
        )
        return gcode_path

    def test_subscriber_creation(self):
        sub = Bambu3mfSubscriber(
            gcode_path=Path("dummy.gcode"),
            output_3mf_path=Path("dummy.gcode.3mf"),
        )
        assert sub.gcode_path == Path("dummy.gcode")
        assert sub.weld_sequence == []

    def test_priority_after_gcode(self):
        sub = Bambu3mfSubscriber(
            gcode_path=Path("d.gcode"), output_3mf_path=Path("d.3mf")
        )
        assert sub.get_priority() > 20  # StreamingGCodeSubscriber is 20

    def test_collects_weld_points(self):
        sub = Bambu3mfSubscriber(
            gcode_path=Path("d.gcode"), output_3mf_path=Path("d.3mf")
        )
        points = make_test_points()

        # Feed points only (no processing_complete)
        for pt in points:
            sub.handle_event(PathEvent(action="path_start", path_id=pt["path_id"]))
            sub.handle_event(
                PathEvent(action="point_added", path_id=pt["path_id"], point=pt)
            )

        assert len(sub.weld_sequence) == len(points)

    def test_generates_valid_3mf(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            gcode_path = self._make_gcode_file(tmp_dir)
            output_3mf = tmp_dir / "output.gcode.3mf"

            sub = Bambu3mfSubscriber(gcode_path=gcode_path, output_3mf_path=output_3mf)
            feed_points_to_subscriber(sub, make_test_points())

            assert output_3mf.exists()
            assert output_3mf.stat().st_size > 0

            # It should be a valid ZIP
            assert zipfile.is_zipfile(output_3mf)

    def test_3mf_contains_gcode(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            gcode_path = self._make_gcode_file(tmp_dir)
            output_3mf = tmp_dir / "output.gcode.3mf"

            sub = Bambu3mfSubscriber(gcode_path=gcode_path, output_3mf_path=output_3mf)
            feed_points_to_subscriber(sub, make_test_points())

            with zipfile.ZipFile(output_3mf, "r") as zf:
                names = zf.namelist()
                assert "Metadata/plate_1.gcode" in names
                assert "Metadata/plate_1.gcode.md5" in names

                gcode_content = zf.read("Metadata/plate_1.gcode").decode("utf-8")
                assert "G28" in gcode_content
                assert "MicroWeldr" in gcode_content

    def test_3mf_contains_thumbnail(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            gcode_path = self._make_gcode_file(tmp_dir)
            output_3mf = tmp_dir / "output.gcode.3mf"

            sub = Bambu3mfSubscriber(gcode_path=gcode_path, output_3mf_path=output_3mf)
            feed_points_to_subscriber(sub, make_test_points())

            with zipfile.ZipFile(output_3mf, "r") as zf:
                assert "Metadata/plate_1.png" in zf.namelist()
                png_data = zf.read("Metadata/plate_1.png")
                assert png_data[:8] == b"\x89PNG\r\n\x1a\n"

    def test_3mf_without_points_no_thumbnail(self):
        """When no weld points are provided, the 3MF should still be valid but have no thumbnail."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            gcode_path = self._make_gcode_file(tmp_dir)
            output_3mf = tmp_dir / "output.gcode.3mf"

            sub = Bambu3mfSubscriber(gcode_path=gcode_path, output_3mf_path=output_3mf)
            # Trigger completion with no points
            sub.handle_event(
                Event(
                    event_type=EventType.OUTPUT_GENERATION,
                    timestamp=0.0,
                    data={"action": "processing_complete"},
                    source="test",
                )
            )

            assert output_3mf.exists()
            with zipfile.ZipFile(output_3mf, "r") as zf:
                assert "Metadata/plate_1.gcode" in zf.namelist()
                assert "Metadata/plate_1.png" not in zf.namelist()

    def test_missing_gcode_file_no_crash(self):
        """If gcode file doesn't exist, subscriber should log error, not crash."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            output_3mf = tmp_dir / "output.gcode.3mf"

            sub = Bambu3mfSubscriber(
                gcode_path=tmp_dir / "nonexistent.gcode",
                output_3mf_path=output_3mf,
            )
            # Should not raise
            sub.handle_event(
                Event(
                    event_type=EventType.OUTPUT_GENERATION,
                    timestamp=0.0,
                    data={"action": "processing_complete"},
                    source="test",
                )
            )
            assert not output_3mf.exists()

    def test_md5_matches_gcode(self):
        """The MD5 in the archive should match the gcode content."""
        import hashlib

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            gcode_path = self._make_gcode_file(tmp_dir)
            output_3mf = tmp_dir / "output.gcode.3mf"

            sub = Bambu3mfSubscriber(gcode_path=gcode_path, output_3mf_path=output_3mf)
            feed_points_to_subscriber(sub, make_test_points())

            with zipfile.ZipFile(output_3mf, "r") as zf:
                gcode_bytes = zf.read("Metadata/plate_1.gcode")
                md5_stored = zf.read("Metadata/plate_1.gcode.md5").decode("utf-8")
                md5_computed = hashlib.md5(gcode_bytes).hexdigest()
                assert md5_stored == md5_computed
