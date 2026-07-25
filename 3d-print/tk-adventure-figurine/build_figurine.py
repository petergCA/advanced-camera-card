#!/usr/bin/env python3
"""Build a 3D-printable minifig-style teacher figurine.

Generates a figurine (8 inches / 203.2 mm tall) of a smiling teacher with
wavy shoulder-length hair, round glasses, a paw-print shirt, a camera on a
neck strap, a frappuccino in one hand, and a book titled "Our TK Adventure"
in the other, standing on a stud base plate.

Outputs (in the same directory):
  - tk_adventure_figurine.stl          full model, single solid, watertight
  - parts/<color>.stl                  color-separated groups for painting or
                                       multi-material printing (same origin)
  - preview_front.png / preview_three_quarter.png   rendered previews

Requires: trimesh, manifold3d, shapely, numpy, matplotlib, mapbox_earcut
"""

import os
import numpy as np
import trimesh
from trimesh.creation import cylinder, box as tbox, icosphere, torus, extrude_polygon
from trimesh.transformations import rotation_matrix
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union
from matplotlib.textpath import TextPath
from matplotlib.font_manager import FontProperties

OUT = os.path.dirname(os.path.abspath(__file__))
TARGET_HEIGHT_MM = 203.2  # 8 inches

SEG = 64  # cylinder sections

# ---------------------------------------------------------------- helpers

def T(x=0.0, y=0.0, z=0.0):
    m = np.eye(4)
    m[:3, 3] = (x, y, z)
    return m

def RX(deg):
    return rotation_matrix(np.radians(deg), [1, 0, 0])

def RY(deg):
    return rotation_matrix(np.radians(deg), [0, 1, 0])

def RZ(deg):
    return rotation_matrix(np.radians(deg), [0, 0, 1])

# XY-plane artwork (text/paw/heart, +Z extrusion) -> upright relief on a
# vertical +Y-facing surface, readable by a viewer standing at +Y.
FACE_PLUS_Y = rotation_matrix(np.radians(180), [0, 0, 1]) @ \
    rotation_matrix(np.radians(90), [1, 0, 0])

def box(sx, sy, sz, at=(0, 0, 0)):
    b = tbox(extents=(sx, sy, sz))
    b.apply_translation(at)
    return b

def cyl(r, h, at=(0, 0, 0), axis="z"):
    c = cylinder(radius=r, height=h, sections=SEG)
    if axis == "x":
        c.apply_transform(RY(90))
    elif axis == "y":
        c.apply_transform(RX(90))
    c.apply_translation(at)
    return c

def seg_cyl(r, p0, p1):
    return cylinder(radius=r, sections=SEG, segment=[p0, p1])

def sph(r, at=(0, 0, 0), scale=(1, 1, 1)):
    s = icosphere(subdivisions=3, radius=r)
    s.apply_scale(scale)
    s.apply_translation(at)
    return s

def ring(major_r, minor_r, at=(0, 0, 0), axis="y"):
    t = torus(major_radius=major_r, minor_radius=minor_r,
              major_sections=SEG, minor_sections=24)
    if axis == "y":
        t.apply_transform(RX(90))
    elif axis == "x":
        t.apply_transform(RY(90))
    t.apply_translation(at)
    return t

def union(meshes):
    return trimesh.boolean.union(meshes, engine="manifold")

def difference(a, b):
    return trimesh.boolean.difference([a, b], engine="manifold")

# --------------------------------------------------------------- 2D shapes

FONT = FontProperties(family="DejaVu Sans", weight="bold")

def text_polygons(s, size):
    """Return a list of shapely Polygons (with holes) for a text string."""
    tp = TextPath((0, 0), s, size=size, prop=FONT)
    rings = [Polygon(p) for p in tp.to_polygons() if len(p) >= 3]
    rings = [r if r.is_valid else r.buffer(0) for r in rings]
    rings.sort(key=lambda r: r.area, reverse=True)
    solids = []
    for r in rings:
        placed = False
        for i, srec in enumerate(solids):
            outer, holes = srec
            if outer.contains(r.representative_point()):
                inside_hole = any(h.contains(r.representative_point()) for h in holes)
                if inside_hole:
                    solids.append((r, []))  # island inside a hole (rare)
                else:
                    holes.append(r)
                placed = True
                break
        if not placed:
            solids.append((r, []))
    polys = []
    for outer, holes in solids:
        polys.append(Polygon(outer.exterior.coords,
                             [h.exterior.coords for h in holes]))
    return polys

