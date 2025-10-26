# Printer Connection Configuration

The MicroWeldr UI supports two methods for connecting to your Prusa printer.

## Method 1: secrets.toml (Recommended)

Create a `secrets.toml` file for secure credential storage:

```toml
[prusalink]
host = "192.168.1.100"  # Your printer's IP address
username = "maker"      # Usually "maker"
password = "your-lcd-password"  # Password from printer's LCD display
timeout = 30            # Optional: connection timeout in seconds
```

**Advantages:**
- ✅ Secure credential storage
- ✅ Separate from main config
- ✅ Can be excluded from version control
- ✅ Standard MicroWeldr format

## Method 2: config.toml (Convenient)

Add printer settings to your main `config.toml`:

```toml
[printer]
# Prusa Core One specific settings
bed_size_x = 250.0
bed_size_y = 220.0
max_z_height = 270.0

# PrusaLink connection settings
host = "192.168.1.100"  # Your printer's IP address
username = "maker"      # Usually "maker"
password = "your-lcd-password"  # Password from printer's LCD display
timeout = 30            # Optional: connection timeout in seconds

[temperatures]
bed_temperature = 60    # Your preferred bed temperature
# ... rest of config
```

**Advantages:**
- ✅ Single configuration file
- ✅ All settings in one place
- ✅ Easy to manage

## Connection Priority

The UI tries connection methods in this order:

1. **secrets.toml** (if file exists)
2. **config.toml [printer] section** (if settings present)
3. **No connection** (graceful degradation)

## Finding Your Printer Information

### Printer IP Address
- Check your router's admin panel
- Look on printer's LCD: Settings → Network → IP Address
- Use network scanner: `nmap -sn 192.168.1.0/24`

### LCD Password
- On your Prusa printer: Settings → Network → PrusaLink
- The password will be displayed on screen
- Usually 6-8 characters

## Usage Examples

```bash
# Use with secrets.toml
microweldr-ui examples/square-circle.svg

# Use with config.toml containing printer settings
microweldr-ui examples/square-circle.svg -c my-config.toml

# Use specific config file
microweldr-ui examples/square-circle.svg -c examples/config.toml
```

## Troubleshooting

### Connection Issues
1. Verify printer IP address is correct
2. Check that PrusaLink is enabled on printer
3. Confirm LCD password matches configuration
4. Test network connectivity: `ping <printer-ip>`

### UI Shows "Disconnected"
- Check `microweldr_ui.log` for detailed error messages
- Verify configuration file format (valid TOML)
- Ensure printer is powered on and connected to network

### Security Note
If using `config.toml` for printer connection, be careful not to commit passwords to version control. Consider using `secrets.toml` for production environments.
