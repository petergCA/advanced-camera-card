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
             ds=0.35, nphi=18, radial=1.0, stripe=HALF_TWIST):
    """A 2-ply twisted rope ring following the rounded-rect path.

    handed: +1 (row A) or -1 (row B). Twist count is rounded to a whole
    number of half-turns for seamless closure; pitch shifts imperceptibly.
    radial < 1 squashes the rope toward the wall (elliptical cross-section);
    stripe is the target arc length of one visible twist stripe.
    Returns a list of watertight meshes (one or two tori).
    """
    P = perimeter(W, L, R)
    n_half = max(2, round(P / stripe))
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
        d_off = radial * (cd[:, None] + strand_r * np.cos(phi)[None, :])
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
ROPE_H0 = 2 * (STRAND_R + PLY_OFFSET)   # original rope height (4.192 mm)


def build_parts(width, length, height, corner_r=CORNER_R_DEFAULT,
                rope_h=None, rope_d=None, stripe=None, ds=0.35, nphi=18,
                base_t=BASE_T):
    """Build the unique meshes plus their placements (no union).

    rope_h / rope_d set the rope cross-section (vertical x radial, mm);
    default is the original 4.19 x 4.19. Row spacing, foot, and twist stripe
    pitch scale proportionally with rope_h unless stripe is given explicitly.
    Returns a dict: named unique meshes and lists of z offsets where the two
    row types repeat. Row meshes are centered on z=0; base/foot sit at
    their absolute position.
    """
    corner_r = min(corner_r, width / 2 - 1, length / 2 - 1)
    if rope_h is None:
        rope_h = ROPE_H0
    if rope_d is None:
        rope_d = rope_h
    s = rope_h / ROPE_H0                 # vertical scale vs. the original
    radial = rope_d / rope_h
    if stripe is None:
        stripe = HALF_TWIST * s
    strand_r = STRAND_R * s
    ply_e = PLY_OFFSET * s
    row0 = ROW0_Z * s
    pair = PAIR_PITCH * s
    gap_ab = GAP_AB * s
    half_h = rope_h / 2
    if row0 - half_h > base_t - 0.3:
        row0 = base_t - 0.3 + half_h     # keep the first row rooted in the base

    n_pairs = max(1, round((height - row0 - half_h) / pair))
    actual_h = row0 + n_pairs * pair + half_h
    P = perimeter(width, length, corner_r)
    n_half = max(2, round(P / stripe))
    print(f"outline {width} x {length}, corner R{corner_r}, perimeter {P:.1f} mm")
    print(f"rope: {rope_h:.1f} tall x {rope_d:.1f} deep, row pitch {pair / 2:.2f}")
    print(f"rows: {n_pairs + 1} A + {n_pairs} B -> height {actual_h:.1f} mm "
          f"(requested {height})")
    print(f"twist: {n_half} half-turns, stripe pitch {P / n_half:.2f} mm "
          f"(target {stripe:.2f})")

    base = base_slab(width, length, corner_r, base_t)

    # foot ring around the base band, scaled like the wall rope
    foot = rope_row(width, length, corner_r, min(FOOT_Z * s, base_t / 2), -1,
                    TWIST_B_PHASE, FOOT_R * s, FOOT_OFFSET * s, ds, nphi,
                    radial, stripe)
    big = max(width, length) + 4 * rope_d + 20
    band = trimesh.creation.box(extents=(big, big, base_t))
    band.apply_translation((0, 0, base_t / 2))
    foot = trimesh.boolean.union(
        [trimesh.boolean.intersection([f, band], engine="manifold")
         for f in foot], engine="manifold")

    row_a = trimesh.boolean.union(
        rope_row(width, length, corner_r, 0.0, +1, TWIST_A_PHASE,
                 strand_r, ply_e, ds, nphi, radial, stripe), engine="manifold")
    row_b = trimesh.boolean.union(
        rope_row(width, length, corner_r, 0.0, -1, TWIST_B_PHASE,
                 strand_r, ply_e, ds, nphi, radial, stripe), engine="manifold")
    z_a = [row0 + i * pair for i in range(n_pairs + 1)]
    z_b = [row0 + gap_ab + i * pair for i in range(n_pairs)]
    return {"base": base, "foot": foot, "row_a": row_a, "row_b": row_b,
            "z_a": z_a, "z_b": z_b, "actual_h": actual_h}


