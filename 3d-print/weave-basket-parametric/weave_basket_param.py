#!/usr/bin/env python3
"""Parametric rebuild of Eternity Labs' "The Weave Stitch Basket" (WeaveBasketv3).

The original 3MF is a fixed 120 x 80 x 41.3 mm assembly. Reverse-engineering it
shows every wall row is a 2-ply twisted rope swept around a rounded-rectangle
path (strand radius 1.197 mm, ply offset 0.899 mm, exactly 40 half-twists
around the 382.8 mm perimeter = 9.571 mm per half-twist), with adjacent rows
twisted in opposite directions (that's what creates the chevron weave look),
stacked at alternating +3.4 / +1.8 mm gaps, over a 3 mm solid base with a
smaller flat-trimmed rope as a foot/starter ring.

This script regenerates the basket at ANY size while keeping the rope geometry
constant: enlarging the basket adds twists along the perimeter and rows up the
wall - nothing stretches, and walls stay a single-rope thick so material use
scales with area, not volume.

Usage:
    python3 weave_basket_param.py --width 120 --length 80 --height 41.3
    python3 weave_basket_param.py --width 170 --length 110 --height 60 -o big_basket

All dimensions in mm. width/length are the base-outline size (the rope wall
bulges ~2.1 mm outward beyond that; overall footprint = width+4.2 etc.).
Height is snapped to a whole number of rope rows and reported.

Requires: numpy, trimesh, manifold3d, shapely, scipy(optional)
"""

import argparse
import math
import os

import numpy as np
import trimesh

# ----------------- rope constants measured from the original -----------------
STRAND_R = 1.197        # strand (ply) radius
PLY_OFFSET = 0.899      # distance of each ply center from the path
HALF_TWIST = 9.571      # arc length of one half-twist (visible stripe pitch)
TWIST_A_PHASE = 2.434   # ply rotation phase of row type A at s=0
TWIST_B_PHASE = 0.698   # ply rotation phase of row type B (opposite handedness)
ROW0_Z = 2.8            # center height of the first A row
PAIR_PITCH = 5.2        # vertical pitch of an A+B row pair
GAP_AB = 3.4            # z gap A -> B within a pair (B center = A center + 3.4)
BASE_T = 3.0            # base slab thickness
FOOT_R = 1.336          # starter/foot rope strand radius
FOOT_OFFSET = 0.545     # starter ply offset
FOOT_Z = 1.548          # starter rope center height
CORNER_R_DEFAULT = 10.0


# ----------------------- rounded-rectangle path helpers -----------------------
def path_frame(W, L, R, s):
    """Point and outward normal of the rounded-rect outline at arc length s.

    Path starts at (-hx, -L/2) heading +x, runs counter-clockwise.
    Returns (px, py, nx, ny) arrays for array input s.
    """
    hx, hy = W / 2 - R, L / 2 - R
    arc = math.pi / 2 * R
    P = 4 * hx + 4 * hy + 4 * arc
    s = np.mod(s, P)
    px = np.empty_like(s); py = np.empty_like(s)
    nx = np.empty_like(s); ny = np.empty_like(s)
    b = [0, 2 * hx, 2 * hx + arc, 2 * hx + arc + 2 * hy, 2 * hx + 2 * arc + 2 * hy,
         4 * hx + 2 * arc + 2 * hy, 4 * hx + 3 * arc + 2 * hy,
         4 * hx + 3 * arc + 4 * hy, P]
    # bottom edge
    m = s < b[1]
    px[m] = -hx + s[m]; py[m] = -L / 2; nx[m] = 0; ny[m] = -1
    # BR corner
    m = (s >= b[1]) & (s < b[2])
    a = -math.pi / 2 + (s[m] - b[1]) / R
    px[m] = hx + R * np.cos(a); py[m] = -hy + R * np.sin(a)
    nx[m] = np.cos(a); ny[m] = np.sin(a)
    # right edge
    m = (s >= b[2]) & (s < b[3])
    px[m] = W / 2; py[m] = -hy + (s[m] - b[2]); nx[m] = 1; ny[m] = 0
    # TR corner
    m = (s >= b[3]) & (s < b[4])
    a = (s[m] - b[3]) / R
    px[m] = hx + R * np.cos(a); py[m] = hy + R * np.sin(a)
    nx[m] = np.cos(a); ny[m] = np.sin(a)
    # top edge
    m = (s >= b[4]) & (s < b[5])
    px[m] = hx - (s[m] - b[4]); py[m] = L / 2; nx[m] = 0; ny[m] = 1
    # TL corner
    m = (s >= b[5]) & (s < b[6])
    a = math.pi / 2 + (s[m] - b[5]) / R
    px[m] = -hx + R * np.cos(a); py[m] = hy + R * np.sin(a)
    nx[m] = np.cos(a); ny[m] = np.sin(a)
    # left edge
    m = (s >= b[6]) & (s < b[7])
    px[m] = -W / 2; py[m] = hy - (s[m] - b[6]); nx[m] = -1; ny[m] = 0
    # BL corner
    m = s >= b[7]
    a = math.pi + (s[m] - b[7]) / R
    px[m] = -hx + R * np.cos(a); py[m] = -hy + R * np.sin(a)
    nx[m] = np.cos(a); ny[m] = np.sin(a)
    return px, py, nx, ny


