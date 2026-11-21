"""Environment-art helpers for the ICE RIOT generators (rink, arena, props, branding).

Generic numpy image / flat-render / mesh-building / material-manifest helpers.

Conventions used in this module
-------------------------------
* numpy images are float32 arrays shaped (H, W, C), row 0 = BOTTOM of the image
  (Blender's pixel order), values are display/sRGB-encoded 0..1 unless noted.
* "flat" renders are orthographic top-down Eevee renders of emission-shaded geometry
  with the Standard view transform, so an emission color of srgb_to_linear(c)
  comes out as exactly c in the PNG.
* Material specs follow Docs/ASSET_SPEC.md (colors are LINEAR RGB 0..1).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import bmesh  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import shutil  # noqa: E402
import tempfile  # noqa: E402

import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

import ir_common as hc  # noqa: E402

# ---------------------------------------------------------------------------
# Paths / constants
# ---------------------------------------------------------------------------
ROOT = hc.ROOT
EXPORT_DIR = hc.EXPORT_DIR
MESH_DIR = hc.MESH_DIR
TEX_DIR = hc.TEX_DIR
PREVIEW_DIR = hc.PREVIEW_DIR
MAT_DIR = os.path.join(EXPORT_DIR, "Materials")
MANIFEST_DIR = os.path.join(EXPORT_DIR, "Manifests")
UI_DIR = os.path.join(EXPORT_DIR, "UI")
for _d in (MESH_DIR, TEX_DIR, PREVIEW_DIR, MAT_DIR, MANIFEST_DIR, UI_DIR):
    os.makedirs(_d, exist_ok=True)

FONT_IMPACT = hc.FONT_IMPACT
FONT_DIN = hc.FONT_DIN
FONT_ARIAL_BLACK = hc.FONT_ARIAL_BLACK
FONT_FUTURA = "/System/Library/Fonts/Supplemental/Futura.ttc"

# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------
def srgb(h):
    """'#RRGGBB' -> display (sRGB-encoded) tuple 0..1."""
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def lin(h):
    """'#RRGGBB' -> linear RGB tuple (what goes into Blender Base Color / the material JSON)."""
    return tuple(hc.srgb_to_linear(srgb(h)))


def lin3(c):
    """display tuple -> linear tuple."""
    return tuple(hc.srgb_to_linear(tuple(c)))


def np_to_linear(a):
    a = np.asarray(a, np.float32)
    return np.where(a <= 0.04045, a / 12.92, np.power((np.maximum(a, 0.0) + 0.055) / 1.055, 2.4)).astype(np.float32)


def np_to_srgb(a):
    a = np.maximum(np.asarray(a, np.float32), 0.0)
    return np.where(a <= 0.0031308, a * 12.92, 1.055 * np.power(a, 1.0 / 2.4) - 0.055).astype(np.float32)


def mix(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def rnd_list(c, nd=4):
    return [round(float(v), nd) for v in c]


# ---------------------------------------------------------------------------
# Image IO (numpy, bottom-up rows, display values)
# ---------------------------------------------------------------------------
def save_png(arr, path, alpha=None):
    arr = np.asarray(arr, np.float32)
    if arr.ndim == 2:
        arr = arr[..., None]
    h, w, c = arr.shape
    rgba = np.ones((h, w, 4), np.float32)
    if c == 1:
        rgba[..., :3] = arr
    else:
        rgba[..., :3] = arr[..., :3]
    has_alpha = (c == 4) or (alpha is not None)
    if c == 4:
        rgba[..., 3] = arr[..., 3]
    if alpha is not None:
        rgba[..., 3] = alpha
    np.clip(rgba, 0.0, 1.0, out=rgba)
    # round instead of truncate when Blender converts float -> byte
    rgba = (np.floor(rgba * 255.0 + 0.5) / 255.0).astype(np.float32)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img = bpy.data.images.new("__ir_save", w, h, alpha=has_alpha, float_buffer=False)
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    print("WROTE", path, "%dx%d" % (w, h))
    return path


def load_png(path):
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    buf = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(buf)
    bpy.data.images.remove(img)
    return buf.reshape(h, w, 4)


def resize_nearest(arr, new_w, new_h):
    h, w = arr.shape[:2]
    yi = (np.arange(new_h) * h // new_h).astype(np.int64)
    xi = (np.arange(new_w) * w // new_w).astype(np.int64)
    return arr[yi][:, xi]


def downsample(arr, f):
    """Box-filter downsample by an integer factor."""
    h, w = arr.shape[:2]
    h2, w2 = h // f, w // f
    a = arr[:h2 * f, :w2 * f]
    return a.reshape(h2, f, w2, f, *a.shape[2:]).mean(axis=(1, 3)).astype(np.float32)


def box_blur(a, r, axis_both=True):
    """Separable box blur with radius r (pixels) using cumulative sums; edges clamp."""
    if r <= 0:
        return a
    out = a.astype(np.float32)
    for ax in ((0, 1) if axis_both else (1,)):
        pad = [(0, 0)] * out.ndim
        pad[ax] = (r + 1, r)
        p = np.pad(out, pad, mode="edge")
        c = np.cumsum(p, axis=ax, dtype=np.float64)
        n = out.shape[ax]
        hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=ax)
        lo = np.take(c, np.arange(0, n), axis=ax)
        out = ((hi - lo) / (2 * r + 1)).astype(np.float32)
    return out


def gauss_blur(a, sigma):
    """Approximate gaussian via 3 box blurs."""
    if sigma <= 0.3:
        return a
    r = max(1, int(round(math.sqrt(12 * sigma * sigma / 3 + 1) / 2)))
    out = a
    for _ in range(3):
        out = box_blur(out, r)
    return out


def dilate(mask, r):
    """Grey dilation with a (2r+1) square-ish (octagonal over iterations) structuring element."""
    out = mask.copy()
    for i in range(r):
        p = np.pad(out, 1, mode="edge")
        if i % 2 == 0:
            out = np.maximum.reduce([p[1:-1, 1:-1], p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:]])
        else:
            out = np.maximum.reduce([p[1:-1, 1:-1], p[:-2, :-2], p[2:, 2:], p[:-2, 2:], p[2:, :-2],
                                     p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:]])
    return out


def over(dst_rgb, src_rgb, src_a):
    """Straight-alpha 'over' composite in display space. dst (H,W,3), src (H,W,3), a (H,W)."""
    a = src_a[..., None]
    return dst_rgb * (1.0 - a) + src_rgb * a


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# ---------------------------------------------------------------------------
# Value noise (numpy)
# ---------------------------------------------------------------------------
class LatticeNoise:
    """Tileable 2D value noise with smoothstep interpolation, values in [-1, 1]."""

    def __init__(self, seed, size=(256, 256)):
        r = np.random.default_rng(seed)
        self.ny, self.nx = size
        self.tab = (r.random(size, dtype=np.float32) * 2.0 - 1.0)

    def __call__(self, x, y):
        x = np.asarray(x, np.float32)
        y = np.asarray(y, np.float32)
        x0 = np.floor(x)
        y0 = np.floor(y)
        fx = x - x0
        fy = y - y0
        fx = fx * fx * (3.0 - 2.0 * fx)
        fy = fy * fy * (3.0 - 2.0 * fy)
        ix = x0.astype(np.int64) % self.nx
        iy = y0.astype(np.int64) % self.ny
        ix1 = (ix + 1) % self.nx
        iy1 = (iy + 1) % self.ny
        t = self.tab
        a = t[iy, ix] + (t[iy, ix1] - t[iy, ix]) * fx
        b = t[iy1, ix] + (t[iy1, ix1] - t[iy1, ix]) * fx
        return a + (b - a) * fy


def fbm(noise, x, y, octaves=4, lacunarity=2.0, gain=0.5):
    amp = 1.0
    tot = 0.0
    norm = 0.0
    fx = 1.0
    for i in range(octaves):
        tot = tot + noise(x * fx + 17.3 * i, y * fx + 31.7 * i) * amp
        norm += amp
        amp *= gain
        fx *= lacunarity
    return tot / norm


# ---------------------------------------------------------------------------
# Flat (texture) rendering
# ---------------------------------------------------------------------------
def flat_scene(res_x, res_y, samples=16, transparent=True, filter_size=1.2):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x = int(res_x)
    sc.render.resolution_y = int(res_y)
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = transparent
    sc.render.filter_size = filter_size
    try:
        sc.eevee.taa_render_samples = samples
    except Exception:
        pass
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = 0.0
    sc.view_settings.gamma = 1.0
    sc.display_settings.display_device = "sRGB"
    sc.render.use_compositing = False
    sc.render.use_sequencer = False
    if sc.world is None:
        sc.world = bpy.data.worlds.new("FlatWorld")
    sc.world.use_nodes = True
    bg = sc.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0, 0, 0, 1)
        bg.inputs["Strength"].default_value = 0.0
    s = sc.render.image_settings
    s.file_format = "PNG"
    s.color_mode = "RGBA"
    s.color_depth = "8"
    return sc


def ortho_camera(cx, cy, width, z=50.0, name="FlatCam"):
    cam = bpy.data.objects.get(name)
    if cam is None:
        cd = bpy.data.cameras.new(name)
        cam = bpy.data.objects.new(name, cd)
        bpy.context.scene.collection.objects.link(cam)
    cd = cam.data
    cd.type = "ORTHO"
    cd.sensor_fit = "HORIZONTAL"
    cd.ortho_scale = width
    cd.clip_start = 0.5
    cd.clip_end = 200.0
    cd.shift_x = 0.0
    cd.shift_y = 0.0
    cam.location = (cx, cy, z)
    cam.rotation_euler = (0.0, 0.0, 0.0)
    bpy.context.scene.camera = cam
    return cam


_TMPDIR = None


def _tmpdir():
    global _TMPDIR
    if _TMPDIR is None or not os.path.isdir(_TMPDIR):
        _TMPDIR = tempfile.mkdtemp(prefix="ir_env_")
    return _TMPDIR


def cleanup_tmp():
    global _TMPDIR
    if _TMPDIR and os.path.isdir(_TMPDIR):
        shutil.rmtree(_TMPDIR, ignore_errors=True)
    _TMPDIR = None


def render_rgba(name="flat"):
    """Render the current scene/camera and return an (H, W, 4) float32 array (bottom-up, straight alpha)."""
    sc = bpy.context.scene
    path = os.path.join(_tmpdir(), name + ".png")
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return load_png(path)


def render_region(x0, y0, x1, y1, res_x, res_y, name="flat"):
    """Orthographic top-down render covering world rect [x0,x1]x[y0,y1] at res_x x res_y."""
    flat_scene(res_x, res_y, samples=bpy.context.scene.eevee.taa_render_samples)
    ortho_camera((x0 + x1) * 0.5, (y0 + y1) * 0.5, x1 - x0)
    return render_rgba(name)


_flat_mats = {}


def flat_mat(name, color_srgb, alpha=1.0):
    """Emission material that renders exactly as color_srgb (display) under flat_scene()."""
    if isinstance(color_srgb, str):
        color_srgb = srgb(color_srgb)
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = tuple(lin3(color_srgb)) + (1.0,)
    em.inputs["Strength"].default_value = 1.0
    if alpha < 1.0:
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mx = nt.nodes.new("ShaderNodeMixShader")
        mx.inputs["Fac"].default_value = alpha
        nt.links.new(tr.outputs[0], mx.inputs[1])
        nt.links.new(em.outputs[0], mx.inputs[2])
        nt.links.new(mx.outputs[0], out.inputs["Surface"])
        try:
            m.surface_render_method = "BLENDED"
        except Exception:
            pass
    else:
        nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def gradient_mat(name, stops, axis="Y", v0=0.0, v1=1.0, center=None, alpha_stops=None):
    """Emission material with a color ramp along a world axis ('X','Y','Z') or radial (center=(x,y)).

    stops: list of (position 0..1, '#hex' or display tuple). Interpolation happens in linear space.
    alpha_stops: optional list of (pos, alpha) -> blended transparency.
    """
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    if center is not None:
        vm = nt.nodes.new("ShaderNodeVectorMath")
        vm.operation = "DISTANCE"
        vm.inputs[1].default_value = (center[0], center[1], 0.0)
        # flatten z by using a separate/combine
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        comb = nt.nodes.new("ShaderNodeCombineXYZ")
        nt.links.new(geo.outputs["Position"], sep.inputs[0])
        nt.links.new(sep.outputs[0], comb.inputs[0])
        nt.links.new(sep.outputs[1], comb.inputs[1])
        nt.links.new(comb.outputs[0], vm.inputs[0])
        src = vm.outputs["Value"]
    else:
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(geo.outputs["Position"], sep.inputs[0])
        src = sep.outputs["XYZ".index(axis)]
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = v0
    mr.inputs["From Max"].default_value = v1
    mr.clamp = True
    nt.links.new(src, mr.inputs["Value"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    while len(els) > 1:
        els.remove(els[-1])
    for i, (p, c) in enumerate(stops):
        if isinstance(c, str):
            c = srgb(c)
        e = els[0] if i == 0 else els.new(p)
        e.position = p
        e.color = tuple(lin3(c)) + (1.0,)
    nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
    if alpha_stops:
        ar = nt.nodes.new("ShaderNodeValToRGB")
        aels = ar.color_ramp.elements
        while len(aels) > 1:
            aels.remove(aels[-1])
        for i, (p, a) in enumerate(alpha_stops):
            e = aels[0] if i == 0 else aels.new(p)
            e.position = p
            e.color = (a, a, a, 1.0)
        nt.links.new(mr.outputs["Result"], ar.inputs["Fac"])
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mx = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(ar.outputs["Color"], mx.inputs["Fac"])
        nt.links.new(tr.outputs[0], mx.inputs[1])
        nt.links.new(em.outputs[0], mx.inputs[2])
        nt.links.new(mx.outputs[0], out.inputs["Surface"])
        try:
            m.surface_render_method = "BLENDED"
        except Exception:
            pass
    else:
        nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


# ---------------------------------------------------------------------------
# 2D geometry -> flat meshes
# ---------------------------------------------------------------------------
def bezier(p0, p1, p2, p3, n=24, include_end=False):
    pts = []
    rng = range(n + 1) if include_end else range(n)
    for i in rng:
        t = i / n
        u = 1 - t
        x = u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0]
        y = u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1]
        pts.append((x, y))
    return pts


def circle_pts(cx, cy, r, n=64, a0=0.0, a1=2 * math.pi, include_end=False):
    pts = []
    m = n + 1 if include_end else n
    for i in range(m):
        a = a0 + (a1 - a0) * i / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def poly_area(pts):
    s = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        s += x0 * y1 - x1 * y0
    return 0.5 * s


def xform2d(pts, scale=1.0, offset=(0.0, 0.0), rot=0.0, sx=None, sy=None):
    c, s = math.cos(rot), math.sin(rot)
    sx = scale if sx is None else sx
    sy = scale if sy is None else sy
    out = []
    for x, y in pts:
        x, y = x * sx, y * sy
        out.append((x * c - y * s + offset[0], x * s + y * c + offset[1]))
    return out


def dedupe(pts, eps=1e-7):
    out = []
    for p in pts:
        if not out or (abs(p[0] - out[-1][0]) > eps or abs(p[1] - out[-1][1]) > eps):
            out.append(p)
    if len(out) > 2 and abs(out[0][0] - out[-1][0]) < eps and abs(out[0][1] - out[-1][1]) < eps:
        out.pop()
    return out


def bm_add_fill(bm, pts, z=0.0, holes=()):
    """Filled (possibly concave) polygon with optional holes, +Z facing triangles.

    Uses mathutils.geometry.tessellate_polygon: bmesh.ops.triangulate mis-fills concave n-gons.
    """
    from mathutils import geometry
    loops = [dedupe(pts)] + [dedupe(h) for h in holes]
    flat = [p for lp in loops for p in lp]
    tris = geometry.tessellate_polygon([[Vector((p[0], p[1], 0.0)) for p in lp] for lp in loops])
    vs = [bm.verts.new((p[0], p[1], z)) for p in flat]
    for (i, j, k) in tris:
        a, b, c = flat[i], flat[j], flat[k]
        if (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1]) < 0:
            j, k = k, j
        try:
            bm.faces.new((vs[i], vs[j], vs[k]))
        except ValueError:
            pass


def bm_add_disk(bm, cx, cy, r, z=0.0, seg=12):
    c = bm.verts.new((cx, cy, z))
    ring = [bm.verts.new((cx + r * math.cos(2 * math.pi * i / seg), cy + r * math.sin(2 * math.pi * i / seg), z))
            for i in range(seg)]
    for i in range(seg):
        bm.faces.new((c, ring[i], ring[(i + 1) % seg]))


def bm_add_stroke(bm, pts, hw, z=0.0, closed=True, round_joins=True, seg=12):
    """Union of edge rectangles (+ round joins) = Minkowski sum of the polyline with a disk of radius hw."""
    pts = dedupe(pts)
    n = len(pts)
    m = n if closed else n - 1
    for i in range(m):
        a = Vector(pts[i])
        b = Vector(pts[(i + 1) % n])
        t = b - a
        if t.length < 1e-9:
            continue
        t.normalize()
        nn = Vector((-t.y, t.x)) * hw
        v = [bm.verts.new((a.x + nn.x, a.y + nn.y, z)), bm.verts.new((a.x - nn.x, a.y - nn.y, z)),
             bm.verts.new((b.x - nn.x, b.y - nn.y, z)), bm.verts.new((b.x + nn.x, b.y + nn.y, z))]
        bm.faces.new(v)
    if round_joins:
        for p in pts:
            bm_add_disk(bm, p[0], p[1], hw, z, seg)


def bm_add_ring(bm, cx, cy, r_in, r_out, z=0.0, seg=256, a0=0.0, a1=2 * math.pi):
    full = abs((a1 - a0) - 2 * math.pi) < 1e-9
    n = seg
    inner, outer = [], []
    m = n if full else n + 1
    for i in range(m):
        a = a0 + (a1 - a0) * i / n
        inner.append(bm.verts.new((cx + r_in * math.cos(a), cy + r_in * math.sin(a), z)))
        outer.append(bm.verts.new((cx + r_out * math.cos(a), cy + r_out * math.sin(a), z)))
    for i in range(n):
        j = (i + 1) % m if full else i + 1
        bm.faces.new((inner[i], outer[i], outer[j], inner[j]))


def obj_from_bm(name, bm, mat=None, collection=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(o)
    if mat is not None:
        me.materials.append(mat)
    return o


def fill_obj(name, polys, z=0.0, mat=None, collection=None):
    bm = bmesh.new()
    for p in polys:
        bm_add_fill(bm, p, z)
    return obj_from_bm(name, bm, mat, collection)


def stroke_obj(name, polylines, hw, z=0.0, mat=None, closed=False, collection=None, seg=12):
    bm = bmesh.new()
    for p in polylines:
        bm_add_stroke(bm, p, hw, z, closed=closed, seg=seg)
    return obj_from_bm(name, bm, mat, collection)


def outline_obj(name, polys, d, z=0.0, mat=None, collection=None, seg=12):
    """Filled polygons dilated by d (fill + boundary stroke)."""
    bm = bmesh.new()
    for p in polys:
        bm_add_fill(bm, p, z)
        if d > 0:
            bm_add_stroke(bm, p, d, z, closed=True, seg=seg)
    return obj_from_bm(name, bm, mat, collection)


def dilate_mesh_obj(src, name, d, z=None, mat=None, collection=None, seg=10):
    """Copy of a flat mesh object (world space) grown by d: faces + boundary edge quads + vertex disks."""
    me = src.data
    mw = src.matrix_basis
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.transform(mw)
    zz = z
    if zz is None:
        zz = sum(v.co.z for v in bm.verts) / max(1, len(bm.verts))
    for v in bm.verts:
        v.co.z = zz
    edges = [(e.verts[0].co.copy(), e.verts[1].co.copy()) for e in bm.edges if len(e.link_faces) == 1]
    bverts = {v.index: v.co.copy() for v in bm.verts if any(len(e.link_faces) == 1 for e in v.link_edges)}
    if d > 0:
        for a, b in edges:
            t = (b - a)
            t.z = 0
            if t.length < 1e-9:
                continue
            t.normalize()
            nn = Vector((-t.y, t.x, 0.0)) * d
            bm.faces.new([bm.verts.new(a + nn), bm.verts.new(a - nn), bm.verts.new(b - nn), bm.verts.new(b + nn)])
        for co in bverts.values():
            bm_add_disk(bm, co.x, co.y, d, zz, seg)
    o = obj_from_bm(name, bm, mat, collection)
    return o


def text_obj(name, body, size, font=FONT_IMPACT, loc=(0, 0, 0), mat=None, shear=0.0, spacing=1.0,
             align_x="CENTER", align_y="CENTER", collection=None, as_mesh=True, extrude=0.0, bevel=0.0,
             bevel_res=2, offset=0.0, resolution=6):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.font = bpy.data.fonts.load(font, check_existing=True)
    cu.size = size
    cu.shear = shear
    cu.space_character = spacing
    cu.align_x = align_x
    cu.align_y = align_y
    cu.extrude = extrude
    cu.bevel_depth = bevel
    cu.bevel_resolution = bevel_res
    cu.offset = offset
    cu.resolution_u = resolution
    o = bpy.data.objects.new(name, cu)
    o.location = loc
    (collection or bpy.context.scene.collection).objects.link(o)
    if as_mesh:
        dg = bpy.context.evaluated_depsgraph_get()
        oe = o.evaluated_get(dg)
        me = bpy.data.meshes.new_from_object(oe)
        mo = bpy.data.objects.new(name, me)
        mo.location = o.location
        (collection or bpy.context.scene.collection).objects.link(mo)
        bpy.data.objects.remove(o)
        bpy.data.curves.remove(cu)
        o = mo
    if mat is not None:
        o.data.materials.clear()
        o.data.materials.append(mat)
    return o


def bake_obj(o):
    """Apply the object's own loc/rot/scale into its mesh data (matrix_basis is always current;
    matrix_world can be stale in background scripts until the depsgraph updates)."""
    from mathutils import Matrix
    M = o.matrix_basis.copy()
    if M != Matrix.Identity(4):
        o.data.transform(M)
        o.location = (0.0, 0.0, 0.0)
        o.rotation_euler = (0.0, 0.0, 0.0)
        o.scale = (1.0, 1.0, 1.0)
        o.data.update()
    return o


def mesh_bounds(o):
    """World-space (min, max) of a mesh object's vertices."""
    mw = o.matrix_basis
    co = np.empty(len(o.data.vertices) * 3, np.float32)
    o.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    if len(co) == 0:
        return Vector((0, 0, 0)), Vector((0, 0, 0))
    M = np.array(mw, np.float32)
    w = co @ M[:3, :3].T + M[:3, 3]
    return Vector(w.min(axis=0)), Vector(w.max(axis=0))