def build_basket(width, length, height, corner_r=CORNER_R_DEFAULT,
                 rope_h=None, rope_d=None, stripe=None, ds=0.35, nphi=18,
                 parts=None):
    """Single watertight union of the whole basket (heavy for tall baskets)."""
    if parts is None:
        parts = build_parts(width, length, height, corner_r, rope_h,
                            rope_d, stripe, ds, nphi)
    sol = [parts["base"], parts["foot"]]
    for z in parts["z_a"]:
        m = parts["row_a"].copy(); m.apply_translation((0, 0, z)); sol.append(m)
    for z in parts["z_b"]:
        m = parts["row_b"].copy(); m.apply_translation((0, 0, z)); sol.append(m)
    print(f"unioning {len(sol)} parts...")
    basket = trimesh.boolean.union(sol, engine="manifold")
    print(f"watertight={basket.is_watertight}  extents={np.round(basket.extents, 1)}"
          f"  volume={basket.volume / 1000:.1f} cm^3  faces={len(basket.faces)}")
    return basket


# ------------------------- Bambu Studio project export -------------------------
NSXML = ('xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
         'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" '
         'requiredextensions="p"')
IDENT = "1 0 0 0 1 0 0 0 1 0 0 0"
CONTENT_TYPES = ('<?xml version="1.0" encoding="UTF-8"?>\n'
 '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
 ' <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
 ' <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n'
 ' <Default Extension="png" ContentType="image/png"/>\n'
 '</Types>')
RELS = ('<?xml version="1.0" encoding="UTF-8"?>\n'
 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
 ' <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel" />\n'
 '</Relationships>')
OBJ_RELS = ('<?xml version="1.0" encoding="UTF-8"?>\n'
 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
 ' <Relationship Target="/3D/Objects/object_1.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n'
 '</Relationships>')
SLICE_INFO = ('<?xml version="1.0" encoding="UTF-8"?>\n'
 '<config>\n  <header>\n'
 '    <header_item key="X-BBL-Client-Type" value="slicer"/>\n'
 '    <header_item key="X-BBL-Client-Version" value="02.04.00.70"/>\n'
 '  </header>\n</config>')


