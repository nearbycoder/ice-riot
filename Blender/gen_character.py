"""ICE RIOT characters: SK_Skater + SK_Goalie on the shared SK_Skater_Skeleton, plus the loose props
SM_Helmet / SM_Glove / SM_Stick and the character textures (T_Face, T_GoalieMask, T_RefStripes).

    blender -b --factory-startup --python-exit-code 1 -P Blender/gen_character.py

Material slots are the Unreal material-instance names (see Docs/ASSET_SPEC.md). Team-colored slots use the
`team` shader (vector param Color); MI_Helmet / MI_Gloves / MI_Pants / MI_GoaliePads / MI_GoalieMask /
MI_StickShaft are `team` too so the game can tint them.  Saves Art/Blend/character.blend (rig in cm) for
gen_anims.py.
"""

import bpy
import bmesh
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ir_common as hc  # noqa: E402
import ir_env as eh  # noqa: E402
import ir_draw as dr  # noqa: E402
import ir_rig as rig  # noqa: E402
from ir_draw import Canvas  # noqa: E402
from ir_teams import BY_ID, HOME, REF  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector, Matrix  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402
from mathutils.kdtree import KDTree  # noqa: E402

S = 100.0
HEAD_PIVOT = Vector((0.0, 0.0, 1.665))
hc.reset_scene()

TEAM = BY_ID[HOME]

# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------
MATS = {}
TEX_FACE = "T_Face"
TEX_MASK = "T_GoalieMask"


def team_mat(name, hex_color, rough=0.6, metal=0.0, texture=None):
    c = eh.lin(hex_color)
    MATS[name] = {"shader": "team", "color": eh.rnd_list(c), "roughness": rough, "metallic": metal}
    if texture:
        MATS[name]["texture"] = texture
    return preview_mat(name, c, rough, metal, texture)


def opaque_mat(name, hex_color, rough=0.5, metal=0.0):
    c = eh.lin(hex_color)
    MATS[name] = {"shader": "opaque", "color": eh.rnd_list(c), "roughness": rough, "metallic": metal}
    return preview_mat(name, c, rough, metal)


def preview_mat(name, color, rough, metal, texture=None):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = tuple(color) + (1,)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if texture and os.path.exists(os.path.join(hc.TEX_DIR, texture + ".png")):
        tn = nt.nodes.new("ShaderNodeTexImage")
        tn.image = bpy.data.images.load(os.path.join(hc.TEX_DIR, texture + ".png"), check_existing=True)
        mx = nt.nodes.new("ShaderNodeMix")
        mx.data_type = "RGBA"
        mx.blend_type = "MULTIPLY"
        mx.inputs["Factor"].default_value = 1.0
        nt.links.new(tn.outputs["Color"], mx.inputs["A"])
        mx.inputs["B"].default_value = tuple(color) + (1,)
        nt.links.new(mx.outputs["Result"], b.inputs["Base Color"])
    nt.links.new(b.outputs[0], out.inputs["Surface"])
    m.diffuse_color = tuple(color) + (1,)
    return m


def skin_mat(name, hex_color, texture=None, amount=1.0):
    c = eh.lin(hex_color)
    MATS[name] = {"shader": "skin", "skin_color": eh.rnd_list(c), "roughness": 0.55, "face_amount": amount}
    if texture:
        MATS[name]["texture"] = texture
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Roughness"].default_value = 0.55
    b.inputs["Base Color"].default_value = tuple(c) + (1,)
    p = os.path.join(hc.TEX_DIR, (texture or "") + ".png")
    if texture and amount > 0 and os.path.exists(p):
        tn = nt.nodes.new("ShaderNodeTexImage")
        tn.image = bpy.data.images.load(p, check_existing=True)
        mx = nt.nodes.new("ShaderNodeMix")
        mx.data_type = "RGBA"
        nt.links.new(tn.outputs["Alpha"], mx.inputs["Factor"])
        mx.inputs["A"].default_value = tuple(c) + (1,)
        nt.links.new(tn.outputs["Color"], mx.inputs["B"])
        nt.links.new(mx.outputs["Result"], b.inputs["Base Color"])
    nt.links.new(b.outputs[0], out.inputs["Surface"])
    return m


def glass_mat(name, hex_color, opacity, rough=0.05):
    c = eh.lin(hex_color)
    MATS[name] = {"shader": "glass", "color": eh.rnd_list(c), "opacity": opacity, "roughness": rough}
    return eh.build_preview_material(name, MATS[name])


def number_mat(name, fill, outline, tens=1, ones=7):
    MATS[name] = {"shader": "number", "color": eh.rnd_list(eh.lin(fill)), "outline_color": eh.rnd_list(eh.lin(outline)),
                  "tens": tens, "ones": ones, "texture": "T_Digits"}
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Roughness"].default_value = 0.6
    p = os.path.join(hc.TEX_DIR, "T_Digits.png")
    if os.path.exists(p):
        uv = nt.nodes.new("ShaderNodeUVMap")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(uv.outputs["UV"], sep.inputs[0])

        def math_node(op, a, bb=None, val=None):
            n = nt.nodes.new("ShaderNodeMath")
            n.operation = op
            if isinstance(a, (int, float)):
                n.inputs[0].default_value = a
            else:
                nt.links.new(a, n.inputs[0])
            if bb is not None:
                if isinstance(bb, (int, float)):
                    n.inputs[1].default_value = bb
                else:
                    nt.links.new(bb, n.inputs[1])
            return n.outputs[0]
        u = sep.outputs["X"]
        right = math_node("GREATER_THAN", u, 0.5)                    # 1 on the ones half
        lu = math_node("FRACT", math_node("MULTIPLY", u, 2.0))
        digit = math_node("ADD", math_node("MULTIPLY", right, float(ones - tens)), float(tens))
        au = math_node("DIVIDE", math_node("ADD", digit, lu), 10.0)
        comb = nt.nodes.new("ShaderNodeCombineXYZ")
        nt.links.new(au, comb.inputs[0])
        nt.links.new(sep.outputs["Y"], comb.inputs[1])
        tn = nt.nodes.new("ShaderNodeTexImage")
        tn.image = bpy.data.images.load(p, check_existing=True)
        tn.image.colorspace_settings.name = "Non-Color"
        nt.links.new(comb.outputs[0], tn.inputs["Vector"])
        sp = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(tn.outputs["Color"], sp.inputs[0])
        mx = nt.nodes.new("ShaderNodeMix")
        mx.data_type = "RGBA"
        nt.links.new(sp.outputs[0], mx.inputs["Factor"])
        mx.inputs["A"].default_value = tuple(eh.lin(outline)) + (1,)
        mx.inputs["B"].default_value = tuple(eh.lin(fill)) + (1,)
        nt.links.new(mx.outputs["Result"], b.inputs["Base Color"])
        gt = math_node("GREATER_THAN", sp.outputs[1], 0.5)
        nt.links.new(gt, b.inputs["Alpha"])
    nt.links.new(b.outputs[0], out.inputs["Surface"])
    return m


