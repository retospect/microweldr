# Coordinate Centering Guide

MicroWeldr includes **automatic coordinate centering** that ensures welding patterns are properly positioned on the printer bed using a sophisticated two-pass processing system.

## 🎯 Overview

The coordinate centering system uses a **two-pass event-driven architecture**:

1. **Pass 1**: Analyzes all coordinates to calculate the bounding box
2. **Pass 2**: Replays the welding sequence with centering offset applied

This ensures optimal use of the build area and prevents patterns from being positioned at the edge or outside the printable area.

## 📐 Bed Configuration

**Default Printer Bed (Prusa Core One):**
- **Width**: 250mm (X-axis)
- **Depth**: 220mm (Y-axis)
- **Center**: (125, 110)

## 🔧 Automatic Centering (Built-in)

**All G-code generation now includes automatic centering:**

```bash
# Automatically centers patterns during G-code generation
microweldr -weld design.svg -g_out centered_output.gcode

# Combined welding with automatic centering
microweldr -weld normal.dxf -frange frangible.dxf -g_out combined.gcode
```

**Example Output:**
```
🔍 Pass 1: Analyzing coordinate bounds...
📐 Calculated centering offset: (+125.000, +146.000)
🎯 Pass 2: Generating centered G-code...
✅ Centered G-code generated: output.gcode (72,734 bytes)
📐 Applied centering offset: (+125.000, +146.000)mm
```

## 📊 Centering Analysis

The centering script provides detailed analysis:

```
=== COORDINATE ANALYSIS ===
Current bounds: X(-15.000 to 15.000), Y(-72.000 to 0.000)
Pattern size: 30.000 x 72.000mm
Current center: (0.000, -36.000)
Required offset: (+125.000, +146.000)
New center: (125.000, 110.000)
New bounds: X(110.000 to 140.000), Y(74.000 to 146.000)
✅ Centered G-code saved to: output_centered.gcode
```

## 🎯 Benefits

**✅ Optimal Positioning:**
- Patterns centered on bed for best adhesion
- Maximum margin from bed edges
- Consistent positioning across different designs

**✅ Automatic Bounds Checking:**
- Verifies pattern fits within bed dimensions
- Warns if pattern exceeds bed bounds
- Calculates safety margins

**✅ Preserves Weld Quality:**
- Maintains relative positioning of weld points
- Preserves weld heights and timing
- Only translates X/Y coordinates

## 🔍 Technical Details

### Two-Pass Architecture

The centering system uses an event-driven two-pass architecture:

**Pass 1 - Outline Analysis:**
1. **OutlineSubscriber** collects all coordinates from events
2. **Calculates** bounding box (min/max X and Y)
3. **Determines** pattern center point
4. **Computes** offset to move pattern center to bed center
5. **EventRecorder** captures all events for replay

**Pass 2 - Centered Generation:**
1. **StreamingGCodeSubscriber** initialized with centering offset
2. **Events replayed** with offset applied to each coordinate
3. **G-code generated** with centered coordinates

### Bed Bounds Verification

After centering, the system checks:
- **X bounds**: 0 ≤ X ≤ 250mm
- **Y bounds**: 0 ≤ Y ≤ 220mm
- **Margins**: Distance from pattern edges to bed edges

### File Compatibility

**Supported G-code:**
- Standard G1 movement commands
- Prusa Core One format
- MicroWeldr generated files

**Preserved Elements:**
- All non-coordinate G-code commands
- Comments and metadata
- Temperature settings
- Timing and weld parameters

## 🛠️ Configuration

### Custom Bed Sizes

To use different bed dimensions, modify the configuration:

```toml
# In microweldr_config.toml
[printer]
bed_size_x = 300.0  # Custom bed width
bed_size_y = 250.0  # Custom bed depth
```

### Integration with Custom Workflows

```python
from microweldr.processors.two_pass_processor import TwoPassProcessor

# Initialize processor with custom bed size
processor = TwoPassProcessor(config, bed_size_x=300.0, bed_size_y=250.0)

# Process with automatic centering
success = processor.process_with_centering(
    events=events,
    output_path=Path("output.gcode")
)

# Get centering statistics
stats = processor.get_centering_statistics()
offset_x = stats["centering_offset"]["x"]
offset_y = stats["centering_offset"]["y"]
```

## 📋 Examples

### Example 1: Small Pattern
```
Original: 30mm × 72mm pattern at (0, -36)
Centered: Same pattern at (125, 110) - bed center
Result: Perfect centering with 110mm margins
```

### Example 2: Large Pattern
```
Original: 200mm × 180mm pattern
Centered: Fits within 250mm × 220mm bed
Result: 25mm X-margin, 20mm Y-margin
```

## ⚠️ Current Limitations

- **Single Bed Configuration**: One bed size per configuration file
- **Event Replay Overhead**: Two-pass processing uses more memory for large patterns
- **Animation Centering**: Animation output centering not yet implemented

## 🚀 Future Enhancements

- **Multi-bed Profiles**: Support for multiple printer configurations
- **Animation Centering**: Extend centering to animation generation
- **Real-time Preview**: Visual centering preview before generation
- **Smart Margins**: Configurable safety margins from bed edges
- **Pattern Rotation**: Automatic rotation for optimal bed utilization
