# Parametric Weave Stitch Basket

A parametric rebuild of Eternity Labs' "The Weave Stitch Basket"
(`WeaveBasketv3.3mf`, original fixed at 120 x 80 x 41.3 mm).

## How the original works (reverse-engineered)

Every wall row is a **2-ply twisted rope** swept around a rounded-rectangle
path: strand radius 1.197 mm, ply offset 0.899 mm, exactly 40 half-twists
around the 382.8 mm perimeter (9.571 mm per visible stripe). Adjacent rows
twist in opposite directions — that's what creates the chevron "weave" look —
and stack with alternating 3.4 / 1.8 mm gaps (5.2 mm per row pair) above a
3 mm solid base with a smaller flat-trimmed rope as the foot ring. The rebuild
reproduces the original surface to ~0.1 mm.

## Why parametric beats scaling

Scaling the mesh stretches the rope (fat strands, distorted weave) and wastes
material because everything thickens. This generator instead keeps the rope
cross-section and twist pitch **constant** at any size: a larger basket gets
*more* twists around the perimeter and *more* rows up the wall. Walls stay one
rope thick, so material grows with area, not volume.

## Usage

```bash
pip install numpy scipy trimesh manifold3d shapely networkx rtree mapbox_earcut
python3 weave_basket_param.py --width 120 --length 80 --height 41.3   # original
python3 weave_basket_param.py --width 170 --length 110 --height 60 -o big_basket
```

- `--width` / `--length`: base outline in mm, any value (the rope wall bulges
  2.1 mm outward beyond it, so overall footprint is +4.2 mm). No snapping —
  the twist count is rounded to a whole number so the rope closes seamlessly,
  which shifts the stripe pitch by at most ~1 %.
- `--height`: snapped to a whole number of rows (5.2 mm steps); the actual
  height is printed.
- `--corner-radius` (default 10), `--strand-radius` (default 1.197) and
  `--resolution` (sweep step, default 0.35 mm; use 0.5 for smaller files)
  are also available.

Outputs a watertight STL + a **Bambu Studio project 3MF** (full Metadata/
config package, so it opens without the "invalid config, load geometry data
only" dialog). Pass `--template /path/to/WeaveBasketv3.3mf` to carry the
original designer's tuned print profile into the output project. Print like
the original: no supports, the rope overhangs are self-supporting at this
scale.

`size_comparison.png` shows 120x80x41 next to 170x110x62 — same rope, more
weave.