def make_materials():
    t = TEAM
    m = {}
    m["prim"] = team_mat("MI_TeamPrimary", t["primary"], 0.7)
    m["sec"] = team_mat("MI_TeamSecondary", t["secondary"], 0.7)
    m["trim"] = team_mat("MI_TeamTrim", t["trim"], 0.7)
    m["helmet"] = team_mat("MI_Helmet", t["secondary"], 0.25, 0.0)
    m["visor"] = glass_mat("MI_Visor", "#CFE8FF", 0.22, 0.03)
    m["skin"] = skin_mat("MI_Skin", "#D9A47E", TEX_FACE, amount=0.0)
    m["face"] = skin_mat("MI_Face", "#D9A47E", TEX_FACE, amount=1.0)
    m["gloves"] = team_mat("MI_Gloves", t["secondary"], 0.55)
    m["pants"] = team_mat("MI_Pants", t["secondary"], 0.6)
    m["boot"] = opaque_mat("MI_SkateBoot", "#15161A", 0.35)
    m["blade"] = opaque_mat("MI_SkateBlade", "#D8DDE3", 0.18, 1.0)
    m["shaft"] = team_mat("MI_StickShaft", "#1B1C20", 0.35, 0.0)
    m["tape"] = opaque_mat("MI_StickTape", "#F4F4F0", 0.8)
    m["number"] = number_mat("MI_Number", t["trim"], t["secondary"], 1, 7)
    m["crest"] = None
    m["pads"] = team_mat("MI_GoaliePads", "#F4F4F4", 0.5)
    m["mask"] = team_mat("MI_GoalieMask", t["primary"], 0.2, 0.0, texture=TEX_MASK)
    # extras (not part of the slot contract, used by the game)
    MATS["MI_JerseyCrest"] = {"shader": "masked", "texture": "T_Logo_" + HOME, "color": [1, 1, 1], "roughness": 0.65}
    m["crest"] = eh.build_preview_material("MI_JerseyCrest", MATS["MI_JerseyCrest"])
    MATS["MI_RefJersey"] = {"shader": "team", "color": [1, 1, 1], "roughness": 0.7, "texture": "T_RefStripes"}
    return m


# ---------------------------------------------------------------------------
# Textures
# ---------------------------------------------------------------------------
FACE_U0, FACE_W = 0.5, 0.26           # u = 0.5 + x / 0.26
FACE_Z0, FACE_H = 1.62, 0.28          # v = (z - 1.62) / 0.28
EYE_X, EYE_Z = 0.041, 1.772
MOUTH_Z = 1.700


def face_uv(x, z):
    return (FACE_U0 + x / FACE_W, (z - FACE_Z0) / FACE_H)


def make_face_texture():
    R = 1024
    cv = Canvas(R, R, (0, 0, 1, 1))
    ink = "#1B1210"
    for s in (-1, 1):
        ex, ey = face_uv(s * EYE_X, EYE_Z)
        # eye black (athlete grease) under the eye
        cv.fill(cv.ellipse(ex, ey - 0.072, 0.060, 0.022, 0.0), "#141012", alpha=0.85)
        # white of the eye
        white = cv.ellipse(ex, ey, 0.060, 0.040, 0.0)
        lid_cut = cv.Y - (ey + 0.022 - 0.35 * (cv.X - ex) * s * 0.0)
        cv.fill(np.maximum(white, lid_cut), "#FBF8F2")
        # iris / pupil / highlight
        cv.fill(np.maximum(cv.circle(ex - s * 0.004, ey - 0.002, 0.030), np.maximum(white, lid_cut)), "#5A3A22")
        cv.fill(np.maximum(cv.circle(ex - s * 0.004, ey - 0.002, 0.016), np.maximum(white, lid_cut)), "#0A0706")
        cv.fill(cv.circle(ex - s * 0.004 + 0.010, ey + 0.008, 0.007), "#FFFFFF")
        # heavy upper lid line (determined squint)
        lid = cv.poly([(ex - 0.068, ey + 0.010 - s * 0.004), (ex + 0.068, ey + 0.010 + s * 0.004),
                       (ex + 0.066, ey + 0.032 + s * 0.008), (ex - 0.066, ey + 0.030 - s * 0.010)])
        cv.fill(lid, ink)
        cv.fill(cv.seg((ex - 0.05, ey - 0.032), (ex + 0.05, ey - 0.032), 0.004), "#7A4A38", alpha=0.6)
        # brows: thick, angled down toward the nose
        inner = (ex - s * 0.050, ey + 0.060)
        outer = (ex + s * 0.070, ey + 0.088)
        brow = cv.poly([(inner[0], inner[1] - 0.012), (outer[0], outer[1] - 0.006), (outer[0] - s * 0.01, outer[1] + 0.018),
                        (inner[0] + s * 0.004, inner[1] + 0.022)])
        cv.fill(brow, "#2A1A12")
    # nose shading + nostrils
    nx, ny = face_uv(0.0, 1.738)
    cv.fill(cv.ellipse(nx, ny - 0.005, 0.05, 0.018), "#6B3A28", alpha=0.35)
    for s in (-1, 1):
        cv.fill(cv.ellipse(nx + s * 0.026, ny, 0.011, 0.007), "#3A1E16", alpha=0.85)
    # mouth: confident smirk + lips
    mx, my = face_uv(0.0, MOUTH_Z)
    lips = cv.ellipse(mx, my - 0.012, 0.075, 0.020)
    cv.fill(lips, "#A0544A", alpha=0.55)
    line = []
    for i in range(21):
        t = i / 20 - 0.5
        line.append((mx + t * 0.16, my + 0.004 + 0.035 * t * t * 2 + 0.018 * max(0.0, t) ** 1.2))
    cv.fill(cv.polyline(line, 0.0055), "#3A1A16")
    # stubble / jaw shadow
    jaw = np.maximum(cv.ellipse(mx, my - 0.03, 0.26, 0.15), -(cv.Y - (my + 0.03)) * -1 + 0.0)
    cv.fill(np.maximum(cv.ellipse(mx, my - 0.05, 0.30, 0.14), cv.Y - (my + 0.05)), "#3B2A22", alpha=0.18)
    # cheeks
    for s in (-1, 1):
        cx_, cy_ = face_uv(s * 0.062, 1.735)
        cv.fill(cv.circle(cx_, cy_, 0.045), "#D0504A", alpha=0.10)
    cv.save(os.path.join(hc.TEX_DIR, "T_Face.png"))


def make_mask_texture():
    """Goalie mask paint: white base with dark graphics (the game tints it with Color)."""
    R = 1024
    cv = Canvas(R, R, (0, 0, 1, 1), bg="#FFFFFF")
    dark = "#2A2E36"
    mid = "#8A909A"
    # mask UV = planar side/front wrap: u around the head (0.5 = front), v = height
    # big fangs/teeth graphic at the chin, flames up the sides, star on top
    for s in (-1, 1):
        flame = []
        for i in range(30):
            t = i / 29
            flame.append((0.5 + s * (0.12 + 0.28 * t), 0.18 + 0.55 * t + 0.06 * math.sin(t * 14)))
        cv.fill(cv.polyline(flame, 0.035), dark)
        cv.fill(cv.polyline([(x + s * 0.03, y - 0.03) for x, y in flame], 0.015), mid)
    # teeth across the jaw
    cv.fill(cv.box(0.5, 0.20, 0.20, 0.05), dark)
    for i in range(8):
        x = 0.33 + i * 0.048
        cv.fill(cv.poly([(x, 0.25), (x + 0.04, 0.25), (x + 0.02, 0.19)]), "#FFFFFF")
        cv.fill(cv.poly([(x + 0.02, 0.15), (x + 0.06, 0.15), (x + 0.04, 0.205)]), "#FFFFFF")
    # brow chevron
    cv.fill(cv.polyline([(0.30, 0.78), (0.5, 0.70), (0.70, 0.78)], 0.03), dark)
    cv.fill(cv.poly([(0.5 + 0.06 * math.cos(a), 0.88 + 0.06 * math.sin(a)) if i % 2 == 0 else
                     (0.5 + 0.024 * math.cos(a), 0.88 + 0.024 * math.sin(a))
                     for i, a in enumerate(np.linspace(math.pi / 2, math.pi / 2 + 2 * math.pi, 10, endpoint=False))]),
            dark)
    cv.save(os.path.join(hc.TEX_DIR, "T_GoalieMask.png"), opaque=True)


