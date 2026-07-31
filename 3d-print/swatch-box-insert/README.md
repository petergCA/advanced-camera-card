# Modified Swatch-Box Interior Insert

A re-parameterized rebuild of the uploaded `Box_interior.3mf` (the comb-style
slot insert from a filament-swatch storage box).

## Changes from the original

| Property | Original | Modified |
| --- | --- | --- |
| Sides | Bulged locating ribs | **Flat** |
| Number of slots | 47 | **13** |
| Slot width | 3.4 mm | **5.0 mm** |
| Slot length | ~50 mm | **40.0 mm** |
| Slot depth | ~23 mm | **45.0 mm** |

Kept from the original: 1.6 mm dividers, 2.4 mm side walls, 5.8 mm end
walls, 2.9 mm floor.

Resulting outer size: **44.8 × 95.8 × 47.9 mm**.

## Files

- `box_interior_modified.3mf` — modified model (3MF, same format as uploaded)
- `box_interior_modified.stl` — same model as STL
- `build_insert.py` — parametric build script; edit the constants at the top
  and re-run to change any dimension
- `preview_*.png` — renders

## Printing

Prints support-free as oriented (flat base, vertical walls). Note the 1.6 mm
dividers are now 45 mm tall — a 0.4 mm nozzle prints them as 4 perimeters;
consider 0.2 mm layers and moderate speeds for clean thin walls.