def text_mesh(s, size, depth):
    """Extruded text, centered at origin in XY, thickness `depth` in +Z."""
    polys = text_polygons(s, size)
    merged = unary_union(polys)
    minx, miny, maxx, maxy = merged.bounds
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    parts = []
    geoms = merged.geoms if merged.geom_type == "MultiPolygon" else [merged]
    for g in geoms:
        m = extrude_polygon(g, height=depth)
        parts.append(m)
    mesh = union(parts)
    mesh.apply_translation((-cx, -cy, 0))
    return mesh, (maxx - minx, maxy - miny)

def text_mesh_fit(s, width, max_size, depth):
    """Text scaled so its width is at most `width`, font size at most max_size."""
    m, (w, h) = text_mesh(s, max_size, depth)
    if w > width:
        f = width / w
        m.apply_scale((f, f, 1.0))
    return m

def paw_polygon(scale=1.0):
    """A paw print in the XY plane, centered, ~unit size before scaling."""
    pad = Point(0, -2.0).buffer(4.2, resolution=32)
    pad = trimesh.path.polygons.Polygon(
        np.array(pad.exterior.coords) * np.array([1.15, 0.95]))
    toes = []
    for x, y, r in [(-4.6, 4.0, 2.0), (-1.6, 6.0, 2.1),
                    (1.6, 6.0, 2.1), (4.6, 4.0, 2.0)]:
        toes.append(Point(x, y).buffer(r, resolution=24))
    paw = unary_union([pad] + toes)
    return trimesh.path.polygons.Polygon(np.array(paw.exterior.coords) * scale) \
        if paw.geom_type == "Polygon" else paw

def paw_mesh(scale, depth):
    paw = paw_polygon(scale)
    geoms = paw.geoms if paw.geom_type == "MultiPolygon" else [paw]
    return union([extrude_polygon(g, height=depth) for g in geoms])

def heart_mesh(size, depth):
    """A heart outline (relief) in XY, extruded in +Z."""
    c1 = Point(-0.35, 0.25).buffer(0.5, resolution=32)
    c2 = Point(0.35, 0.25).buffer(0.5, resolution=32)
    tri = Polygon([(-0.83, 0.05), (0.83, 0.05), (0, -1.0)])
    heart = unary_union([c1, c2, tri])
    ring2d = heart.boundary.buffer(0.13)
    geoms = ring2d.geoms if ring2d.geom_type == "MultiPolygon" else [ring2d]
    m = union([extrude_polygon(Polygon(g.exterior.coords,
                                       [i.coords for i in g.interiors]),
                               height=depth) for g in geoms])
    m.apply_scale((size, size, 1))
    return m

# ================================================================= FIGURE
# Design frame: Z up, figure faces +Y. Units: design-mm (scaled at the end).

parts = {}  # color group -> list of meshes

def add(group, *meshes):
    parts.setdefault(group, []).extend(meshes)

# ---- base plate (black) with two studs -------------------------------
plate = box(104, 64, 8, at=(0, 2, 4))
stud_l = cyl(11, 6, at=(-32, 22, 11))
stud_r = cyl(11, 6, at=(32, 22, 11))
add("black", plate, stud_l, stud_r)

# ---- legs (blue) ------------------------------------------------------
LEG_TOP = 70
for sx in (-1, 1):
    leg = box(25, 28, 50, at=(sx * 14.5, 0, 8 + 25))       # z 8..58
    foot = box(25, 34, 12, at=(sx * 14.5, 3, 8 + 6))        # deeper foot
    add("blue", leg, foot)
hips = box(56, 27, 12, at=(0, 0, 58 + 6))                    # z 58..70
add("blue", hips)

# ---- torso (white), tapered: hull of bottom and top slabs -------------
t_bot = box(56, 27, 2, at=(0, 0, LEG_TOP + 1))
t_top = box(46, 23, 2, at=(0, 0, 129))
torso = trimesh.convex.convex_hull(union([t_bot, t_top]))
add("white", torso)

# ---- paw print on the shirt (yellow, raised) --------------------------
paw = paw_mesh(scale=1.6, depth=3.0)
paw.apply_transform(FACE_PLUS_Y)                # face +Y, upright
paw.apply_transform(T(0, 11.0, 112))            # embedded in chest surface
add("yellow", paw)

