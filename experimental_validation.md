# Experimental Validation - Plastic Welding Parameters

## Experimental Setup

### Printer Configuration
- **Printer**: Prusa Core One
- **Print Sheet**: CORE One Satin Powder-coated Print Sheet
  - **Part Number**: Available at [prusa3d.com](https://www.prusa3d.com/product/core-one-satin-powder-coated-print-sheet/)
  - **Surface**: Double-sided satin powder-coated spring steel sheet
  - **Finish**: Lightly textured matte finish with optimal adhesion properties
  - **Compatibility**: Designed for PLA, PETG, ABS, ASA, PC, and other materials

### Sample Preparation & Positioning
- **Film Placement**: Plastic films laid as flat as possible on the satin bed surface
- **Securing Method**: Neodymium magnets for film positioning
  - **Magnet Dimensions**: 2mm height × 6mm diameter
  - **Purpose**: Hold plastic films flat against bed surface during welding
  - **Positioning**: Strategic placement to avoid interference with nozzle path

### Environmental Conditions
- **Bed Temperature**: 120°C (maintained throughout experiment)
- **Chamber**: Prusa Core One enclosed chamber
- **Ambient**: [To be recorded during experiments]

### Setup Notes & Considerations
- **Magnet Safety**: 2mm height magnets provide sufficient clearance for nozzle movement
- **Heat Resistance**: Neodymium magnets maintain magnetism at 120°C bed temperature
- **Film Flatness**: Critical for consistent weld depth and quality
- **Nozzle Clearance**: Ensure magnet placement doesn't interfere with welding paths
- **Thermal Expansion**: Account for film expansion at elevated bed temperature

## Material Information

**Roll 1**: [Amazon IE - B09FF42PPK](https://www.amazon.ie/dp/B09FF42PPK?ref_=ppx_hzsearch_conn_dt_b_fed_asin_title_3)
- Material: [To be determined from product listing]
- Thickness: [To be measured]
- Color: [To be noted]

## Experimental Results

| Exp # | Roll | Material Orientation | Nozzle Temp (°C) | Bed Temp (°C) | Weld Time (s) | Dot Spacing (mm) | Result Quality | Bond Strength | Notes |
|-------|------|---------------------|------------------|---------------|---------------|------------------|----------------|---------------|-------|
| 001   | 1    | PP surfaces together (inner/concave) | 170 | 120 | 0.1 | 0.9 | **Excellent** | **Strong** | SUCCESS: PP welding surfaces bond properly |
| 002   | 1    | Non-PP surfaces together (outer/convex) | 170 | 120 | 0.1 | 0.9 | **Failed** | **Poor** | FAILURE: Easy delamination, no proper bond |

## Evaluation Criteria

### Result Quality Scale
- **Excellent**: Clean, consistent weld line, no burning, good adhesion
- **Good**: Minor imperfections, acceptable weld quality
- **Fair**: Some issues but functional weld
- **Poor**: Significant defects, weak bond
- **Failed**: No bond or severe damage

### Bond Strength Test Methods
1. **Visual Inspection**: Check for continuous weld line
2. **Peel Test**: Attempt to separate welded areas by hand
3. **Pull Test**: Apply controlled force to test bond strength
4. **Leak Test**: For sealed pouches, test air/water retention

## Parameter Optimization Notes

### Current Configuration (config.toml)
```toml
[temperatures]
bed_temperature = 120  # °C
nozzle_temperature = 170  # °C - upper end of PP melt range

[normal_welds]
weld_time = 0.1  # seconds
dot_spacing = 0.9  # mm
weld_height = 0.020  # mm (20 microns)
```

### Variables to Test
- [ ] Temperature range: 160-180°C (nozzle)
- [ ] Bed temperature: 100-130°C
- [ ] Weld time: 0.05-0.2s
- [ ] Dot spacing: 0.5-1.2mm
- [ ] Material orientation (inside vs outside)
- [ ] Multiple passes
- [ ] Different materials/rolls

## Future Experiments

### Planned Tests
- [ ] Temperature sweep (160, 165, 170, 175, 180°C)
- [ ] Time variation (0.05, 0.1, 0.15, 0.2s)
- [ ] Spacing optimization (0.5, 0.7, 0.9, 1.1mm)
- [ ] Multi-pass welding
- [ ] Different plastic materials

### Success Metrics
1. **Weld Quality**: Visual appearance and consistency
2. **Bond Strength**: Resistance to separation
3. **Process Reliability**: Repeatability of results
4. **Material Compatibility**: Works across different plastic types
5. **Speed**: Optimal balance of quality and welding time

## Material Analysis

### Roll 1 Characteristics
- **Source**: Amazon IE B09FF42PPK
- **Suspected Material**: [Check product description - likely PE or PP]
- **Thickness**: [Measure with calipers]
- **Surface Identification**:
  - **Inner surface** (concave side that faced roll center): PP welding surface
  - **Outer surface** (convex side that faced outward on roll): Non-welding surface
- **Transparency**: [Clear, translucent, opaque]

## Observations

### Experiment 001 - PP Surfaces Together (Inner/Concave Sides)
- **Setup**: Roll inner surfaces (concave, PP welding surfaces) placed in contact
- **Material Orientation**: PP welding surfaces facing each other
- **Result**: **SUCCESS** - Proper adhesion achieved, weld holds firmly
- **Bond Quality**: Strong, consistent weld with good adhesion
- **Observations**: The PP surfaces (inner/concave sides of roll) weld effectively at 170°C/0.1s

### Experiment 002 - Non-PP Surfaces Together (Outer/Convex Sides)
- **Setup**: Roll outer surfaces (convex, non-welding surfaces) placed in contact
- **Material Orientation**: Non-PP surfaces facing each other
- **Result**: **FAILURE** - Poor adhesion, easy delamination
- **Bond Quality**: Weak bond that separates easily under minimal force
- **Observations**: The outer surfaces (convex sides of roll) do not weld properly, indicating different material composition or surface treatment

## Key Findings

### ⚠️ **Critical Material Orientation Discovery**
**IMPORTANT**: This material has **asymmetric surfaces** with different welding properties:

- ✅ **PP Welding Surface**: Inner/concave side (faced roll center) - **WELDS PROPERLY**
- ❌ **Non-PP Surface**: Outer/convex side (faced outward on roll) - **DOES NOT WELD**

### Practical Implications
1. **Always use PP surfaces for welding** (inner/concave sides of original roll)
2. **Material identification is critical** - surface orientation affects weld success
3. **Laminated or coated material** - likely PP layer on one side, different material on other
4. **Quality control** - verify surface orientation before welding operations

## Next Steps

1. **Complete current experiments** and fill in results
2. **Identify material type** from Amazon listing
3. **Measure material thickness** accurately
4. **Document surface differences** between inside/outside
5. **Plan systematic parameter sweep** based on initial results
6. **Consider additional test materials** for broader validation

---

*Last Updated: [Date]*
*Experimenter: [Name]*
