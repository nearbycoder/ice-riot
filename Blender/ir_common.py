"""Shared helpers for the ICE RIOT Blender asset generators.

Every asset in the game is generated procedurally by the scripts in this folder.
Run them headless, e.g.:

    blender -b --factory-startup -P Blender/gen_rink.py

Conventions
-----------
* Blender units are meters. Z is up. The rink runs along the X axis.
* Characters face -Y in Blender (Blender "front" view). After FBX import into
  Unreal the skeletal mesh faces +Y (UE), so the game rotates the mesh -90 yaw.
* Material slot names are the contract with Unreal: the import script maps them
  to Unreal materials by name.
"""

import bpy
import bmesh
import math
import os
import random
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EXPORT_DIR = os.path.join(ROOT, "Art", "Export")
MESH_DIR = os.path.join(EXPORT_DIR, "Meshes")
ANIM_DIR = os.path.join(EXPORT_DIR, "Anims")
TEX_DIR = os.path.join(EXPORT_DIR, "Textures")
PREVIEW_DIR = os.path.join(ROOT, "Art", "Previews")
MAT_DIR = os.path.join(EXPORT_DIR, "Materials")
MANIFEST_DIR = os.path.join(EXPORT_DIR, "Manifests")

for _d in (MESH_DIR, ANIM_DIR, TEX_DIR, PREVIEW_DIR, MAT_DIR, MANIFEST_DIR):
    os.makedirs(_d, exist_ok=True)

FONT_IMPACT = "/System/Library/Fonts/Supplemental/Impact.ttf"
FONT_DIN = "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf"
FONT_ARIAL_BLACK = "/System/Library/Fonts/Supplemental/Arial Black.ttf"


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    sc.render.fps = 30
    return sc


def link(obj, collection=None):
    (collection or bpy.context.scene.collection).objects.link(obj)
    return obj


def new_object(name, mesh):
    obj = bpy.data.objects.new(name, mesh)
    link(obj)
    return obj


