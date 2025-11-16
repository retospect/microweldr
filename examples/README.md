# MicroWeldr Examples

This directory contains example files demonstrating MicroWeldr's capabilities with different file formats and their corresponding animated visualizations.

## Example Files

### SVG Example
- **Source**: `flask_simple.svg` (1,053 bytes)
- **Animation**: `flask_svg_animation.gif` (1,435KB, 628 frames)
- **Points**: 628 weld points
- **Duration**: ~62.8 seconds
- **Features**: Bézier curves, unified 0.5mm spacing, scale-aware point sizing

### DXF Example
- **Source**: `flask.dxf` (2,546 bytes)
- **Animation**: `flask_dxf_animation.gif` (1,278KB, 467 frames)
- **Points**: 467 weld points
- **Duration**: ~46.7 seconds
- **Features**: Unified 0.5mm spacing, straight line interpolation, scale-aware points

## Animation Features

### Visual Elements
- **Point-by-point progression**: Shows every single weld point in sequence
- **Color coding**: Different colors for each weld type (normal=blue, frangible=red, etc.)
- **Current point highlighting**: Red outline on active weld point
- **Point numbering**: Sequential numbers showing weld order
- **No connecting lines**: Clean visualization focusing on weld points

### Technical Specifications
- **Format**: Animated GIF (web-compatible)
- **Dimensions**: 800x600 pixels
- **Frame rate**: 100ms per frame (10 FPS)
- **No frame skipping**: Every weld point gets its own frame
- **Simplified generation**: No multi-pass welding complexity

## Generation Commands

```bash
# Generate SVG animation
microweldr -weld flask_simple.svg -animation flask_svg_animation.gif

# Generate DXF animation
microweldr -weld flask.dxf -animation flask_dxf_animation.gif

# Generate both G-code and animation
microweldr -weld flask_simple.svg -g_out flask.gcode -animation flask_animation.gif
```

## File Format Comparison

| Aspect | SVG | DXF |
|--------|-----|-----|
| **Source** | Vector graphics with curves | CAD line segments |
| **Precision** | Artistic/design focused | Engineering precision |
| **Curves** | Bézier curves (smooth) | Tessellated line segments |
| **File Size** | Smaller source (1KB) | Larger source (2.5KB) |
| **Points** | 628 (0.5mm spacing) | 467 (0.5mm spacing) |
| **Use Case** | Design visualization | Technical drawings |

## System Improvements

These examples demonstrate the simplified MicroWeldr system:

- ✅ **No multi-pass welding logic** - direct point-to-point welding
- ✅ **No break/pause functionality** - continuous welding sequence
- ✅ **Unified configuration** - both SVG and DXF use same 0.5mm dot_spacing
- ✅ **Complete visualization** - every weld point shown in animation
- ✅ **Scale-aware point sizing** - based on nozzle diameter from config
- ✅ **Web-ready output** - animated GIFs work in all browsers

## Configuration Consistency

Both examples now use the unified configuration system:

- **Dot Spacing**: 0.5mm for both SVG and DXF (from `normal_welds.dot_spacing`)
- **Point Sizing**: Based on 1.1mm nozzle outer diameter (from `nozzle.outer_diameter`)
- **Consistent Behavior**: Same spacing logic across all file formats
- **High Detail**: 4x more points than previous 2.0mm spacing

Perfect for understanding weld sequences and verifying welding patterns before sending to the printer!