# ---- neck + head (yellow) --------------------------------------------
neck = cyl(10, 8, at=(0, 0, 130 + 3))
HEAD_C = 156                                     # head center z
head_core = cyl(21, 30, at=(0, 0, HEAD_C))
head_soft = cyl(19, 40, at=(0, 0, HEAD_C))
head = trimesh.convex.convex_hull(union([head_core, head_soft]))
add("yellow", neck, head)

# ---- face features ----------------------------------------------------
FACE_Y = 21.0                                    # face surface radius (head r)
# glasses: two rings + bridge (brown)
for sx in (-1, 1):
    add("brown", ring(7.2, 1.6, at=(sx * 9.2, FACE_Y, 160), axis="y"))
add("brown", box(5.5, 2.6, 2.6, at=(0, FACE_Y, 161.5)))
# temple arms back toward the hair
for sx in (-1, 1):
    add("brown", seg_cyl(1.3, (sx * 15.6, 17.5, 161), (sx * 19.5, 6.0, 162)))
# eyes (black raised dots inside the rings)
for sx in (-1, 1):
    add("black", cyl(2.6, 2.4, at=(sx * 9.2, FACE_Y + 0.4, 160), axis="y"))
# eyebrows (brown)
for sx in (-1, 1):
    brow = box(9, 2.2, 2.0, at=(sx * 9.2, FACE_Y + 0.3, 170.5))
    brow.apply_transform(
        T(sx * 9.2, 0, 170.5) @ RY(sx * 12) @ T(-sx * 9.2, 0, -170.5))
    add("brown", brow)
# open smile: lower half of a torus outline + dark mouth fill + teeth strip
smile_full = ring(6.5, 1.9, at=(0, FACE_Y + 0.2, 148), axis="y")
smile = difference(smile_full, box(30, 30, 12, at=(0, FACE_Y, 148 + 6)))
add("black", smile)
mouth = cyl(4.8, 3.0, at=(0, FACE_Y + 0.4, 147), axis="y")
mouth = difference(mouth, box(30, 30, 12, at=(0, FACE_Y, 147 + 7.4)))
add("black", mouth)
teeth = box(7.0, 1.6, 2.2, at=(0, FACE_Y + 1.6, 146.6))
add("white", teeth)

# ---- earrings (blue) --------------------------------------------------
for sx in (-1, 1):
    add("blue", cyl(3.4, 3.0, at=(sx * 21.5, 2, 149), axis="x"))

# ---- hair (brown): cap + back panel + side locks down to shoulders ----
hair = [
    sph(26.5, at=(0, -2.5, 168), scale=(1.02, 1.0, 0.92)),      # top cap
    sph(24, at=(0, -8, 152), scale=(1.05, 0.85, 1.35)),         # back mass
]
for sx in (-1, 1):
    hair.append(sph(11, at=(sx * 20, -4, 150), scale=(1.0, 1.25, 2.2)))   # side lock
    hair.append(sph(9, at=(sx * 24, -3, 132), scale=(1.0, 1.3, 1.8)))     # lock ends
    hair.append(sph(8, at=(sx * 16, -12, 130), scale=(1.1, 1.2, 1.7)))    # back ends
hair_solid = union(hair)
# carve out the face opening
face_window = box(34, 30, 34, at=(0, 16, 155))
face_window = union([face_window,
                     cyl(17, 30, at=(0, 16, 172), axis="z")])
hair_solid = difference(hair_solid, face_window)
# keep hair from swallowing the shoulders' front
hair_solid = difference(hair_solid, box(120, 60, 40, at=(0, 14, 110)))
add("brown", hair_solid)

# ---- arms (white sleeves) + hands (yellow) ----------------------------
SHO = 121  # shoulder z
# figure's RIGHT arm (at -X) holds the BOOK, angled out/down/forward
r_sh, r_el, r_ha = (-25, 1, SHO), (-40, 9, 104), (-49, 15, 97)
add("white", sph(9.5, at=r_sh), seg_cyl(8.5, r_sh, r_el),
    sph(8.5, at=r_el), seg_cyl(8, r_el, r_ha))
