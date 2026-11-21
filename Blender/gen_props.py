"""ICE RIOT props: hat-trick hats, gag ambulance, ice resurfacer, 3D title logo.

    blender -b --factory-startup --python-exit-code 1 -P Blender/gen_props.py

Outputs Meshes/SM_Hat1..3, SM_Ambulance, SM_Resurfacer, SM_TitleLogo (+ Materials/props.json).
Vehicles: ground contact at z = 0, centered on the origin, driving toward +X (Unreal +X).
Hats: pivot at the hat center. Title logo: centered on the origin, letters face -Blender Y (= Unreal +Y).
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Vector, Matrix  # noqa: E402

import ir_common as hc  # noqa: E402
import ir_env as eh  # noqa: E402
import ir_draw as dr  # noqa: E402

M = eh.MatLib("props")


def mats():
    m = {}
    m["hat1"] = M.opaque("MI_Hat1", eh.lin("#C8102E"), roughness=0.8)
    m["hat2"] = M.opaque("MI_Hat2", eh.lin("#1F4FD8"), roughness=0.85)
    m["hat3"] = M.opaque("MI_Hat3", eh.lin("#2A2A2E"), roughness=0.7)
    m["hatband"] = M.opaque("MI_HatTrim", eh.lin("#F2F2F2"), roughness=0.8)
    m["amb_body"] = M.opaque("MI_AmbulanceBody", eh.lin("#F7F7F2"), roughness=0.35)
    m["amb_stripe"] = M.opaque("MI_AmbulanceStripe", eh.lin("#E0182D"), roughness=0.35)
    m["amb_text"] = M.opaque("MI_AmbulanceText", eh.lin("#E0182D"), roughness=0.4)
    m["glass"] = M.opaque("MI_VehicleGlass", eh.lin("#1D2A3A"), roughness=0.08, metallic=0.3)
    m["tire"] = M.opaque("MI_Tire", eh.lin("#141416"), roughness=0.85)
    m["rim"] = M.opaque("MI_WheelRim", eh.lin("#C9CED6"), roughness=0.3, metallic=1.0)
    m["lamp_r"] = M.emissive("MI_SirenRed", eh.lin("#FF2020"), emissive_strength=12.0)
    m["lamp_b"] = M.emissive("MI_SirenBlue", eh.lin("#2E6BFF"), emissive_strength=12.0)
    m["head"] = M.emissive("MI_Headlight", eh.lin("#FFF4D8"), emissive_strength=6.0)
    m["res_body"] = M.opaque("MI_ResurfacerBody", eh.lin("#1F4FD8"), roughness=0.35)
    m["res_trim"] = M.opaque("MI_ResurfacerTrim", eh.lin("#F2F2F2"), roughness=0.4)
    m["res_dark"] = M.opaque("MI_ResurfacerDark", eh.lin("#202328"), roughness=0.6)
    m["res_metal"] = M.opaque("MI_ResurfacerMetal", eh.lin("#B9C0CA"), roughness=0.3, metallic=1.0)
    m["logo_ice"] = M.opaque("MI_TitleIce", eh.lin("#7FD3FF"), roughness=0.15, metallic=0.2,
                             emissive=eh.lin("#38B6FF"), emissive_strength=0.6)
    m["logo_riot"] = M.opaque("MI_TitleRiot", eh.lin("#FF4A12"), roughness=0.2, metallic=0.2,
                              emissive=eh.lin("#FF6A13"), emissive_strength=0.6)
    m["logo_back"] = M.opaque("MI_TitleBack", eh.lin("#06142B"), roughness=0.4)
    m["logo_edge"] = M.opaque("MI_TitleEdge", eh.lin("#F4F8FB"), roughness=0.25, metallic=0.6)
    return m


def rbox(name, center, half, mat, r=0.03, seg=3):
    lo = [center[i] - half[i] for i in range(3)]
    hi = [center[i] + half[i] for i in range(3)]
    return eh.box_obj(name, lo, hi, mat, bevel=r, segments=seg)


def cyl(name, center, radius, depth, axis, mat, verts=24):
    rot = {"X": (0, math.pi / 2, 0), "Y": (math.pi / 2, 0, 0), "Z": (0, 0, 0)}[axis]
    o = hc.cylinder(name, radius, depth, location=center, rotation=rot, verts=verts, mat=mat)
    eh.bake_obj(o)
    return o


def ell(name, center, radii, mat, seg=24, rings=12):
    o = hc.sphere(name, 1.0, location=center, segments=seg, rings=rings, mat=mat, scale=radii)
    eh.bake_obj(o)
    return o


def text3d(name, body, height, mat, extrude=0.02, font=dr.FONT_IMPACT, shear=0.0, bevel=0.0):
    o = eh.text_obj(name, body, 1.0, font=font, mat=mat, shear=shear, extrude=extrude, bevel=bevel, resolution=8)
    eh.bake_obj(o)
    lo, hi = eh.mesh_bounds(o)
    s = height / (hi.y - lo.y)
    c = (lo + hi) * 0.5
    o.data.transform(Matrix.Scale(s, 4) @ Matrix.Translation(-c))
    o.data.update()
    return o


# ---------------------------------------------------------------------------
def build_hats(m):
    hats = []
    # 1: ball cap
    crown = ell("Crown", (0, 0, 0.0), (0.105, 0.115, 0.095), m["hat1"])
    bm = bmesh.new()
    bm.from_mesh(crown.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -0.005], context="VERTS")
    bm.to_mesh(crown.data)
    bm.free()
    brim = cyl("Brim", (0, -0.11, 0.0), 0.085, 0.012, "Z", m["hat1"])
    brim.data.transform(Matrix.Translation((0, -0.11, 0)) @ Matrix.Diagonal((1.0, 0.75, 1.0, 1.0)) @ Matrix.Translation((0, 0.11, 0)))
    button = ell("Button", (0, 0, 0.095), (0.012, 0.012, 0.008), m["hatband"])
    band = cyl("Band", (0, 0, 0.012), 0.107, 0.022, "Z", m["hatband"])
    h1 = eh.join_objs([crown, brim, button, band], "SM_Hat1")
    hats.append(h1)
    # 2: beanie with pom
    b = ell("Beanie", (0, 0, 0.0), (0.105, 0.105, 0.12), m["hat2"])
    bm = bmesh.new()
    bm.from_mesh(b.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -0.002], context="VERTS")
    bm.to_mesh(b.data)
    bm.free()
    cuff = cyl("Cuff", (0, 0, 0.03), 0.112, 0.06, "Z", m["hatband"])
    pom = ell("Pom", (0, 0, 0.13), (0.04, 0.04, 0.04), m["hatband"])
    hats.append(eh.join_objs([b, cuff, pom], "SM_Hat2"))
    # 3: brimmed fedora-ish
    c3 = cyl("Crown3", (0, 0, 0.055), 0.095, 0.11, "Z", m["hat3"], verts=28)
    top = ell("Top3", (0, 0, 0.11), (0.095, 0.095, 0.025), m["hat3"])
    brim3 = cyl("Brim3", (0, 0, 0.004), 0.17, 0.008, "Z", m["hat3"], verts=32)
    band3 = cyl("Band3", (0, 0, 0.025), 0.097, 0.026, "Z", m["hat1"], verts=28)
    hats.append(eh.join_objs([c3, top, brim3, band3], "SM_Hat3"))
    for h in hats:
        hc.shade(h, smooth=True, angle=50)
    return hats


def wheel(name, x, y, r, w, m):
    t = cyl(name + "T", (x, y, r), r, w, "Y", m["tire"], verts=24)
    rr = cyl(name + "R", (x, y + (w / 2 + 0.002) * (1 if y > 0 else -1), r), r * 0.55, 0.01, "Y", m["rim"], verts=16)
    return [t, rr]


def side_text(text, x, z, height, y, mat, facing):
    """Text on a vehicle side. facing=-1: on the -Y side (reads left->right along +X from -Y)."""
    o = text3d("Txt_" + text, text, height, mat, extrude=0.008)
    # text built in XY plane facing +Z; rotate to face -Y (or +Y)
    if facing < 0:
        R = Matrix.Rotation(math.radians(90), 4, "X")
    else:
        R = Matrix.Rotation(math.radians(-90), 4, "X") @ Matrix.Rotation(math.radians(180), 4, "Y")
        R = Matrix.Rotation(math.radians(180), 4, "Z") @ Matrix.Rotation(math.radians(90), 4, "X")
    o.data.transform(Matrix.Translation((x, y, z)) @ R)
    o.data.update()
    return o


def build_ambulance(m):
    L, W = 4.6, 1.9
    parts = []
    # box body (rear) + cab (front, +X)
    parts.append(rbox("Box", (-0.45, 0, 1.35), (1.45, W / 2, 0.95), m["amb_body"], r=0.10))
    parts.append(rbox("Cab", (1.45, 0, 1.05), (0.65, W / 2 - 0.05, 0.65), m["amb_body"], r=0.14))
    parts.append(rbox("Hood", (1.95, 0, 0.85), (0.35, W / 2 - 0.08, 0.38), m["amb_body"], r=0.12))
    parts.append(rbox("Bumper", (2.32, 0, 0.42), (0.06, W / 2 - 0.05, 0.12), m["rim"], r=0.03))
    parts.append(rbox("Under", (0.0, 0, 0.42), (2.2, W / 2 - 0.12, 0.10), m["tire"], r=0.02))
    # windshield + side windows
    parts.append(rbox("Wind", (1.98, 0, 1.38), (0.03, W / 2 - 0.16, 0.24), m["glass"], r=0.02))
    for sy in (-1, 1):
        parts.append(rbox("SideWin", (1.50, sy * (W / 2 - 0.04), 1.32), (0.32, 0.02, 0.22), m["glass"], r=0.02))
        # red stripe along the box + cab
        parts.append(rbox("Stripe", (0.0, sy * (W / 2 - 0.04), 0.95), (2.0, 0.02, 0.10), m["amb_stripe"], r=0.01))
        parts.append(rbox("Stripe2", (-0.45, sy * (W / 2 + 0.002), 2.12), (1.42, 0.02, 0.05), m["amb_stripe"], r=0.01))
        parts.append(side_text("MEDIC", -0.45, 1.55, 0.42, sy * (W / 2 + 0.012), m["amb_text"], sy))
        for x in (-1.3, 1.55):
            parts += wheel("Wh", x, sy * (W / 2 - 0.12), 0.38, 0.28, m)
        parts.append(rbox("Head", (2.30, sy * 0.62, 0.78), (0.03, 0.16, 0.08), m["head"], r=0.02))
    # rear doors windows
    parts.append(rbox("RearWin", (-1.92, 0, 1.70), (0.02, 0.6, 0.18), m["glass"], r=0.02))
    # light bar
    parts.append(rbox("BarBase", (1.40, 0, 1.73), (0.18, 0.75, 0.04), m["tire"], r=0.02))
    parts.append(rbox("SirenR", (1.40, -0.38, 1.82), (0.14, 0.30, 0.07), m["lamp_r"], r=0.04))
    parts.append(rbox("SirenB", (1.40, 0.38, 1.82), (0.14, 0.30, 0.07), m["lamp_b"], r=0.04))
    for sy in (-1, 1):
        parts.append(rbox("Corner", (-1.88, sy * 0.86, 2.20), (0.06, 0.06, 0.06), m["lamp_r"], r=0.02))
    amb = eh.join_objs(parts, "SM_Ambulance")
    hc.shade(amb, smooth=True, angle=40)
    return amb


def build_resurfacer(m):
    parts = []
    parts.append(rbox("Base", (0.0, 0, 0.62), (1.85, 1.0, 0.42), m["res_body"], r=0.12))
    parts.append(rbox("Tank", (-0.35, 0, 1.35), (1.2, 0.92, 0.36), m["res_trim"], r=0.18))
    parts.append(rbox("Hopper", (-0.55, 0, 1.85), (0.95, 0.85, 0.18), m["res_body"], r=0.08))
    parts.append(rbox("Seat", (1.15, 0.25, 1.25), (0.25, 0.25, 0.08), m["res_dark"], r=0.04))
    parts.append(rbox("SeatBack", (0.95, 0.25, 1.55), (0.06, 0.25, 0.25), m["res_dark"], r=0.04))
    parts.append(rbox("Dash", (1.65, 0.15, 1.30), (0.12, 0.45, 0.22), m["res_dark"], r=0.05))
    parts.append(cyl("Wheel", (1.48, 0.25, 1.55), 0.16, 0.03, "X", m["res_dark"]))
    parts.append(rbox("Conditioner", (-2.05, 0, 0.30), (0.22, 1.08, 0.24), m["res_metal"], r=0.04))
    parts.append(rbox("Bumper", (1.95, 0, 0.35), (0.08, 0.95, 0.12), m["res_trim"], r=0.04))
    for x in (-1.2, 1.2):
        for sy in (-1, 1):
            parts += wheel("Wh", x, sy * 0.93, 0.32, 0.24, m)
    # canopy posts + roof
    for (x, y) in ((0.8, -0.85), (0.8, 0.85), (1.85, -0.85), (1.85, 0.85)):
        parts.append(rbox("Post", (x, y, 1.75), (0.03, 0.03, 0.75), m["res_dark"], r=0.01))
    parts.append(rbox("Roof", (1.3, 0, 2.5), (0.7, 0.95, 0.04), m["res_body"], r=0.03))
    parts.append(rbox("Beacon", (1.3, 0, 2.6), (0.08, 0.08, 0.07), m["lamp_r"], r=0.03))
    for sy in (-1, 1):
        parts.append(side_text("ICE RIOT", -0.35, 1.35, 0.34, sy * 0.935, m["res_body"], sy))
        parts.append(rbox("Stripe", (0.0, sy * 1.0, 0.75), (1.75, 0.02, 0.06), m["res_trim"], r=0.01))
    res = eh.join_objs(parts, "SM_Resurfacer")
    hc.shade(res, smooth=True, angle=40)
    return res


def build_title_logo(m):
    ice = text3d("ICE", "ICE", 1.0, m["logo_ice"], extrude=0.12, shear=0.18, bevel=0.025)
    riot = text3d("RIOT", "RIOT", 1.0, m["logo_riot"], extrude=0.12, shear=0.18, bevel=0.025)
    lo1, hi1 = eh.mesh_bounds(ice)
    lo2, hi2 = eh.mesh_bounds(riot)
    w1, w2 = hi1.x - lo1.x, hi2.x - lo2.x
    gap = 0.18
    total = w1 + w2 + gap
    ice.data.transform(Matrix.Translation((-total / 2 + w1 / 2, 0, 0)))
    riot.data.transform(Matrix.Translation((total / 2 - w2 / 2, 0, 0)))
    # backing plate: dilated outline of both words
    copies = []
    for o in (ice, riot):
        cp = bpy.data.objects.new(o.name + "_cp", o.data.copy())
        bpy.context.scene.collection.objects.link(cp)
        copies.append(cp)
    back_src = eh.join_objs(copies, "BackSrc")
    # keep only the front faces (flat letter shapes) for the outline
    bm = bmesh.new()
    bm.from_mesh(back_src.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.normal.z < 0.9], context="FACES")
    bm.to_mesh(back_src.data)
    bm.free()
    eh.set_z(back_src, 0.0)
    plate = eh.dilate_mesh_obj(back_src, "Plate", 0.09, z=0.0, mat=m["logo_back"], seg=8)
    bpy.data.objects.remove(back_src)
    bm = bmesh.new()
    bm.from_mesh(plate.data)
    r = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
    for v in [e for e in r["geom"] if isinstance(e, bmesh.types.BMVert)]:
        v.co.z -= 0.10
    bm.to_mesh(plate.data)
    bm.free()
    plate.data.transform(Matrix.Translation((0, 0, -0.02)))
    bm = bmesh.new()
    bm.from_mesh(plate.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.004)
    bm.to_mesh(plate.data)
    bm.free()
    dm = plate.modifiers.new("Dec", "DECIMATE")
    dm.ratio = min(1.0, 6000 / max(1, eh.tri_count(plate)))
    hc.apply_modifiers(plate)
    logo = eh.join_objs([ice, riot, plate], "SM_TitleLogo")
    # stand it up: letters face -Y (toward the camera side), reading along +X
    logo.data.transform(Matrix.Rotation(math.radians(90), 4, "X"))
    logo.data.update()
    hc.shade(logo, smooth=True, angle=35)
    return logo


def preview(objs):
    eh.preview_scene(res=(1600, 900), samples=32, view="AgX", world=(0.18, 0.2, 0.24))
    eh.area_light("Key", (3, -6, 6), (0, 0, 1), 3000, size=4)
    eh.area_light("Fill", (-6, -4, 3), (0, 0, 1), 1200, size=4)
    xs = [-6.5, -1.0, 4.5, 7.0]
    for o, x in zip(objs, xs):
        o.location.x = x
    cam = eh.look_cam("Cam", (0.0, -16.0, 5.0), (0.0, 0, 1.6), lens=32)
    eh.render_preview(os.path.join(hc.PREVIEW_DIR, "props.png"))
    for o in objs:
        o.location.x = 0


def main():
    hc.reset_scene()
    m = mats()
    M.write()
    hats = build_hats(m)
    amb = build_ambulance(m)
    res = build_resurfacer(m)
    logo = build_title_logo(m)
    for o in hats + [amb, res, logo]:
        eh.bake_obj(o)
        eh.report_mesh(o)
        hc.export_static_fbx([o], o.name + ".fbx")
    hc.save_blend("props.blend")
    for i, h in enumerate(hats):
        h.scale = (4, 4, 4)
        h.location = (8.5 + i * 1.2, 0, 2.6)
    logo.location.z = 3.4
    preview([amb, res, logo] + [])
    print("PROPS DONE")


if __name__ == "__main__":
    main()
