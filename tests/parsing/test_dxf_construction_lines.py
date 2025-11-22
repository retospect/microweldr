"""Tests ensuring DXF construction lines do not generate weld points."""

import tempfile
from pathlib import Path

from microweldr.generators.point_iterator_factory import PointIteratorFactory


class TestDXFConstructionLines:
    """Tests for ignoring construction entities in DXF files."""

    def create_test_dxf(self, content: str) -> Path:
        """Create a temporary DXF file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".dxf", delete=False) as f:
            f.write(content)
            return Path(f.name)

    def test_construction_layer_generates_no_points(self):
        """Entities on construction-like layers must not generate any weld points."""
        dxf_content = """0
SECTION
2
HEADER
9
$INSUNITS
70
4
0
ENDSEC
0
SECTION
2
ENTITIES
0
LINE
8
CONSTRUCTION
10
0.0
20
0.0
11
50.0
21
0.0
0
LWPOLYLINE
8
Guide
100
AcDbEntity
100
AcDbPolyline
90
2
70
0
43
0.0
10
0.0
20
0.0
42
0.0
10
10.0
20
0.0
42
0.0
0
ENDSEC
0
EOF
"""

        dxf_path = self.create_test_dxf(dxf_content)
        try:
            iterator = PointIteratorFactory.create_iterator(str(dxf_path))
            points = list(iterator.iterate_points(dxf_path))

            assert (
                len(points) == 0
            ), f"Expected no points from construction layers, got {len(points)}"
        finally:
            dxf_path.unlink()