def fit_obj(o, width=None, height=None, center=None):
    """Uniformly scale a flat mesh object (in place, baked) to a width or height and optionally center it."""
    bake_obj(o)
    lo, hi = mesh_bounds(o)
    w = hi.x - lo.x
    h = hi.y - lo.y
    s = 1.0
    if width is not None and height is not None:
        s = min(width / w, height / h)
    elif width is not None:
        s = width / w
    elif height is not None:
        s = height / h
    cx = (lo.x + hi.x) * 0.5
    cy = (lo.y + hi.y) * 0.5
    from mathutils import Matrix
    zc = (lo.z + hi.z) * 0.5
    T = Matrix.Translation((-cx, -cy, 0.0))
    S = Matrix.Diagonal((s, s, 1.0, 1.0))
    o.data.transform(S @ T)
    if center is not None:
        o.data.transform(Matrix.Translation((center[0], center[1], 0.0)))
    o.data.update()
    return s


def set_z(o, z):
    bake_obj(o)
    co = np.empty(len(o.data.vertices) * 3, np.float32)
    o.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    co[:, 2] = z
    o.data.vertices.foreach_set("co", co.ravel())
    o.data.update()
    return o


def clear_scene():
    hc.reset_scene()
    _flat_mats.clear()


# ---------------------------------------------------------------------------
# Fast mesh construction from numpy arrays
# ---------------------------------------------------------------------------
def mesh_from_arrays(name, verts, faces, face_sizes=None, uvs=None, colors=None, mat_idx=None, materials=None,
                     smooth=False, collection=None, uv_name="UVMap"):
    """Build a mesh object.

    verts: (N,3); faces: (M,k) int array (uniform polygons) or flat corner array with face_sizes (M,)
    uvs: (L,2) per-corner or None; colors: (L,4) per-corner linear floats or None
    mat_idx: (M,) material slot indices; materials: list of bpy materials.
    """
    verts = np.asarray(verts, np.float32).reshape(-1, 3)
    if face_sizes is None:
        faces = np.asarray(faces, np.int32)
        k = faces.shape[1]
        corners = faces.ravel()
        sizes = np.full(faces.shape[0], k, np.int32)
    else:
        corners = np.asarray(faces, np.int32).ravel()
        sizes = np.asarray(face_sizes, np.int32)
    starts = np.zeros(len(sizes), np.int32)
    if len(sizes) > 1:
        starts[1:] = np.cumsum(sizes)[:-1]
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(verts))
    me.vertices.foreach_set("co", verts.ravel())
    me.loops.add(len(corners))
    me.loops.foreach_set("vertex_index", corners)
    me.polygons.add(len(sizes))
    me.polygons.foreach_set("loop_start", starts)
    me.polygons.foreach_set("loop_total", sizes)
    me.update(calc_edges=True)
    if uvs is not None:
        uvl = me.uv_layers.new(name=uv_name)
        uvl.data.foreach_set("uv", np.asarray(uvs, np.float32).ravel())
    if colors is not None:
        ca = me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
        ca.data.foreach_set("color", np.asarray(colors, np.float32).ravel())
        try:
            me.color_attributes.active_color = ca
            me.color_attributes.render_color_index = 0
        except Exception:
            pass
    if materials:
        for m in materials:
            me.materials.append(m)
        if mat_idx is not None:
            me.polygons.foreach_set("material_index", np.asarray(mat_idx, np.int32))
    sm = np.full(len(sizes), bool(smooth))
    me.polygons.foreach_set("use_smooth", sm)
    me.validate(verbose=False)
    me.update()
    o = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(o)
    return o


