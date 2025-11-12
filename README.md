# MicroWeldr

[![PyPI version](https://badge.fury.io/py/microweldr.svg)](https://badge.fury.io/py/microweldr)
[![Test Suite](https://github.com/retospect/microweldr/actions/workflows/test.yml/badge.svg)](https://github.com/retospect/microweldr/actions/workflows/test.yml)

A Python package that converts **SVG and DXF files** to Prusa Core One G-code for **continuous plastic line welding**. The package processes vector graphics and generates G-code that creates **waterproof welded lines** by placing many precise weld "dots" in sequence along the paths, without extruding any plastic material.

**Multi-Format Support** - Processes both SVG and DXF files with automatic weld type detection based on colors, layers, or filenames.

**Optimized for Prusa Core One**: Includes chamber temperature control (M141/M191), proper bed dimensions (250×220×270mm), and CoreXY-specific settings for reliable plastic welding operations.

This enables rapid **microfluidics prototyping** with a 3D printer by creating **sealed, waterproof channels and barriers**. Each vector path becomes a continuous welded line through precisely controlled sequential dot placement.

## 🆕 Version 5.3.0 - Major Refactoring

- **DXF Support**: Full DXF file processing with lines, arcs, circles, and polylines
- **Multi-File Processing**: Process multiple SVG and DXF files in a single command
- **Frangible Welds**: Renamed from "light welds" for better terminology
- **Filename-Based Detection**: Automatic weld type detection from filenames as fallback
- **Modular CLI**: Refactored command architecture with better error handling
- **Publisher-Subscriber Architecture**: Extensible file processing framework

## Project Structure

```
microweldr/
├── microweldr/           # Main package
│   ├── core/            # Core functionality
│   │   ├── dxf_reader.py      # DXF file processing
│   │   ├── svg_reader.py      # SVG file processing
│   │   ├── file_readers.py    # Publisher-subscriber framework
│   │   ├── data_models.py     # Structured data models
│   │   ├── error_handling.py  # Centralized error handling
│   │   └── constants.py       # Application constants
│   ├── cli/             # Command line interface
│   │   └── commands/    # Modular command structure
│   ├── validation/      # Validation modules
│   └── animation/       # Animation generation
├── tests/               # Comprehensive test suite
│   ├── unit/           # Unit tests (33 tests)
│   └── integration/    # Integration tests
├── examples/           # Example files and configurations
└── pyproject.toml     # Poetry configuration
```

## Features

### File Format Support
- **SVG Files**: Paths, lines, circles, rectangles, groups, and use elements
- **DXF Files**: Lines, arcs, circles, polylines, and LWPOLYLINES
- **Multi-File Processing**: Mix SVG and DXF files in single command
- **Unit Validation**: DXF files must use millimeters (throws exception otherwise)
- **Construction Filtering**: Automatically ignores construction layers in DXF

### Weld Type Detection
Multiple methods for determining weld types:

#### 1. Color-Based (SVG)
- **Black elements** → Normal welds
- **Blue elements** → Frangible welds (breakaway seals)
- **Red elements** → Stop points (pause for user intervention)
- **Magenta elements** → Pipette points (filling operations)

#### 2. Layer-Based (DXF)
- **Normal layers**: Any layer name
- **Frangible layers**: Containing `frangible`, `light`, `break`, `seal`, `weak`
- **Construction layers**: Containing `construction`, `const`, `guide`, `reference`, `ref` (ignored)

#### 3. Filename-Based (Fallback)
When colors/layers don't specify weld type, filenames are checked:
- **Normal welds**: `main_welds.dxf`, `structure.svg`
- **Frangible welds**: `frangible_seals.dxf`, `light_welds.svg`, `break_points.dxf`

### Advanced Features
- **Configurable Parameters**: TOML-based configuration for temperatures, heights, and timing
- **Multi-Pass Welding**: Configurable initial and final dot spacing
- **Optimized Z Movement**: Separate weld move height for faster intra-path welding
- **Chamber Temperature Control**: Prusa Core One chamber heating
- **Animation Output**: Generates animated SVG showing the welding sequence
- **Proper G-code Structure**: Includes heating, cooling, and safety procedures
- **Error Handling**: Comprehensive error reporting and recovery
- **Statistics Collection**: Processing metrics and validation results

## Installation

### From PyPI
```bash
pip install microweldr
```

### With DXF Support
```bash
pip install microweldr[dxf]  # Includes ezdxf for DXF processing
```

### From Source
```bash
git clone https://github.com/retospect/microweldr.git
cd microweldr
poetry install --with dev
```

## Quick Start

### Basic Usage
```bash
# Convert single SVG file
microweldr convert design.svg -o output.gcode

# Convert DXF file with unit validation
microweldr convert drawing.dxf -o output.gcode

# Process multiple files (SVG + DXF)
microweldr convert main_welds.dxf frangible_seals.dxf design.svg -o combined.gcode

# Validate files before processing
microweldr validate *.svg *.dxf
```

### Fusion 360 Workflow
Perfect for CAD-based microfluidics design:

1. **Design in Fusion 360**: Create your microfluidic channels and seals
2. **Export two DXF files**:
   - `main_welds.dxf` - Primary structural welds
   - `frangible_seals.dxf` - Breakaway seals for filling ports
3. **Process both files**: `microweldr convert main_welds.dxf frangible_seals.dxf -o device.gcode`
4. **Print**: Load G-code on Prusa Core One

### Configuration

Create `microweldr_config.toml` for custom settings:

```toml
[printer]
bed_x = 250
bed_y = 220
bed_z = 270
chamber_temperature = 45

[movement]
move_height = 5.0  # mm - height for safe movement between paths
weld_move_offset = 0.5  # mm - offset above weld height for intra-path movement (faster welding)
frame_height = 10.0  # mm - height for frame drawing (clearance check)
travel_speed = 3000  # mm/min - travel speed for movements
z_speed = 600  # mm/min - optimized Z speed (near maximum safe limit for Core One)

[normal_welds]
weld_height = 0.020          # mm - compression depth
weld_temperature = 160       # °C - nozzle temperature
weld_time = 0.1             # seconds - dwell time
dot_spacing = 0.5           # mm - final spacing
initial_dot_spacing = 6.0   # mm - first pass spacing
cooling_time_between_passes = 2.0  # seconds

[frangible_welds]
weld_height = 0.020          # mm - same precision
weld_temperature = 160       # °C - same temperature
weld_time = 0.3             # seconds - longer for weaker bond
dot_spacing = 0.5           # mm - same density
initial_dot_spacing = 3.6   # mm - closer first pass
cooling_time_between_passes = 1.5  # seconds

[output]
gcode_extension = ".gcode"
animation_extension = "_animation.svg"
```

## Command Reference

### Convert Command
```bash
microweldr convert [OPTIONS] INPUT_FILES...

Options:
  -o, --output PATH     Output G-code file
  -c, --config PATH     Configuration file
  --no-animation       Skip animation generation
  --chamber-temp FLOAT Chamber temperature override
```

### Validate Command
```bash
microweldr validate [OPTIONS] INPUT_FILES...

Options:
  -c, --config PATH     Configuration file
  --detailed           Show detailed validation info
```

## File Format Details

### SVG Support
- **Elements**: `<path>`, `<line>`, `<circle>`, `<rect>`, `<g>`, `<use>`
- **Attributes**: `stroke`, `class`, `id` for weld type detection
- **Namespaces**: Handles standard SVG namespaces
- **Definitions**: Processes `<defs>` and referenced elements

### DXF Support
- **Entities**: LINE, ARC, CIRCLE, POLYLINE, LWPOLYLINE
- **Units**: Must be millimeters (validated automatically)
- **Layers**: Used for weld type and construction detection
- **Coordinate System**: Preserves original coordinates

### Weld Type Examples

#### Filename-Based Detection
```bash
# These filenames automatically detect frangible welds:
microweldr convert frangible_seals.dxf      # → Frangible
microweldr convert light_connections.svg    # → Frangible
microweldr convert break_points.dxf         # → Frangible
microweldr convert seal_layer.svg           # → Frangible

# These default to normal welds:
microweldr convert main_structure.dxf       # → Normal
microweldr convert primary_welds.svg        # → Normal
```

#### Layer-Based Detection (DXF)
```
Layer "main_welds"        → Normal welds
Layer "frangible_seals"   → Frangible welds
Layer "construction"      → Ignored
Layer "break_points"      → Frangible welds
```

## Development

### Running Tests
```bash
poetry run pytest                    # All tests
poetry run pytest tests/unit/       # Unit tests only
poetry run pytest -v               # Verbose output
```

### Code Quality
```bash
poetry run black .                  # Format code
poetry run bandit -r microweldr/   # Security check
poetry run pre-commit run --all-files  # All checks
```

### Building
```bash
poetry build                        # Build wheel and source
poetry install dist/*.whl          # Install local build
```

## Examples

### Multi-File Processing
```bash
# Process structural and frangible welds together
microweldr convert \
  main_structure.dxf \
  frangible_seals.dxf \
  alignment_marks.svg \
  -o complete_device.gcode \
  --chamber-temp 50
```

### Validation Workflow
```bash
# Validate all design files
microweldr validate *.dxf *.svg --detailed

# Convert if validation passes
microweldr convert *.dxf *.svg -o final_device.gcode
```

## Troubleshooting

### DXF Issues
- **Unit Error**: Ensure DXF uses millimeters in drawing units
- **No Entities**: Check that layers contain supported entities (lines, arcs, circles)
- **Construction Layers**: Rename layers to avoid construction keywords

### SVG Issues
- **No Paths**: Ensure elements have `stroke` attribute (not just `fill`)
- **Complex Paths**: Curves are approximated with line segments
- **Nested Groups**: Deep nesting may affect processing

### Weld Type Detection
- **Wrong Type**: Check filename, layer names, or SVG colors
- **All Normal**: Add frangible keywords to filenames or layers
- **All Frangible**: Remove frangible keywords from filenames

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make changes with tests: `poetry run pytest`
4. Format code: `poetry run black .`
5. Submit pull request

## License

MIT License - see LICENSE file for details.

## Changelog

### Version 5.3.0 (Latest)
- **NEW**: Full DXF file support with ezdxf integration
- **NEW**: Multi-file processing (mix SVG and DXF)
- **NEW**: Filename-based weld type detection as fallback
- **BREAKING**: Renamed "light_welds" to "frangible_welds" in all configs
- **IMPROVED**: Modular CLI architecture with better error handling
- **IMPROVED**: Publisher-subscriber file processing framework
- **IMPROVED**: Comprehensive test coverage (33 tests)
- **IMPROVED**: Structured data models with validation

### Version 5.2.x
- Enhanced SVG processing
- Animation improvements
- Configuration validation

### Version 5.1.x
- Initial public release
- Basic SVG to G-code conversion
- Prusa Core One optimization