def _mesh_xml(buf, oid, mesh):
    """Append one <object> element containing a mesh to the string buffer."""
    import uuid
    buf.write(f'  <object id="{oid}" p:UUID="{uuid.uuid4()}" type="model">\n'
              '   <mesh>\n    <vertices>\n')
    for x, y, z in np.asarray(mesh.vertices, dtype=np.float64):
        buf.write(f'     <vertex x="{x:.9g}" y="{y:.9g}" z="{z:.9g}"/>\n')
    buf.write('    </vertices>\n    <triangles>\n')
    for a, b, c in np.asarray(mesh.faces, dtype=np.int64):
        buf.write(f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>\n')
    buf.write('    </triangles>\n   </mesh>\n  </object>\n')


def _write_package(path, objects_xml, root_xml, model_settings, obj_id,
                   template_3mf=None):
    import zipfile
    cut_info = ('<?xml version="1.0" encoding="utf-8"?>\n<objects>\n'
                f' <object id="{obj_id}">\n'
                '  <cut_id id="0" check_sum="1" connectors_cnt="0"/>\n'
                ' </object>\n</objects>')
    project_settings = None
    if template_3mf and os.path.exists(template_3mf):
        try:
            with zipfile.ZipFile(template_3mf) as z:
                project_settings = z.read("Metadata/project_settings.config")
            print(f"carrying print profile over from {os.path.basename(template_3mf)}")
        except KeyError:
            print("template has no project_settings.config; writing without profile")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("3D/3dmodel.model", root_xml)
        z.writestr("3D/_rels/3dmodel.model.rels", OBJ_RELS)
        z.writestr("3D/Objects/object_1.model", objects_xml)
        z.writestr("Metadata/model_settings.config", model_settings)
        z.writestr("Metadata/slice_info.config", SLICE_INFO)
        z.writestr("Metadata/cut_information.xml", cut_info)
        z.writestr("Metadata/filament_sequence.json", '{"plate_1":{"sequence":[]}}')
        if project_settings is not None:
            z.writestr("Metadata/project_settings.config", project_settings)


def _root_and_settings(name, components, total_faces):
    """3dmodel.model + model_settings.config for a list of components.

    components: list of (mesh_object_id, part_name, z_offset, face_count).
    The assembly object id is max mesh id + 1.
    """
    import uuid
    obj_id = max(c[0] for c in components) + 1
    comp_lines, part_lines = [], []
    for i, (mid, pname, z, fc) in enumerate(components):
        comp_lines.append(
            f'    <component p:path="/3D/Objects/object_1.model" objectid="{mid}" '
            f'p:UUID="{uuid.uuid4()}" transform="1 0 0 0 1 0 0 0 1 0 0 {z:.9g}" />')
        part_lines.append(
            f'    <part id="{i + 1}" subtype="normal_part">\n'
            f'      <metadata key="name" value="{pname}"/>\n'
            f'      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 {z:.9g} 0 0 0 1"/>\n'
            f'      <metadata key="source_object_id" value="{i}"/>\n'
            f'      <metadata key="source_volume_id" value="0"/>\n'
            f'      <metadata key="extruder" value="1"/>\n'
            f'      <mesh_stat face_count="{fc}" edges_fixed="0" degenerate_facets="0"'
            f' facets_removed="0" facets_reversed="0" backwards_edges="0"/>\n'
            f'    </part>')
    comp_block = "\n".join(comp_lines)
    part_block = "\n".join(part_lines)
    root_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<model unit="millimeter" xml:lang="en-US" {NSXML} '
        'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021">\n'
        ' <metadata name="Application">BambuStudio-02.04.00.70</metadata>\n'
        ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n'
        f' <metadata name="Title">{name}</metadata>\n'
        ' <resources>\n'
        f'  <object id="{obj_id}" p:UUID="{uuid.uuid4()}" type="model">\n'
        '   <components>\n'
        f'{comp_block}\n'
        '   </components>\n'
        '  </object>\n'
        ' </resources>\n'
        f' <build p:UUID="{uuid.uuid4()}">\n'
        f'  <item objectid="{obj_id}" p:UUID="{uuid.uuid4()}" '
        'transform="1 0 0 0 1 0 0 0 1 128 128 0" printable="1" />\n'
        ' </build>\n'
        '</model>\n')
    model_settings = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<config>\n'
        f'  <object id="{obj_id}">\n'
        f'    <metadata key="name" value="{name}"/>\n'
        '    <metadata key="extruder" value="1"/>\n'
        f'    <metadata face_count="{total_faces}"/>\n'
        f'{part_block}\n'
        '  </object>\n'
        '  <plate>\n'
        '    <metadata key="plater_id" value="1"/>\n'
        '    <metadata key="plater_name" value=""/>\n'
        '    <metadata key="locked" value="false"/>\n'
        '    <model_instance>\n'
        f'      <metadata key="object_id" value="{obj_id}"/>\n'
        '      <metadata key="instance_id" value="0"/>\n'
        '      <metadata key="identify_id" value="84"/>\n'
        '    </model_instance>\n'
        '  </plate>\n'
        '  <assemble>\n'
        f'   <assemble_item object_id="{obj_id}" instance_id="0" '
        f'transform="{IDENT}" offset="0 0 0" />\n'
        '  </assemble>\n'
        '</config>\n')
    return root_xml, model_settings, obj_id


def export_bambu_project_3mf(mesh, path, name="Weave Basket", template_3mf=None):
    """Single-mesh Bambu Studio project 3MF (for already-unioned models)."""
    import io
    buf = io.StringIO()
    buf.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    buf.write(f'<model unit="millimeter" xml:lang="en-US" {NSXML}>\n')
    buf.write(' <metadata name="BambuStudio:3mfVersion">1</metadata>\n <resources>\n')
    _mesh_xml(buf, 1, mesh)
    buf.write(' </resources>\n</model>\n')
    comps = [(1, "Basket", 0.0, len(mesh.faces))]
    root_xml, model_settings, obj_id = _root_and_settings(name, comps,
                                                          len(mesh.faces))
    _write_package(path, buf.getvalue(), root_xml, model_settings, obj_id,
                   template_3mf)