def tri_count(obj):
    me = obj.data
    n = len(me.polygons)
    if n == 0:
        return 0
    lt = np.empty(n, np.int32)
    me.polygons.foreach_get("loop_total", lt)
    return int((lt - 2).sum())


class MeshBuilder:
    """Accumulates quads/tris (numpy-friendly) with per-face material slot + optional per-corner UVs/colors."""

    def __init__(self):
        self.verts = []
        self.faces = []      # list of tuples of vertex indices
        self.mats = []
        self.uvs = []        # per-face list of (u,v) per corner, or None
        self.cols = []
        self.smooth = []
        self.has_uv = False
        self.has_col = False

    def v(self, co):
        self.verts.append(tuple(co))
        return len(self.verts) - 1

    def face(self, idx, mat=0, uv=None, col=None, smooth=False):
        self.faces.append(tuple(idx))
        self.mats.append(mat)
        self.uvs.append(uv)
        self.cols.append(col)
        self.smooth.append(smooth)
        if uv is not None:
            self.has_uv = True
        if col is not None:
            self.has_col = True
        return len(self.faces) - 1

    def quad(self, a, b, c, d, mat=0, uv=None, col=None, smooth=False):
        ia, ib, ic, id_ = self.v(a), self.v(b), self.v(c), self.v(d)
        return self.face((ia, ib, ic, id_), mat, uv, col, smooth)

    def tri(self, a, b, c, mat=0, uv=None, col=None, smooth=False):
        return self.face((self.v(a), self.v(b), self.v(c)), mat, uv, col, smooth)

    def box(self, lo, hi, mat=0, skip=(), uvscale=None):
        """Axis-aligned box from lo to hi. skip: subset of {'-x','+x','-y','+y','-z','+z'}."""
        x0, y0, z0 = lo
        x1, y1, z1 = hi
        P = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
             (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        F = {"-z": (0, 3, 2, 1), "+z": (4, 5, 6, 7), "-y": (0, 1, 5, 4), "+y": (2, 3, 7, 6),
             "-x": (3, 0, 4, 7), "+x": (1, 2, 6, 5)}
        for k, f in F.items():
            if k in skip:
                continue
            self.quad(*(P[i] for i in f), mat=mat)

    def oriented_box(self, center, ax, ay, az, hx, hy, hz, mat=0, skip=(), col=None):
        """Box with local axes ax, ay, az (unit Vectors) and half sizes."""
        c = Vector(center)
        ax, ay, az = Vector(ax), Vector(ay), Vector(az)
        P = []
        for sz in (-1, 1):
            for (sx, sy) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                P.append(tuple(c + ax * (sx * hx) + ay * (sy * hy) + az * (sz * hz)))
        F = {"-z": (0, 3, 2, 1), "+z": (4, 5, 6, 7), "-y": (0, 1, 5, 4), "+y": (2, 3, 7, 6),
             "-x": (3, 0, 4, 7), "+x": (1, 2, 6, 5)}
        for k, f in F.items():
            if k in skip:
                continue
            self.quad(*(P[i] for i in f), mat=mat, col=col)

    def extend(self, other_verts, other_faces, mat=0):
        base = len(self.verts)
        self.verts.extend(tuple(v) for v in other_verts)
        for f in other_faces:
            self.face(tuple(base + i for i in f), mat)

    def _box_uv_face(self, f, scale=0.5):
        P = [Vector(self.verts[i]) for i in f]
        n = (P[1] - P[0]).cross(P[2] - P[0])
        ax = max(range(3), key=lambda k: abs(n[k]))
        out = []
        for p in P:
            u = p.y if ax == 0 else p.x
            v = p.y if ax == 2 else p.z
            out.append((u * scale, v * scale))
        return out

    def build(self, name, materials, collection=None, weld=False):
        if not self.faces:
            return None
        sizes = np.array([len(f) for f in self.faces], np.int32)
        corners = np.array([i for f in self.faces for i in f], np.int32)
        uvs = None
        cols = None
        if self.has_uv:
            uvs = []
            for f, uv in zip(self.faces, self.uvs):
                if uv is None:
                    uv = self._box_uv_face(f)
                uvs.extend(uv)
            uvs = np.array(uvs, np.float32)
        if self.has_col:
            cols = []
            for f, c in zip(self.faces, self.cols):
                if c is None:
                    c = (1, 1, 1, 1)
                if len(c) == 4 and not isinstance(c[0], (tuple, list)):
                    cols.extend([c] * len(f))
                else:
                    cols.extend(c)
            cols = np.array(cols, np.float32)
        o = mesh_from_arrays(name, np.array(self.verts, np.float32), corners, sizes, uvs=uvs, colors=cols,
                             mat_idx=np.array(self.mats, np.int32), materials=materials, collection=collection)
        o.data.polygons.foreach_set("use_smooth", np.array(self.smooth, bool))
        if weld:
            bm = bmesh.new()
            bm.from_mesh(o.data)
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
            bm.to_mesh(o.data)
            bm.free()
        o.data.update()
        return o


# ---------------------------------------------------------------------------
# Material registry: Blender materials + Art/Export/Materials/<generator>.json
# ---------------------------------------------------------------------------
def _tex_path(name):
    return os.path.join(TEX_DIR, name + ".png")


def build_preview_material(name, spec, emission_scale=1.0):
    """Create/refresh a Blender material that approximates the Unreal shader described by spec."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    sh = spec.get("shader", "opaque")
    # hockey specific shaders preview like their closest generic cousin
    sh = {"ice": "opaque", "team": "opaque", "skin": "opaque", "number": "opaque", "screen": "emissive",
          "goallight": "opaque", "netting": "masked"}.get(sh, sh)
    color = tuple(spec.get("color", [1, 1, 1]))[:3]

    def tex_node(alpha_needed=False):
        tname = spec.get("texture")
        if not tname:
            return None
        p = _tex_path(tname)
        if not os.path.exists(p):
            return None
        img = bpy.data.images.load(p, check_existing=True)
        tn = nt.nodes.new("ShaderNodeTexImage")
        tn.image = img
        tn.interpolation = "Linear"
        til = spec.get("tiling")
        if til:
            tc = nt.nodes.new("ShaderNodeTexCoord")
            mp = nt.nodes.new("ShaderNodeMapping")
            mp.inputs["Scale"].default_value = (til[0], til[1], 1.0)
            nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
            nt.links.new(mp.outputs["Vector"], tn.inputs["Vector"])
        return tn

    def mul_color(src_socket):
        mx = nt.nodes.new("ShaderNodeMix")
        mx.data_type = "RGBA"
        mx.blend_type = "MULTIPLY"
        mx.inputs["Factor"].default_value = 1.0
        nt.links.new(src_socket, mx.inputs["A"])
        mx.inputs["B"].default_value = color + (1.0,)
        return mx.outputs["Result"]

    if sh in ("opaque", "vertexcolor", "masked", "crowd"):
        b = nt.nodes.new("ShaderNodeBsdfPrincipled")
        b.inputs["Roughness"].default_value = spec.get("roughness", 0.5 if sh != "crowd" else 0.8)
        b.inputs["Metallic"].default_value = spec.get("metallic", 0.0)
        try:
            b.inputs["Specular IOR Level"].default_value = spec.get("specular", 0.5)
        except Exception:
            pass
        b.inputs["Base Color"].default_value = color + (1.0,)
        if sh in ("vertexcolor", "crowd"):
            va = nt.nodes.new("ShaderNodeVertexColor")
            va.layer_name = ""
            nt.links.new(mul_color(va.outputs["Color"]) if sh == "vertexcolor" else va.outputs["Color"],
                         b.inputs["Base Color"])
        else:
            tn = tex_node()
            if tn is not None:
                nt.links.new(mul_color(tn.outputs["Color"]), b.inputs["Base Color"])
                if sh == "masked":
                    gt = nt.nodes.new("ShaderNodeMath")
                    gt.operation = "GREATER_THAN"
                    gt.inputs[1].default_value = 0.5
                    nt.links.new(tn.outputs["Alpha"], gt.inputs[0])
                    nt.links.new(gt.outputs[0], b.inputs["Alpha"])
        if spec.get("emissive") is not None:
            b.inputs["Emission Color"].default_value = tuple(spec["emissive"])[:3] + (1.0,)
            b.inputs["Emission Strength"].default_value = spec.get("emissive_strength", 1.0) * emission_scale
        nt.links.new(b.outputs[0], out.inputs["Surface"])
    elif sh == "glass":
        gl = nt.nodes.new("ShaderNodeBsdfGlossy")
        gl.inputs["Color"].default_value = color + (1.0,)
        gl.inputs["Roughness"].default_value = spec.get("roughness", 0.05)
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        tr.inputs["Color"].default_value = tuple(0.75 + 0.25 * c for c in color) + (1.0,)
        mx = nt.nodes.new("ShaderNodeMixShader")
        mx.inputs["Fac"].default_value = spec.get("opacity", 0.2)
        nt.links.new(tr.outputs[0], mx.inputs[1])
        nt.links.new(gl.outputs[0], mx.inputs[2])
        nt.links.new(mx.outputs[0], out.inputs["Surface"])
        try:
            m.surface_render_method = "BLENDED"
        except Exception:
            pass
    elif sh == "emissive":
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Strength"].default_value = spec.get("emissive_strength", 1.0) * emission_scale
        em.inputs["Color"].default_value = color + (1.0,)
        tn = tex_node()
        if tn is not None:
            nt.links.new(mul_color(tn.outputs["Color"]), em.inputs["Color"])
        nt.links.new(em.outputs[0], out.inputs["Surface"])
    m.diffuse_color = color + (1.0,)
    return m


class MatLib:
    """Collects material specs for one generator and creates matching Blender materials."""

    def __init__(self, generator, emission_scale=1.0):
        self.generator = generator
        self.specs = {}
        self.emission_scale = emission_scale

    def _add(self, name, spec):
        assert name.startswith("MI_"), name
        clean = {}
        for k, v in spec.items():
            if v is None:
                continue
            if isinstance(v, (tuple, list)):
                v = rnd_list(v)
            elif isinstance(v, float):
                v = round(v, 4)
            clean[k] = v
        self.specs[name] = clean
        return build_preview_material(name, clean, self.emission_scale)

    def opaque(self, name, color, roughness=0.5, metallic=0.0, specular=0.5, texture=None, tiling=None,
               emissive=None, emissive_strength=None):
        return self._add(name, dict(shader="opaque", texture=texture, color=color, roughness=roughness,
                                    metallic=metallic, specular=specular, tiling=tiling, emissive=emissive,
                                    emissive_strength=emissive_strength))

    def vertexcolor(self, name, color=(1, 1, 1), roughness=0.6, metallic=0.0, specular=0.5):
        return self._add(name, dict(shader="vertexcolor", color=color, roughness=roughness, metallic=metallic,
                                    specular=specular))

    def glass(self, name, color, opacity, roughness):
        return self._add(name, dict(shader="glass", color=color, opacity=opacity, roughness=roughness))

    def emissive(self, name, color=(1, 1, 1), emissive_strength=1.0, texture=None, pan_u=None, pan_v=None,
                 tiling=None):
        return self._add(name, dict(shader="emissive", texture=texture, color=color,
                                    emissive_strength=emissive_strength, pan_u=pan_u, pan_v=pan_v, tiling=tiling))

    def masked(self, name, texture, color=(1, 1, 1), roughness=0.6, metallic=0.0, specular=0.5):
        return self._add(name, dict(shader="masked", texture=texture, color=color, roughness=roughness,
                                    metallic=metallic, specular=specular))

    def custom(self, name, shader, **kw):
        """Any other shader type from the material contract (ice, screen, goallight, team, skin, number...)."""
        d = dict(shader=shader)
        d.update(kw)
        return self._add(name, d)

    def crowd(self, name="MI_Crowd"):
        return self._add(name, dict(shader="crowd"))

    def write(self):
        path = os.path.join(MAT_DIR, self.generator + ".json")
        with open(path, "w") as f:
            json.dump(self.specs, f, indent=2, sort_keys=True)
        print("WROTE", path)
        return path


def write_manifest(generator, data):
    path = os.path.join(MANIFEST_DIR, generator + ".json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print("WROTE", path)
    return path


def load_material_specs():
    specs = {}
    if os.path.isdir(MAT_DIR):
        for fn in sorted(os.listdir(MAT_DIR)):
            if fn.endswith(".json"):
                with open(os.path.join(MAT_DIR, fn)) as f:
                    try:
                        specs.update(json.load(f))
                    except Exception as ex:
                        print("WARN bad material json", fn, ex)
    return specs


# ---------------------------------------------------------------------------
# Preview scene helpers (lit renders of exported assets)
# ---------------------------------------------------------------------------
def preview_scene(res=(1600, 900), samples=48, view="AgX", exposure=0.0, world=(0.02, 0.02, 0.025),
                  world_strength=1.0, transparent=False):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = transparent
    sc.render.filter_size = 1.5
    try:
        sc.eevee.taa_render_samples = samples
        sc.eevee.use_shadows = True
        sc.eevee.use_raytracing = True
        sc.eevee.ray_tracing_options.resolution_scale = "1"
    except Exception:
        pass
    try:
        sc.eevee.shadow_pool_size = "2048"
    except Exception:
        pass
    try:
        sc.view_settings.view_transform = view
    except Exception:
        sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    if view == "AgX":
        for lk in ("AgX - Punchy", "Punchy"):
            try:
                sc.view_settings.look = lk
                break
            except Exception:
                pass
    sc.view_settings.exposure = exposure
    if sc.world is None:
        sc.world = bpy.data.worlds.new("PreviewWorld")
    sc.world.use_nodes = True
    bg = sc.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = tuple(world) + (1.0,)
        bg.inputs["Strength"].default_value = world_strength
    s = sc.render.image_settings
    s.file_format = "PNG"
    s.color_mode = "RGBA" if transparent else "RGB"
    s.color_depth = "8"
    sc.render.use_compositing = False
    return sc


def look_cam(name, loc, target, lens=35.0, sensor=36.0):
    return_cam = hc.add_camera(name, loc, target, lens=lens)
    return_cam.data.sensor_width = sensor
    return_cam.data.clip_start = 0.05
    return_cam.data.clip_end = 500.0
    return return_cam


def area_light(name, loc, target, energy, size=2.0, size_y=None, color=(1, 1, 1), spread=None, shadow=True):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = energy
    ld.color = color
    try:
        ld.use_shadow = shadow
    except Exception:
        pass
    if size_y is not None:
        ld.shape = "RECTANGLE"
        ld.size = size
        ld.size_y = size_y
    else:
        ld.size = size
    if spread is not None:
        ld.spread = spread
    o = bpy.data.objects.new(name, ld)
    o.location = loc
    o.rotation_euler = hc.look_at_rotation(loc, target)
    bpy.context.scene.collection.objects.link(o)
    return o


def spot_light(name, loc, target, energy, angle_deg=40.0, blend=0.3, color=(1, 1, 1), radius=0.2):
    ld = bpy.data.lights.new(name, "SPOT")
    ld.energy = energy
    ld.color = color
    ld.spot_size = math.radians(angle_deg)
    ld.spot_blend = blend
    ld.shadow_soft_size = radius
    o = bpy.data.objects.new(name, ld)
    o.location = loc
    o.rotation_euler = hc.look_at_rotation(loc, target)
    bpy.context.scene.collection.objects.link(o)
    return o


def render_preview(path):
    sc = bpy.context.scene
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("RENDERED", path)
    return path


def report_mesh(o, label=None):
    n = tri_count(o)
    print("MESH %-28s tris=%7d  mats=%s" % (label or o.name, n, [m.name for m in o.data.materials]))
    return n


# ---------------------------------------------------------------------------
# Solid-modelling helpers (bmesh based, one object per material, join afterwards)
# ---------------------------------------------------------------------------
def box_obj(name, lo, hi, mat=None, bevel=0.0, segments=2, collection=None):
    """Axis-aligned box from lo to hi with optional bevelled edges."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    sx, sy, sz = (hi[0] - lo[0]), (hi[1] - lo[1]), (hi[2] - lo[2])
    for v in bm.verts:
        v.co.x = lo[0] + (v.co.x + 0.5) * sx
        v.co.y = lo[1] + (v.co.y + 0.5) * sy
        v.co.z = lo[2] + (v.co.z + 0.5) * sz
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(bevel, 0.49 * min(sx, sy, sz)), segments=segments,
                        profile=0.5, affect="EDGES", clamp_overlap=True)
    return obj_from_bm(name, bm, mat, collection)


