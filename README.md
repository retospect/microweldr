# SVG to G-code Welder

A Python package that converts SVG files to Prusa Core One G-code for plastic "spot" welding applications. The package processes SVG vector graphics and generates G-code that creates weld spots along the paths without extruding any plastic material.

**Optimized for Prusa Core One**: Includes chamber temperature control (M141/M191), proper bed dimensions (250×220×270mm), CoreXY-specific settings, and **layed back mode** for when your printer is chillin' on its back (door pointing up).

This allows for rapid microfluidics prototyping with a 3d printer.
While the edges are not as smooth as a laser weld, the 3d printer is more available than a laser welder. 

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
- **PrusaLink Integration**: Direct G-code submission to Prusa MINI via PrusaLink API

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

## Installation

### **From PyPI (Recommended)**
```bash
# Basic installation
pip install svg-welder

# With optional validation features
pip install svg-welder[validation]

# With all features (validation + development tools)
pip install svg-welder[validation,dev]
```

### **Development Installation**
```bash
# Clone repository
git clone <repository-url>
cd PrusaWelder

# Install with poetry (recommended for development)
poetry install

# Or install with pip (editable mode)
pip install -e .

# Install with validation features
pip install -e .[validation]

# Run tests
make test
```

## Available Commands

After installation, these console commands are available:

### **Main Commands**
```bash
# SVG to G-code conversion (all equivalent)
svg-welder input.svg -o output.gcode
svg2gcode input.svg -o output.gcode  
prusa-welder input.svg -o output.gcode

# Print with automatic monitoring
svg-welder input.svg --submit-to-printer --monitor
svg-welder input.svg --submit-to-printer --monitor --monitor-mode pipetting
```

### **Unified Printer Control**
```bash
# All-in-one printer control tool
printer-control status                    # Check printer status
printer-control status --verbose         # Detailed status
printer-control monitor                   # Monitor current print
printer-control monitor --mode layed-back --interval 20
printer-control stop                      # Stop current print
printer-control stop --force             # Force stop
printer-control test                      # Test connection

# Test PrusaLink connection
test-prusalink
```

### **Legacy Commands (Deprecated)**
```bash
# These still work but use printer-control instead
monitor-print --mode pipetting
printer-status --verbose  
stop-print --force
```

## Configuration

Edit `config.toml` to adjust welding parameters:

```toml
[temperatures]
bed_temperature = 80        # °C
nozzle_temperature = 200    # °C for normal welds
chamber_temperature = 35    # °C - Core One chamber temperature
use_chamber_heating = false # Set to false to disable chamber heating (useful if sensor is not working)

[movement]
move_height = 5.0          # mm - safe travel height
weld_height = 0.2          # mm - welding height

[normal_welds]
weld_temperature = 200     # °C
dot_spacing = 0.3          # mm - final desired spacing
initial_dot_spacing = 8.0  # mm - spacing for first pass (wider)
cooling_time_between_passes = 2.0  # seconds - cooling between passes

[light_welds]
weld_temperature = 180     # °C - lower temperature
spot_dwell_time = 0.3      # seconds - shorter time
dot_spacing = 0.3          # mm - final desired spacing
initial_dot_spacing = 12.0 # mm - spacing for first pass (wider)
cooling_time_between_passes = 1.5  # seconds - cooling between passes

[nozzle]
outer_diameter = 0.4        # mm - nozzle outer diameter
inner_diameter = 0.2        # mm - nozzle inner diameter (opening)

[animation]
time_between_welds = 0.1    # seconds - time between weld points in animation
pause_time = 3.0            # seconds - how long pause messages are displayed
min_animation_duration = 10.0  # seconds - minimum total animation time
```

## Layed Back Mode (⚠️ EXPERIMENTAL - NOT WORKING YET)

**⚠️ WARNING: Layed back mode is currently under development and does not work properly. Use standard upright mode for reliable operation.**

The SVG welder was designed to support "layed back printer operation" - when your printer is chillin' on its back with the door pointing up for easy access to microfluidic devices. However, this mode is currently experiencing technical issues.

