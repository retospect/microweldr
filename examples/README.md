# SVG Welder Examples

This directory contains example SVG files and configurations to help you get started with the SVG Welder for Prusa Core One plastic welding.

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/your-repo/PrusaWelder.git
cd PrusaWelder

# Install the package
pip install -e .

# Or install from PyPI (when available)
pip install svg-welder
```

### Basic Usage

```bash
# Generate G-code from an example
svg-welder examples/example.svg

# Generate and submit to printer
svg-welder examples/example.svg --submit-to-printer

# Use custom config
svg-welder examples/example.svg --config examples/config.toml
```

## 📁 Example Files

### 🔧 Basic Examples

**`example.svg`** - Simple welding demonstration
- Basic lines and shapes
- Good for first-time users
- ~30 weld points

**`pause_examples.svg`** - Interactive welding with pauses
- Demonstrates pause functionality
- Custom pause messages
- User interaction during welding

### 🔬 Advanced Examples

**`comprehensive_sample.svg`** - Full-featured demonstration
- All weld types (normal, light, stop, pipette)
- Complex geometries
- Professional workflow example

**`pipetting_example.svg`** - Microfluidics application
- Pipette stops for liquid handling
- Precise positioning
- Laboratory workflow

**`calibration_test.svg`** - Parameter optimization
- 48 test conditions (6 temps × 2 dwell times × 4 compressions)
- Scientific parameter validation
- Diagonal orientation reference

## ⚙️ Configuration

**`config.toml`** - Optimized settings template
- Calibration-validated parameters
- 130°C temperature (optimal)
- 0.1s dwell time (fast & effective)
- 20µm compression (light touch)
- 600 mm/min Z-speed (maximum safe)

## 🎯 Recommended Workflow

### 1. Start Simple
```bash
svg-welder examples/example.svg
```

### 2. Test Parameters
```bash
svg-welder examples/calibration_test.svg --submit-to-printer
```

### 3. Analyze Results
- Examine the 48 test conditions
- Identify optimal parameters for your material
- Update config.toml with best settings

### 4. Production Use
```bash
svg-welder your_design.svg --config examples/config.toml
```

## 🔬 Calibration Test Details

The `calibration_test.svg` provides comprehensive parameter testing:

**Temperature Range:** 130°C to 180°C (10°C increments)
**Dwell Times:** 0.1s and 0.2s
**Compression Depths:** 20µm, 40µm, 60µm, 80µm
**Total Tests:** 48 conditions + 1 orientation reference

**Grid Layout:**
```
       130°C  140°C  150°C  160°C  170°C  180°C
0.1s   20µm   20µm   20µm   20µm   20µm   20µm
       40µm   40µm   40µm   40µm   40µm   40µm
       60µm   60µm   60µm   60µm   60µm   60µm
       80µm   80µm   80µm   80µm   80µm   80µm

0.2s   20µm   20µm   20µm   20µm   20µm   20µm
       40µm   40µm   40µm   40µm   40µm   40µm
       60µm   60µm   60µm   60µm   60µm   60µm
       80µm   80µm   80µm   80µm   80µm   80µm
```

## 🎨 Creating Your Own SVGs

### Weld Types (by stroke color)
- **Black:** Normal welds (130°C, 0.1s, 20µm)
- **Blue:** Light welds (180°C, 0.3s, 20µm)
- **Red:** Stop points (pause for user interaction)
- **Pink/Magenta:** Pipette stops (for liquid handling)

### Custom Parameters
Add custom attributes to any element:
```xml
<line x1="10" y1="10" x2="25" y2="10" 
      data-temp="150" 
      data-dwell="0.2" 
      data-height="0.040"
      stroke="black"/>
```

## 🔧 Troubleshooting

### Common Issues
- **403 Forbidden:** Check PrusaLink credentials in `secrets.toml`
- **No weld paths found:** Ensure SVG elements have proper stroke colors
- **Temperature not reached:** Check nozzle heating in printer settings

### Getting Help
- Check the main README.md for detailed documentation
- Review generated G-code for debugging
- Use `--verbose` flag for detailed output

## 📊 Performance Tips

- Use the calibration test to find optimal parameters for your material
- Start with the provided config.toml defaults (scientifically validated)
- Monitor first prints closely to verify weld quality
- Adjust parameters based on material thickness and type

Happy welding! 🔥