def prism_obj(name, pts2d, axis, lo, hi, mat=None, collection=None):
    """Extrude a 2D profile (in the plane perpendicular to axis) from lo to hi along axis ('X','Y','Z').

    For axis 'Y' the profile coordinates are (x, z); for 'X' they are (y, z); for 'Z' they are (x, y).
    """
    pts2d = dedupe(pts2d)
    if poly_area(pts2d) < 0:
        pts2d = pts2d[::-1]

    def P(a, b, t):
        if axis == "Y":
            return (a, t, b)
        if axis == "X":
            return (t, a, b)
        return (a, b, t)
    bm = bmesh.new()
    n = len(pts2d)
    bot = [bm.verts.new(P(p[0], p[1], lo)) for p in pts2d]
    top = [bm.verts.new(P(p[0], p[1], hi)) for p in pts2d]
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    from mathutils import geometry
    tris = geometry.tessellate_polygon([[Vector((p[0], p[1], 0.0)) for p in pts2d]])
    for (i, j, k) in tris:
        try:
            bm.faces.new((top[i], top[j], top[k]))
        except ValueError:
            pass
        try:
            bm.faces.new((bot[k], bot[j], bot[i]))
        except ValueError:
            pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return obj_from_bm(name, bm, mat, collection)


def oriented_box_obj(name, p0, p1, w, h, mat=None, up=(0, 0, 1), collection=None, bevel=0.0):
    """Box of cross-section w x h running from p0 to p1 (h measured along 'up' projected)."""
    p0 = Vector(p0)
    p1 = Vector(p1)
    ax = (p1 - p0)
    L = ax.length
    ax.normalize()
    upv = Vector(up)
    side = ax.cross(upv)
    if side.length < 1e-6:
        side = ax.cross(Vector((1, 0, 0)))
    side.normalize()
    upv = side.cross(ax).normalized()
    o = box_obj(name, (0, -w / 2, -h / 2), (L, w / 2, h / 2), mat, bevel=bevel, collection=collection)
    from mathutils import Matrix
    M = Matrix(((ax.x, side.x, upv.x, p0.x), (ax.y, side.y, upv.y, p0.y), (ax.z, side.z, upv.z, p0.z),
                (0, 0, 0, 1)))
    o.data.transform(M)
    o.data.update()
    return o