### **Known Issues:**
- ❌ Calibration conflicts with manual positioning
- ❌ Z-axis homing issues when printer is on its back
- ❌ Coordinate system needs adjustment for inverted orientation
- ❌ Safety features need refinement for this configuration

### **Current Recommendation:**
```toml
[printer]
layed_back_mode = false  # Use standard upright mode for now
```

### **Future Development:**
Once the issues are resolved, layed back mode will provide:
- Easy access for pipetting and microfluidic operations
- Manual positioning with trusted coordinates
- Optimized G-code for inverted printer orientation

### **📍 Manual Positioning Required**
**IMPORTANT**: Before starting any print (your printer is trusting you completely!):
1. **Manually position** the print head to the **rear right corner** of the bed
2. **Set Z-height manually** - position nozzle at desired starting height above bed
3. **All positioning trusted** - the printer is chillin' and trusts your complete setup
4. **G92 X0 Y0 Z0** sets all axes as origin (no automatic homing performed)

### **🛡️ Safety Features for Layed Back Mode**
- ✅ **No automatic homing** (prevents all endpoint errors when printer is on its back)
- ✅ **Fully manual positioning** (complete trust in your setup for all axes)
- ✅ **No bed leveling** (too risky when printer is layed back)
- ✅ **Slower movements** (3000 mm/min travel, 150 mm/min Z-axis - no rush!)
- ✅ **Disabled stepper timeout** (M84 S0 - printer stays relaxed)
- ✅ **Gentle Z positioning** (slow movements to avoid crashes)

### **⚙️ Standard Mode (For Uptight Printers)**
Set `layed_back_mode = false` for normal upright printer operation with full homing and bed leveling.

## PrusaLink Configuration

To enable direct G-code submission to your Prusa Core One, you need to configure PrusaLink access:

### 1. Setup PrusaLink on Your Printer
- Enable PrusaLink on your Prusa Core One (should be enabled by default on newer firmware)
- Connect your printer to your network (WiFi or Ethernet)
- Note your printer's IP address (check printer display or router) or find its `.local` hostname

### 2. Find Your Printer's Address
You can use either:
- **IP Address**: Check your printer's display or router's connected devices
- **.local hostname**: Usually `prusacoreone.local` or similar (check printer display for exact name)

### 3. Get Authentication Credentials
**Choose ONE method:**

**Method A: LCD Password (Recommended - Easier)**
- Check your printer's LCD display for the password (usually shown in network settings)
- No web interface setup needed

**Method B: API Key (Alternative)**
- Open your printer's web interface: `http://YOUR_PRINTER_IP` or `http://prusacoreone.local`
- Go to Settings → API
- Generate or copy your API key

### 4. Configure secrets.toml
Copy the template and fill in your details:
```bash
cp secrets.toml.template secrets.toml
```

Edit `secrets.toml`:
```toml
[prusalink]
host = "192.168.1.100"         # Your printer's IP address
# OR use .local hostname:
# host = "prusacoreone.local"  # More convenient, doesn't change with DHCP

# Method A: LCD Password (recommended)
username = "maker"             # Default username (usually "maker")
password = "your-lcd-password" # Password from printer's LCD display

# Method B: API Key (alternative - comment out Method A if using this)
# username = "maker"
# api_key = "your-api-key-here"  # From printer's web interface

default_storage = "local"      # "local" or "usb"
auto_start_print = true        # Whether to start printing immediately
timeout = 30                   # Connection timeout in seconds
```

### 5. Test Connection
```bash
python test_prusalink.py
```

### 6. Submit G-code to Printer
```bash
# Generate and submit G-code (starts printing immediately with default config)
svg-welder input.svg --submit-to-printer

# Force immediate printing (overrides config)
svg-welder input.svg --submit-to-printer --auto-start-print

# Use USB storage instead of local
svg-welder input.svg --submit-to-printer --printer-storage usb

# Upload without starting (override config default)
svg-welder input.svg --submit-to-printer --no-auto-start

# Queue the file for later printing (clearer intent)
svg-welder input.svg --submit-to-printer --queue-only
```

## Printing Modes

The SVG welder supports three different printing modes when submitting to your printer:

