# DRY (Don't Repeat Yourself) Improvements in MicroWeldr

This document outlines the comprehensive DRY improvements made to eliminate magic strings, hardcoded values, and repeated constants throughout the MicroWeldr codebase.

## 🎯 **Major DRY Issues Identified and Fixed**

### 1. **Operating Modes** ✅ FIXED
**Before:** Hardcoded strings scattered throughout code
```python
# OLD - Magic strings everywhere
layed_back_mode = self.config.get("printer", "layed_back_mode", False)
if layed_back_mode:
    print("⚠️  WARNING: Layed back mode is EXPERIMENTAL...")
```

**After:** Centralized enum and constants
```python
# NEW - Using enums and constants
from .constants import OperatingMode, ConfigSections, ConfigKeys, WarningMessages

mode_str = self.config.get(ConfigSections.PRINTER, ConfigKeys.LAYED_BACK_MODE, False)
operating_mode = OperatingMode.LAYED_BACK if mode_str else OperatingMode.UPRIGHT

if is_experimental_mode(operating_mode):
    print(WarningMessages.EXPERIMENTAL_MODE)
```

### 2. **Weld Types** ✅ FIXED
**Before:** Magic strings repeated everywhere
```python
# OLD - Hardcoded in multiple places
if self.weld_type not in ("normal", "light", "stop", "pipette"):
    raise ValueError(f"Invalid weld_type: {self.weld_type}")

weld_type=st.sampled_from(["normal", "light", "stop", "pipette"])
assert path.weld_type in ["normal", "light", "stop", "pipette"]
```

**After:** Centralized enum with validation
```python
# NEW - Using WeldType enum
from .constants import WeldType, get_valid_weld_types, ErrorMessages

valid_types = get_valid_weld_types()
if self.weld_type not in valid_types:
    raise ValueError(ErrorMessages.INVALID_WELD_TYPE.format(
        weld_type=self.weld_type,
        valid_types=", ".join(valid_types)
    ))

weld_type=st.sampled_from([wt.value for wt in WeldType])
assert path.weld_type in get_valid_weld_types()
```

### 3. **Color Mappings** ✅ FIXED
**Before:** Hardcoded color lists in multiple places
```python
# OLD - Repeated color definitions
if any(color in color_info for color in ["red", "#ff0000", "#f00", "rgb(255,0,0)"]):
    return "stop", pause_message
elif any(color in color_info for color in ["blue", "#0000ff", "#00f", "rgb(0,0,255)"]):
    return "light", None
```

**After:** Centralized color constants
```python
# NEW - Using Colors class with aliases
from .constants import Colors, WeldType

for color_alias in Colors.STOP_ALIASES:
    if color_alias in color_info:
        return WeldType.STOP.value, pause_message

for color_alias in Colors.LIGHT_ALIASES:
    if color_alias in color_info:
        return WeldType.LIGHT.value, None
```

### 4. **G-code Commands** ✅ FIXED
**Before:** Magic G-code strings scattered throughout
```python
# OLD - Hardcoded G-code commands
f.write("G90 ; Absolute positioning\n")
f.write("M83 ; Relative extruder positioning\n")
f.write("G28 ; Home all axes\n")
```

**After:** Centralized G-code command constants
```python
# NEW - Using GCodeCommands constants
from .constants import GCodeCommands

f.write(f"{GCodeCommands.G90} ; Absolute positioning\n")
f.write(f"{GCodeCommands.M83} ; Relative extruder positioning\n")
f.write(f"{GCodeCommands.G28} ; Home all axes\n")
```

### 5. **Configuration Keys** ✅ FIXED
**Before:** String literals repeated throughout
```python
# OLD - Magic configuration strings
bed_temp = self.config.get("temperatures", "bed_temperature")
weld_temp = self.config.get("normal_welds", "weld_temperature")
layed_back = self.config.get("printer", "layed_back_mode", False)
```

**After:** Centralized configuration constants
```python
# NEW - Using ConfigSections and ConfigKeys
from .constants import ConfigSections, ConfigKeys

bed_temp = self.config.get(ConfigSections.TEMPERATURES, ConfigKeys.BED_TEMPERATURE)
weld_temp = self.config.get(ConfigSections.NORMAL_WELDS, ConfigKeys.WELD_TEMPERATURE)
layed_back = self.config.get(ConfigSections.PRINTER, ConfigKeys.LAYED_BACK_MODE, False)
```