def tube_obj(name, polylines, radius, sides=6, mat=None, closed=False, smooth=True, collection=None, caps=True):
    """Swept polygonal tubes along 3D polylines (parallel-transport frames)."""
    bm = bmesh.new()
    for pl in polylines:
        P = [Vector(p) for p in pl]
        n = len(P)
        if n < 2:
            continue
        T = []
        for i in range(n):
            if closed:
                a, b = P[(i - 1) % n], P[(i + 1) % n]
            else:
                a, b = P[max(i - 1, 0)], P[min(i + 1, n - 1)]
            t = (b - a)
            T.append(t.normalized() if t.length > 1e-9 else Vector((0, 0, 1)))
        ref = Vector((0, 0, 1)) if abs(T[0].z) < 0.9 else Vector((1, 0, 0))
        N = (ref - T[0] * ref.dot(T[0])).normalized()
        rings = []
        for i in range(n):
            if i > 0:
                N = (N - T[i] * N.dot(T[i]))
                if N.length < 1e-9:
                    N = (ref - T[i] * ref.dot(T[i]))
                N.normalize()
            B = T[i].cross(N)
            ring = []
            for k in range(sides):
                a = 2 * math.pi * k / sides
                ring.append(bm.verts.new(P[i] + (N * math.cos(a) + B * math.sin(a)) * radius))
            rings.append(ring)
        segs = n if closed else n - 1
        for i in range(segs):
            r0, r1 = rings[i], rings[(i + 1) % n]
            for k in range(sides):
                k1 = (k + 1) % sides
                f = bm.faces.new((r0[k], r0[k1], r1[k1], r1[k]))
                f.smooth = smooth
        if caps and not closed:
            f0 = bm.faces.new(list(reversed(rings[0])))
            f1 = bm.faces.new(rings[-1])
            f0.smooth = f1.smooth = False
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return obj_from_bm(name, bm, mat, collection)


