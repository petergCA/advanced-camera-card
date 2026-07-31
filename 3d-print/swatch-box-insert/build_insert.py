#!/usr/bin/env python3
"""Rebuild of "Box_interior" (filament-swatch box comb insert), re-parameterized.

Changes vs. the original model:
  - sides are flat (the original's side locating ribs/bulges are removed)
  - 13 slots (was 47)
  - slot width 5.0 mm (was 3.4)
  - slot length 40.0 mm (was ~50)
  - slot depth 45.0 mm (was ~23)

Wall/floor thicknesses match the original: 1.6 mm dividers, 2.4 mm side
walls, 5.8 mm end walls, 2.9 mm floor.

Outputs: box_interior_modified.stl, box_interior_modified.3mf, preview PNGs.
"""

import os
import numpy as np
import trimesh
from trimesh.creation import box as tbox

OUT = os.path.dirname(os.path.abspath(__file__))

# ------------------------- parameters (mm) -------------------------
NUM_SLOTS = 13
SLOT_W = 5.0      # slot width (along the row)
SLOT_L = 40.0     # slot length (across the insert)
SLOT_D = 45.0     # slot depth
DIVIDER = 1.6     # wall between slots
END_WALL = 5.8    # wall at each end of the row
SIDE_WALL = 2.4   # wall on each long side
FLOOR = 2.9       # thickness under the slots

TOTAL_L = NUM_SLOTS * SLOT_W + (NUM_SLOTS - 1) * DIVIDER + 2 * END_WALL
TOTAL_W = SLOT_L + 2 * SIDE_WALL
TOTAL_H = SLOT_D + FLOOR
print(f"outer size: {TOTAL_W:.1f} x {TOTAL_L:.1f} x {TOTAL_H:.1f} mm")

def mkbox(sx, sy, sz, at):
    b = tbox(extents=(sx, sy, sz))
    b.apply_translation(at)
    return b

outer = mkbox(TOTAL_W, TOTAL_L, TOTAL_H, (TOTAL_W / 2, TOTAL_L / 2, TOTAL_H / 2))

slots = []
for i in range(NUM_SLOTS):
    y0 = END_WALL + i * (SLOT_W + DIVIDER)
    slots.append(mkbox(SLOT_L, SLOT_W, SLOT_D + 1,
                       (TOTAL_W / 2, y0 + SLOT_W / 2, FLOOR + (SLOT_D + 1) / 2)))

insert = trimesh.boolean.difference([outer] + slots, engine="manifold")
assert insert.is_watertight
print(f"watertight={insert.is_watertight}, extents={np.round(insert.extents, 2)}, "
      f"volume={insert.volume / 1000:.1f} cm^3, faces={len(insert.faces)}")

insert.export(os.path.join(OUT, "box_interior_modified.stl"))
scene = trimesh.Scene({"box_interior_modified": insert})
scene.export(os.path.join(OUT, "box_interior_modified.3mf"))
print("exported STL + 3MF")

# ------------------------------ preview ------------------------------
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

light = np.array([0.4, 0.7, 0.6])
light = light / np.linalg.norm(light)
lam = np.clip(insert.face_normals @ light, 0, 1)
fc = np.clip(np.array([[0.35, 0.55, 0.8]]) * (0.4 + 0.6 * lam)[:, None], 0, 1)
fc = np.hstack([fc, np.ones((len(fc), 1))])
tris = insert.vertices[insert.faces]

for name, (e, a) in {"iso": (30, -55), "top": (88, -90), "end": (5, 0)}.items():
    fig = plt.figure(figsize=(9, 7), dpi=100)
    ax = fig.add_subplot(111, projection="3d")
    ax.add_collection3d(Poly3DCollection(tris, facecolors=fc, edgecolors="none"))
    c = insert.bounds.mean(axis=0)
    r = insert.extents.max() / 2
    ax.set_xlim(c[0] - r, c[0] + r)
    ax.set_ylim(c[1] - r, c[1] + r)
    ax.set_zlim(c[2] - r, c[2] + r)
    ax.set_box_aspect((1, 1, 1))
    ax.set_axis_off()
    ax.view_init(elev=e, azim=a)
    plt.savefig(os.path.join(OUT, f"preview_{name}.png"),
                bbox_inches="tight", facecolor="#efeff2")
    plt.close(fig)
print("previews done")
