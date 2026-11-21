"""ICE RIOT rink: ice markings texture, ice slab, boards + ads, glass + stanchions, nets, goal light, puck.

    blender -b --factory-startup --python-exit-code 1 -P Blender/gen_rink.py [-- notex]

Outputs (Art/Export): Textures/T_IceMarkings.png (4096x2048), T_Netting.png, T_PuckTop.png,
Meshes/SM_Ice.fbx, SM_Boards.fbx, SM_Glass.fbx, SM_Net.fbx, SM_GoalLight.fbx, SM_Puck.fbx,
Materials/rink.json, Manifests/rink.json, Previews/rink_*.png, Blend/rink.blend.
All static mesh pivots are the Blender world origin (the net / goal light are modelled at the +X end).
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import bmesh  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

import ir_common as hc  # noqa: E402
import ir_env as eh  # noqa: E402
import ir_draw as dr  # noqa: E402
from ir_draw import Canvas  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

HX, HY, CR = 23.0, 10.5, 6.5          # boards inner face half sizes + corner radius
BOARD_H, BOARD_T = 1.07, 0.15
KICK_H = 0.22
GLASS_TOP = 2.45
GOAL_X = 19.5
BLUE_X = 6.0
RED = "#C8102E"
BLUE = "#1E4FC2"
ICE_BASE = "#EEF4F8"
CREASE = "#8DCDF5"

# ---------------------------------------------------------------------------
# Rounded-rectangle perimeter (offset d outward from the boards inner face)
# ---------------------------------------------------------------------------


def perimeter(d=0.0, step=0.25, n_arc=None):
    """Clockwise (seen from above) closed polyline around the rink at outward offset d.
    Returns list of (x, y, nx, ny, s) with s = clockwise arc length starting at the far-side center."""
    r = CR + d
    ax, ay = HX - CR, HY - CR
    pts = []
    # start at (0, HY+d) heading +X (clockwise from above: +Y side moving toward +X)
    segs = [
        ("line", (0.0, ay + r), (ax, ay + r)),
        ("arc", (ax, ay), math.pi / 2, 0.0),
        ("line", (ax + r, ay), (ax + r, -ay)),
        ("arc", (ax, -ay), 0.0, -math.pi / 2),
        ("line", (ax, -ay - r), (-ax, -ay - r)),
        ("arc", (-ax, -ay), -math.pi / 2, -math.pi),
        ("line", (-ax - r, -ay), (-ax - r, ay)),
        ("arc", (-ax, ay), math.pi, math.pi / 2),
        ("line", (-ax, ay + r), (0.0, ay + r)),
    ]
    s = 0.0
    for sg in segs:
        if sg[0] == "line":
            a, b = Vector(sg[1]), Vector(sg[2])
            L = (b - a).length
            n = max(1, int(math.ceil(L / step)))
            t = (b - a).normalized()
            nrm = Vector((-t.y, t.x))      # clockwise travel: outward = left-hand side
            for i in range(n):
                p = a + (b - a) * (i / n)
                pts.append((p.x, p.y, nrm.x, nrm.y, s + L * i / n))
            s += L
        else:
            c, a0, a1 = Vector(sg[1]), sg[2], sg[3]
            L = abs(a1 - a0) * r
            n = n_arc or max(8, int(math.ceil(L / step)))
            for i in range(n):
                a = a0 + (a1 - a0) * i / n
                pts.append((c.x + r * math.cos(a), c.y + r * math.sin(a), math.cos(a), math.sin(a), s + L * i / n))
            s += L
    return pts, s


def point_at(d, s_query):
    """Position + outward normal at clockwise arc length s (exact)."""
    r = CR + d
    ax, ay = HX - CR, HY - CR
    La, Lb = 2 * ax, 2 * ay
    Larc = math.pi / 2 * r
    total = 2 * La + 2 * Lb + 4 * Larc
    s = s_query % total
    pieces = [("line", (0.0, ay + r), (1, 0), ax), ("arc", (ax, ay), math.pi / 2, -1),
              ("line", (ax + r, ay), (0, -1), Lb), ("arc", (ax, -ay), 0.0, -1),
              ("line", (ax, -ay - r), (-1, 0), La), ("arc", (-ax, -ay), -math.pi / 2, -1),
              ("line", (-ax - r, -ay), (0, 1), Lb), ("arc", (-ax, ay), math.pi, -1),
              ("line", (-ax, ay + r), (1, 0), ax)]
    for pc in pieces:
        L = pc[3] if pc[0] == "line" else Larc
        if s <= L + 1e-9:
            if pc[0] == "line":
                p0, t = pc[1], pc[2]
                x, y = p0[0] + t[0] * s, p0[1] + t[1] * s
                return (x, y), (-t[1], t[0])
            a = pc[2] - s / r
            return (pc[1][0] + r * math.cos(a), pc[1][1] + r * math.sin(a)), (math.cos(a), math.sin(a))
        s -= L
    return point_at(d, 0.0)


def perim_total(d=0.0):
    r = CR + d
    return 4 * (HX - CR) + 4 * (HY - CR) + 2 * math.pi * r


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------
M = eh.MatLib("rink")


def make_materials():
    mats = {}
    mats["ice"] = M.custom("MI_Ice", "ice", texture="T_IceMarkings", color=[1, 1, 1], roughness=0.07, wear=0.0)
    mats["board"] = M.opaque("MI_Boards", eh.lin("#F7F8F6"), roughness=0.35, specular=0.5)
    mats["kick"] = M.opaque("MI_BoardKick", eh.lin("#F5C518"), roughness=0.4)
    mats["rail"] = M.opaque("MI_BoardRail", eh.lin("#12264A"), roughness=0.3)
    mats["outer"] = M.opaque("MI_BoardOuter", eh.lin("#101C33"), roughness=0.6)
    mats["ads"] = M.opaque("MI_BoardAds", (1, 1, 1), roughness=0.35, texture="T_BoardAds")
    mats["glass"] = M.glass("MI_Glass", eh.lin("#DDEFFF"), opacity=0.16, roughness=0.04)
    mats["glass_near"] = M.glass("MI_GlassNear", eh.lin("#E6F4FF"), opacity=0.05, roughness=0.03)
    mats["stanchion"] = M.opaque("MI_Stanchion", eh.lin("#C9CED6"), roughness=0.3, metallic=1.0)
    mats["post"] = M.opaque("MI_GoalPost", eh.lin("#D0141E"), roughness=0.25, metallic=0.0)
    mats["netting"] = M.custom("MI_Netting", "masked", texture="T_Netting", color=[1, 1, 1], roughness=0.7,
                               tiling=[1, 1])
    mats["skirt"] = M.opaque("MI_NetSkirt", eh.lin("#F2F2F2"), roughness=0.8)
    mats["goallight"] = M.custom("MI_GoalLight", "goallight", color=eh.lin("#FF1A10"), roughness=0.2,
                                 emissive_strength=60.0, on=0.0)
    mats["glbase"] = M.opaque("MI_GoalLightBase", eh.lin("#1A1C22"), roughness=0.45, metallic=0.6)
    mats["puck"] = M.opaque("MI_Puck", eh.lin("#121214"), roughness=0.55)
    mats["pucktop"] = M.opaque("MI_PuckTop", (1, 1, 1), roughness=0.5, texture="T_PuckTop")
    return mats


# ---------------------------------------------------------------------------
# Textures
# ---------------------------------------------------------------------------
def ice_texture():
    W = 4096
    Hs = int(round(W * (2 * HY) / (2 * HX)))   # square pixels while drawing, resampled to 2048 rows
    cv = Canvas(W, Hs, (-HX, -HY, HX, HY))
    X, Y = cv.X, cv.Y
    # base ice with very subtle cloudiness (the shader adds gloss / scratches)
    noise = eh.LatticeNoise(7, (256, 256))
    n = eh.fbm(noise, X * 0.35, Y * 0.35, 4)
    base = np.array(dr.col(ICE_BASE), np.float32)
    rgb = base[None, None, :] * (1.0 + 0.018 * n[..., None]) - 0.012 * np.clip(eh.fbm(noise, X * 2.2, Y * 2.2, 3), 0, 1)[..., None]
    cv.rgb[:] = rgb
    cv.a[:] = 1.0
    # rounded-rect mask (outside the boards stays plain)
    def rr_sd(x, y):
        qx = np.abs(x) - (HX - CR)
        qy = np.abs(y) - (HY - CR)
        return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - CR
    inside = rr_sd(X, Y)

    def lim(sd):
        return np.maximum(sd, inside)

    # goal-line trapezoids behind the nets
    for sx in (-1, 1):
        trap = cv.poly([(sx * GOAL_X, -3.35), (sx * HX * 1.01, -4.3), (sx * HX * 1.01, 4.3), (sx * GOAL_X, 3.35)])
        cv.fill(lim(np.abs(trap) - 0.025), RED)
    # goal creases (fill + outline), opening toward center ice
    for sx in (-1, 1):
        c = cv.circle(sx * GOAL_X, 0.0, 1.8)
        half = (X - sx * GOAL_X) * sx            # >0 behind the goal line
        crease = np.maximum(c, half)
        cv.fill(crease, CREASE)
        cv.fill(np.maximum(np.abs(crease + 0.025) - 0.025, half - 0.0), RED)
        # small L marks inside the crease
        for sy in (-1, 1):
            cv.fill(cv.box(sx * (GOAL_X - 1.22), sy * 1.22, 0.025, 0.12), RED)
    # goal lines (span to the boards)
    for sx in (-1, 1):
        cv.fill(lim(np.abs(X - sx * GOAL_X) - 0.025), RED)
    # blue lines
    for sx in (-1, 1):
        cv.fill(lim(np.abs(X - sx * BLUE_X) - 0.15), BLUE)
    # center red line with the classic dashed white inset
    cv.fill(lim(np.abs(X) - 0.15), RED)
    dash = np.maximum(np.abs(X) - 0.035, np.abs(((Y + 0.25) % 1.0) - 0.5) - 0.25)
    cv.fill(lim(np.maximum(dash, cv.circle(0, 0, 4.0) * -1)), "#FFFFFF", alpha=0.85)
    # end-zone face-off circles
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = sx * 14.5, sy * 5.5
            cv.fill(cv.ring(cx, cy, 4.0 - 0.025, 0.05), RED)
            # hash marks on the circle (outside, top and bottom)
            for hx in (-0.9, 0.9):
                for hy in (-1, 1):
                    y_edge = cy + hy * math.sqrt(4.0 ** 2 - hx ** 2)
                    cv.fill(cv.box(cx + hx, y_edge + hy * 0.3, 0.025, 0.3), RED)
            # L marks around the dot
            for lx in (-1, 1):
                for ly in (-1, 1):
                    x0 = cx + lx * 0.45
                    y0 = cy + ly * 0.25
                    cv.fill(cv.box(x0 + lx * 0.6, y0, 0.6, 0.025), RED)
                    cv.fill(cv.box(x0, y0 + ly * 0.45, 0.025, 0.45), RED)
            cv.fill(cv.circle(cx, cy, 0.30), RED)
            cv.fill(np.maximum(cv.circle(cx, cy, 0.24), np.abs(Y - cy) - 0.08), "#FFFFFF")
    # neutral zone dots
    for sx in (-1, 1):
        for sy in (-1, 1):
            cv.fill(cv.circle(sx * 4.5, sy * 5.5, 0.30), RED)
    # center circle + dot
    cv.fill(cv.ring(0, 0, 4.0 - 0.025, 0.05), BLUE)
    cv.fill(cv.circle(0, 0, 0.15), BLUE)
    # center ice logo (reads from the -Y camera side)
    logo_p = os.path.join(hc.TEX_DIR, "T_LogoIceRiot.png")
    if os.path.exists(logo_p):
        logo = eh.load_png(logo_p)
        cv.stamp(logo, (0.0, 0.0), 7.2, alpha=0.92)
    # neutral zone sponsor decals (from the board ad atlas)
    ads_p = os.path.join(hc.TEX_DIR, "T_BoardAds.png")
    if os.path.exists(ads_p):
        ads = eh.load_png(ads_p)
        cells = [(0, 0), (1, 4)]
        for (col_, row), sx in zip(cells, (-1, 1)):
            h0 = 2048 - (row + 1) * 256
            cell = ads[h0:h0 + 256, col_ * 1024:(col_ + 1) * 1024].copy()
            cell[..., 3] = 1.0
            cv.stamp(cell, (sx * 10.2, 0.0), 4.6, rot=0.0, alpha=0.55)
    # faint scuff / snow near the boards
    edge = np.clip(1.0 - (-inside) / 1.2, 0, 1) * (inside < 0)
    cv.put(edge * 0.25 * np.clip(0.5 + 0.5 * eh.fbm(noise, X * 1.5, Y * 1.5, 3), 0, 1), "#FFFFFF")
    img = cv.rgba()
    img[..., 3] = 1.0
    # resample rows to 2048 (linear)
    H2 = 2048
    src = (np.arange(H2) + 0.5) * (Hs / H2) - 0.5
    i0 = np.clip(np.floor(src).astype(int), 0, Hs - 1)
    i1 = np.clip(i0 + 1, 0, Hs - 1)
    f = (src - i0)[:, None, None].astype(np.float32)
    out = img[i0] * (1 - f) + img[i1] * f
    eh.save_png(out, os.path.join(hc.TEX_DIR, "T_IceMarkings.png"))
    return out


def scratch_texture():
    """Tileable grey scratch/skate-mark detail for the ice shader (R = scratch amount)."""
    S = 512
    rng = np.random.default_rng(3)
    img = np.zeros((S, S), np.float32)
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    for i in range(260):
        x0, y0 = rng.uniform(0, S, 2)
        ang = rng.normal(0.0, 0.5) + (0 if rng.random() < 0.7 else math.pi / 2)
        L = rng.uniform(20, 160)
        w = rng.uniform(0.4, 1.4)
        dx, dy = math.cos(ang), math.sin(ang)
        # wrap-around distance for tileability
        px = (xx - x0 + S / 2) % S - S / 2
        py = (yy - y0 + S / 2) % S - S / 2
        t = np.clip(px * dx + py * dy, 0, L)
        d = np.hypot(px - t * dx, py - t * dy)
        img = np.maximum(img, np.clip(1.0 - d / w, 0, 1) * rng.uniform(0.25, 0.9))
    noise = eh.LatticeNoise(11, (64, 64))
    img = np.clip(img + 0.15 * (eh.fbm(noise, xx / 32.0, yy / 32.0, 4) * 0.5 + 0.5), 0, 1)
    eh.save_png(np.stack([img, img, img], -1), os.path.join(hc.TEX_DIR, "T_IceScratches.png"))


def netting_texture():
    S = 256
    cv = Canvas(S, S, (0, 0, 1, 1))
    k = 5   # holes per tile
    gx = np.abs(((cv.X * k) % 1.0) - 0.5)
    gy = np.abs(((cv.Y * k) % 1.0) - 0.5)
    d = np.minimum(0.5 - gx, 0.5 - gy) / k   # distance to nearest strand
    cv.fill(d - 0.012, "#FFFFFF")
    # knots
    for i in range(k + 1):
        for j in range(k + 1):
            cv.fill(cv.circle(i / k, j / k, 0.018), "#F4F4F4")
    cv.save(os.path.join(hc.TEX_DIR, "T_Netting.png"))


def puck_texture():
    S = 512
    cv = Canvas(S, S, (-1, -1, 1, 1), bg="#121214")
    cv.fill(cv.ring(0, 0, 0.90, 0.025), "#3A3A40")
    logo_p = os.path.join(hc.TEX_DIR, "T_LogoIceRiot.png")
    if os.path.exists(logo_p):
        logo = eh.load_png(logo_p)
        # desaturated silver print
        g = logo.copy()
        lum = g[..., 0] * 0.3 + g[..., 1] * 0.59 + g[..., 2] * 0.11
        g[..., 0] = g[..., 1] = g[..., 2] = 0.35 + 0.6 * lum
        cv.stamp(g, (0, 0.0), 1.6)
    cv.save(os.path.join(hc.TEX_DIR, "T_PuckTop.png"), opaque=True)


# ---------------------------------------------------------------------------
# Meshes
# ---------------------------------------------------------------------------
def build_ice(mats):
    pts, _ = perimeter(0.0, step=0.5, n_arc=24)
    poly = [(p[0], p[1]) for p in pts][::-1]  # CCW
    bm = bmesh.new()
    eh.bm_add_fill(bm, poly, 0.0)
    # thin skirt down to -0.06 so no gap shows under the boards
    n = len(poly)
    top = [bm.verts.new((x, y, 0.0)) for x, y in poly]
    bot = [bm.verts.new((x, y, -0.06)) for x, y in poly]
    for i in range(n):
        j = (i + 1) % n
        try:
            bm.faces.new((top[i], bot[i], bot[j], top[j]))
        except ValueError:
            pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    o = eh.obj_from_bm("SM_Ice", bm, mats["ice"])
    me = o.data
    uvl = me.uv_layers.new(name="UVMap")
    for poly_ in me.polygons:
        for li in poly_.loop_indices:
            v = me.vertices[me.loops[li].vertex_index].co
            uvl.data[li].uv = ((v.x + HX) / (2 * HX), (v.y + HY) / (2 * HY))
    return o


def sweep_profile(name, d_pts, profile, mats_list, step=0.25, n_arc=24, closed=True):
    """Sweep a 2D (outward offset, z) profile around the rink. profile = [(o, z, mat_index_of_segment_to_next)]."""
    pts, total = perimeter(0.0, step=step, n_arc=n_arc)
    mb = eh.MeshBuilder()
    rings = []
    for (x, y, nx, ny, s) in pts:
        rings.append([(x + nx * o, y + ny * o, z) for (o, z, _) in profile])
    N = len(rings)
    for i in range(N):
        a = rings[i]
        b = rings[(i + 1) % N]
        for k in range(len(profile) - 1):
            mi = profile[k][2]
            if mi is None:
                continue
            # profile is listed so that faces point outward from the swept solid
            mb.quad(a[k], b[k], b[k + 1], a[k + 1], mat=mi, smooth=profile[k][2] in (2,))
    o = mb.build(name, mats_list)
    eh.box_uv(o, 1.0)
    return o


def build_boards(mats):
    # material indices: 0 board, 1 kick, 2 rail, 3 outer, 4 ads
    mlist = [mats["board"], mats["kick"], mats["rail"], mats["outer"], mats["ads"]]
    rail = []
    for i in range(9):
        a = math.pi * i / 8
        rail.append((0.075 - 0.095 * math.cos(a), BOARD_H - 0.045 + 0.045 * math.sin(a), 2))
    profile = ([(0.0, -0.05, 1), (0.0, KICK_H, 0), (0.0, BOARD_H - 0.045, 2)] + rail[:-1] +
               [(0.17, BOARD_H - 0.045, 3), (BOARD_T, BOARD_H - 0.06, 3), (BOARD_T, -0.05, None)])
    # fix: segments go inner face up -> rail -> outer face down; normals must face away from the solid
    profile = [(o, z, m) for (o, z, m) in profile]
    boards = sweep_profile("Boards", 0.0, profile, mlist)
    # reverse faces if the sweep produced inward normals
    bm = bmesh.new()
    bm.from_mesh(boards.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(boards.data)
    bm.free()
    # sponsor panels (inner face, slightly proud), UV into the 2x8 atlas; u grows clockwise = viewer's right
    ad_z0, ad_z1 = 0.30, 0.94
    pitch = 2.62
    gap = 0.06
    total = perim_total(-0.003)
    npan = int(total // pitch)
    pitch = total / npan
    mb = eh.MeshBuilder()
    order = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    for k in range(npan):
        s0 = k * pitch + gap / 2
        s1 = (k + 1) * pitch - gap / 2
        cell = order[k % 16]
        col_, row = cell % 2, cell // 2
        u0, u1 = col_ * 0.5 + 0.002, col_ * 0.5 + 0.498
        vt = 1.0 - row * 0.125 - 0.002
        vb = vt - 0.121
        nseg = 6
        for j in range(nseg):
            sa = s0 + (s1 - s0) * j / nseg
            sb = s0 + (s1 - s0) * (j + 1) / nseg
            (xa, ya), (nxa, nya) = point_at(0.0, sa)
            (xb, yb), (nxb, nyb) = point_at(0.0, sb)
            o = -0.004
            A0 = (xa + nxa * o, ya + nya * o, ad_z0)
            B0 = (xb + nxb * o, yb + nyb * o, ad_z0)
            B1 = (xb + nxb * o, yb + nyb * o, ad_z1)
            A1 = (xa + nxa * o, ya + nya * o, ad_z1)
            ua = u0 + (u1 - u0) * j / nseg
            ub = u0 + (u1 - u0) * (j + 1) / nseg
            mb.quad(A0, A1, B1, B0, mat=0, uv=[(ua, vb), (ua, vt), (ub, vt), (ub, vb)])
    ads = mb.build("BoardAds", [mats["ads"]])
    out = eh.join_objs([boards, ads], "SM_Boards")
    return out


def build_glass(mats):
    pitch_target = 2.2
    total = perim_total(0.06)
    n = int(round(total / pitch_target))
    pitch = total / n
    mb = eh.MeshBuilder()
    st = eh.MeshBuilder()
    z0, z1 = BOARD_H - 0.01, GLASS_TOP
    for k in range(n):
        s0 = k * pitch
        s1 = (k + 1) * pitch
        sub = 4
        for j in range(sub):
            sa = s0 + (s1 - s0) * j / sub
            sb = s0 + (s1 - s0) * (j + 1) / sub
            (xa, ya), _ = point_at(0.06, sa)
            (xb, yb), _ = point_at(0.06, sb)
            near = (ya + yb) * 0.5 < -0.5 * HY
            mi = 1 if near else 0
            mb.quad((xa, ya, z0), (xb, yb, z0), (xb, yb, z1), (xa, ya, z1), mat=mi,
                    uv=[(sa / 2, 0), (sb / 2, 0), (sb / 2, 1), (sa / 2, 1)])
        # stanchion at s0
        (x, y), (nx, ny) = point_at(0.06, s0)
        tx, ty = ny, -nx
        c = Vector((x, y, (z0 + z1 + 0.04) * 0.5))
        st.oriented_box(c, (tx, ty, 0), (nx, ny, 0), (0, 0, 1), 0.025, 0.05, (z1 + 0.04 - z0) * 0.5, mat=0)
    glass = mb.build("Glass", [mats["glass"], mats["glass_near"]])
    stan = st.build("Stanchions", [mats["stanchion"]])
    eh.box_uv(stan, 1.0)
    return eh.join_objs([glass, stan], "SM_Glass")


def build_net(mats):
    """+X net: mouth on the goal line (x = 19.5) facing -X, depth 1.0 toward the end boards."""
    W2, H = 0.915, 1.22
    R = 0.03
    D = 1.0
    gx = GOAL_X
    parts = []
    # posts + crossbar
    frame = [[(gx + R, -W2, 0.0), (gx + R, -W2, H), (gx + R, W2, H), (gx + R, W2, 0.0)]]
    parts.append(eh.tube_obj("NetFrame", frame, R, sides=12, mat=mats["post"]))
    # base hoop (back, on the ice) - semi-ellipse from post to post
    base = []
    for i in range(25):
        a = -math.pi / 2 + math.pi * i / 24
        base.append((gx + R + D * math.cos(a) * 0.98, W2 * math.sin(a) * 1.0, 0.025))
    parts.append(eh.tube_obj("NetBase", [base], 0.025, sides=8, mat=mats["post"]))
    # top shelf frame: back from the crossbar 0.45 m
    top = []
    for i in range(17):
        a = -math.pi / 2 + math.pi * i / 16
        top.append((gx + R + 0.45 * math.cos(a), W2 * math.sin(a), H))
    parts.append(eh.tube_obj("NetTop", [top], 0.018, sides=8, mat=mats["post"]))
    # netting surfaces: top shelf (crossbar -> top hoop), back (top hoop -> base hoop), sides
    nb = eh.MeshBuilder()
    nu, nv = 24, 8

    def top_pt(a, t):   # a in [-pi/2, pi/2] along the hoop, t from front (0) to hoop (1)
        return Vector((gx + R + 0.45 * math.cos(a) * t, W2 * math.sin(a), H))

    def back_pt(a, t):  # t from top hoop (0) to base hoop (1), bulging slightly outward
        p0 = Vector((gx + R + 0.45 * math.cos(a), W2 * math.sin(a), H))
        p1 = Vector((gx + R + D * 0.98 * math.cos(a), W2 * math.sin(a), 0.02))
        p = p0.lerp(p1, t)
        bulge = math.sin(math.pi * t) * 0.10
        p.x += bulge * math.cos(a)
        p.y += bulge * math.sin(a) * 0.4
        return p

    def grid(fn, uscale, vscale):
        for i in range(nu):
            for j in range(nv):
                a0 = -math.pi / 2 + math.pi * i / nu
                a1 = -math.pi / 2 + math.pi * (i + 1) / nu
                t0, t1 = j / nv, (j + 1) / nv
                P = [fn(a0, t0), fn(a1, t0), fn(a1, t1), fn(a0, t1)]
                uv = [(a0 * uscale, t0 * vscale), (a1 * uscale, t0 * vscale), (a1 * uscale, t1 * vscale),
                      (a0 * uscale, t1 * vscale)]
                nb.quad(*[tuple(p) for p in P], mat=0, uv=uv)
    grid(top_pt, 3.2, 1.6)
    grid(back_pt, 3.2, 4.2)
    net = nb.build("Netting", [mats["netting"]])
    parts.append(net)
    # white skirt pad inside the base
    sk = []
    for i in range(25):
        a = -math.pi / 2 + math.pi * i / 24
        sk.append((gx + R + D * 0.96 * math.cos(a), W2 * 0.98 * math.sin(a), 0.0))
    skb = eh.MeshBuilder()
    for i in range(24):
        a, b = sk[i], sk[i + 1]
        skb.quad((a[0], a[1], 0.0), (b[0], b[1], 0.0), (b[0], b[1], 0.16), (a[0], a[1], 0.16), mat=0)
    skirt = skb.build("Skirt", [mats["skirt"]])
    eh.box_uv(skirt)
    parts.append(skirt)
    return eh.join_objs(parts, "SM_Net")


def build_goal_light(mats):
    """Red dome on a small housing, on top of the glass behind the +X net."""
    x, z = HX + 0.06, GLASS_TOP
    base = eh.box_obj("GLBase", (x - 0.16, -0.16, z), (x + 0.16, 0.16, z + 0.12), mats["glbase"], bevel=0.02)
    cyl = hc.cylinder("GLRing", 0.13, 0.05, location=(x, 0, z + 0.145), verts=24, mat=mats["glbase"])
    dome = hc.sphere("GLDome", 0.12, location=(x, 0, z + 0.17), segments=24, rings=12, mat=mats["goallight"])
    # drop the lower half of the dome
    bm = bmesh.new()
    bm.from_mesh(dome.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -0.001], context="VERTS")
    bm.to_mesh(dome.data)
    bm.free()
    dome.data.transform(__import__("mathutils").Matrix.Scale(1.25, 4, (0, 0, 1)))
    cage = []
    for i in range(4):
        a = math.pi * i / 4
        cage.append([(x + 0.125 * math.cos(a), 0.125 * math.sin(a), z + 0.17),
                     (x, 0, z + 0.17 + 0.155),
                     (x - 0.125 * math.cos(a), -0.125 * math.sin(a), z + 0.17)])
    cg = eh.tube_obj("GLCage", cage, 0.006, sides=6, mat=mats["glbase"])
    for o in (cyl, dome):
        eh.bake_obj(o)
    return eh.join_objs([base, cyl, dome, cg], "SM_GoalLight")


def build_puck(mats):
    r, h = 0.038, 0.0254
    n = 64
    bm = bmesh.new()
    rings = []
    zs = [-h / 2, -h / 2 + 0.002, -0.0045, 0.0045, h / 2 - 0.002, h / 2]
    for k, z in enumerate(zs):
        ring = []
        for i in range(n):
            a = 2 * math.pi * i / n
            rr = r - (0.0012 if k in (0, 5) else 0.0)
            if k in (2, 3) or True:
                pass
            # knurled band between the bevels
            if 0 < k < 5 and k not in (1, 4):
                rr = r - (0.0006 if i % 2 else 0.0)
            ring.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), z)))
        rings.append(ring)
    for k in range(len(rings) - 1):
        for i in range(n):
            j = (i + 1) % n
            f = bm.faces.new((rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]))
            f.material_index = 0
    cb = bm.verts.new((0, 0, -h / 2))
    ct = bm.verts.new((0, 0, h / 2))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((rings[0][j], rings[0][i], cb)).material_index = 0
        bm.faces.new((rings[-1][i], rings[-1][j], ct)).material_index = 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    o = eh.obj_from_bm("SM_Puck", bm)
    o.data.materials.append(mats["puck"])
    o.data.materials.append(mats["pucktop"])
    uvl = o.data.uv_layers.new(name="UVMap")
    for p in o.data.polygons:
        for li in p.loop_indices:
            v = o.data.vertices[o.data.loops[li].vertex_index].co
            uvl.data[li].uv = (0.5 + v.x / (2 * r), 0.5 + v.y / (2 * r))
    hc.shade(o, smooth=True, angle=35)
    return o


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------
def preview(objs):
    eh.preview_scene(res=(1600, 900), samples=32, view="AgX", world=(0.05, 0.055, 0.07), world_strength=1.0)
    for i, x in enumerate((-15, 0, 15)):
        eh.area_light("Key%d" % i, (x, -4, 16), (x, 0, 0), 9000, size=8.0)
    eh.area_light("Fill", (0, -25, 10), (0, 0, 0), 4000, size=10.0)
    cam = eh.look_cam("Cam", (0, -27, 13), (0, 1.5, 0), lens=30)
    eh.render_preview(os.path.join(hc.PREVIEW_DIR, "rink_gamecam.png"))
    cam.location = (14.0, -6.5, 3.2)
    cam.rotation_euler = hc.look_at_rotation(cam.location, (19.8, 0.0, 0.6))
    cam.data.lens = 35
    eh.render_preview(os.path.join(hc.PREVIEW_DIR, "rink_net.png"))
    cam.location = (0.0, 6.0, 1.6)
    cam.rotation_euler = hc.look_at_rotation(cam.location, (0.0, 12.0, 0.8))
    cam.data.lens = 24
    eh.render_preview(os.path.join(hc.PREVIEW_DIR, "rink_boards.png"))
    cam.location = (0.0, -0.18, 0.12)
    cam.rotation_euler = hc.look_at_rotation(cam.location, (0.0, 0.0, 0.0))
    cam.data.lens = 50
    for o in bpy.context.scene.objects:
        if o.type == "MESH" and o.name != "SM_Puck":
            o.hide_render = True
    bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y = 600, 400
    eh.render_preview(os.path.join(hc.PREVIEW_DIR, "rink_puck.png"))


def main():
    hc.reset_scene()
    if "notex" not in ARGS:
        ice_texture()
        scratch_texture()
        netting_texture()
        puck_texture()
    hc.reset_scene()
    mats = make_materials()
    M.write()
    ice = build_ice(mats)
    boards = build_boards(mats)
    glass = build_glass(mats)
    net = build_net(mats)
    gl = build_goal_light(mats)
    puck = build_puck(mats)
    stats = {}
    for o in (ice, boards, glass, net, gl, puck):
        eh.bake_obj(o)
        stats[o.name] = eh.report_mesh(o)
        hc.export_static_fbx([o], o.name + ".fbx")
    eh.write_manifest("rink", {"tris": stats, "goal_x": GOAL_X, "rink_half": [HX, HY], "corner_r": CR})
    hc.save_blend("rink.blend")
    # mirrored net/light just for the preview
    for src in (net, gl):
        cp = src.copy()
        cp.data = src.data.copy()
        cp.scale = (-1, 1, 1)
        bpy.context.scene.collection.objects.link(cp)
    preview([ice, boards, glass, net, gl, puck])
    print("RINK DONE", stats)


if __name__ == "__main__":
    main()