def perimeter(W, L, R):
    return 4 * (W / 2 - R) + 4 * (L / 2 - R) + 2 * math.pi * R


# ------------------------------- mesh builders --------------------------------
def torus_grid_mesh(pts_ring):
    """Close a (ns, nphi, 3) grid of tube rings into a watertight torus mesh."""
    ns, nphi, _ = pts_ring.shape
    V = pts_ring.reshape(-1, 3)
    i = np.arange(ns)[:, None]
    j = np.arange(nphi)[None, :]
    a = i * nphi + j
    bq = ((i + 1) % ns) * nphi + j
    c = ((i + 1) % ns) * nphi + (j + 1) % nphi
    d = i * nphi + (j + 1) % nphi
    F = np.concatenate([np.stack([a, bq, c], axis=-1).reshape(-1, 3),
                        np.stack([a, c, d], axis=-1).reshape(-1, 3)])
    return trimesh.Trimesh(vertices=V, faces=F, process=False)


def rope_row(W, L, R, z_center, handed, phase, strand_r, ply_e,
             ds=0.35, nphi=18):
    """A 2-ply twisted rope ring following the rounded-rect path.

    handed: +1 (row A) or -1 (row B). Twist count is rounded to a whole
    number of half-turns for seamless closure; pitch shifts imperceptibly.
    Returns a list of watertight meshes (one or two tori).
    """
    P = perimeter(W, L, R)
    n_half = max(2, round(P / HALF_TWIST))
    rate = handed * n_half * math.pi / P     # rad per mm, exact closure

    loops = 1 if n_half % 2 == 0 else 2      # odd half-turns: plies join into one loop
    ns = int(np.ceil(P * loops / ds))
    s = np.linspace(0, P * loops, ns, endpoint=False)
    px, py, nxv, nyv = path_frame(W, L, R, s)
    phi = np.linspace(0, 2 * math.pi, nphi, endpoint=False)

    meshes = []
    n_plies = 1 if loops == 2 else 2
    for k in range(n_plies):
        th = rate * s + phase + k * math.pi
        cd = ply_e * np.cos(th)              # ply center offset along outward normal
        cz = ply_e * np.sin(th)              # ... and along z
        d_off = cd[:, None] + strand_r * np.cos(phi)[None, :]
        z_off = cz[:, None] + strand_r * np.sin(phi)[None, :]
        X = px[:, None] + nxv[:, None] * d_off
        Y = py[:, None] + nyv[:, None] * d_off
        Z = z_center + z_off
        meshes.append(torus_grid_mesh(np.stack([X, Y, Z], axis=-1)))
    return meshes


def base_slab(W, L, R, thickness, seg=48):
    from shapely.geometry import Point, box as sbox
    from shapely.ops import unary_union
    hx, hy = W / 2 - R, L / 2 - R
    shape = unary_union([sbox(-hx, -L / 2, hx, L / 2), sbox(-W / 2, -hy, W / 2, hy),
                         Point(hx, hy).buffer(R, resolution=seg),
                         Point(-hx, hy).buffer(R, resolution=seg),
                         Point(hx, -hy).buffer(R, resolution=seg),
                         Point(-hx, -hy).buffer(R, resolution=seg)])
    m = trimesh.creation.extrude_polygon(shape, height=thickness)
    return m


