# MicroWeldr Interactive UI

The `microweldr-ui` command provides a terminal-based curses interface for interactive plastic welding operations.

## Features

### 🖥️ Real-time Status Display
- **File Information**: Shows loaded SVG file, generated G-code, dimensions, and weld path count
- **Printer Status**: Live connection status, temperatures, position, and last update time
- **Bounds Information**: X/Y extents and borders of the welding pattern

### 🎛️ Interactive Controls

**1. Calibrate** ✅/⏸️
- Performs printer homing (G28) and auto bed leveling (G29)
- Shows checkmark when calibration is complete
- Required before welding operations

**2. Plate Heater Control** 🔥/❄️
- Toggle bed heater ON/OFF at 60°C (configurable)
- Real-time temperature display
- Press '2' to toggle heater state

**3. Bounding Box Preview** 📐
- Draws the outline of welding pattern at fly height (5mm)
- Helps visualize the welding area before starting
- Useful for checking positioning and clearance

**4. Load/Unload Plate** 📤
- Drops the print bed 5cm for easy film loading/unloading
- Provides safe access to the welding surface
- Returns to normal height automatically

**5. Start Print** ▶️
- Executes the welding G-code
- Runs only the stamping operations (no calibration)
- Requires SVG file to be loaded and converted

**6. Settings** ⚙️
- Access configuration options (future feature)
- Modify welding parameters
- Regenerate G-code with new settings

## Usage

### Basic Usage
```bash
# Launch UI without file
microweldr-ui

# Launch with SVG file pre-loaded
microweldr-ui path/to/design.svg

# Specify custom config
microweldr-ui design.svg --config my_config.toml
```

### Workflow Example
1. **Load SVG**: `microweldr-ui my_design.svg`
2. **Check Connection**: Verify printer shows "✅ Connected"
3. **Calibrate**: Press `1` to home and level the bed
4. **Heat Bed**: Press `2` to start heating to 60°C
5. **Preview**: Press `3` to see bounding box outline
6. **Load Film**: Press `4` to lower bed for film loading
7. **Start Welding**: Press `5` to begin the welding process

### Keyboard Controls
- **Number keys (1-6)**: Execute menu functions
- **'r'**: Refresh display
- **'q'**: Quit application

## Requirements

### Hardware
- Prusa Core One 3D printer
- PrusaLink enabled and accessible
- Network connection to printer

### Software
- Python 3.8+
- Curses support (built-in on Unix/Linux/macOS)
- Valid `secrets.toml` file for printer connection

### Configuration Files

**secrets.toml** (required for printer connection):
```toml
[prusalink]
host = "192.168.1.100"  # Your printer's IP
username = "maker"
password = "your-lcd-password"  # From printer display
```

**config.toml** (optional, auto-created if missing):
```toml
[printer]
bed_width = 250
bed_height = 220
bed_depth = 270

[welding]
default_temp = 200
default_bed_temp = 60
weld_time = 2.0
```

## Status Indicators

### Connection Status
- ✅ **Connected**: Printer is reachable and responding
- ❌ **Disconnected**: Cannot connect to printer
- **Last Update**: Shows seconds since last status refresh

### Temperature Display
- **Bed Temp**: Current/Target temperature (e.g., "45.2°C / 60.0°C")
- Updates every 2 seconds when connected

### Position Display
- **Position**: Current X/Y/Z coordinates
- Updates in real-time during operations

## Troubleshooting

### Connection Issues
1. Check printer IP address in `secrets.toml`
2. Verify PrusaLink is enabled on printer
3. Test network connectivity: `ping <printer-ip>`
4. Check LCD password matches `secrets.toml`

### UI Display Issues
- Ensure terminal supports curses (most Unix terminals do)
- Try resizing terminal window if display is garbled
- Use 'r' key to refresh display

### File Loading Problems
- Verify SVG file exists and is readable
- Check SVG contains valid weld elements with `data-weld-type` attributes
- Review `microweldr_ui.log` for detailed error messages

## Logging

The UI logs all operations to `microweldr_ui.log` in the current directory:
- Printer commands and responses
- File loading operations
- Error messages and debugging info
- Status updates and user actions

## Safety Features

- **Confirmation prompts** for destructive operations
- **Status validation** before executing commands
- **Error handling** with graceful degradation
- **Log file** for troubleshooting and audit trail

## Future Enhancements

- Settings screen for live configuration editing
- Multi-file job queue
- Print progress visualization
- Temperature graphing
- Custom G-code injection
- Printer camera integration