### **🚀 Immediate Printing** (Default)
Files are uploaded and printing starts immediately:
```bash
svg-welder input.svg --submit-to-printer
# or force immediate printing:
svg-welder input.svg --submit-to-printer --auto-start-print
```

### **📋 Queue Mode**
Files are uploaded and queued for later printing:
```bash
svg-welder input.svg --submit-to-printer --queue-only
```
Use this when:
- You want to prepare multiple files
- The printer is currently busy
- You want to review the file before printing

### **📁 Upload Only**
Files are uploaded without any automatic behavior:
```bash
svg-welder input.svg --submit-to-printer --no-auto-start
```

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
- `--no-validation`: Skip validation steps
- `--verbose, -v`: Enable verbose output
- `--weld-sequence`: Welding sequence algorithm (linear, binary, farthest, skip)
- `--submit-to-printer`: Submit G-code to PrusaLink after generation
- `--secrets-config`: Path to secrets configuration file (default: secrets.toml)
- `--printer-storage`: Target storage on printer (local or usb)
- `--auto-start-print`: Automatically start printing after upload (overrides config)
- `--no-auto-start`: Do not start printing after upload (overrides config)
- `--queue-only`: Queue the file without starting (clearer intent than --no-auto-start)

## SVG Requirements

### Coordinate System
- SVG coordinates should be in millimeters
- Origin (0,0) corresponds to the printer bed origin

### Element Processing Order
- Elements are processed in order of their SVG ID attributes
- IDs with numeric components are sorted numerically
- Elements without IDs are processed last

### Color-Based Weld Types

The SVG welder supports different weld types based on element colors:

- **Black elements** (default): Normal welding with full temperature and multi-pass
- **Blue elements**: Light welding with reduced temperature  
- **Red elements**: Stop points with custom pause messages
- **Pink/Magenta elements**: Pipetting stops for microfluidic device filling

Colors can be specified via:
- `stroke` attribute
- `fill` attribute  
- `style` attribute (CSS format)

### Pipetting Stops for Microfluidics 🧪

**Pink/Magenta elements** create pipetting stops specifically designed for microfluidic device operation:

**Supported Colors:**
- `magenta`, `pink`, `fuchsia`
- `#ff00ff`, `#f0f`, `#ff69b4`, `#ffc0cb`
- `rgb(255,0,255)`, `rgb(255,105,180)`, `rgb(255,192,203)`

**Use Cases:**
- **Reagent filling**: Pause to add reagents to pouches
- **Sample injection**: Stop for sample introduction
- **Buffer addition**: Add buffers or washing solutions
- **Collection**: Insert collection tubes or containers

**Example:**
```xml
<!-- Pipetting stop with custom message -->
<circle cx="60" cy="50" r="8" fill="magenta" 
        title="Fill with 10μL reagent A using micropipette"/>
```

### Custom Pause Messages

Both red elements (stop points) and pink elements (pipetting stops) can include custom messages displayed on the printer screen. Messages can be specified using any of these SVG attributes (in order of priority):

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

## Sending G-code to Prusa Printer

Once you've generated the G-code file, you can send it to your Prusa Core One printer using several methods:

### Method 1: PrusaConnect (Recommended)
**Best for**: Remote monitoring and cloud-based printing