def torus_obj(name, center, R, r, seg=48, sides=10, mat=None, collection=None):
    pts = [(center[0] + R * math.cos(2 * math.pi * i / seg), center[1] + R * math.sin(2 * math.pi * i / seg),
            center[2]) for i in range(seg)]
    return tube_obj(name, [pts], r, sides, mat, closed=True, collection=collection)


def box_uv(o, scale=1.0):
    """World-space box projection into UV0 (1 UV unit = 1/scale m). Overwrites the active UV map."""
    me = o.data
    if len(me.polygons) == 0:
        return o
    uvl = me.uv_layers.active or me.uv_layers.new(name="UVMap")
    nv, nl, nf = len(me.vertices), len(me.loops), len(me.polygons)
    co = np.empty(nv * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    M = np.array(o.matrix_basis, np.float32)
    co = co @ M[:3, :3].T + M[:3, 3]
    vi = np.empty(nl, np.int32)
    me.loops.foreach_get("vertex_index", vi)
    pn = np.empty(nf * 3, np.float32)
    me.polygons.foreach_get("normal", pn)
    pn = np.abs(pn.reshape(-1, 3))
    ls = np.empty(nf, np.int32)
    me.polygons.foreach_get("loop_start", ls)
    lt = np.empty(nf, np.int32)
    me.polygons.foreach_get("loop_total", lt)
    face_of_loop = np.zeros(nl, np.int32)
    for f in range(nf):
        face_of_loop[ls[f]:ls[f] + lt[f]] = f
    n = pn[face_of_loop]
    p = co[vi]
    ax = np.argmax(n, axis=1)
    u = np.where(ax == 0, p[:, 1], p[:, 0])
    v = np.where(ax == 2, p[:, 1], p[:, 2])
    uvl.data.foreach_set("uv", (np.stack([u, v], 1) * scale).astype(np.float32).ravel())
    return o


def join_objs(objs, name, uv_scale=1.0):
    """Join objects (materials merged); parts without a UV map get a box projection first."""
    objs = [o for o in objs if o is not None]
    for o in objs:
        if o.type == "MESH" and not o.data.uv_layers:
            box_uv(o, uv_scale)
        elif o.type == "MESH" and o.data.uv_layers and o.data.uv_layers[0].name != "UVMap":
            o.data.uv_layers[0].name = "UVMap"
    out = hc.join(objs, name)
    return out


def translate_mesh(o, d):
    from mathutils import Matrix
    bake_obj(o)
    o.data.transform(Matrix.Translation(Vector(d)))
    o.data.update()
    return o


def mesh_world_bounds(o):
    lo, hi = mesh_bounds(o)
    return [round(v, 4) for v in lo], [round(v, 4) for v in hi]
