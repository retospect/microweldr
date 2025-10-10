"""Unit tests for SVG parser."""

import tempfile
from pathlib import Path

import pytest

from svg_welder.core.models import WeldPoint
from svg_welder.core.svg_parser import SVGParseError, SVGParser


class TestSVGParser:
    """Test cases for SVGParser class."""

    def create_temp_svg(self, content: str) -> Path:
        """Create a temporary SVG file with given content."""
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.svg', delete=False)
        temp_file.write(content)
        temp_file.close()
        return Path(temp_file.name)

    def test_parse_simple_line(self):
        """Test parsing a simple line element."""
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <line id="line1" x1="10" y1="20" x2="30" y2="40" stroke="black"/>
</svg>'''
        
        svg_path = self.create_temp_svg(svg_content)
        try:
            parser = SVGParser(dot_spacing=5.0)
            weld_paths = parser.parse_file(str(svg_path))
            
            assert len(weld_paths) == 1
            path = weld_paths[0]
            assert path.svg_id == 'line1'
            assert path.weld_type == 'normal'
            assert len(path.points) >= 2  # Should have interpolated points
        finally:
            svg_path.unlink()

    def test_parse_circle(self):
        """Test parsing a circle element."""
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <circle id="circle1" cx="50" cy="50" r="20" stroke="blue"/>
</svg>'''
        
        svg_path = self.create_temp_svg(svg_content)
        try:
            parser = SVGParser(dot_spacing=2.0)
            weld_paths = parser.parse_file(str(svg_path))
            
            assert len(weld_paths) == 1
            path = weld_paths[0]
            assert path.svg_id == 'circle1'
            assert path.weld_type == 'light'  # Blue color
            assert len(path.points) > 8  # Should have multiple points around circle
        finally:
            svg_path.unlink()

    def test_parse_rectangle(self):
        """Test parsing a rectangle element."""
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <rect id="rect1" x="10" y="10" width="30" height="20" stroke="black"/>
</svg>'''
        
        svg_path = self.create_temp_svg(svg_content)
        try:
            parser = SVGParser(dot_spacing=3.0)
            weld_paths = parser.parse_file(str(svg_path))
            
            assert len(weld_paths) == 1
            path = weld_paths[0]
            assert path.svg_id == 'rect1'
            assert path.weld_type == 'normal'
            assert len(path.points) >= 5  # Rectangle should have at least 5 points (closed)
        finally:
            svg_path.unlink()

    def test_parse_stop_point_with_message(self):
        """Test parsing a stop point with custom message."""
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <circle id="stop1" cx="50" cy="50" r="3" fill="red" data-message="Check quality"/>
</svg>'''
        
        svg_path = self.create_temp_svg(svg_content)
        try:
            parser = SVGParser()
            weld_paths = parser.parse_file(str(svg_path))
            
            assert len(weld_paths) == 1
            path = weld_paths[0]
            assert path.svg_id == 'stop1'
            assert path.weld_type == 'stop'
            assert path.pause_message == 'Check quality'
        finally:
            svg_path.unlink()

    def test_parse_path_element(self):
        """Test parsing a path element."""
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <path id="path1" d="M 10 10 L 20 20 L 30 10" stroke="black"/>
</svg>'''
        
        svg_path = self.create_temp_svg(svg_content)
        try:
            parser = SVGParser(dot_spacing=2.0)
            weld_paths = parser.parse_file(str(svg_path))
            
            assert len(weld_paths) == 1
            path = weld_paths[0]
            assert path.svg_id == 'path1'
            assert path.weld_type == 'normal'
            assert len(path.points) >= 3  # Should have interpolated points
        finally:
            svg_path.unlink()

    def test_element_sorting_by_id(self):
        """Test that elements are sorted by ID."""
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <line id="line3" x1="30" y1="30" x2="40" y2="40" stroke="black"/>
  <line id="line1" x1="10" y1="10" x2="20" y2="20" stroke="black"/>
  <line id="line2" x1="20" y1="20" x2="30" y2="30" stroke="black"/>
</svg>'''
        
        svg_path = self.create_temp_svg(svg_content)
        try:
            parser = SVGParser()
            weld_paths = parser.parse_file(str(svg_path))
            
            assert len(weld_paths) == 3
            assert weld_paths[0].svg_id == 'line1'
            assert weld_paths[1].svg_id == 'line2'
            assert weld_paths[2].svg_id == 'line3'
        finally:
            svg_path.unlink()

    def test_color_detection_variations(self):
        """Test different ways of specifying colors."""
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <line id="red1" x1="0" y1="0" x2="10" y2="10" stroke="red"/>
  <line id="red2" x1="0" y1="0" x2="10" y2="10" stroke="#ff0000"/>
  <line id="blue1" x1="0" y1="0" x2="10" y2="10" stroke="blue"/>
  <line id="blue2" x1="0" y1="0" x2="10" y2="10" stroke="#0000ff"/>
  <line id="black1" x1="0" y1="0" x2="10" y2="10" stroke="black"/>
</svg>'''
        
        svg_path = self.create_temp_svg(svg_content)
        try:
            parser = SVGParser()
            weld_paths = parser.parse_file(str(svg_path))
            
            # Find paths by ID
            paths_by_id = {path.svg_id: path for path in weld_paths}
            
            assert paths_by_id['red1'].weld_type == 'stop'
            assert paths_by_id['red2'].weld_type == 'stop'
            assert paths_by_id['blue1'].weld_type == 'light'
            assert paths_by_id['blue2'].weld_type == 'light'
            assert paths_by_id['black1'].weld_type == 'normal'
        finally:
            svg_path.unlink()

    def test_invalid_svg_file_raises_error(self):
        """Test that invalid SVG file raises SVGParseError."""
        invalid_content = "This is not valid XML"
        
        svg_path = self.create_temp_svg(invalid_content)
        try:
            parser = SVGParser()
            
            with pytest.raises(SVGParseError, match="Invalid SVG file"):
                parser.parse_file(str(svg_path))
        finally:
            svg_path.unlink()

    def test_missing_file_raises_error(self):
        """Test that missing file raises SVGParseError."""
        parser = SVGParser()
        
        with pytest.raises(SVGParseError, match="SVG file .* not found"):
            parser.parse_file("nonexistent_file.svg")

    def test_interpolation_with_different_spacing(self):
        """Test point interpolation with different dot spacing."""
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <line id="line1" x1="0" y1="0" x2="10" y2="0" stroke="black"/>
</svg>'''
        
        svg_path = self.create_temp_svg(svg_content)
        try:
            # Test with large spacing
            parser_large = SVGParser(dot_spacing=5.0)
            paths_large = parser_large.parse_file(str(svg_path))
            
            # Test with small spacing
            parser_small = SVGParser(dot_spacing=1.0)
            paths_small = parser_small.parse_file(str(svg_path))
            
            # Small spacing should produce more points
            assert len(paths_small[0].points) > len(paths_large[0].points)
        finally:
            svg_path.unlink()

    def test_empty_svg_returns_empty_list(self):
        """Test that SVG with no drawable elements returns empty list."""
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <text x="10" y="10">No drawable elements</text>
</svg>'''
        
        svg_path = self.create_temp_svg(svg_content)
        try:
            parser = SVGParser()
            weld_paths = parser.parse_file(str(svg_path))
            
            assert len(weld_paths) == 0
        finally:
            svg_path.unlink()
