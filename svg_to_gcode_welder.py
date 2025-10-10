#!/usr/bin/env python3
"""
SVG to G-code Welder
Converts SVG files to Prusa Core One G-code for plastic welding.
"""

import argparse
import sys
import os
from pathlib import Path
import toml
import xml.etree.ElementTree as ET
import re
import math
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass

# Validation libraries
try:
    from lxml import etree
    from gcodeparser import GcodeParser
    import pygcode
    VALIDATION_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Validation libraries not available: {e}")
    print("Install with: pip install lxml gcodeparser pygcode xmlschema")
    VALIDATION_AVAILABLE = False


@dataclass
class WeldPoint:
    """Represents a single weld point."""
    x: float
    y: float
    weld_type: str  # 'normal', 'light', or 'stop'


@dataclass
class WeldPath:
    """Represents a path with multiple weld points."""
    points: List[WeldPoint]
    weld_type: str
    svg_id: str
    pause_message: Optional[str] = None  # Custom message for stop points


class SVGToGCodeWelder:
    """Main class for converting SVG to G-code."""
    
    def __init__(self, config_path: str):
        """Initialize with configuration file."""
        self.config = self.load_config(config_path)
        self.weld_paths: List[WeldPath] = []
        
    def load_config(self, config_path: str) -> dict:
        """Load configuration from TOML file."""
        try:
            with open(config_path, 'r') as f:
                return toml.load(f)
        except FileNotFoundError:
            print(f"Error: Configuration file '{config_path}' not found.")
            sys.exit(1)
        except toml.TomlDecodeError as e:
            print(f"Error: Invalid TOML configuration: {e}")
            sys.exit(1)
    
    def validate_svg(self, svg_path: str) -> bool:
        """Validate SVG file structure and syntax."""
        if not VALIDATION_AVAILABLE:
            print("Warning: SVG validation skipped - validation libraries not available")
            return True
        
        try:
            # Parse with lxml for better validation
            with open(svg_path, 'rb') as f:
                doc = etree.parse(f)
            
            # Basic SVG structure validation
            root = doc.getroot()
            if root.tag != '{http://www.w3.org/2000/svg}svg':
                print(f"Warning: Root element is not SVG: {root.tag}")
                return False
            
            # Check for required attributes
            if 'width' not in root.attrib or 'height' not in root.attrib:
                print("Warning: SVG missing width or height attributes")
            
            print(f"✓ SVG validation passed: {svg_path}")
            return True
            
        except etree.XMLSyntaxError as e:
            print(f"Error: Invalid SVG syntax: {e}")
            return False
        except Exception as e:
            print(f"Warning: SVG validation failed: {e}")
            return True  # Continue processing despite validation issues
    
    def validate_gcode(self, gcode_path: str) -> bool:
        """Validate generated G-code syntax and structure."""
        if not VALIDATION_AVAILABLE:
            print("Warning: G-code validation skipped - validation libraries not available")
            return True
        
        try:
            with open(gcode_path, 'r') as f:
                gcode_content = f.read()
            
            # Parse with gcodeparser
            parser = GcodeParser(gcode_content, include_comments=True)
            lines = parser.lines
            
            # Basic validation checks
            has_init = False
            has_home = False
            has_temp_commands = False
            has_movement = False
            
            for line in lines:
                if hasattr(line, 'command') and line.command:
                    cmd_letter, cmd_number = line.command
                    
                    if cmd_letter == 'G':
                        if cmd_number == 28:  # Home
                            has_home = True
                        elif cmd_number == 90:  # Absolute positioning
                            has_init = True
                        elif cmd_number in [0, 1]:  # Movement
                            has_movement = True
                    
                    elif cmd_letter == 'M':
                        if cmd_number in [104, 109, 140, 190]:  # Temperature commands
                            has_temp_commands = True
            
            # Validation results
            issues = []
            if not has_init:
                issues.append("Missing initialization commands (G90)")
            if not has_home:
                issues.append("Missing home command (G28)")
            if not has_temp_commands:
                issues.append("Missing temperature commands")
            if not has_movement:
                issues.append("Missing movement commands")
            
            if issues:
                print("G-code validation warnings:")
                for issue in issues:
                    print(f"  - {issue}")
            else:
                print(f"✓ G-code validation passed: {gcode_path}")
            
            return len(issues) == 0
            
        except Exception as e:
            print(f"Warning: G-code validation failed: {e}")
            return True  # Continue despite validation issues
    
    def validate_output_svg(self, svg_path: str) -> bool:
        """Validate generated animation SVG."""
        if not VALIDATION_AVAILABLE:
            return True
        
        try:
            with open(svg_path, 'rb') as f:
                doc = etree.parse(f)
            
            root = doc.getroot()
            
            # Check for animation elements
            animations = root.xpath('//svg:animate', namespaces={'svg': 'http://www.w3.org/2000/svg'})
            circles = root.xpath('//svg:circle', namespaces={'svg': 'http://www.w3.org/2000/svg'})
            
            if len(animations) == 0:
                print("Warning: No animation elements found in output SVG")
                return False
            
            if len(circles) == 0:
                print("Warning: No circle elements found in animation SVG")
                return False
            
            print(f"✓ Animation SVG validation passed: {svg_path} ({len(animations)} animations, {len(circles)} circles)")
            return True
            
        except Exception as e:
            print(f"Warning: Animation SVG validation failed: {e}")
            return True
    
    def parse_svg(self, svg_path: str) -> None:
        """Parse SVG file and extract weld paths."""
        try:
            tree = ET.parse(svg_path)
            root = tree.getroot()
        except ET.ParseError as e:
            print(f"Error: Invalid SVG file: {e}")
            sys.exit(1)
        except FileNotFoundError:
            print(f"Error: SVG file '{svg_path}' not found.")
            sys.exit(1)
        
        # Define SVG namespace
        namespaces = {'svg': 'http://www.w3.org/2000/svg'}
        
        # Find all path elements and sort by ID
        elements = []
        
        # Get paths
        for path in root.findall('.//svg:path', namespaces):
            elements.append(('path', path))
        
        # Get lines
        for line in root.findall('.//svg:line', namespaces):
            elements.append(('line', line))
        
        # Get circles
        for circle in root.findall('.//svg:circle', namespaces):
            elements.append(('circle', circle))
        
        # Get rectangles
        for rect in root.findall('.//svg:rect', namespaces):
            elements.append(('rect', rect))
        
        # Sort by ID if available
        def get_sort_key(element_tuple):
            element_type, element = element_tuple
            element_id = element.get('id', '')
            # Try to extract numeric part for sorting
            match = re.search(r'(\d+)', element_id)
            return int(match.group(1)) if match else float('inf')
        
        elements.sort(key=get_sort_key)
        
        # Process each element
        for element_type, element in elements:
            weld_type, pause_message = self.determine_weld_type(element)
            svg_id = element.get('id', f'unnamed_{len(self.weld_paths)}')
            
            if element_type == 'path':
                points = self.parse_path_element(element)
            elif element_type == 'line':
                points = self.parse_line_element(element)
            elif element_type == 'circle':
                points = self.parse_circle_element(element)
            elif element_type == 'rect':
                points = self.parse_rect_element(element)
            else:
                continue
            
            if points:
                weld_path = WeldPath(points=points, weld_type=weld_type, svg_id=svg_id, pause_message=pause_message)
                self.weld_paths.append(weld_path)
    
    def determine_weld_type(self, element) -> Tuple[str, Optional[str]]:
        """Determine weld type based on element color and extract pause message if applicable."""
        # Check stroke color
        stroke = element.get('stroke', '').lower()
        fill = element.get('fill', '').lower()
        style = element.get('style', '').lower()
        
        # Parse style attribute for color information
        color_info = f"{stroke} {fill} {style}"
        
        # Extract pause message for red elements
        pause_message = None
        
        if any(color in color_info for color in ['red', '#ff0000', '#f00', 'rgb(255,0,0)']):
            # Look for pause message in various SVG attributes
            pause_message = (
                element.get('data-message') or  # Custom data attribute
                element.get('title') or         # SVG title attribute
                element.get('desc') or          # SVG description
                element.get('aria-label') or    # Accessibility label
                'Manual intervention required'  # Default message
            )
            return 'stop', pause_message
        elif any(color in color_info for color in ['blue', '#0000ff', '#00f', 'rgb(0,0,255)']):
            return 'light', None
        else:
            return 'normal', None  # Default for black or other colors
    
    def parse_path_element(self, path_element) -> List[WeldPoint]:
        """Parse SVG path element and return weld points."""
        d = path_element.get('d', '')
        if not d:
            return []
        
        points = []
        # Simple path parser - handles M, L, Z commands
        commands = re.findall(r'[MLZ][^MLZ]*', d)
        current_x, current_y = 0, 0
        
        for command in commands:
            cmd = command[0]
            coords = re.findall(r'-?\d+\.?\d*', command[1:])
            coords = [float(c) for c in coords]
            
            if cmd == 'M' and len(coords) >= 2:  # Move to
                current_x, current_y = coords[0], coords[1]
                points.append(WeldPoint(current_x, current_y, 'normal'))
            elif cmd == 'L' and len(coords) >= 2:  # Line to
                current_x, current_y = coords[0], coords[1]
                points.append(WeldPoint(current_x, current_y, 'normal'))
        
        return self.interpolate_points(points)
    
    def parse_line_element(self, line_element) -> List[WeldPoint]:
        """Parse SVG line element."""
        x1 = float(line_element.get('x1', 0))
        y1 = float(line_element.get('y1', 0))
        x2 = float(line_element.get('x2', 0))
        y2 = float(line_element.get('y2', 0))
        
        points = [
            WeldPoint(x1, y1, 'normal'),
            WeldPoint(x2, y2, 'normal')
        ]
        
        return self.interpolate_points(points)
    
    def parse_circle_element(self, circle_element) -> List[WeldPoint]:
        """Parse SVG circle element."""
        cx = float(circle_element.get('cx', 0))
        cy = float(circle_element.get('cy', 0))
        r = float(circle_element.get('r', 1))
        
        # Generate points around the circle
        points = []
        num_points = max(8, int(2 * math.pi * r / 2))  # Rough approximation
        
        for i in range(num_points):
            angle = 2 * math.pi * i / num_points
            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle)
            points.append(WeldPoint(x, y, 'normal'))
        
        return self.interpolate_points(points)
    
    def parse_rect_element(self, rect_element) -> List[WeldPoint]:
        """Parse SVG rectangle element."""
        x = float(rect_element.get('x', 0))
        y = float(rect_element.get('y', 0))
        width = float(rect_element.get('width', 0))
        height = float(rect_element.get('height', 0))
        
        # Create rectangle path
        points = [
            WeldPoint(x, y, 'normal'),
            WeldPoint(x + width, y, 'normal'),
            WeldPoint(x + width, y + height, 'normal'),
            WeldPoint(x, y + height, 'normal'),
            WeldPoint(x, y, 'normal')  # Close the rectangle
        ]
        
        return self.interpolate_points(points)
    
    def interpolate_points(self, points: List[WeldPoint]) -> List[WeldPoint]:
        """Interpolate points along the path based on dot spacing."""
        if len(points) < 2:
            return points
        
        # Use normal weld dot spacing as default
        dot_spacing = self.config['normal_welds']['dot_spacing']
        interpolated = []
        
        for i in range(len(points) - 1):
            start = points[i]
            end = points[i + 1]
            
            # Calculate distance
            dx = end.x - start.x
            dy = end.y - start.y
            distance = math.sqrt(dx * dx + dy * dy)
            
            if distance == 0:
                continue
            
            # Calculate number of points needed
            num_points = max(1, int(distance / dot_spacing))
            
            # Add interpolated points
            for j in range(num_points + 1):
                t = j / num_points if num_points > 0 else 0
                x = start.x + t * dx
                y = start.y + t * dy
                interpolated.append(WeldPoint(x, y, start.weld_type))
        
        return interpolated
    
    def generate_gcode(self, output_path: str, skip_bed_leveling: bool = False) -> None:
        """Generate G-code file."""
        with open(output_path, 'w') as f:
            # Write header
            f.write("; Generated by SVG to G-code Welder\n")
            f.write("; Prusa Core One Plastic Welding G-code\n")
            f.write(f"; Total paths: {len(self.weld_paths)}\n\n")
            
            # Initialize printer
            f.write("; Initialize printer\n")
            f.write("G90 ; Absolute positioning\n")
            f.write("M83 ; Relative extruder positioning\n")
            f.write("G28 ; Home all axes\n\n")
            
            # Bed leveling (optional)
            if not skip_bed_leveling:
                f.write("; Bed leveling\n")
                f.write("G29 ; Auto bed leveling\n\n")
            
            # Heat bed
            bed_temp = self.config['temperatures']['bed_temperature']
            f.write(f"; Heat bed to {bed_temp}°C\n")
            f.write(f"M140 S{bed_temp} ; Set bed temperature\n")
            f.write(f"M190 S{bed_temp} ; Wait for bed temperature\n\n")
            
            # Heat nozzle to initial temperature
            nozzle_temp = self.config['temperatures']['nozzle_temperature']
            f.write(f"; Heat nozzle to {nozzle_temp}°C\n")
            f.write(f"M104 S{nozzle_temp} ; Set nozzle temperature\n")
            f.write(f"M109 S{nozzle_temp} ; Wait for nozzle temperature\n\n")
            
            # User pause for plastic sheets
            f.write("; Pause for user to insert plastic sheets\n")
            f.write("M0 ; Pause - Insert plastic sheets and press continue\n\n")
            
            # Move to safe height
            move_height = self.config['movement']['move_height']
            f.write(f"G1 Z{move_height} F{self.config['movement']['z_speed']} ; Move to safe height\n\n")
            
            # Process each weld path
            for path in self.weld_paths:
                f.write(f"; Processing path: {path.svg_id} (type: {path.weld_type})\n")
                
                if path.weld_type == 'stop':
                    # Use custom message if available, otherwise default
                    message = path.pause_message or 'Manual intervention required'
                    # Escape quotes and limit message length for G-code safety
                    safe_message = message.replace('"', "'").replace(';', ',')[:50]
                    f.write(f'M0 "{safe_message}" ; User stop requested\n\n')
                    continue
                
                # Get settings for this weld type
                if path.weld_type == 'light':
                    weld_config = self.config['light_welds']
                else:
                    weld_config = self.config['normal_welds']
                
                # Set temperature if different
                if weld_config['weld_temperature'] != nozzle_temp:
                    nozzle_temp = weld_config['weld_temperature']
                    f.write(f"M104 S{nozzle_temp} ; Set temperature for {path.weld_type} welds\n")
                    f.write(f"M109 S{nozzle_temp} ; Wait for temperature\n")
                
                # Process each point in the path
                for point in path.points:
                    # Move to position at safe height
                    f.write(f"G1 X{point.x:.3f} Y{point.y:.3f} Z{move_height} F{self.config['movement']['travel_speed']}\n")
                    
                    # Lower to weld height
                    f.write(f"G1 Z{weld_config['weld_height']:.3f} F{self.config['movement']['z_speed']}\n")
                    
                    # Dwell for welding
                    f.write(f"G4 P{weld_config['spot_dwell_time'] * 1000:.0f} ; Dwell for welding\n")
                    
                    # Raise to safe height
                    f.write(f"G1 Z{move_height} F{self.config['movement']['z_speed']}\n")
                
                f.write("\n")
            
            # Cool down
            cooldown_temp = self.config['temperatures']['cooldown_temperature']
            f.write("; Cool down\n")
            f.write(f"M104 S{cooldown_temp} ; Cool nozzle\n")
            f.write(f"M140 S{cooldown_temp} ; Cool bed\n")
            f.write("G28 X Y ; Home X and Y\n")
            f.write("M84 ; Disable steppers\n")
            f.write("; End of G-code\n")
    
    def generate_animation(self, output_path: str) -> None:
        """Generate animated SVG showing the welding process."""
        if not self.weld_paths:
            return
        
        # Get animation configuration
        time_between_welds = self.config['animation']['time_between_welds']
        pause_time = self.config['animation']['pause_time']
        min_animation_duration = self.config['animation']['min_animation_duration']
        
        # Calculate bounds
        all_points = []
        for path in self.weld_paths:
            all_points.extend(path.points)
        
        if not all_points:
            return
        
        min_x = min(p.x for p in all_points)
        max_x = max(p.x for p in all_points)
        min_y = min(p.y for p in all_points)
        max_y = max(p.y for p in all_points)
        
        # Add padding
        padding = 20  # Increased padding for pause messages
        width = max_x - min_x + 2 * padding
        height = max_y - min_y + 2 * padding + 40  # Extra space for messages
        
        # Calculate total animation time
        total_weld_points = sum(len(path.points) for path in self.weld_paths if path.weld_type != 'stop')
        total_pause_time = sum(pause_time for path in self.weld_paths if path.weld_type == 'stop')
        calculated_duration = total_weld_points * time_between_welds + total_pause_time
        animation_duration = max(min_animation_duration, calculated_duration)
        
        with open(output_path, 'w') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write(f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">\n')
            f.write(f'  <rect width="100%" height="100%" fill="white"/>\n')
            
            # Add title
            f.write(f'  <text x="{width/2}" y="20" text-anchor="middle" font-family="Arial" font-size="14" fill="black">SVG Welding Animation</text>\n')
            
            # Add timing info
            f.write(f'  <text x="{width/2}" y="35" text-anchor="middle" font-family="Arial" font-size="10" fill="gray">Duration: {animation_duration:.1f}s | Weld interval: {time_between_welds}s | Pause time: {pause_time}s</text>\n')
            
            current_time = 0
            
            for path_idx, path in enumerate(self.weld_paths):
                # Handle stop points (pause messages)
                if path.weld_type == 'stop':
                    # Get the first point for message positioning
                    if path.points:
                        point = path.points[0]
                        x = point.x - min_x + padding
                        y = point.y - min_y + padding
                        
                        # Display pause message
                        message = path.pause_message or 'Manual intervention required'
                        safe_message = message.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                        
                        # Message background
                        f.write(f'  <rect x="{x-50}" y="{y-25}" width="100" height="20" fill="yellow" stroke="red" stroke-width="1" opacity="0">\n')
                        f.write(f'    <animate attributeName="opacity" values="0;0.9;0.9;0" dur="{animation_duration}s" begin="{current_time:.2f}s" repeatCount="indefinite"/>\n')
                        f.write(f'  </rect>\n')
                        
                        # Message text
                        f.write(f'  <text x="{x}" y="{y-10}" text-anchor="middle" font-family="Arial" font-size="8" fill="red" opacity="0">\n')
                        f.write(f'    <animate attributeName="opacity" values="0;1;1;0" dur="{animation_duration}s" begin="{current_time:.2f}s" repeatCount="indefinite"/>\n')
                        f.write(f'    {safe_message[:30]}{"..." if len(safe_message) > 30 else ""}\n')
                        f.write(f'  </text>\n')
                        
                        # Stop indicator circle
                        f.write(f'  <circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="red" stroke="darkred" stroke-width="2" opacity="0">\n')
                        f.write(f'    <animate attributeName="opacity" values="0;1;1;0" dur="{animation_duration}s" begin="{current_time:.2f}s" repeatCount="indefinite"/>\n')
                        f.write(f'  </circle>\n')
                    
                    current_time += pause_time
                    continue
                
                # Determine color based on weld type
                if path.weld_type == 'light':
                    color = 'blue'
                else:
                    color = 'black'
                
                # Process weld points
                for point_idx, point in enumerate(path.points):
                    # Adjust coordinates
                    x = point.x - min_x + padding
                    y = point.y - min_y + padding + 40  # Offset for header
                    
                    # Create animated weld point circle
                    f.write(f'  <circle cx="{x:.2f}" cy="{y:.2f}" r="2" fill="{color}" opacity="0">\n')
                    f.write(f'    <animate attributeName="opacity" values="0;1;1;0.3" dur="{animation_duration}s" begin="{current_time:.2f}s" repeatCount="indefinite"/>\n')
                    f.write(f'  </circle>\n')
                    
                    current_time += time_between_welds
            
            # Add legend
            legend_y = height - 15
            f.write(f'  <text x="10" y="{legend_y}" font-family="Arial" font-size="10" fill="gray">Legend:</text>\n')
            f.write(f'  <circle cx="60" cy="{legend_y-4}" r="2" fill="black"/>\n')
            f.write(f'  <text x="70" y="{legend_y}" font-family="Arial" font-size="9" fill="gray">Normal Welds</text>\n')
            f.write(f'  <circle cx="160" cy="{legend_y-4}" r="2" fill="blue"/>\n')
            f.write(f'  <text x="170" y="{legend_y}" font-family="Arial" font-size="9" fill="gray">Light Welds</text>\n')
            f.write(f'  <circle cx="250" cy="{legend_y-4}" r="4" fill="red"/>\n')
            f.write(f'  <text x="260" y="{legend_y}" font-family="Arial" font-size="9" fill="gray">Stop Points</text>\n')
            
            f.write('</svg>\n')


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Convert SVG files to Prusa Core One G-code for plastic welding",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.svg -o output.gcode
  %(prog)s input.svg --skip-bed-leveling
  %(prog)s input.svg -c custom_config.toml
        """
    )
    
    parser.add_argument('input_svg', help='Input SVG file path')
    parser.add_argument('-o', '--output', help='Output G-code file path (default: input_name.gcode)')
    parser.add_argument('-c', '--config', default='config.toml', help='Configuration file path (default: config.toml)')
    parser.add_argument('--skip-bed-leveling', action='store_true', help='Skip automatic bed leveling')
    parser.add_argument('--no-animation', action='store_true', help='Skip generating animation SVG')
    
    args = parser.parse_args()
    
    # Validate input file
    if not os.path.exists(args.input_svg):
        print(f"Error: Input SVG file '{args.input_svg}' not found.")
        sys.exit(1)
    
    # Determine output paths
    input_path = Path(args.input_svg)
    if args.output:
        output_gcode = args.output
    else:
        output_gcode = input_path.with_suffix('.gcode')
    
    output_animation = input_path.with_name(input_path.stem + '_animation.svg')
    
    # Initialize converter
    try:
        converter = SVGToGCodeWelder(args.config)
    except SystemExit:
        return
    
    print(f"Processing SVG file: {args.input_svg}")
    
    # Validate input SVG
    print("Validating input SVG...")
    if not converter.validate_svg(args.input_svg):
        print("Warning: SVG validation failed, but continuing processing...")
    
    # Parse SVG
    converter.parse_svg(args.input_svg)
    print(f"Found {len(converter.weld_paths)} weld paths")
    
    # Generate G-code
    print(f"Generating G-code: {output_gcode}")
    converter.generate_gcode(str(output_gcode), args.skip_bed_leveling)
    
    # Validate generated G-code
    print("Validating generated G-code...")
    converter.validate_gcode(str(output_gcode))
    
    # Generate animation
    if not args.no_animation:
        print(f"Generating animation: {output_animation}")
        converter.generate_animation(str(output_animation))
        
        # Validate generated animation
        print("Validating animation SVG...")
        converter.validate_output_svg(str(output_animation))
    
    print("Conversion complete!")


if __name__ == '__main__':
    main()
