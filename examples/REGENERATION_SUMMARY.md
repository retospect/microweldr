# Example Files Regeneration Summary

Generated on: 2025-10-10T20:08:40+01:00

## Configuration Update: 1mm Nozzle with Minimal Overlap
- **Nozzle Outer Diameter**: 1.0mm
- **Dot Spacing**: 0.9mm (minimal overlap by 0.1mm for continuous welding)
- **Initial Spacing**: 3.6mm (4x final spacing for first pass)
- **Overlap Percentage**: 10% overlap between adjacent dots
- **Default Algorithm**: Skip (every 5th dot first, then fill gaps)

## Files Regenerated

### Basic Examples
- **example.svg** → **example.gcode** + **example_animation.svg**
  - 6 weld paths, **504 weld points** (efficient minimal overlap)
  - Bounds: (10.0, 10.0) to (90.0, 90.0)
  - Animation: 505 animations, 504 circles

### Pause Examples
- **pause_examples.svg** → **pause_examples.gcode** + **pause_examples_animation.svg**
  - 8 weld paths, **411 weld points** (efficient minimal overlap)
  - Bounds: (10.0, 25.0) to (190.0, 130.0)
  - Animation: 418 animations, 411 circles
  - Features custom pause messages

### Comprehensive Sample
- **comprehensive_sample.svg** → **comprehensive_sample.gcode** + **comprehensive_sample_animation.svg**
  - 14 weld paths, **1,746 weld points** (efficient minimal overlap)
  - Bounds: (20.0, 30.0) to (183.0, 245.0)
  - Animation: 1,751 animations, 1,746 circles
  - Demonstrates all features

## Weld Sequence Algorithm Examples

### Linear Sequence
- **example_linear.gcode** - Sequential welding order (1, 2, 3, ...)
- **comprehensive_sample_linear.gcode** - Linear sequence for complex patterns

### Binary Sequence
- **example_binary.gcode** - Binary subdivision pattern for balanced thermal distribution
- **comprehensive_sample_binary.gcode** - Binary sequence for complex patterns

### Farthest Point Sequence
- **example_farthest.gcode** - Greedy Farthest-Point Traversal for optimal thermal management
- **comprehensive_sample_farthest.gcode** - Farthest point sequence for complex patterns

### Skip Sequence (Default)
- **example.gcode** - Skip algorithm (every 5th dot first, then fill gaps)
- **comprehensive_sample.gcode** - Skip sequence for optimal thermal distribution

## Validation Results

All generated files passed validation:
- ✓ SVG input validation (structure, syntax, attributes)
- ✓ G-code output validation (commands, sequences)
- ✓ Animation SVG validation (elements, structure)

## File Sizes (1mm Nozzle, 0.9mm Spacing)

| File | Size | Type | Efficiency |
|------|------|------|------------|
| example.gcode | 78,602 bytes | G-code | 31% smaller than 0.6mm spacing |
| example_animation.svg | 129,228 bytes | Animation | 31% smaller than 0.6mm spacing |
| pause_examples.gcode | 71,162 bytes | G-code | 33% smaller than 0.6mm spacing |
| pause_examples_animation.svg | 107,673 bytes | Animation | 32% smaller than 0.6mm spacing |
| comprehensive_sample.gcode | 277,039 bytes | G-code | 33% smaller than 0.6mm spacing |
| comprehensive_sample_animation.svg | 445,143 bytes | Animation | 31% smaller than 0.6mm spacing |

## Features Demonstrated

1. **Basic Welding**: Simple paths, lines, and shapes
2. **Pause Messages**: Custom pause instructions for red elements
3. **Weld Types**: Normal (black), light (blue), stop (red) welding
4. **Thermal Management**: Three different sequencing algorithms
5. **Animation**: Visual representation of welding progression
6. **Validation**: Comprehensive input/output validation

All examples are ready for use with Prusa Core One plastic welding applications.