def set_active(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def apply_transforms(obj, location=True, rotation=True, scale=True):
    set_active(obj)
    bpy.ops.object.transform_apply(location=location, rotation=rotation, scale=scale)


def apply_modifiers(obj):
    set_active(obj)
    for m in list(obj.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)


def join(objs, name=None):
    objs = [o for o in objs if o is not None]
    set_active(objs[0])
    for o in objs:
        o.select_set(True)
    bpy.ops.object.join()
    out = bpy.context.view_layer.objects.active
    if name:
        out.name = name
        out.data.name = name
    return out


def set_origin(obj, world_point):
    """Move the object's origin to world_point without moving the geometry."""
    world_point = Vector(world_point)
    mw = obj.matrix_world.copy()
    local = mw.inverted() @ world_point
    obj.data.transform(Matrix.Translation(-local))
    obj.matrix_world = mw @ Matrix.Translation(local)


def shade(obj, smooth=True, angle=40.0):
    me = obj.data
    if smooth:
        me.shade_smooth()
        if angle is not None and hasattr(me, "set_sharp_from_angle"):
            me.set_sharp_from_angle(angle=math.radians(angle))
    else:
        me.shade_flat()


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------
def srgb_to_linear(c):
    def f(x):
        return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4
    return tuple(f(v) for v in c)


def hex_color(h, alpha=1.0):
    h = h.lstrip("#")
    rgb = tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return srgb_to_linear(rgb) + (alpha,)


def material(name, color=(0.8, 0.8, 0.8, 1.0), rough=0.5, metal=0.0, emission=None, strength=1.0):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if len(color) == 3:
        color = tuple(color) + (1.0,)
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if emission is not None:
        if len(emission) == 3:
            emission = tuple(emission) + (1.0,)
        bsdf.inputs["Emission Color"].default_value = emission
        bsdf.inputs["Emission Strength"].default_value = strength
    m.diffuse_color = color
    return m


def emission_material(name, color, strength=1.0):
    """Flat unlit color (used for texture renders)."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    if len(color) == 3:
        color = tuple(color) + (1.0,)
    em.inputs["Color"].default_value = color
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return m


def assign_material(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def add_material_slot(obj, mat):
    """Append a material to obj if missing and return its slot index."""
    mats = obj.data.materials
    for i, m in enumerate(mats):
        if m == mat:
            return i
    mats.append(mat)
    return len(mats) - 1


# ---------------------------------------------------------------------------
# Mesh primitives (bmesh based so they work headless without operators)
# ---------------------------------------------------------------------------
def mesh_from_bmesh(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return new_object(name, me)


def box(name, size, location=(0, 0, 0), mat=None, bevel=0.0, segments=2):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    o = bpy.context.active_object
    o.name = name
    o.data.name = name
    o.scale = size
    apply_transforms(o, location=False)
    if bevel > 0:
        m = o.modifiers.new("Bevel", "BEVEL")
        m.width = bevel
        m.segments = segments
        m.limit_method = "ANGLE"
        apply_modifiers(o)
    if mat:
        assign_material(o, mat)
    return o


def cylinder(name, radius, depth, location=(0, 0, 0), rotation=(0, 0, 0), verts=24, mat=None, radius2=None):
    if radius2 is None:
        bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=depth,
                                            location=location, rotation=rotation)
    else:
        bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=radius, radius2=radius2, depth=depth,
                                        location=location, rotation=rotation)
    o = bpy.context.active_object
    o.name = name
    o.data.name = name
    if mat:
        assign_material(o, mat)
    return o


def sphere(name, radius, location=(0, 0, 0), segments=24, rings=12, mat=None, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=radius, location=location)
    o = bpy.context.active_object
    o.name = name
    o.data.name = name
    o.scale = scale
    apply_transforms(o, location=False)
    if mat:
        assign_material(o, mat)
    return o


def torus(name, major, minor, location=(0, 0, 0), rotation=(0, 0, 0), major_seg=48, minor_seg=12, mat=None):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor, major_segments=major_seg,
                                     minor_segments=minor_seg, location=location, rotation=rotation)
    o = bpy.context.active_object
    o.name = name
    o.data.name = name
    if mat:
        assign_material(o, mat)
    return o


def tube_along(name, points, radius, mat=None, bevel_res=6, closed=False):
    """Create a round tube following a polyline of 3D points (curve bevel -> mesh)."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = bevel_res
    cu.use_fill_caps = True
    sp = cu.splines.new("POLY")
    sp.points.add(len(points) - 1)
    for i, p in enumerate(points):
        sp.points[i].co = (p[0], p[1], p[2], 1.0)
    sp.use_cyclic_u = closed
    o = bpy.data.objects.new(name, cu)
    link(o)
    set_active(o)
    bpy.ops.object.convert(target="MESH")
    o = bpy.context.active_object
    if mat:
        assign_material(o, mat)
    return o


def polygon_fill(name, pts2d, z=0.0, mat=None):
    """Filled flat polygon from a list of 2D points (may be concave)."""
    bm = bmesh.new()
    vs = [bm.verts.new((p[0], p[1], z)) for p in pts2d]
    f = bm.faces.new(vs)
    bmesh.ops.triangulate(bm, faces=[f], quad_method="BEAUTY", ngon_method="EAR_CLIP")
    o = mesh_from_bmesh(name, bm)
    if mat:
        assign_material(o, mat)
    return o


def strip_polyline(name, pts2d, width, z=0.0, mat=None, closed=False):
    """Flat ribbon of the given width along a 2D polyline (used for court lines)."""
    bm = bmesh.new()
    n = len(pts2d)
    left, right = [], []
    for i in range(n):
        p = Vector((pts2d[i][0], pts2d[i][1]))
        if closed:
            a = Vector(pts2d[(i - 1) % n]); b = Vector(pts2d[(i + 1) % n])
        else:
            a = Vector(pts2d[max(i - 1, 0)]); b = Vector(pts2d[min(i + 1, n - 1)])
        t = (b - a)
        if t.length < 1e-9:
            t = Vector((1, 0))
        t.normalize()
        nrm = Vector((-t.y, t.x))
        left.append(bm.verts.new((p.x + nrm.x * width * 0.5, p.y + nrm.y * width * 0.5, z)))
        right.append(bm.verts.new((p.x - nrm.x * width * 0.5, p.y - nrm.y * width * 0.5, z)))
    rng = n if closed else n - 1
    for i in range(rng):
        j = (i + 1) % n
        bm.faces.new((left[i], right[i], right[j], left[j]))
    o = mesh_from_bmesh(name, bm)
    if mat:
        assign_material(o, mat)
    return o


def arc_points(cx, cy, r, a0, a1, steps=64):
    pts = []
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * i / steps
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def text_mesh(name, body, size=1.0, font_path=FONT_IMPACT, extrude=0.0, align_x="CENTER", align_y="CENTER",
              location=(0, 0, 0), rotation=(0, 0, 0), mat=None, bevel=0.0, spacing=1.0):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    if font_path and os.path.exists(font_path):
        cu.font = bpy.data.fonts.load(font_path, check_existing=True)
    cu.size = size
    cu.extrude = extrude
    cu.bevel_depth = bevel
    cu.align_x = align_x
    cu.align_y = align_y
    cu.space_character = spacing
    o = bpy.data.objects.new(name, cu)
    o.location = location
    o.rotation_euler = rotation
    link(o)
    set_active(o)
    bpy.ops.object.convert(target="MESH")
    o = bpy.context.active_object
    if mat:
        assign_material(o, mat)
    return o


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
def _select_only(objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def export_static_fbx(objs, filename):
    """Export one or more mesh objects as a single static mesh FBX (they get combined on import)."""
    if not isinstance(objs, (list, tuple)):
        objs = [objs]
    path = os.path.join(MESH_DIR, filename)
    _select_only(objs)
    bpy.ops.export_scene.fbx(
        filepath=path, use_selection=True, object_types={"MESH"},
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_NONE", global_scale=1.0,
        use_space_transform=True, bake_space_transform=False,
        mesh_smooth_type="FACE", use_mesh_modifiers=True, use_tspace=False,
        use_custom_props=False, bake_anim=False, axis_forward="-Z", axis_up="Y",
        colors_type="LINEAR", path_mode="AUTO")
    print("EXPORTED", path)
    return path


def export_skeletal_fbx(armature, meshes, filename, directory=None, with_anim=False):
    path = os.path.join(directory or MESH_DIR, filename)
    _select_only([armature] + list(meshes))
    bpy.context.view_layer.objects.active = armature
    bpy.ops.export_scene.fbx(
        filepath=path, use_selection=True, object_types={"ARMATURE", "MESH"},
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_ALL", global_scale=1.0,
        mesh_smooth_type="FACE", use_mesh_modifiers=True, use_tspace=False,
        add_leaf_bones=False, primary_bone_axis="Y", secondary_bone_axis="X",
        use_armature_deform_only=False, armature_nodetype="NULL",
        bake_anim=with_anim, bake_anim_use_all_bones=True, bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=False, bake_anim_force_startend_keying=True,
        bake_anim_simplify_factor=0.0, axis_forward="-Z", axis_up="Y", colors_type="LINEAR")
    print("EXPORTED", path)
    return path


def export_anim_fbx(armature, filename):
    path = os.path.join(ANIM_DIR, filename)
    _select_only([armature])
    bpy.ops.export_scene.fbx(
        filepath=path, use_selection=True, object_types={"ARMATURE"},
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_ALL", global_scale=1.0,
        add_leaf_bones=False, primary_bone_axis="Y", secondary_bone_axis="X",
        use_armature_deform_only=False, armature_nodetype="NULL",
        bake_anim=True, bake_anim_use_all_bones=True, bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=False, bake_anim_force_startend_keying=True,
        bake_anim_simplify_factor=0.0, axis_forward="-Z", axis_up="Y")
    print("EXPORTED", path)
    return path


# ---------------------------------------------------------------------------
# Preview rendering (used to visually verify generated assets)
# ---------------------------------------------------------------------------
def setup_preview_render(res=(1024, 1024), samples=32, transparent=False):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = transparent
    try:
        sc.eevee.taa_render_samples = samples
    except Exception:
        pass
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    if sc.world is None:
        sc.world = bpy.data.worlds.new("World")
    sc.world.use_nodes = True
    bg = sc.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.32, 0.34, 0.38, 1)
        bg.inputs["Strength"].default_value = 0.7
    return sc


def add_sun(name="Sun", rotation=(math.radians(50), 0, math.radians(30)), energy=3.0):
    ld = bpy.data.lights.new(name, "SUN")
    ld.energy = energy
    o = bpy.data.objects.new(name, ld)
    o.rotation_euler = rotation
    link(o)
    return o


def add_area(name, location, rotation, energy=500.0, size=4.0):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = energy
    ld.size = size
    o = bpy.data.objects.new(name, ld)
    o.location = location
    o.rotation_euler = rotation
    link(o)
    return o


def look_at_rotation(cam_loc, target):
    d = Vector(target) - Vector(cam_loc)
    return d.to_track_quat("-Z", "Y").to_euler()


def add_camera(name, location, target, lens=50.0, ortho_scale=None):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_end = 1000
    if ortho_scale:
        cd.type = "ORTHO"
        cd.ortho_scale = ortho_scale
    o = bpy.data.objects.new(name, cd)
    o.location = location
    o.rotation_euler = look_at_rotation(location, target)
    link(o)
    bpy.context.scene.camera = o
    return o


def render_to(path):
    sc = bpy.context.scene
    sc.render.filepath = path
    sc.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    print("RENDERED", path)


def save_blend(name):
    path = os.path.join(ROOT, "Art", "Blend", name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    print("SAVED", path)
