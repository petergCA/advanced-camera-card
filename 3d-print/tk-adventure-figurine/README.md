# "Our TK Adventure" Teacher Figurine — 3D Print Files

A minifig-style figurine of a smiling teacher with wavy shoulder-length hair,
round glasses, a paw-print shirt, a camera on a neck strap, a frappuccino with
a heart label in one hand, and a book titled **"Our TK Adventure"** in the
other, standing on a stud base plate.

## Files

| File | Description |
| --- | --- |
| `tk_adventure_figurine.stl` | The full model as a single watertight solid — print this one. |
| `parts/*.stl` | The same model split into 6 color groups (blue, white, yellow, brown, black, cream), all in the same coordinate frame. Use these for a multi-material/multi-color printer (import all six as one object) or as a painting reference. |
| `build_figurine.py` | The parametric Python script that generates everything. Edit and re-run to change the text, pose, or proportions. |
| `preview_front.png`, `preview_three_quarter.png` | Rendered previews. |

## Dimensions

- Height: **203.2 mm (8.0 in)** exactly, base plate included
- Footprint: 163.7 mm wide × 67.6 mm deep — fits a 220 × 220 mm bed
- Solid volume: ~474 cm³ (roughly 85–100 g of PLA at 15 % infill)

## Print settings (suggested)

- **Orientation:** as modeled — standing upright on the base plate
- **Supports:** required (tree/organic supports recommended) for the
  outstretched book and cup arms, the camera, and under the chin/hair
- **Layer height:** 0.2 mm (0.12 mm if you want crisper face details and text)
- **Infill:** 10–15 %
- **Material:** PLA or PETG
- The title text, paw prints, glasses, and heart are raised ~1.5–2.3 mm
  relief, which prints cleanly at this scale and is easy to hand-paint.

## Regenerating / customizing

```bash
pip install trimesh manifold3d shapely numpy scipy matplotlib mapbox_earcut
python3 build_figurine.py
```

To change the book title, edit the `LINES` list in the script (text, font
size per line). `TARGET_HEIGHT_MM` sets the overall height.