add("yellow", sph(8, at=r_ha), cyl(7, 12, at=r_ha, axis="x"))
# figure's LEFT arm (at +X) holds the CUP, raised
l_sh, l_el, l_ha = (25, 1, SHO), (38, 10, 106), (43, 15, 116)
add("white", sph(9.5, at=l_sh), seg_cyl(8.5, l_sh, l_el),
    sph(8.5, at=l_el), seg_cyl(8, l_el, l_ha))
add("yellow", sph(8, at=l_ha), cyl(7, 12, at=l_ha, axis="z"))

# ---- camera on a neck strap (black) -----------------------------------
CAM_Z = 88
cam_body = box(30, 13, 19, at=(0, 15, CAM_Z))
cam_top = box(14, 11, 4, at=(0, 14, CAM_Z + 11))
cam_lens = cyl(7.5, 8, at=(0, 22, CAM_Z), axis="y")
cam_lens2 = cyl(5.5, 12, at=(0, 24, CAM_Z), axis="y")
cam_btn = cyl(2.2, 3, at=(9, 14, CAM_Z + 12), axis="z")
add("black", cam_body, cam_top, cam_lens, cam_lens2, cam_btn)
# strap: from each side of the neck down to the camera's top corners
for sx in (-1, 1):
    p_neck = (sx * 12, 8, 127)
    p_mid = (sx * 15.5, 12.5, 108)
    p_cam = (sx * 13, 14, CAM_Z + 9)
    add("black", seg_cyl(2.2, p_neck, p_mid), seg_cyl(2.2, p_mid, p_cam),
        sph(2.2, at=p_mid))

# ---- BOOK: "Our TK Adventure" (blue cover, white text/details) --------
# built in a local frame: cover in XZ plane facing +Y, centered at origin
BW, BT, BH = 42, 11, 54          # width, thickness, height
book_cover = box(BW, BT, BH, at=(0, 0, 0))
spine = cyl(BT / 2, BH, at=(-BW / 2, 0, 0), axis="z")
book_blue = union([book_cover, spine])
# page block: white strip inset on the outer edge
pages = box(3.5, BT - 3, BH - 6, at=(BW / 2 - 0.5, 0, 0))
book_white = [pages]
# raised title text on the front cover (local +Y face at y = BT/2)
LINES = [("Our", 11.5), ("TK", 13.5), ("Adventure", 9.0)]
line_z = [15.5, 3.0, -9.5]
for (txt, size), lz in zip(LINES, line_z):
    tm = text_mesh_fit(txt, width=BW - 8, max_size=size, depth=2.2)
    tm.apply_transform(FACE_PLUS_Y)                # upright on the +Y cover
    tm.apply_transform(T(0.5, BT / 2 - 0.4, lz))
    book_white.append(tm)
# small paw + dashes under the title (yellow like the image's accents)
bp = paw_mesh(scale=0.62, depth=2.0)
bp.apply_transform(FACE_PLUS_Y)
bp.apply_transform(T(0.5, BT / 2 - 0.4, -20.5))
book_yellow = [bp]
for sx in (-1, 1):
    d = box(5, 2.0, 1.8, at=(sx * 13, BT / 2 - 0.2, -19.5))
    book_white.append(d)
# place the book at the right hand, tilted like the photo
book_xf = T(-58, 21, 100) @ RY(-14) @ RX(6)
for m in [book_blue] + book_white + book_yellow:
    m.apply_transform(book_xf)
add("blue", book_blue)
add("white", *book_white)
add("yellow", *book_yellow)