def make_ref_stripes():
    W, H = 256, 64
    cv = Canvas(W, H, (0, 0, 1, 0.25), bg="#F2F2F2")
    cv.fill(cv.box(0.75, 0.125, 0.25, 0.2), "#121212")
    cv.save(os.path.join(hc.TEX_DIR, "T_RefStripes.png"), opaque=True)


# ---------------------------------------------------------------------------
# bmesh helpers
# ---------------------------------------------------------------------------
def bm_ell(bm, center, radii, seg=24, rings=14):
    ret = bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0)
    c = Vector(center)
    for v in ret["verts"]:
        v.co = Vector((v.co.x * radii[0], v.co.y * radii[1], v.co.z * radii[2])) + c
    return ret["verts"]


def bm_limb(bm, p0, p1, r0, r1, seg=20, caps=True):
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    ret = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r0, radius2=r1,
                                depth=d.length)
    rot = Vector((0, 0, 1)).rotation_difference(d.normalized()).to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=Matrix.Translation((p0 + p1) / 2) @ rot, verts=ret["verts"])
    if caps:
        bm_ell(bm, p0, (r0, r0, r0), seg, max(8, seg // 2))
        bm_ell(bm, p1, (r1, r1, r1), seg, max(8, seg // 2))


def bm_rbox(bm, center, half, frame=None, r=0.02):
    """Rounded box (bevelled) at center with half sizes, optional 3x3 frame (columns = local axes)."""
    tmp = bmesh.new()
    bmesh.ops.create_cube(tmp, size=1.0)
    for v in tmp.verts:
        v.co = Vector((v.co.x * 2 * half[0], v.co.y * 2 * half[1], v.co.z * 2 * half[2]))
    bmesh.ops.bevel(tmp, geom=list(tmp.edges), offset=min(r, 0.9 * min(half)), segments=3, profile=0.5,
                    affect="EDGES", clamp_overlap=True)
    F = frame if frame is not None else Matrix.Identity(3)
    M = Matrix.Translation(Vector(center)) @ F.to_4x4()
    me = bpy.data.meshes.new("tmp")
    tmp.to_mesh(me)
    tmp.free()
    me.transform(M)
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)


def obj_from_bm(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    return o


def tri_count(o):
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def remesh(obj, voxel, smooth_iter=4, smooth_factor=0.6, target_tris=None):
    m = obj.modifiers.new("Remesh", "REMESH")
    m.mode = "VOXEL"
    m.voxel_size = voxel
    m.adaptivity = 0.0
    hc.apply_modifiers(obj)
    if smooth_iter:
        sm = obj.modifiers.new("Smooth", "SMOOTH")
        sm.factor = smooth_factor
        sm.iterations = smooth_iter
        hc.apply_modifiers(obj)
    if target_tris:
        n = tri_count(obj)
        if n > target_tris:
            dm = obj.modifiers.new("Decimate", "DECIMATE")
            dm.ratio = target_tris / n
            hc.apply_modifiers(obj)
    return obj


def mirror_x_copy(obj, name):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    for v in bm.verts:
        v.co.x = -v.co.x
    bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for mt in obj.data.materials:
        me.materials.append(mt)
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    return o


def set_slots(obj, mats):
    obj.data.materials.clear()
    for mt in mats:
        obj.data.materials.append(mt)
    return {mt.name: i for i, mt in enumerate(mats)}


def solidify(obj, thickness, offset=-1.0):
    s = obj.modifiers.new("Solid", "SOLIDIFY")
    s.thickness = thickness
    s.offset = offset
    hc.apply_modifiers(obj)


# ---------------------------------------------------------------------------
# Skeleton reference
# ---------------------------------------------------------------------------
SEGS = {b[0]: (Vector(b[1]), Vector(b[2])) for b in rig.bone_table() if b[0] in rig.DEFORM_BONES}


def seg_dist(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
    return (a + ab * t - p).length


def nearest_bone(p, allowed=None):
    best, bd = None, 1e9
    for n, (a, b) in SEGS.items():
        if allowed and n not in allowed:
            continue
        d = seg_dist(p, a, b)
        if d < bd:
            best, bd = n, d
    return best, bd


def arm_t(p, s):
    sh, el, wr, tip, d = rig._arm_pts(s)
    return (p - sh).dot(d)


# ---------------------------------------------------------------------------
# BODY (jersey + sleeves + breezers + socks) as one skinned surface
# ---------------------------------------------------------------------------
JERSEY_HEM = 0.955
PANTS_BOTTOM = 0.680
YOKE_Z = 1.435
SLEEVE_STRIPES = [(0.345, 0.362, "trim"), (0.362, 0.432, "sec"), (0.432, 0.449, "trim")]
HEM_STRIPES = [(1.020, 1.036, "trim"), (1.036, 1.098, "sec"), (1.098, 1.114, "trim")]
SOCK_STRIPES = [(0.455, 0.470, "trim"), (0.470, 0.535, "sec"), (0.535, 0.550, "trim")]
COLLAR = (1.490, 1.535)
NECK_GUARD = 1.600
HEAD_SCALE = 1.10


def build_body(goalie=False):
    g = 1.10 if goalie else 1.0
    bm = bmesh.new()
    bm_ell(bm, (0, 0.012, 0.925), (0.218 * g, 0.168 * g, 0.135))                 # breezers core
    bm_ell(bm, (0, 0.010, 1.130), (0.228 * g, 0.162 * g, 0.215))                 # jersey belly
    bm_ell(bm, (0, -0.004, 1.355), (0.252 * g, 0.170 * g, 0.170))                # chest
    bm_ell(bm, (0, 0.030, 1.440), (0.225 * g, 0.140 * g, 0.105))                 # upper back
    for s in (1, -1):
        bm_ell(bm, (0.208 * s * g, 0.004, 1.462), (0.130 * g, 0.132 * g, 0.112))  # shoulder pads
    bm_limb(bm, (0, 0.012, 1.48), (0, -0.004, 1.70), 0.070, 0.066)               # neck
    for s in (1, -1):
        sh, el, wr, tip, d = rig._arm_pts(s)
        bm_limb(bm, sh + d * 0.04, el, 0.092 * g, 0.078 * g)                        # sleeve upper
        bm_ell(bm, el, (0.082 * g, 0.082 * g, 0.082 * g))                           # elbow pad
        bm_limb(bm, el, el + d * 0.20, 0.076 * g, 0.068 * g)                        # sleeve forearm
        hip, knee, ankle, ball, toe = rig._leg_pts(s)
        bm_limb(bm, hip + Vector((0.012 * s, 0.0, 0.0)), Vector((0.128 * s, -0.012, PANTS_BOTTOM + 0.02)),
                0.138 * g, 0.128 * g)                                               # breezer leg
        bm_limb(bm, Vector((0.122 * s, -0.012, PANTS_BOTTOM + 0.03)), ankle + Vector((0, -0.01, 0.10)),
                0.092, 0.070)                                                       # sock over shin pad
        bm_ell(bm, knee + Vector((0, -0.032, 0)), (0.090, 0.090, 0.098))           # knee pad
    body = obj_from_bm("Body", bm)
    remesh(body, voxel=0.0125, smooth_iter=6, smooth_factor=0.6, target_tris=3800 if not goalie else 3900)
    return body


def _cut(bm, co, no, region=None):
    if region:
        faces = [f for f in bm.faces if region(f.calc_center_median())]
        vs = {v for f in faces for v in f.verts}
        es = {e for f in faces for e in f.edges}
        geom = list(vs) + list(es) + faces
    else:
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-6, plane_co=Vector(co), plane_no=Vector(no))


def region_name(c):
    nb, _ = nearest_bone(c)
    return nb


def dress_body(body, m, goalie=False):
    slots = set_slots(body, [m["prim"], m["sec"], m["trim"], m["pants"], m["skin"], m["boot"]])
    bm = bmesh.new()
    bm.from_mesh(body.data)

    def is_torso(c):
        nb = region_name(c)
        return nb in ("pelvis", "spine_01", "spine_02", "spine_03", "clavicle_l", "clavicle_r", "neck")

    def is_leg(c):
        return c.z < 1.0 and region_name(c).startswith(("thigh", "calf", "foot", "pelvis"))

    for z in [JERSEY_HEM, JERSEY_HEM + 0.020, NECK_GUARD, PANTS_BOTTOM, YOKE_Z, COLLAR[0], COLLAR[1]] + [a for a, b, k in HEM_STRIPES] + \
            [b for a, b, k in HEM_STRIPES]:
        _cut(bm, (0, 0, z), (0, 0, 1), region=lambda c: abs(c.x) < 0.42)
    for a, b, k in SOCK_STRIPES:
        for z in (a, b):
            _cut(bm, (0, 0, z), (0, 0, 1), region=lambda c: c.z < 0.75)
    for s in (1, -1):
        sh, el, wr, tip, d = rig._arm_pts(s)
        side = "l" if s > 0 else "r"

        def is_arm(c, side=side):
            return region_name(c) in ("upperarm_" + side, "lowerarm_" + side)
        for a, b, k in SLEEVE_STRIPES:
            for t in (a, b):
                _cut(bm, sh + d * t, d, region=is_arm)
        _cut(bm, sh + d * 0.085, d, region=is_arm)
    bm.normal_update()
    for f in bm.faces:
        c = f.calc_center_median()
        f.material_index = slots[classify(c, f.normal, m).name]
    bm.to_mesh(body.data)
    bm.free()
    body.data.update()


def classify(c, n, m):
    nb = region_name(c)
    z = c.z
    if nb in ("neck", "head") and z > COLLAR[1]:
        return m["skin"] if z > NECK_GUARD else m["boot"]
    if nb.startswith(("upperarm", "lowerarm", "hand")):
        s = 1 if nb.endswith("_l") else -1
        t = arm_t(c, s)
        for a, b, k in SLEEVE_STRIPES:
            if a <= t < b:
                return m[k]
        if t < 0.085:
            return m["sec"]            # shoulder yoke continues over the cap
        return m["prim"]
    if z >= JERSEY_HEM and abs(c.x) < 0.42:
        if COLLAR[0] <= z < COLLAR[1] + 0.02 and nb in ("neck", "spine_03") and abs(c.x) < 0.11:
            return m["trim"]
        if z >= YOKE_Z:
            return m["sec"]
        for a, b, k in HEM_STRIPES:
            if a <= z < b:
                return m[k]
        if z < JERSEY_HEM + 0.020:
            return m["trim"]
        return m["prim"]
    if z >= PANTS_BOTTOM:
        return m["pants"]
    for a, b, k in SOCK_STRIPES:
        if a <= z < b:
            return m[k]
    return m["prim"]


def body_uvs(o):
    """Cylindrical UVs (used by the referee stripe texture): u = angle around Z * 13 stripe pairs, v = z."""
    me = o.data
    uvl = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
    for p in me.polygons:
        cx = sum(me.vertices[i].co.x for i in p.vertices) / len(p.vertices)
        for li in p.loop_indices:
            v = me.vertices[me.loops[li].vertex_index].co
            ang = math.atan2(v.x, -v.y)
            # keep a face from wrapping across the seam at the back
            if abs(ang) > math.pi * 0.9 and cx * v.x < 0:
                ang = math.copysign(math.pi, cx) if cx != 0 else ang
            uvl.data[li].uv = (ang / (2 * math.pi) * 13.0, v.z * 2.0)


# ---------------------------------------------------------------------------
# HEAD, HELMET, VISOR, GOALIE MASK
# ---------------------------------------------------------------------------
def build_head(m, target=1450):
    bm = bmesh.new()
    bm_ell(bm, (0, 0.006, 1.790), (0.112, 0.122, 0.128), 32, 20)          # cranium
    bm_ell(bm, (0, -0.018, 1.722), (0.100, 0.100, 0.086), 28, 18)         # jaw/cheeks
    bm_ell(bm, (0, -0.066, 1.682), (0.056, 0.046, 0.044), 20, 12)         # chin (strong)
    bm_ell(bm, (0, -0.086, 1.808), (0.090, 0.036, 0.028), 20, 12)         # brow ridge
    for s in (1, -1):
        bm_ell(bm, (0.058 * s, -0.078, 1.748), (0.036, 0.026, 0.028), 16, 10)  # cheekbones
        bm_ell(bm, (0.110 * s, 0.002, 1.765), (0.020, 0.032, 0.042), 16, 10)   # ears
    bm_limb(bm, (0, -0.110, 1.800), (0, -0.136, 1.748), 0.015, 0.021, 14)  # nose bridge
    bm_ell(bm, (0, -0.128, 1.742), (0.032, 0.022, 0.019), 16, 10)          # nostrils
    bm_limb(bm, (0, 0.0, 1.60), (0, -0.004, 1.72), 0.062, 0.068)          # neck stub
    head = obj_from_bm("Head", bm)
    remesh(head, voxel=0.0045, smooth_iter=4, smooth_factor=0.5, target_tris=target)
    slots = set_slots(head, [m["skin"], m["face"]])
    uvl = head.data.uv_layers.new(name="UVMap")
    me = head.data
    for p in me.polygons:
        c = p.center
        p.material_index = 1 if (p.normal.y < -0.2 and 1.64 < c.z < 1.835 and abs(c.x) < 0.105) else 0
        for li in p.loop_indices:
            v = me.vertices[me.loops[li].vertex_index].co
            uvl.data[li].uv = face_uv(v.x, v.z)
    return head


def build_helmet(m):
    bm = bmesh.new()
    bm_ell(bm, (0, 0.010, 1.802), (0.140, 0.156, 0.140), 32, 20)
    bm_ell(bm, (0, 0.050, 1.770), (0.128, 0.118, 0.105), 24, 14)
    for s in (1, -1):
        bm_ell(bm, (0.122 * s, 0.002, 1.755), (0.034, 0.062, 0.064), 16, 10)
    # top ridge
    bm_ell(bm, (0, 0.03, 1.915), (0.05, 0.11, 0.025), 16, 8)   # low crown ridge
    helm = obj_from_bm("Helmet", bm)
    remesh(helm, voxel=0.0065, smooth_iter=3, smooth_factor=0.5)
    bm = bmesh.new()
    bm.from_mesh(helm.data)

    def keep(c):
        if c.z > 1.818:
            return True
        if c.z < 1.675:
            return False
        if c.y > 0.035:
            return c.z > 1.69
        if abs(c.x) > 0.100:
            return c.z > 1.695
        return False
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if not keep(f.calc_center_median())], context="FACES")
    bm.to_mesh(helm.data)
    bm.free()
    solidify(helm, 0.010, -1.0)
    dm = helm.modifiers.new("Dec", "DECIMATE")
    dm.ratio = min(1.0, 960 / max(1, tri_count(helm)))
    hc.apply_modifiers(helm)
    set_slots(helm, [m["helmet"]])
    # visor: curved strip in front of the eyes
    vb = bmesh.new()
    rings = []
    for j in range(4):
        z = 1.752 + 0.024 * j
        row = []
        for i in range(17):
            a = math.radians(-64 + 128 * i / 16)
            r = 0.150 + 0.004 * j
            row.append(vb.verts.new((r * math.sin(a), -r * math.cos(a) + 0.004, z)))
        rings.append(row)
    for j in range(3):
        for i in range(16):
            vb.faces.new((rings[j][i], rings[j][i + 1], rings[j + 1][i + 1], rings[j + 1][i]))
    visor = obj_from_bm("Visor", vb)
    solidify(visor, 0.004, 0.0)
    set_slots(visor, [m["visor"]])
    # chin strap (dark)
    sb = bmesh.new()
    pts = [Vector((0.118, -0.01, 1.72)), Vector((0.085, -0.06, 1.665)), Vector((0.0, -0.085, 1.640)),
           Vector((-0.085, -0.06, 1.665)), Vector((-0.118, -0.01, 1.72))]
    for a, b in zip(pts[:-1], pts[1:]):
        bm_limb(sb, a, b, 0.007, 0.007, 6, caps=False)
    strap = obj_from_bm("Strap", sb)
    set_slots(strap, [m["boot"]])
    return helm, visor, strap


def build_goalie_mask(m):
    bm = bmesh.new()
    bm_ell(bm, (0, 0.000, 1.790), (0.138, 0.150, 0.150), 32, 20)
    bm_ell(bm, (0, -0.050, 1.700), (0.110, 0.100, 0.090), 24, 14)          # chin cup
    bm_ell(bm, (0, -0.080, 1.770), (0.105, 0.075, 0.110), 24, 14)          # face plate
    mask = obj_from_bm("Mask", bm)
    remesh(mask, voxel=0.0065, smooth_iter=3, smooth_factor=0.5, target_tris=800)
    # cut the eye opening out of the face plate (the cage covers it)
    bm = bmesh.new()
    bm.from_mesh(mask.data)
    dele = [f for f in bm.faces if (lambda c: c.y < -0.05 and 1.735 < c.z < 1.815 and abs(c.x) < 0.085)(
        f.calc_center_median())]
    bmesh.ops.delete(bm, geom=dele, context="FACES")
    bm.to_mesh(mask.data)
    bm.free()
    solidify(mask, 0.008)
    set_slots(mask, [m["mask"]])
    # UV wrap: u = 0.5 + angle/2.4, v = (z-1.6)/0.36
    uvl = mask.data.uv_layers.new(name="UVMap")
    me = mask.data
    for p in me.polygons:
        for li in p.loop_indices:
            v = me.vertices[me.loops[li].vertex_index].co
            uvl.data[li].uv = (0.5 + math.atan2(v.x, -v.y) / 3.2, (v.z - 1.60) / 0.36)
    # cage bars
    cb = bmesh.new()
    for i in range(5):
        a = math.radians(-50 + 25 * i)
        p0 = Vector((0.155 * math.sin(a), -0.155 * math.cos(a) + 0.01, 1.73))
        p1 = Vector((0.150 * math.sin(a), -0.150 * math.cos(a) + 0.01, 1.83))
        bm_limb(cb, p0, p1, 0.005, 0.005, 5, caps=False)
    for z in (1.755, 1.795):
        prev = None
        for i in range(9):
            a = math.radians(-60 + 15 * i)
            p = Vector((0.158 * math.sin(a), -0.158 * math.cos(a) + 0.01, z))
            if prev is not None:
                bm_limb(cb, prev, p, 0.005, 0.005, 5, caps=False)
            prev = p
    cage = obj_from_bm("Cage", cb)
    set_slots(cage, [m["blade"]])
    return mask, cage


# ---------------------------------------------------------------------------
# GLOVES (canonical left hand: +X palm normal, +Y fingers, +Z thumb, wrist at origin)
# ---------------------------------------------------------------------------
def build_glove_canonical(m, goalie_kind=None):
    bm = bmesh.new()
    bm_limb(bm, (0, -0.135, 0), (0, -0.01, 0), 0.080, 0.070, 20)             # cuff
    bm_rbox(bm, (-0.012, 0.065, 0.0), (0.048, 0.068, 0.060), r=0.03)          # back of hand
    bm_limb(bm, (0.012, 0.138, -0.058), (0.012, 0.138, 0.050), 0.042, 0.040, 16)   # rolled fingers
    bm_ell(bm, (0.030, 0.118, -0.004), (0.035, 0.035, 0.055))
    bm_limb(bm, (0.022, 0.040, 0.062), (0.040, 0.100, 0.074), 0.030, 0.027, 14)   # thumb
    o = obj_from_bm("GloveCanon", bm)
    remesh(o, voxel=0.0055, smooth_iter=3, smooth_factor=0.5, target_tris=640)
    slots = set_slots(o, [m["gloves"], m["trim"]])
    for p in o.data.polygons:
        c = p.center
        if -0.125 < c.y < -0.105:
            p.material_index = 1      # cuff roll stripe
    return o


def build_blocker(m):
    """Goalie blocker: glove + board on the back of the hand (canonical left-hand space, mirrored for right)."""
    g = build_glove_canonical(m)
    bm = bmesh.new()
    bm_rbox(bm, (-0.085, 0.010, 0.0), (0.024, 0.200, 0.110), r=0.02)
    b = obj_from_bm("BlockerBoard", bm)
    set_slots(b, [m["pads"]])
    return hc.join([g, b], "Blocker")


def build_trapper(m):
    bm = bmesh.new()
    bm_limb(bm, (0, -0.15, 0), (0, -0.01, 0), 0.085, 0.078, 20)
    bm_ell(bm, (0.035, 0.11, 0.02), (0.065, 0.17, 0.14), 24, 14)             # pocket
    bm_ell(bm, (0.030, 0.22, 0.10), (0.050, 0.10, 0.06), 16, 10)             # T-trap web
    o = obj_from_bm("Trapper", bm)
    remesh(o, voxel=0.007, smooth_iter=3, smooth_factor=0.5, target_tris=900)
    slots = set_slots(o, [m["gloves"], m["pads"]])
    for p in o.data.polygons:
        if p.center.x > 0.06:
            p.material_index = 1      # palm side of the trapper
    return o


def place_hand(canon, side, offset=0.0):
    sh, el, wr, tip, d = rig._arm_pts(1)
    A = rig.ARM_ABDUCTION
    palm_n = Vector((-math.cos(A), 0.0, -math.sin(A)))
    thumb = Vector((0.0, -1.0, 0.0))
    M = Matrix((palm_n, d, thumb)).transposed().to_4x4()
    M.translation = wr - d * 0.005
    o = bpy.data.objects.new("Hand_" + side, canon.data.copy())
    bpy.context.scene.collection.objects.link(o)
    o.data.transform(M)
    if side == "r":
        m2 = mirror_x_copy(o, "Hand_r")
        bpy.data.objects.remove(o)
        o = m2
    return o


# ---------------------------------------------------------------------------
# SKATES (left built, right mirrored)
# ---------------------------------------------------------------------------
def build_skate_left(m):
    cx = 0.125
    y_heel, y_toe = 0.105, -0.205
    L = y_heel - y_toe
    z_sole = 0.082

    def width(t):
        return 0.090 + 0.028 * math.sin(math.pi * min(1.0, t * 1.1)) ** 0.8 - 0.02 * max(0, t - 0.8) / 0.2

    def height(t):
        # tall boot at the heel (ankle support), dropping to the toe cap
        return 0.335 - 0.205 * min(1.0, max(0.0, (t - 0.30) / 0.45)) ** 0.8

    nsec, narc = 12, 10
    bm = bmesh.new()
    rings = []
    for i in range(nsec + 1):
        t = i / nsec
        y = y_heel - L * t
        w = width(t) * 0.5
        h = height(t)
        ring = []
        for j in range(narc + 1):
            a = math.pi * j / narc
            x = cx + w * math.cos(a)
            z = z_sole + (h - z_sole) * math.sin(a) ** 0.7
            ring.append(bm.verts.new((x, y, z)))
        rings.append(ring)
    for i in range(nsec):
        for j in range(narc):
            bm.faces.new((rings[i][j], rings[i + 1][j], rings[i + 1][j + 1], rings[i][j + 1]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bot = [rings[i][0] for i in range(nsec + 1)] + [rings[i][narc] for i in range(nsec, -1, -1)]
    try:
        bm.faces.new(bot)
    except ValueError:
        pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    boot = obj_from_bm("Boot", bm)
    set_slots(boot, [m["boot"], m["trim"]])
    for p in boot.data.polygons:
        c = p.center
        t = (y_heel - c.y) / L
        pass
    # tongue
    tb = bmesh.new()
    bm_rbox(tb, (cx, -0.035, 0.30), (0.035, 0.018, 0.06), r=0.012)
    tongue = obj_from_bm("Tongue", tb)
    set_slots(tongue, [m["boot"]])
    # blade holder (two posts + bridge) and steel runner
    hb = bmesh.new()
    bm_rbox(hb, (cx, 0.065, 0.062), (0.022, 0.038, 0.024), r=0.01)
    bm_rbox(hb, (cx, -0.155, 0.062), (0.020, 0.040, 0.024), r=0.01)
    bm_rbox(hb, (cx, -0.045, 0.048), (0.010, 0.140, 0.012), r=0.006)
    holder = obj_from_bm("Holder", hb)
    set_slots(holder, [m["tape"]])
    rb = bmesh.new()
    pts = []
    for i in range(25):
        t = i / 24
        y = 0.135 - 0.33 * t
        z = 0.004 + 0.035 * ((2 * t - 1) ** 8)
        pts.append((y, z))
    top = 0.040
    verts_b = [rb.verts.new((cx - 0.004, y, z)) for y, z in pts]
    verts_t = [rb.verts.new((cx - 0.004, y, top)) for y, z in pts]
    verts_b2 = [rb.verts.new((cx + 0.004, y, z)) for y, z in pts]
    verts_t2 = [rb.verts.new((cx + 0.004, y, top)) for y, z in pts]
    for i in range(24):
        rb.faces.new((verts_b[i], verts_b[i + 1], verts_t[i + 1], verts_t[i]))
        rb.faces.new((verts_b2[i + 1], verts_b2[i], verts_t2[i], verts_t2[i + 1]))
        rb.faces.new((verts_b[i + 1], verts_b[i], verts_b2[i], verts_b2[i + 1]))
    rb.faces.new((verts_b[0], verts_t[0], verts_t2[0], verts_b2[0]))
    rb.faces.new((verts_b[-1], verts_b2[-1], verts_t2[-1], verts_t[-1]))
    runner = obj_from_bm("Runner", rb)
    set_slots(runner, [m["blade"]])
    return hc.join([boot, tongue, holder, runner], "Skate_l")


# ---------------------------------------------------------------------------
# STICK (rest pose, world space)
# ---------------------------------------------------------------------------
def build_stick(m, goalie=False):
    st = rig.stick_rest()
    G, down, heel, B, N, up_blade = st["grip"], st["down"], st["heel"], st["B"], st["N"], st["up"]
    side = down.cross(N).normalized()
    butt = st["butt"]
    bm = bmesh.new()
    # shaft: rounded rectangle tube from butt to just above the heel
    shaft_end = heel - down * 0.06
    L = (shaft_end - butt).length
    F = Matrix((N, side, down)).transposed()      # local x = N (thin), y = side (wide), z = along shaft
    bm_rbox(bm, (butt + shaft_end) / 2, (0.0135, 0.0185, L / 2), F, r=0.009)
    shaft_o = obj_from_bm("Shaft", bm)
    set_slots(shaft_o, [m["shaft"], m["tape"]])
    for p in shaft_o.data.polygons:
        if (p.center - butt).dot(down) < 0.13:
            p.material_index = 1      # knob tape
    parts = [shaft_o]
    if goalie:
        pb = bmesh.new()
        pa = butt + down * 0.85
        pe = heel - down * 0.05
        bm_rbox(pb, (pa + pe) / 2, (0.014, 0.045, (pe - pa).length / 2), F, r=0.01)
        paddle = obj_from_bm("Paddle", pb)
        set_slots(paddle, [m["shaft"]])
        parts.append(paddle)
    # blade: lofted curved plate from the heel to the toe (flat on the ice at the 42 deg play lie)
    blen = rig.BLADE_LEN * (1.15 if goalie else 1.0)
    bh = rig.BLADE_H * (1.2 if goalie else 1.0)
    bt = rig.BLADE_T
    nseg = 12
    bb = bmesh.new()
    rows = []
    heel_flat = st["heel_bottom"]
    for i in range(nseg + 1):
        t = i / nseg
        hook = 0.030 * t * t
        c = heel_flat + B * (blen * t) + N * hook - B * 0.02
        h = bh * (1.0 - 0.15 * t) if t < 0.9 else bh * (0.85 - 1.5 * (t - 0.9))
        tang = (B + N * (0.06 * t)).normalized()
        nrm = up_blade.cross(tang).normalized()
        ring = [bb.verts.new(c + nrm * (bt / 2) + up_blade * 0.002), bb.verts.new(c - nrm * (bt / 2) + up_blade * 0.002),
                bb.verts.new(c - nrm * (bt / 2) + up_blade * h), bb.verts.new(c + nrm * (bt / 2) + up_blade * h)]
        rows.append(ring)
    for i in range(nseg):
        a, b_ = rows[i], rows[i + 1]
        for k in range(4):
            k2 = (k + 1) % 4
            bb.faces.new((a[k], b_[k], b_[k2], a[k2]))
    bb.faces.new(list(reversed(rows[0])))
    bb.faces.new(rows[-1])
    bmesh.ops.recalc_face_normals(bb, faces=bb.faces[:])
    blade = obj_from_bm("Blade", bb)
    set_slots(blade, [m["shaft"], m["tape"]])
    for p in blade.data.polygons:
        t = (p.center - heel_flat).dot(B) / blen
        if 0.08 < t < 0.92:
            p.material_index = 1
    # hosel: short taper from the shaft end into the heel
    hb = bmesh.new()
    bm_limb(hb, shaft_end, heel_flat + up_blade * (bh * 0.55) - B * 0.01, 0.013, 0.011, 10)
    hosel = obj_from_bm("Hosel", hb)
    set_slots(hosel, [m["shaft"]])
    parts += [blade, hosel]
    return hc.join(parts, "Stick")


# ---------------------------------------------------------------------------
# GOALIE gear
# ---------------------------------------------------------------------------
def build_leg_pad(m, s):
    hip, knee, ankle, ball, toe = rig._leg_pts(s)
    bm = bmesh.new()
    x = 0.128 * s
    # main face: tall slab in front of the shin with vertical channels (three bulging columns)
    for k, dx in enumerate((-0.085, 0.0, 0.085)):
        bm_rbox(bm, (x + dx, -0.095 - (0.012 if k == 1 else 0.0), 0.40), (0.048, 0.062, 0.33), r=0.04)
    # knee stack: three horizontal rolls
    for k, z in enumerate((0.66, 0.73, 0.80)):
        bm_limb(bm, (x - 0.12, -0.11 + 0.01 * k, z), (x + 0.12, -0.11 + 0.01 * k, z), 0.045 - 0.006 * k,
                0.045 - 0.006 * k, 14)
    # boot / toe bridge over the skate
    bm_rbox(bm, (x, -0.17, 0.10), (0.12, 0.07, 0.07), r=0.04)
    bm_rbox(bm, (x - 0.08 * s, -0.02, 0.40), (0.035, 0.10, 0.30), r=0.03)     # inner knee wing
    pad = obj_from_bm("Pad_%d" % s, bm)
    remesh(pad, voxel=0.0085, smooth_iter=3, smooth_factor=0.5, target_tris=1050)
    set_slots(pad, [m["pads"], m["prim"], m["sec"]])
    for p in pad.data.polygons:
        c = p.center
        front = p.normal.y < -0.35
        if 0.765 < c.z < 0.835 or 0.155 < c.z < 0.20:
            p.material_index = 1          # top roll + toe band in team primary
        elif front and 0.44 < c.z < 0.50:
            p.material_index = 2          # horizontal stripe across the face
        elif front and abs(c.x - x) < 0.028 and 0.22 < c.z < 0.60:
            p.material_index = 1          # center channel accent
    return pad


# ---------------------------------------------------------------------------
# NUMBERS + CREST (conformed quads, UV 0..1 over the two-digit area)
# ---------------------------------------------------------------------------
def conform_grid(name, bvh, center, right, up, width, height, ray_dir, nu=8, nv=6, lift=0.004, mat=None,
                 flip_u=False):
    bm = bmesh.new()
    V = []
    uvs = {}
    for j in range(nv + 1):
        row = []
        for i in range(nu + 1):
            u, v = i / nu, j / nv
            p = Vector(center) + Vector(right) * ((u - 0.5) * width) + Vector(up) * ((v - 0.5) * height)
            origin = p - Vector(ray_dir) * 0.5
            hit = bvh.ray_cast(origin, Vector(ray_dir), 1.0)
            if hit[0] is not None:
                p = hit[0] + hit[1] * lift
            vv = bm.verts.new(p)
            row.append(vv)
            uvs[vv] = (1 - u if flip_u else u, v)
        V.append(row)
    faces = []
    for j in range(nv):
        for i in range(nu):
            faces.append(bm.faces.new((V[j][i], V[j][i + 1], V[j + 1][i + 1], V[j + 1][i])))
    uvl = bm.loops.layers.uv.new("UVMap")
    for f in faces:
        for l in f.loops:
            l[uvl].uv = uvs[l.vert]
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    o = obj_from_bm(name, bm)
    # make sure normals face away from the body (along -ray_dir)
    if o.data.polygons[0].normal.dot(Vector(ray_dir)) > 0:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        bm.to_mesh(o.data)
        bm.free()
    if mat:
        set_slots(o, [mat])
    return o


def build_numbers(body, m, goalie=False):
    bvh = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    parts = []
    # back: viewer behind the player (+Y looking -Y): viewer's right = -X
    parts.append(conform_grid("NumBack", bvh, (0, 0.30, 1.255 if not goalie else 1.27), (-1, 0, 0), (0, 0, 1),
                              0.34, 0.215, (0, -1, 0), 10, 6, mat=m["number"]))
    # sleeves (outside of the upper arms, below the yoke), oriented up the arm
    for s in (1, -1):
        sh, el, wr, tip, d = rig._arm_pts(s)
        c = sh + d * 0.17
        outward = Vector((math.cos(rig.ARM_ABDUCTION) * s, 0, math.sin(rig.ARM_ABDUCTION)))
        upv = -d
        # viewer outside the arm looking inward: right = (-outward) x up
        right = (-outward).cross(upv).normalized()
        parts.append(conform_grid("NumSleeve%d" % s, bvh, c + outward * 0.25, right, upv, 0.15, 0.095, -outward,
                                  6, 4, mat=m["number"]))
    nums = hc.join(parts, "Numbers")
    # chest crest (front: viewer at -Y, right = +X)
    crest = conform_grid("Crest", bvh, (0, -0.4, 1.31 if not goalie else 1.33), (1, 0, 0), (0, 0, 1), 0.28, 0.28,
                         (0, 1, 0), 8, 8, mat=m["crest"])
    return nums, crest


# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------
def smooth_weights(obj, blend=0.03, max_inf=4, allowed=None):
    names = allowed or rig.DEFORM_BONES
    groups = {n: obj.vertex_groups.get(n) or obj.vertex_groups.new(name=n) for n in names}
    segs = {n: SEGS[n] for n in names}
    for v in obj.data.vertices:
        p = v.co
        ds = [(n, seg_dist(p, a, b)) for n, (a, b) in segs.items()]
        dmin = min(d for _, d in ds)
        ws = [(n, math.exp(-((d - dmin) / blend) ** 2)) for n, d in ds if d - dmin < blend * 2.5]
        ws.sort(key=lambda t: -t[1])
        ws = ws[:max_inf]
        tot = sum(w for _, w in ws)
        for n, w in ws:
            if w / tot > 0.01:
                groups[n].add([v.index], w / tot, "REPLACE")


def rigid_weights(obj, bone):
    g = obj.vertex_groups.get(bone) or obj.vertex_groups.new(name=bone)
    g.add([v.index for v in obj.data.vertices], 1.0, "REPLACE")


def glove_weights(obj, side):
    sh, el, wr, tip, d = rig._arm_pts(1 if side == "l" else -1)
    gh = obj.vertex_groups.new(name="hand_" + side)
    gl = obj.vertex_groups.new(name="lowerarm_" + side)
    for v in obj.data.vertices:
        t = (v.co - wr).dot(d)             # <0 toward the elbow
        w = max(0.0, min(1.0, (t + 0.12) / 0.10))
        gh.add([v.index], w, "REPLACE")
        if w < 1.0:
            gl.add([v.index], 1.0 - w, "REPLACE")


def skate_weights(obj, side):
    gf = obj.vertex_groups.new(name="foot_" + side)
    gc = obj.vertex_groups.new(name="calf_" + side)
    for v in obj.data.vertices:
        tc = max(0.0, min(1.0, (v.co.z - 0.26) / 0.08)) * 0.35
        gf.add([v.index], 1.0 - tc, "REPLACE")
        if tc > 0:
            gc.add([v.index], tc, "REPLACE")


def pad_weights(obj, side):
    gc = obj.vertex_groups.new(name="calf_" + side)
    gt = obj.vertex_groups.new(name="thigh_" + side)
    gf = obj.vertex_groups.new(name="foot_" + side)
    for v in obj.data.vertices:
        z = v.co.z
        wt = max(0.0, min(1.0, (z - 0.58) / 0.12))
        wf = max(0.0, min(1.0, (0.14 - z) / 0.08)) * 0.6
        wc = max(0.0, 1.0 - wt - wf)
        if wc > 0:
            gc.add([v.index], wc, "REPLACE")
        if wt > 0:
            gt.add([v.index], wt, "REPLACE")
        if wf > 0:
            gf.add([v.index], wf, "REPLACE")


def transfer_weights(target, source):
    src_groups = {g.index: g.name for g in source.vertex_groups}
    verts = source.data.vertices
    kd = KDTree(len(verts))
    for v in verts:
        kd.insert(v.co, v.index)
    kd.balance()
    groups = {}
    for v in target.data.vertices:
        co, idx, dist = kd.find(v.co)
        for ge in verts[idx].groups:
            name = src_groups[ge.group]
            g = groups.get(name) or target.vertex_groups.get(name) or target.vertex_groups.new(name=name)
            groups[name] = g
            g.add([v.index], ge.weight, "REPLACE")


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------
def build_character(m, goalie=False):
    tag = "G" if goalie else "S"
    body = build_body(goalie)
    dress_body(body, m, goalie)
    body_uvs(body)
    smooth_weights(body, blend=0.035)
    head = build_head(m, 450 if goalie else 1450)
    rigid_weights(head, "head")
    parts = [body, head]
    if goalie:
        mask, cage = build_goalie_mask(m)
        for o in (mask, cage):
            rigid_weights(o, "head")
        parts += [mask, cage]
        blk = build_blocker(m)
        trap = build_trapper(m)
        hand_r = place_hand(blk, "r")
        hand_l = place_hand(trap, "l")
        bpy.data.objects.remove(blk)
        bpy.data.objects.remove(trap)
        for s in (1, -1):
            pad = build_leg_pad(m, s)
            pad_weights(pad, "l" if s > 0 else "r")
            parts.append(pad)
    else:
        helm, visor, strap = build_helmet(m)
        for o in (helm, visor, strap):
            rigid_weights(o, "head")
        parts += [helm, visor, strap]
        canon = build_glove_canonical(m)
        hand_l = place_hand(canon, "l")
        hand_r = place_hand(canon, "r")
        bpy.data.objects.remove(canon)
    head_parts = [o for o in parts if o.name.startswith(("Head", "Helmet", "Visor", "Strap", "Mask", "Cage"))]
    Ms = Matrix.Translation(HEAD_PIVOT) @ Matrix.Scale(HEAD_SCALE, 4) @ Matrix.Translation(-HEAD_PIVOT)
    for o in head_parts:
        o.data.transform(Ms)
        o.data.update()
    glove_weights(hand_l, "l")
    glove_weights(hand_r, "r")
    parts += [hand_l, hand_r]
    sk_l = build_skate_left(m)
    sk_r = mirror_x_copy(sk_l, "Skate_r")
    skate_weights(sk_l, "l")
    skate_weights(sk_r, "r")
    parts += [sk_l, sk_r]
    stick = build_stick(m, goalie)
    rigid_weights(stick, "stick")
    parts.append(stick)
    nums, crest = build_numbers(body, m, goalie)
    transfer_weights(nums, body)
    transfer_weights(crest, body)
    parts += [nums, crest]
    for o in parts:
        if not o.data.uv_layers:
            eh.box_uv(o, 2.0)
        elif o.data.uv_layers[0].name != "UVMap":
            o.data.uv_layers[0].name = "UVMap"
    print("PARTS", {o.name: tri_count(o) for o in parts})
    ch = hc.join(parts, "SK_Goalie" if goalie else "SK_Skater")
    hc.shade(ch, smooth=True, angle=None)
    # sharp-ish blade + stick
    print("CHARACTER", ch.name, "tris", tri_count(ch), "slots", [mt.name for mt in ch.data.materials])
    return ch


def build_static_props(m):
    """Loose props (pivot = their own center): helmet with visor, right glove, stick."""
    out = {}
    helm, visor, strap = build_helmet(m)
    hp = hc.join([helm, visor], "SM_Helmet")
    c = Vector((0.0, 0.0, 1.80))
    hp.data.transform(Matrix.Translation(-c))
    out["SM_Helmet"] = hp
    bpy.data.objects.remove(strap)
    canon = build_glove_canonical(m)
    g = bpy.data.objects.new("SM_Glove", canon.data.copy())
    bpy.context.scene.collection.objects.link(g)
    g.data.transform(Matrix.Translation((0, 0.03, 0)) @ Matrix.Rotation(math.radians(90), 4, "X"))
    bpy.data.objects.remove(canon)
    out["SM_Glove"] = g
    stick = build_stick(m, False)
    st = rig.stick_rest()
    mid = (st["butt"] + st["heel"]) * 0.5
    stick.data.transform(Matrix.Translation(-mid))
    stick.name = "SM_Stick"
    out["SM_Stick"] = stick
    for k, o in out.items():
        o.name = k
        o.data.name = k
        if not o.data.uv_layers:
            eh.box_uv(o, 2.0)
        hc.shade(o, smooth=True, angle=50)
    return out


def render_previews(chars):
    hc.setup_preview_render(res=(1500, 1000), samples=32)
    bpy.context.scene.view_settings.view_transform = "AgX"
    w = bpy.context.scene.world.node_tree.nodes["Background"]
    w.inputs["Color"].default_value = (0.25, 0.28, 0.33, 1)
    hc.add_sun("Key", rotation=(math.radians(50), 0, math.radians(-35)), energy=3.5)
    hc.add_sun("Fill", rotation=(math.radians(65), 0, math.radians(150)), energy=1.3)
    hc.add_sun("Rim", rotation=(math.radians(110), 0, math.radians(10)), energy=1.5)
    cam = hc.add_camera("Cam", (0.0, -6.0, 1.1), (0, 0, 1.0), lens=50)
    floor = hc.box("PrevFloor", (8, 8, 0.02), location=(0, 0, -0.01), mat=hc.material("PrevIce", (0.85, 0.9, 0.95), 0.1))

    def shot(loc, target, name, lens=50):
        cam.location = loc
        cam.rotation_euler = hc.look_at_rotation(loc, target)
        cam.data.lens = lens
        hc.render_to(os.path.join(hc.PREVIEW_DIR, name))
    for ch in chars:
        for o in chars:
            o.hide_render = o is not ch
        tag = ch.name.lower()
        shot((0.0, -6.2, 1.1), (0, 0, 0.98), tag + "_front.png")
        shot((6.2, -0.6, 1.1), (0, 0, 0.98), tag + "_side.png")
        shot((-1.0, 6.2, 1.2), (0, 0, 0.98), tag + "_back.png")
        shot((0.55, -1.3, 1.85), (0, -0.02, 1.76), tag + "_face.png", lens=60)
        shot((-1.6, -2.2, 0.6), (-0.3, -0.4, 0.3), tag + "_stick.png", lens=50)
    for o in chars:
        o.hide_render = False
    bpy.data.objects.remove(floor)


def to_centimeters(objs):
    for o in objs:
        o.location = (0, 0, 0)
        o.rotation_euler = (0, 0, 0)
        o.scale = (S, S, S)
        hc.apply_transforms(o)


def bind(obj, arm):
    obj.parent = arm
    obj.matrix_parent_inverse = Matrix.Identity(4)
    mod = obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm


def main():
    make_face_texture()
    make_mask_texture()
    make_ref_stripes()
    hc.reset_scene()
    m = make_materials()
    arm = rig.build_armature("Armature")
    props = build_static_props(m)
    for name, o in props.items():
        hc.export_static_fbx([o], name + ".fbx")
    for o in props.values():
        bpy.data.objects.remove(o)
    skater = build_character(m, goalie=False)
    goalie = build_character(m, goalie=True)
    goalie.location.x = 1.6
    render_previews([skater, goalie])
    goalie.location.x = 0.0
    hc.apply_transforms(goalie)
    bpy.context.scene.unit_settings.scale_length = 0.01
    to_centimeters([arm, skater, goalie])
    for o in (skater, goalie):
        bind(o, arm)
        hc.export_skeletal_fbx(arm, [o], o.name + ".fbx")
    with open(os.path.join(hc.MAT_DIR, "character.json"), "w") as fp:
        json.dump(MATS, fp, indent=2)
    st = rig.stick_rest()
    with open(os.path.join(hc.MANIFEST_DIR, "character.json"), "w") as fp:
        json.dump({"tris": {"SK_Skater": tri_count(skater), "SK_Goalie": tri_count(goalie)},
                   "bones": [b[0] for b in rig.bone_table()],
                   "stick_blade_rest_m": list(st["cradle"]), "grip_rest_m": list(st["grip"])}, fp, indent=2)
    hc.save_blend("character.blend")
    print("CHARACTER DONE", tri_count(skater), tri_count(goalie))


if __name__ == "__main__":
    main()
