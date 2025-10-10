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
            weld_type = self.determine_weld_type(element)
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
                weld_path = WeldPath(points=points, weld_type=weld_type, svg_id=svg_id)
                self.weld_paths.append(weld_path)
    
    def determine_weld_type(self, element) -> str:
        """Determine weld type based on element color."""
        # Check stroke color
        stroke = element.get('stroke', '').lower()
        fill = element.get('fill', '').lower()
        style = element.get('style', '').lower()
        
        # Parse style attribute for color information
        color_info = f"{stroke} {fill} {style}"
        
        if any(color in color_info for color in ['red', '#ff0000', '#f00', 'rgb(255,0,0)']):
            return 'stop'
        elif any(color in color_info for color in ['blue', '#0000ff', '#00f', 'rgb(0,0,255)']):
            return 'light'
        else:
            return 'normal'  # Default for black or other colors
    
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
                    f.write("M0 ; User stop requested\n\n")
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
        padding = 10
        width = max_x - min_x + 2 * padding
        height = max_y - min_y + 2 * padding
        
        # Calculate total animation time
        total_points = sum(len(path.points) for path in self.weld_paths)
        animation_duration = max(10, total_points * 0.1)  # At least 10 seconds
        
        with open(output_path, 'w') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write(f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">\n')
            f.write(f'  <rect width="100%" height="100%" fill="white"/>\n')
            
            # Add title
            f.write(f'  <text x="{width/2}" y="20" text-anchor="middle" font-family="Arial" font-size="14" fill="black">SVG Welding Animation</text>\n')
            
            current_time = 0
            time_per_point = animation_duration / total_points if total_points > 0 else 1
            
            for path_idx, path in enumerate(self.weld_paths):
                # Determine color based on weld type
                if path.weld_type == 'stop':
                    color = 'red'
                elif path.weld_type == 'light':
                    color = 'blue'
                else:
                    color = 'black'
                
                for point_idx, point in enumerate(path.points):
                    # Adjust coordinates
                    x = point.x - min_x + padding
                    y = point.y - min_y + padding
                    
                    # Create animated circle
                    f.write(f'  <circle cx="{x:.2f}" cy="{y:.2f}" r="2" fill="{color}" opacity="0">\n')
                    f.write(f'    <animate attributeName="opacity" values="0;1;1;0" dur="{animation_duration}s" begin="{current_time:.2f}s" repeatCount="indefinite"/>\n')
                    f.write(f'  </circle>\n')
                    
                    current_time += time_per_point
            
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
    
    # Parse SVG
    converter.parse_svg(args.input_svg)
    print(f"Found {len(converter.weld_paths)} weld paths")
    
    # Generate G-code
    print(f"Generating G-code: {output_gcode}")
    converter.generate_gcode(str(output_gcode), args.skip_bed_leveling)
    
    # Generate animation
    if not args.no_animation:
        print(f"Generating animation: {output_animation}")
        converter.generate_animation(str(output_animation))
    
    print("Conversion complete!")


if __name__ == '__main__':
    main()