1. **Upload via Web Interface**:
   - Open [connect.prusa3d.com](https://connect.prusa3d.com) in your browser
   - Log in to your Prusa account
   - Select your printer from the dashboard
   - Click "Upload G-code" or drag and drop your `.gcode` file
   - The file will be transferred to your printer automatically

2. **Start the Print**:
   - The G-code will appear in your printer's file list
   - Select the file on the printer's touchscreen
   - Press "Print" to begin the welding process
   - Monitor progress remotely via PrusaConnect dashboard

### Method 2: USB Drive
**Best for**: Offline printing and large files

1. **Prepare USB Drive**:
   - Use a FAT32 formatted USB drive
   - Copy your `.gcode` file to the root directory or a folder
   - Safely eject the USB drive from your computer

2. **Load on Printer**:
   - Insert the USB drive into the printer's USB port
   - Navigate to "Print from USB" on the touchscreen
   - Browse and select your G-code file
   - Press "Print" to start welding

### Method 3: PrusaLink (Local Network)
**Best for**: Local network printing without cloud dependency

1. **Access PrusaLink Interface**:
   - Find your printer's IP address (Settings → Network → Wi-Fi Info)
   - Open `http://[printer-ip-address]` in your browser
   - Or use the Prusa app to connect locally

2. **Upload G-code**:
   - Click "Upload G-code" in the PrusaLink interface
   - Select your `.gcode` file
   - The file transfers directly to the printer over your local network

3. **Start Printing**:
   - Select the uploaded file from the printer's interface
   - Begin the welding process

### Pre-Print Checklist

Before starting the welding process:

#### **Printer Preparation**
- [ ] **Clean the bed**: Remove any residue from previous prints
- [ ] **Check nozzle**: Ensure nozzle is clean and appropriate for welding
- [ ] **Verify temperatures**: Confirm bed and nozzle temperature settings match your plastic
- [ ] **Load filament**: Even though no extrusion occurs, some printers require filament to be loaded

#### **Material Preparation**
- [ ] **Plastic sheets ready**: Have your plastic sheets cut to size and ready to insert
- [ ] **Workspace clear**: Ensure adequate ventilation for plastic welding
- [ ] **Safety equipment**: Have appropriate safety gear (ventilation, eye protection)

#### **G-code Verification**
- [ ] **Review animation**: Check the generated `*_animation.svg` file to verify weld pattern
- [ ] **Validate settings**: Confirm temperatures and timing are appropriate for your materials
- [ ] **Check pause points**: Note where manual intervention will be required

### During the Welding Process

#### **Initial Setup Phase**
1. **Homing**: Printer will home all axes automatically
2. **Bed Leveling**: If enabled, automatic bed leveling will run (G29)
3. **Heating**: Bed and nozzle will heat to specified temperatures
4. **User Pause**: Printer will pause with message "Insert plastic sheets and press continue"

#### **Welding Phase**
1. **Multi-pass welding**: Printer follows the programmed sequence
2. **Pause points**: Respond to custom pause messages (red elements in SVG)
3. **Monitor progress**: Watch for proper weld formation and material behavior
4. **Temperature management**: Printer automatically manages heating between weld types

#### **Completion**
1. **Cooldown**: Printer will automatically cool down nozzle and bed
2. **Homing**: Final homing sequence
3. **Completion message**: Printer indicates welding is complete

### Troubleshooting Transfer Issues

#### **File Not Recognized**
- Ensure file has `.gcode` extension
- Check file size (some methods have limits)
- Verify G-code syntax with a G-code viewer

#### **Connection Problems**
- **PrusaConnect**: Check internet connection and printer online status
- **PrusaLink**: Verify printer and computer are on same network
- **USB**: Try different USB drive or reformat as FAT32

#### **Upload Failures**
- Check available storage space on printer
- Try smaller file sizes or reduce complexity
- Restart printer network connection if needed

### File Management Tips

- **Organize files**: Use descriptive names like `project_name_v1.gcode`
- **Keep backups**: Save both SVG source and generated G-code files
- **Version control**: Include date/version in filenames for tracking
- **Clean up**: Regularly remove old files from printer storage

### Safety Reminders

- **Never leave unattended**: Always supervise the welding process
- **Emergency stop**: Know how to use the printer's emergency stop function
- **Ventilation**: Ensure adequate ventilation for plastic welding fumes
- **Temperature safety**: Be cautious around heated components

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
python -m venv venv
source venv/bin/activate  # macOS/Linux (venv\Scripts\activate on Windows)
pip install -e .[validation,dev]

# Run examples (with venv activated)
svg-welder examples/example.svg
svg-welder examples/comprehensive_sample.svg
svg-welder examples/example.svg --verbose

# Alternative methods
python -m svg_welder.cli.main examples/example.svg
python svg_welder/cli/main.py examples/example.svg
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
# Using Python module (with virtual environment activated)
python -m svg_welder.cli.main examples/example.svg

# Direct script execution (with virtual environment activated)
python svg_welder/cli/main.py examples/example.svg

# With custom configuration
svg-welder examples/example.svg -c my_config.toml
```

## License

This project is open source. Use at your own risk and ensure proper safety precautions when operating 3D printing equipment.