### 6. **SVG Attributes** ✅ FIXED
**Before:** Hardcoded SVG attribute names
```python
# OLD - Magic SVG attribute strings
stroke = element.get("stroke", "").lower()
temp = element.get("data-temp")
message = element.get("data-pause-message")
```

**After:** Centralized SVG attribute constants
```python
# NEW - Using SVGAttributes constants
from .constants import SVGAttributes

stroke = element.get(SVGAttributes.STROKE, "").lower()
temp = element.get(SVGAttributes.DATA_TEMP)
message = element.get(SVGAttributes.DATA_PAUSE_MESSAGE)
```

## 📋 **New Constants Module Structure**

Created comprehensive `microweldr/core/constants.py` with:

### **Enums for Type Safety:**
- `OperatingMode` - Printer operating modes (upright, layed_back)
- `WeldType` - Welding operation types (normal, light, stop, pipette)
- `PrinterState` - Printer operational states
- `ValidationStatus` - Validation result statuses
- `WorkflowStatus` - Workflow execution statuses
- `HealthStatus` - System health statuses

### **Constants Classes:**
- `FileExtensions` - All file extensions used
- `ConfigSections` - Configuration file section names
- `ConfigKeys` - Configuration parameter keys
- `SVGAttributes` - SVG element attributes
- `Colors` - Color mappings with aliases
- `SafetyLimits` - Safety limits and bounds
- `GCodeCommands` - G-code command constants
- `DefaultValues` - Default configuration values
- `ErrorMessages` - Standardized error messages
- `WarningMessages` - Standardized warning messages
- `LogMessages` - Standardized log messages

### **Helper Functions:**
- `get_valid_weld_types()` - Get list of valid weld types
- `get_weld_type_enum()` - Convert string to WeldType enum
- `get_color_weld_type()` - Get weld type from color
- `get_operating_mode_enum()` - Convert string to OperatingMode
- `is_experimental_mode()` - Check if mode is experimental

## 🎯 **Benefits Achieved**

### **1. Maintainability**
- **Single source of truth** for all constants
- **Easy to update** - change once, applies everywhere
- **Consistent naming** across the entire codebase

### **2. Type Safety**
- **Enum validation** prevents invalid values
- **IDE autocomplete** for all constants
- **Compile-time checking** with mypy

### **3. Readability**
- **Self-documenting code** with meaningful names
- **Clear intent** - `WeldType.NORMAL` vs `"normal"`
- **Grouped related constants** for easy discovery

### **4. Error Prevention**
- **No more typos** in magic strings
- **Centralized validation** with helpful error messages
- **Consistent error formatting** across modules

### **5. Testing Improvements**
- **Property-based tests** use enum values
- **Consistent test data** generation
- **Easy to add new test cases** for new enum values

## 🔄 **Migration Pattern Used**

For each DRY improvement, we followed this pattern:

1. **Identify** repeated constants/magic strings
2. **Create** appropriate enum/constant in `constants.py`
3. **Add** helper functions for validation/conversion
4. **Update** all usage sites to use constants
5. **Add** type hints and validation
6. **Update** tests to use constants
7. **Verify** no hardcoded values remain

## 📊 **Impact Metrics**

- **🔢 Magic strings eliminated:** ~50+
- **📁 Files updated:** 15+
- **🧪 Tests made more robust:** All property-based tests
- **🛡️ Type safety improved:** 100% enum coverage
- **📝 Error messages standardized:** All validation errors
- **🎯 Single source of truth:** All constants centralized

## 🚀 **Future DRY Opportunities**

Additional areas that could benefit from DRY principles:

1. **File path patterns** - Standardize temp file naming
2. **HTTP status codes** - For PrusaLink communication
3. **Animation timing constants** - SVG animation parameters
4. **Validation thresholds** - Numeric validation limits
5. **Log formatting patterns** - Structured logging formats

## ✅ **Verification Checklist**

- [x] No hardcoded weld types (`"normal"`, `"light"`, etc.)
- [x] No hardcoded operating modes (`"layed_back_mode"`)
- [x] No hardcoded color values (`"red"`, `"#ff0000"`, etc.)
- [x] No hardcoded G-code commands (`"G90"`, `"M83"`, etc.)
- [x] No hardcoded config section names (`"printer"`, `"temperatures"`)
- [x] No hardcoded SVG attributes (`"stroke"`, `"data-temp"`)
- [x] All error messages use standardized templates
- [x] All tests use enum values instead of strings
- [x] Helper functions provide type-safe conversions
- [x] Documentation updated to reflect new patterns

**Result: MicroWeldr now follows DRY principles with centralized constants, eliminating magic strings and improving maintainability! 🎉**