def export_bambu_assembly_3mf(parts, path, name="Weave Basket",
                              template_3mf=None):
    """Instanced Bambu project 3MF: each unique row mesh is stored once and
    referenced at every height it repeats, so tall baskets stay small on disk
    (the original WeaveBasketv3.3mf uses the same component structure, just
    with the row meshes duplicated).
    """
    import io
    buf = io.StringIO()
    buf.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    buf.write(f'<model unit="millimeter" xml:lang="en-US" {NSXML}>\n')
    buf.write(' <metadata name="BambuStudio:3mfVersion">1</metadata>\n <resources>\n')
    _mesh_xml(buf, 1, parts["base"])
    _mesh_xml(buf, 2, parts["foot"])
    _mesh_xml(buf, 3, parts["row_a"])
    _mesh_xml(buf, 4, parts["row_b"])
    buf.write(' </resources>\n</model>\n')

    fa, fb = len(parts["row_a"].faces), len(parts["row_b"].faces)
    comps = [(1, "Base", 0.0, len(parts["base"].faces)),
             (2, "Foot", 0.0, len(parts["foot"].faces))]
    comps += [(3, f"RowA_{i + 1}", z, fa) for i, z in enumerate(parts["z_a"])]
    comps += [(4, f"RowB_{i + 1}", z, fb) for i, z in enumerate(parts["z_b"])]
    total = sum(c[3] for c in comps)
    root_xml, model_settings, obj_id = _root_and_settings(name, comps, total)
    _write_package(path, buf.getvalue(), root_xml, model_settings, obj_id,
                   template_3mf)
    print(f"assembly 3MF: {len(comps)} parts from 4 unique meshes, "
          f"{total} faces total when expanded")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--width", type=float, default=120.0,
                    help="base outline width, mm (footprint = +4.2)")
    ap.add_argument("--length", type=float, default=80.0,
                    help="base outline length, mm")
    ap.add_argument("--height", type=float, default=41.3,
                    help="target height, mm (snapped to whole rows)")
    ap.add_argument("--corner-radius", type=float, default=CORNER_R_DEFAULT)
    ap.add_argument("--rope-height", type=float, default=None,
                    help="vertical size of one rope row, mm (default 4.19, "
                         "the original); row spacing scales with it")
    ap.add_argument("--rope-depth", type=float, default=None,
                    help="radial size of the rope / wall thickness, mm "
                         "(default = rope height)")
    ap.add_argument("--stripe-pitch", type=float, default=None,
                    help="arc length of one visible twist stripe, mm "
                         "(default scales with rope height)")
    ap.add_argument("--base-thickness", type=float, default=BASE_T,
                    help="solid base slab thickness, mm")
    ap.add_argument("--nphi", type=int, default=18,
                    help="facets around the rope strand (raise for fat ropes)")
    ap.add_argument("--resolution", type=float, default=0.35,
                    help="sweep step along the rope, mm")
    ap.add_argument("-o", "--output", default="weave_basket",
                    help="output file basename")
    ap.add_argument("--template", default=None,
                    help="path to the original WeaveBasketv3.3mf; its Bambu "
                         "print profile is embedded in the output 3MF")
    ap.add_argument("--no-stl", action="store_true",
                    help="skip the unioned STL (much faster for tall baskets; "
                         "the instanced 3MF is written either way)")
    args = ap.parse_args()

    parts = build_parts(args.width, args.length, args.height,
                        args.corner_radius, args.rope_height, args.rope_depth,
                        args.stripe_pitch, ds=args.resolution, nphi=args.nphi,
                        base_t=args.base_thickness)
    out = os.path.dirname(os.path.abspath(__file__))
    tmf = os.path.join(out, args.output + ".3mf")
    export_bambu_assembly_3mf(parts, tmf, name=args.output,
                              template_3mf=args.template)
    print("wrote", tmf)
    if not args.no_stl:
        basket = build_basket(args.width, args.length, args.height,
                              parts=parts)
        stl = os.path.join(out, args.output + ".stl")
        basket.export(stl)
        print("wrote", stl)


if __name__ == "__main__":
    main()