# --------------------------------- assembly -----------------------------------
def build_basket(width, length, height, corner_r=CORNER_R_DEFAULT,
                 strand_r=STRAND_R, ply_e=PLY_OFFSET, ds=0.35, nphi=18):
    corner_r = min(corner_r, width / 2 - 1, length / 2 - 1)
    n_pairs = max(1, round((height - ROW0_Z - strand_r - PLY_OFFSET) / PAIR_PITCH))
    top_a_z = ROW0_Z + n_pairs * PAIR_PITCH
    actual_h = top_a_z + strand_r + ply_e
    P = perimeter(width, length, corner_r)
    n_half = max(2, round(P / HALF_TWIST))
    print(f"outline {width} x {length}, corner R{corner_r}, perimeter {P:.1f} mm")
    print(f"rows: {n_pairs + 1} A + {n_pairs} B -> height {actual_h:.1f} mm "
          f"(requested {height})")
    print(f"twist: {n_half} half-turns, pitch {P / n_half:.3f} mm "
          f"(original {HALF_TWIST})")

    parts = [base_slab(width, length, corner_r, BASE_T)]

    # foot/starter ring, trimmed flush to the base slab band
    foot = rope_row(width, length, corner_r, FOOT_Z, -1, TWIST_B_PHASE,
                    FOOT_R, FOOT_OFFSET, ds, nphi)
    big = max(width, length) + 20
    band = trimesh.creation.box(extents=(big, big, BASE_T))
    band.apply_translation((0, 0, BASE_T / 2))
    foot = [trimesh.boolean.intersection([f, band], engine="manifold")
            for f in foot]
    parts += foot

    for i in range(n_pairs + 1):
        za = ROW0_Z + i * PAIR_PITCH
        parts += rope_row(width, length, corner_r, za, +1, TWIST_A_PHASE,
                          strand_r, ply_e, ds, nphi)
        if i < n_pairs:
            parts += rope_row(width, length, corner_r, za + GAP_AB, -1,
                              TWIST_B_PHASE, strand_r, ply_e, ds, nphi)

    print(f"unioning {len(parts)} parts...")
    basket = trimesh.boolean.union(parts, engine="manifold")
    print(f"watertight={basket.is_watertight}  extents={np.round(basket.extents, 1)}"
          f"  volume={basket.volume / 1000:.1f} cm^3  faces={len(basket.faces)}")
    return basket


