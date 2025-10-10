# SVG to G-code Welder

A professional Python package that converts SVG files to Prusa Core One G-code for plastic welding applications. The package processes SVG vector graphics and generates G-code that creates weld spots along the paths without extruding any plastic material.

## Project Structure

```
svg-welder/
├── svg_welder/           # Main package
│   ├── core/            # Core functionality
│   ├── validation/      # Validation modules
│   ├── animation/       # Animation generation
│   └── cli/             # Command line interface
├── tests/               # Test suite
│   ├── unit/           # Unit tests
│   └── integration/    # Integration tests
├── examples/           # Example files and configurations
├── docs/              # Documentation
└── pyproject.toml     # Poetry configuration
```

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

### Using Poetry (Recommended)

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd svg-to-gcode-welder
   ```

2. Install with Poetry:
   ```bash
   # Install core dependencies only
   poetry install
   
   # Install with validation libraries
   poetry install --extras validation
   
   # Install with development dependencies
   poetry install --with dev,validation
   ```

3. Activate the virtual environment:
   ```bash
   poetry shell
   ```

### Using pip

```bash
pip install -e .
# Or with validation libraries
pip install -e .[validation]
```

### Development Setup

```bash
# Install development dependencies
make install-dev

# Install pre-commit hooks
make install-pre-commit

# Run tests
make test
```

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
dot_spacing = 2.0          # mm - final desired spacing
initial_dot_spacing = 8.0  # mm - spacing for first pass (wider)
cooling_time_between_passes = 2.0  # seconds - cooling between passes

[light_welds]
weld_temperature = 180     # °C - lower temperature
spot_dwell_time = 0.3      # seconds - shorter time
dot_spacing = 3.0          # mm - final desired spacing
initial_dot_spacing = 12.0 # mm - spacing for first pass (wider)
cooling_time_between_passes = 1.5  # seconds - cooling between passes

[nozzle]
outer_diameter = 0.4        # mm - nozzle outer diameter
inner_diameter = 0.2        # mm - nozzle inner diameter (opening)

[animation]
time_between_welds = 0.1    # seconds - time between weld points in animation
pause_time = 3.0            # seconds - how long pause messages are displayed
min_animation_duration = 10.0  # seconds - minimum total animation time

## Usage

### Basic Usage
```bash
# Using the installed command
svg-welder input.svg

# Using Poetry
poetry run svg-welder input.svg

# Using the module directly
python -m svg_welder.cli.main input.svg
```

### Advanced Options
```bash
# Specify output file
svg-welder input.svg -o output.gcode

# Skip bed leveling
svg-welder input.svg --skip-bed-leveling

# Use custom configuration
svg-welder input.svg -c custom_config.toml

# Skip animation generation
svg-welder input.svg --no-animation

# Skip validation
svg-welder input.svg --no-validation

# Verbose output
svg-welder input.svg --verbose
```

### Quick Start with Examples
```bash
# Run with example files
make run-example
make run-comprehensive
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
5. **Multi-Pass Welding Process**: 
   - **Pass 1**: Create initial dots with wide spacing (allows plastic to set)
   - **Cooling Period**: Wait between passes for plastic to cool
   - **Pass 2+**: Fill in between previous dots until desired density achieved
   - Each dot: Move to position → Lower → Dwell → Raise
6. **Cooldown**: Lower temperatures and home axes

## Multi-Pass Welding System

The welder implements an intelligent multi-pass system that allows plastic to cool between welding operations:

### How It Works
1. **Initial Pass**: Places dots with wide spacing (`initial_dot_spacing`)
2. **Cooling Period**: Waits for `cooling_time_between_passes` to let plastic cool
3. **Subsequent Passes**: Progressively fills in between existing dots
4. **Final Density**: Achieves the desired `dot_spacing` through multiple passes

### Benefits
- **Prevents Overheating**: Allows plastic to cool between passes
- **Better Quality**: Reduces warping and material degradation
- **Consistent Results**: Each dot gets proper cooling time
- **Automatic Calculation**: Number of passes calculated from spacing ratio

### Configuration Example
```toml
[normal_welds]
dot_spacing = 2.0          # Final 2mm spacing
initial_dot_spacing = 8.0  # Start with 8mm spacing
cooling_time_between_passes = 2.0  # 2 seconds between passes
```

This creates **3 passes**: 8mm → 4mm → 2mm spacing with 2-second cooling between each pass.

## Animation Output

The script generates an enhanced animated SVG file showing:
- **Realistic nozzle rings** that flip into existence at each weld point
- **Temperature-based visualization** with color-coded heat zones
- **Overlapping ring patterns** showing actual nozzle contact areas
- **Pause messages displayed** with yellow background and red text
- **Timing information** displayed in header (duration, intervals, pause time)
- **Enhanced legend** with nozzle ring examples and dimensions
- **Endless loop animation** with realistic timing

### Animation Features
- **Realistic nozzle visualization**: Shows outer diameter (contact area) and inner diameter (heated zone)
- **Flip animation**: Nozzle rings scale and flip into existence with realistic physics
- **Temperature visualization**: Orange/red rings for normal welds, blue rings for light welds
- **Heat effects**: Subtle glow animation around weld points
- **Configurable nozzle dimensions**: Set actual nozzle OD/ID in configuration
- **10x scale factor**: Nozzle dimensions scaled up for visibility in animation
- **Pause message display**: Stop points show custom messages for specified `pause_time`
- **Smart duration calculation**: Automatically calculates total time based on weld count and pauses

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

## Running the Examples

### For Installed Package
If you've installed svg-welder as a package:

```bash
# Install the package
pip install svg-welder
# or with validation libraries
pip install svg-welder[validation]

# Run examples (assuming you have the example files)
svg-welder example.svg
svg-welder example.svg --verbose
svg-welder example.svg -o my_output.gcode
```

### For Development/Source Code
If you're working with the source code:

```bash
# Setup (one-time)
poetry install
poetry install --extras validation  # optional validation libraries

# Run examples
poetry run svg-welder examples/example.svg
poetry run svg-welder examples/comprehensive_sample.svg
poetry run svg-welder examples/example.svg --verbose

# Development shortcuts
make run-example          # Quick example run
make run-comprehensive    # Full sample run
make install-dev          # Development setup
```

**📖 For detailed development setup, see [DEVELOPMENT.md](DEVELOPMENT.md)**

### Example Files Included
- **`examples/example.svg`**: Basic demonstration with normal welds, light welds, and stop points
- **`examples/comprehensive_sample.svg`**: Full-featured demo showing all capabilities
- **`examples/pause_examples.svg`**: Examples of different pause message formats
- **`examples/config.toml`**: Complete configuration file with all parameters

### Expected Output
Each run generates:
- **G-code file**: `example.gcode` - Ready to load on Prusa Core One
- **Animation file**: `example_animation.svg` - Visual preview of welding sequence
- **Console output**: Processing details and validation results

### Alternative Run Methods
```bash
# Using Python module (development)
python -m svg_welder.cli.main examples/example.svg

# Direct script execution (development)
python svg_welder/cli/main.py examples/example.svg

# With custom configuration
svg-welder examples/example.svg -c my_config.toml
```

## License

This project is open source. Use at your own risk and ensure proper safety precautions when operating 3D printing equipment.
