# MicroWeldr Examples

This directory contains example files demonstrating MicroWeldr's capabilities with different file formats and their corresponding animated visualizations.

## Example Files

### SVG Example
- **Source**: `flask_simple.svg` (1,053 bytes)
- **Animation**: `flask_svg_animation.gif` (449KB, 154 frames)
- **Points**: 154 weld points
- **Duration**: ~15.4 seconds
- **Features**: Bézier curves with proper curved bottom, scale-aware point sizing

### DXF Example
- **Source**: `flask.dxf` (2,546 bytes)
- **Animation**: `flask_dxf_animation.gif` (305KB, 121 frames)
- **Points**: 121 weld points
- **Duration**: ~12.1 seconds
- **Features**: Distance-based spacing, straight line interpolation, scale-aware points

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
| **Points** | 154 (interpolated curves) | 121 (distance-based + line interpolation) |
| **Use Case** | Design visualization | Technical drawings |

## System Improvements

These examples demonstrate the simplified MicroWeldr system:

- ✅ **No multi-pass welding logic** - direct point-to-point welding
- ✅ **No break/pause functionality** - continuous welding sequence
- ✅ **Simplified point generation** - no complex spacing calculations
- ✅ **Complete visualization** - every weld point shown in animation
- ✅ **Web-ready output** - animated GIFs work in all browsers

Perfect for understanding weld sequences and verifying welding patterns before sending to the printer!