# ---- FRAPPUCCINO (cup body cream, straw brown, heart label brown) -----
# local frame: cup axis +Z, bottom at z=0
cup_h, r_bot, r_top = 27, 8.5, 12
profile_bot = cyl(r_bot, 1, at=(0, 0, 0.5))
profile_top = cyl(r_top, 1, at=(0, 0, cup_h - 0.5))
cup_body = trimesh.convex.convex_hull(union([profile_bot, profile_top]))
lid_rim = cyl(12.8, 2.5, at=(0, 0, cup_h + 1.25))
dome = sph(11.8, at=(0, 0, cup_h + 1.5), scale=(1, 1, 0.85))
dome = difference(dome, box(40, 40, 20, at=(0, 0, cup_h + 1.5 - 10)))
swirl = union([
    sph(6.5, at=(0, 0, cup_h + 8), scale=(1.1, 1.1, 0.8)),
    sph(4.5, at=(0, 0, cup_h + 12), scale=(1, 1, 0.9)),
    sph(2.8, at=(0, 0, cup_h + 15.5)),
])
cup_cream = [cup_body, lid_rim, dome, swirl]
straw = cyl(2.0, 16, at=(0, 0, cup_h + 18))
straw.apply_transform(T(0, 0, cup_h + 14) @ RX(12) @ T(0, 0, -(cup_h + 14)))
cup_brown = [straw]
# heart relief on the cup front (+Y side), embedded into the taper
heart = heart_mesh(size=6.5, depth=2.4)
heart.apply_transform(FACE_PLUS_Y)
heart.apply_transform(T(0, 9.2, 13))
cup_brown.append(heart)
# place the cup into the left hand
cup_xf = T(52, 17, 98)
for m in cup_cream + cup_brown:
    m.apply_transform(cup_xf)
add("cream", *cup_cream)
add("brown", *cup_brown)

# ============================================================ EXPORT

print("unioning color groups...")
group_meshes = {}
for name, ms in parts.items():
    group_meshes[name] = union(ms)
    print(f"  {name}: {len(ms)} parts -> watertight={group_meshes[name].is_watertight}")

print("unioning full model...")
full = union(list(group_meshes.values()))

# scale so total height is exactly 8 inches, and sit on z=0
zmin, zmax = full.bounds[0][2], full.bounds[1][2]
scale = TARGET_HEIGHT_MM / (zmax - zmin)
print(f"design height {zmax - zmin:.1f} -> scale x{scale:.4f}")
xf = T(0, 0, 0)
for m in list(group_meshes.values()) + [full]:
    m.apply_scale(scale)
    m.apply_translation((0, 0, -zmin * scale))

print(f"full model: watertight={full.is_watertight}, "
      f"bounds={np.round(full.extents, 1)} mm, faces={len(full.faces)}")
assert full.is_watertight, "model is not watertight!"

full.export(os.path.join(OUT, "tk_adventure_figurine.stl"))
os.makedirs(os.path.join(OUT, "parts"), exist_ok=True)
for name, m in group_meshes.items():
    m.export(os.path.join(OUT, "parts", f"{name}.stl"))
print("STL export done.")

# ---------------------------------------------------------------- preview
print("rendering previews...")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

COLORS = {
    "blue": "#1867c7", "white": "#f4f2ec", "yellow": "#f6c211",
    "brown": "#8a4b22", "black": "#232323", "cream": "#e8c99a",
}

all_tris, all_fc = [], []
light = np.array([0.4, 0.7, 0.6])
light = light / np.linalg.norm(light)
for name, m in group_meshes.items():
    all_tris.append(m.vertices[m.faces])
    base = np.array(matplotlib.colors.to_rgb(COLORS[name]))
    lam = np.clip(m.face_normals @ light, 0, 1)
    shade_f = (0.45 + 0.55 * lam)[:, None]
    fc = np.clip(base[None, :] * shade_f, 0, 1)
    all_fc.append(np.hstack([fc, np.ones((len(fc), 1))]))
all_tris = np.concatenate(all_tris)
all_fc = np.concatenate(all_fc)

def render(fname, elev, azim):
    fig = plt.figure(figsize=(7, 10), dpi=110)
    ax = fig.add_subplot(111, projection="3d")
    pc = Poly3DCollection(all_tris, facecolors=all_fc, edgecolors="none")
    ax.add_collection3d(pc)
    ext = full.bounds
    c = (ext[0] + ext[1]) / 2
    r = (ext[1] - ext[0]).max() / 2
    ax.set_xlim(c[0] - r, c[0] + r)
    ax.set_ylim(c[1] - r, c[1] + r)
    ax.set_zlim(0, 2 * r)
    ax.set_box_aspect((1, 1, 1))
    ax.set_axis_off()
    ax.view_init(elev=elev, azim=azim)
    plt.tight_layout(pad=0)
    plt.savefig(os.path.join(OUT, fname), bbox_inches="tight",
                facecolor="#efeff2")
    plt.close(fig)

# viewer at azim=90 stands on the +Y side: the figure's front
render("preview_front.png", elev=8, azim=90)
render("preview_three_quarter.png", elev=12, azim=60)
print("previews done.")
