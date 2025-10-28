# Skip Weld Sequencing Algorithm

## Overview

The **Skip Algorithm** is the default weld sequencing method that provides excellent thermal distribution by printing every Nth dot first, then filling in the gaps. This ensures maximum spacing between initial welds, allowing optimal cooling time.

## How It Works

The algorithm works in multiple passes:

1. **Pass 1**: Print every `skip_base_distance` dot (e.g., 0, 5, 10, 15...)
2. **Pass 2**: Print dots offset by 1 (e.g., 1, 6, 11, 16...)
3. **Pass 3**: Print dots offset by 2 (e.g., 2, 7, 12, 17...)
4. **Continue** until all dots are printed

## Configuration

Add to your `config.toml`:

```toml
[sequencing]
# Weld sequencing algorithm settings
skip_base_distance = 5  # dots - for skip algorithm, print every Nth dot first
```

## Example with 20 Points and Skip Distance 5

**Welding Order**: [0, 5, 10, 15, 1, 6, 11, 16, 2, 7, 12, 17, 3, 8, 13, 18, 4, 9, 14, 19]

**Passes**:
- **Pass 1**: [0, 5, 10, 15] - Every 5th dot
- **Pass 2**: [1, 6, 11, 16] - Offset by 1
- **Pass 3**: [2, 7, 12, 17] - Offset by 2
- **Pass 4**: [3, 8, 13, 18] - Offset by 3
- **Pass 5**: [4, 9, 14, 19] - Offset by 4

## Benefits

1. **Optimal Thermal Distribution**: Maximum spacing between consecutive welds in early passes
2. **Reduced Thermal Stress**: Allows cooling time between nearby weld points
3. **Consistent Coverage**: Ensures even distribution across the entire weld path
4. **Configurable**: Adjust `skip_base_distance` based on material and nozzle size

## Usage

```bash
# Use skip algorithm (default)
python -m svg_welder.cli.main input.svg

# Explicitly specify skip algorithm
python -m svg_welder.cli.main input.svg --weld-sequence skip

# Use with custom configuration
python -m svg_welder.cli.main input.svg -c custom_config.toml --weld-sequence skip
```

## Comparison with Other Algorithms

| Algorithm | Thermal Distribution | Complexity | Best For |
|-----------|---------------------|------------|----------|
| **Skip** | Excellent | Low | General welding (default) |
| Linear | Poor | Very Low | Simple testing |
| Binary | Good | Medium | Balanced approach |
| Farthest | Excellent | High | Complex geometries |

## Default Settings

- **Default Algorithm**: Skip
- **Default Skip Distance**: 5 dots
- **Configurable**: Yes, via `config.toml`

The Skip algorithm is the **default sequencing method** due to its excellent thermal properties and simplicity.