# ------------------------- Bambu Studio project export -------------------------
def export_bambu_project_3mf(mesh, path, name="Weave Basket", template_3mf=None):
    """Write a Bambu Studio project 3MF (loads without the "invalid config,
    load geometry data only" dialog).

    Bambu treats a 3MF as a project only when its Metadata/ config files are
    present and consistent with the geometry, so this writes the full package:
    geometry in 3D/Objects/object_1.model, an assembly in 3D/3dmodel.model,
    and a matching model_settings.config. If template_3mf points to the
    original WeaveBasketv3.3mf, its print profile (project_settings.config)
    is carried over so the designer's tuned settings load too.
    """
    import io
    import uuid
    import zipfile

    V = np.asarray(mesh.vertices, dtype=np.float64)
    F = np.asarray(mesh.faces, dtype=np.int64)
    nsxml = ('xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
             'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" '
             'requiredextensions="p"')

    buf = io.StringIO()
    buf.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    buf.write(f'<model unit="millimeter" xml:lang="en-US" {nsxml}>\n')
    buf.write(' <metadata name="BambuStudio:3mfVersion">1</metadata>\n')
    buf.write(f' <resources>\n  <object id="1" p:UUID="{uuid.uuid4()}" type="model">\n'
              '   <mesh>\n    <vertices>\n')
    for x, y, z in V:
        buf.write(f'     <vertex x="{x:.9g}" y="{y:.9g}" z="{z:.9g}"/>\n')
    buf.write('    </vertices>\n    <triangles>\n')
    for a, b, c in F:
        buf.write(f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>\n')
    buf.write('    </triangles>\n   </mesh>\n  </object>\n </resources>\n</model>\n')
    object_xml = buf.getvalue()

    ident = "1 0 0 0 1 0 0 0 1 0 0 0"
    root_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xml:lang="en-US" {nsxml} xmlns:BambuStudio="http://schemas.bambulab.com/package/2021">
 <metadata name="Application">BambuStudio-02.04.00.70</metadata>
 <metadata name="BambuStudio:3mfVersion">1</metadata>
 <metadata name="Title">{name}</metadata>
 <resources>
  <object id="2" p:UUID="{uuid.uuid4()}" type="model">
   <components>
    <component p:path="/3D/Objects/object_1.model" objectid="1" p:UUID="{uuid.uuid4()}" transform="{ident}" />
   </components>
  </object>
 </resources>
 <build p:UUID="{uuid.uuid4()}">
  <item objectid="2" p:UUID="{uuid.uuid4()}" transform="1 0 0 0 1 0 0 0 1 128 128 0" printable="1" />
 </build>
</model>
'''
    model_settings = f'''<?xml version="1.0" encoding="UTF-8"?>
<config>
  <object id="2">
    <metadata key="name" value="{name}"/>
    <metadata key="extruder" value="1"/>
    <metadata face_count="{len(F)}"/>
    <part id="1" subtype="normal_part">
      <metadata key="name" value="Basket"/>
      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>
      <metadata key="source_object_id" value="0"/>
      <metadata key="source_volume_id" value="0"/>
      <metadata key="extruder" value="1"/>
      <mesh_stat face_count="{len(F)}" edges_fixed="0" degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>
    </part>
  </object>
  <plate>
    <metadata key="plater_id" value="1"/>
    <metadata key="plater_name" value=""/>
    <metadata key="locked" value="false"/>
    <model_instance>
      <metadata key="object_id" value="2"/>
      <metadata key="instance_id" value="0"/>
      <metadata key="identify_id" value="84"/>
    </model_instance>
  </plate>
  <assemble>
   <assemble_item object_id="2" instance_id="0" transform="{ident}" offset="0 0 0" />
  </assemble>
</config>
'''
    content_types = '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
 <Default Extension="png" ContentType="image/png"/>
</Types>'''
    rels = '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel" />
</Relationships>'''
    obj_rels = '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/Objects/object_1.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>'''
    slice_info = '''<?xml version="1.0" encoding="UTF-8"?>
<config>
  <header>
    <header_item key="X-BBL-Client-Type" value="slicer"/>
    <header_item key="X-BBL-Client-Version" value="02.04.00.70"/>
  </header>
</config>'''
    cut_info = '''<?xml version="1.0" encoding="utf-8"?>
<objects>
 <object id="2">
  <cut_id id="0" check_sum="1" connectors_cnt="0"/>
 </object>
</objects>'''

    project_settings = None
    if template_3mf and os.path.exists(template_3mf):
        try:
            with zipfile.ZipFile(template_3mf) as z:
                project_settings = z.read("Metadata/project_settings.config")
            print(f"carrying print profile over from {os.path.basename(template_3mf)}")
        except KeyError:
            print("template has no project_settings.config; writing without profile")

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", root_xml)
        z.writestr("3D/_rels/3dmodel.model.rels", obj_rels)
        z.writestr("3D/Objects/object_1.model", object_xml)
        z.writestr("Metadata/model_settings.config", model_settings)
        z.writestr("Metadata/slice_info.config", slice_info)
        z.writestr("Metadata/cut_information.xml", cut_info)
        z.writestr("Metadata/filament_sequence.json", '{"plate_1":{"sequence":[]}}')
        if project_settings is not None:
            z.writestr("Metadata/project_settings.config", project_settings)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--width", type=float, default=120.0,
                    help="base outline width, mm (footprint = +4.2)")
    ap.add_argument("--length", type=float, default=80.0,
                    help="base outline length, mm")
    ap.add_argument("--height", type=float, default=41.3,
                    help="target height, mm (snapped to whole rows)")
    ap.add_argument("--corner-radius", type=float, default=CORNER_R_DEFAULT)
    ap.add_argument("--strand-radius", type=float, default=STRAND_R,
                    help="rope strand radius (constant regardless of size)")
    ap.add_argument("--resolution", type=float, default=0.35,
                    help="sweep step along the rope, mm")
    ap.add_argument("-o", "--output", default="weave_basket",
                    help="output file basename")
    ap.add_argument("--template", default=None,
                    help="path to the original WeaveBasketv3.3mf; its Bambu "
                         "print profile is embedded in the output 3MF")
    args = ap.parse_args()

    basket = build_basket(args.width, args.length, args.height,
                          args.corner_radius, args.strand_radius,
                          ds=args.resolution)
    out = os.path.dirname(os.path.abspath(__file__))
    stl = os.path.join(out, args.output + ".stl")
    tmf = os.path.join(out, args.output + ".3mf")
    basket.export(stl)
    export_bambu_project_3mf(basket, tmf, name=args.output,
                             template_3mf=args.template)
    print("wrote", stl, "and", tmf)


if __name__ == "__main__":
    main()
