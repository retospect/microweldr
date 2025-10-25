# Temperature Control Commands

MicroWeldr provides convenient temperature control commands to manage your printer's heating elements before and after welding operations.

## Commands Overview

### `temp-on` - Heat Up Printer
Turn on printer temperatures for welding operations.

### `temp-off` - Cool Down Printer  
Turn off printer temperatures for safe handling.

## Usage Examples

### Basic Temperature Control

```bash
# Heat up printer to welding temperatures (uses config defaults)
microweldr temp-on

# Cool down printer to safe temperatures  
microweldr temp-off

# Force operations without confirmation
microweldr temp-on --force
microweldr temp-off --force
```

### Custom Temperature Settings

```bash
# Set specific temperatures
microweldr temp-on --bed-temp 65 --nozzle-temp 110 --chamber-temp 40

# Wait for temperatures to be reached
microweldr temp-on --wait

# Set custom cooldown temperature
microweldr temp-off --cooldown-temp 30
```

### Selective Temperature Control

```bash
# Only control bed temperature
microweldr temp-off --bed-only

# Only control nozzle temperature  
microweldr temp-off --nozzle-only

# Only control chamber temperature
microweldr temp-off --chamber-only
```

### Configuration Files

```bash
# Use custom configuration files
microweldr temp-on --config custom_config.toml --secrets-config custom_secrets.toml
```

## Command Reference

### `temp-on` Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--secrets-config` | `-s` | Path to secrets configuration file | `secrets.toml` |
| `--config` | `-c` | Path to main configuration file | `config.toml` |
| `--bed-temp` | `-b` | Bed temperature in °C | From config |
| `--nozzle-temp` | `-n` | Nozzle temperature in °C | From config |
| `--chamber-temp` | `-ch` | Chamber temperature in °C | From config |
| `--wait` | `-w` | Wait for temperatures to be reached | False |
| `--force` | `-f` | Skip confirmation prompts | False |
| `--verbose` | `-v` | Enable verbose output | False |
| `--quiet` | `-q` | Suppress non-error output | False |

### `temp-off` Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--secrets-config` | `-s` | Path to secrets configuration file | `secrets.toml` |
| `--config` | `-c` | Path to main configuration file | `config.toml` |
| `--bed-only` | `-b` | Only turn off bed temperature | False |
| `--nozzle-only` | `-n` | Only turn off nozzle temperature | False |
| `--chamber-only` | `-ch` | Only turn off chamber temperature | False |
| `--cooldown-temp` | `-t` | Target cooldown temperature in °C | From config |
| `--force` | `-f` | Skip confirmation prompts | False |
| `--verbose` | `-v` | Enable verbose output | False |
| `--quiet` | `-q` | Suppress non-error output | False |

## Safety Features

### Temperature Validation
- All temperatures are validated against safety limits (20-120°C)
- Bed temperature limited to 80°C for safety
- Chamber temperature properly controlled for Core One

### Printer State Checking
- Commands check if printer is currently printing
- Warns user before making changes during active prints
- Requires confirmation for potentially disruptive operations

### Confirmation Prompts
- Interactive confirmation before temperature changes
- Shows exactly what temperatures will be set
- Can be bypassed with `--force` flag for automation

## Typical Workflows

### Pre-Welding Setup
```bash
# 1. Heat up printer
microweldr temp-on --wait

# 2. Perform welding operation
microweldr weld design.svg --submit-to-printer

# 3. Cool down after welding
microweldr temp-off
```

### Maintenance Mode
```bash
# Cool down for safe maintenance
microweldr temp-off --cooldown-temp 25 --force

# Heat up for testing
microweldr temp-on --bed-temp 60 --nozzle-temp 100
```

### Emergency Cooldown
```bash
# Immediate cooldown without confirmation
microweldr temp-off --force --cooldown-temp 20
```

## G-code Generation

The temperature control commands generate and execute G-code:

### Heating Commands (`temp-on`)
```gcode
; MicroWeldr Temperature Heating
M140 S60 ; Set bed temperature  
M104 S100 ; Set nozzle temperature
M141 S35 ; Set chamber temperature

; Optional: Wait for temperatures (with --wait)
M190 S60 ; Wait for bed temperature
M109 S100 ; Wait for nozzle temperature  
M191 S35 ; Wait for chamber temperature
```

### Cooling Commands (`temp-off`)
```gcode
; MicroWeldr Temperature Cooldown
M140 S50 ; Set bed temperature
M104 S50 ; Set nozzle temperature
M141 S0 ; Turn off chamber heating
```

## Integration with Other Commands

Temperature control integrates seamlessly with other MicroWeldr commands:

```bash
# Complete workflow with temperature control
microweldr temp-on --wait && \
microweldr weld design.svg --submit-to-printer && \
microweldr temp-off
```

## Troubleshooting

### Common Issues

**"Printer communication error"**
- Check printer is powered on and connected
- Verify `secrets.toml` configuration
- Ensure PrusaLink is enabled on printer

**"Temperature validation failed"**
- Check temperature values are within safe limits (20-120°C)
- Verify configuration file has valid temperature settings

**"Printer is currently printing"**
- Command detected active print job
- Use `--force` to override (not recommended during prints)
- Wait for print to complete or pause it first

### Configuration Requirements

Ensure your `config.toml` has temperature settings:
```toml
[temperatures]
bed_temperature = 60
nozzle_temperature = 100
chamber_temperature = 35
cooldown_temperature = 50
use_chamber_heating = true
```

Ensure your `secrets.toml` has printer connection:
```toml
[prusalink]
host = "192.168.1.100"
username = "maker"
password = "your_password"
```

## Safety Notes

⚠️ **Important Safety Considerations:**

1. **Always allow proper cooldown** before handling printed parts
2. **Monitor temperature changes** - don't leave printer unattended during heating
3. **Use appropriate cooldown temperatures** - too low may cause thermal shock
4. **Check printer state** before temperature changes during prints
5. **Verify configuration** - incorrect temperatures can damage printer or parts

The temperature control commands are designed with safety in mind, but always exercise caution when working with heated printer components.
