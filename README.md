# SVG to G-code Welder

A Python script that converts SVG files to Prusa Core One G-code for plastic welding applications. The script processes SVG vector graphics and generates G-code that creates weld spots along the paths without extruding any plastic material.

## Features

- **SVG Processing**: Converts SVG paths, lines, circles, and rectangles to weld points
- **Color-based Weld Types**: 
  - Black elements → Normal welds
  - Blue elements → Light welds (lower temperature, shorter dwell time)
  - Red elements → Stop points (pause for user intervention)
- **Configurable Parameters**: TOML-based configuration for temperatures, heights, and timing
- **Bed Leveling**: Optional automatic bed leveling (can be disabled)
- **Animation Output**: Generates animated SVG showing the welding sequence
- **Proper G-code Structure**: Includes heating, cooling, and safety procedures

## Installation

1. Clone or download this repository
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Validation Libraries (Optional)
The script includes optional validation for input SVG files, generated G-code, and output animations:

- **lxml**: Advanced SVG structure validation
- **gcodeparser**: G-code syntax and command validation  
- **pygcode**: Additional G-code parsing capabilities
- **xmlschema**: XML schema validation support

If these libraries are not installed, the script will run normally but skip validation steps with warnings.

## Configuration

Edit `config.toml` to adjust welding parameters:

```toml
[temperatures]
bed_temperature = 60        # °C
nozzle_temperature = 200    # °C for normal welds

[movement]
move_height = 5.0          # mm - safe travel height
weld_height = 0.2          # mm - welding height

[normal_welds]
weld_temperature = 200     # °C
spot_dwell_time = 0.5      # seconds
dot_spacing = 2.0          # mm

[light_welds]
weld_temperature = 180     # °C - lower temperature
spot_dwell_time = 0.3      # seconds - shorter time
dot_spacing = 3.0          # mm - wider spacing
```

## Usage

### Basic Usage
```bash
python svg_to_gcode_welder.py input.svg
```

### Advanced Options
```bash
# Specify output file
python svg_to_gcode_welder.py input.svg -o output.gcode

# Skip bed leveling
python svg_to_gcode_welder.py input.svg --skip-bed-leveling

# Use custom configuration
python svg_to_gcode_welder.py input.svg -c custom_config.toml

# Skip animation generation
python svg_to_gcode_welder.py input.svg --no-animation
```

### Command Line Options
- `input_svg`: Input SVG file path (required)
- `-o, --output`: Output G-code file path (default: input_name.gcode)
- `-c, --config`: Configuration file path (default: config.toml)
- `--skip-bed-leveling`: Skip automatic bed leveling
- `--no-animation`: Skip generating animation SVG

## SVG Requirements

### Coordinate System
- SVG coordinates should be in millimeters
- Origin (0,0) corresponds to the printer bed origin

### Element Processing Order
- Elements are processed in order of their SVG ID attributes
- IDs with numeric components are sorted numerically
- Elements without IDs are processed last

### Color Coding
- **Black elements**: Normal welds (higher temperature, longer dwell time)
- **Blue elements**: Light welds (lower temperature, shorter dwell time)
- **Red elements**: Stop points (printer pauses for user intervention)

Colors can be specified via:
- `stroke` attribute
- `fill` attribute  
- `style` attribute (CSS format)

### Custom Pause Messages
Red elements (stop points) can include custom messages that will be displayed on the printer screen during the pause. The message can be specified using any of these SVG attributes (in order of priority):

- `data-message="Your custom message"` - Recommended custom data attribute
- `title="Your custom message"` - Standard SVG title attribute
- `desc="Your custom message"` - SVG description element
- `aria-label="Your custom message"` - Accessibility label

If no message is specified, the default "Manual intervention required" will be used.

**Example:**
```xml
<!-- Stop with custom message -->
<circle cx="50" cy="50" r="2" fill="red" data-message="Check weld quality and adjust temperature"/>

<!-- Stop using title attribute -->
<rect x="10" y="10" width="5" height="5" fill="red" title="Insert second plastic sheet"/>
```

### Supported SVG Elements
- `<path>` - Follows path commands (M, L, Z supported)
- `<line>` - Straight lines between two points
- `<circle>` - Circular paths
- `<rect>` - Rectangular paths

## G-code Output

The generated G-code includes:

1. **Initialization**: Homing, absolute positioning
2. **Bed Leveling**: Optional automatic bed leveling (G29)
3. **Heating**: Bed and nozzle to specified temperatures
4. **User Pause**: For inserting plastic sheets (M0)
5. **Welding Process**: 
   - Move to each weld point at safe height
   - Lower to weld height
   - Dwell for specified time
   - Raise to safe height
6. **Cooldown**: Lower temperatures and home axes

## Animation Output

The script generates an animated SVG file showing:
- Weld points appearing in sequence
- Color-coded by weld type
- Endless loop animation
- Timing based on actual welding sequence

## Validation Features

When validation libraries are installed, the script automatically validates:

### Input SVG Validation
- **Structure Check**: Verifies proper SVG root element and namespace
- **Attribute Validation**: Checks for required width/height attributes
- **Syntax Validation**: Uses lxml for robust XML syntax checking

### G-code Output Validation
- **Command Verification**: Validates G-code syntax and structure
- **Sequence Checking**: Ensures proper initialization, homing, and temperature commands
- **Movement Validation**: Confirms presence of required movement commands
- **Safety Verification**: Checks for proper heating/cooling sequences

### Animation SVG Validation
- **Element Counting**: Verifies presence of animation and circle elements
- **Structure Validation**: Ensures proper SVG animation syntax
- **Content Verification**: Confirms animation elements match expected output

All validation is **non-blocking** - the script continues processing even if validation fails, but provides detailed feedback about any issues found.

## Sample Files

The repository includes several example files:

- **`example.svg`**: Basic demonstration of all weld types and pause messages
- **`pause_examples.svg`**: Comprehensive examples of different pause message attributes
- **`comprehensive_sample.svg`**: Full-featured sample demonstrating all capabilities including:
  - Multiple normal weld shapes (lines, rectangles, circles, complex paths)
  - Light weld patterns with curved paths
  - Stop points with various message attributes
  - Processing order indicators
  - Complete workflow demonstration

## Example Workflow

1. Create an SVG file with your welding pattern (or use `comprehensive_sample.svg`)
2. Use black paths for normal welds, blue for light welds
3. Add red elements where you need manual stops with custom messages
4. Run the script: `python svg_to_gcode_welder.py pattern.svg`
5. Review validation output for any issues
6. Load the generated G-code file on your Prusa Core One
7. Insert plastic sheets when prompted
8. Monitor the welding process and respond to custom pause messages

## Safety Notes

- Always supervise the welding process
- Ensure proper ventilation when welding plastics
- Verify temperatures are appropriate for your plastic materials
- Test with small samples before full production runs
- The script includes safety pauses - use them to check progress

## Troubleshooting

### Common Issues
- **SVG not parsing**: Ensure SVG uses standard elements and attributes
- **Wrong coordinates**: Verify SVG units are in millimeters
- **Missing weld points**: Check dot spacing configuration
- **Temperature issues**: Adjust temperatures in config.toml for your materials

### Debug Tips
- Check the generated animation SVG to verify path interpretation
- Use a G-code viewer to preview the toolpath
- Start with simple test patterns before complex designs

## License

This project is open source. Use at your own risk and ensure proper safety precautions when operating 3D printing equipment.
