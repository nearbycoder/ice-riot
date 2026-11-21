"""ICE RIOT arena: seating bowl, suites, upper deck, roof truss, benches, penalty boxes, tunnels, banners,
crowd (SM_Crowd) and the center-hung jumbotron (SM_Jumbotron).

    blender -b --factory-startup --python-exit-code 1 -P Blender/gen_arena.py

Outputs: Meshes/SM_Arena.fbx, SM_Crowd.fbx, SM_Jumbotron.fbx; Textures/T_RibbonBoard.png, T_JumboDefault.png;
Materials/arena.json; Manifests/arena.json; Previews/arena_*.png; Blend/arena.blend.
Pivot of every mesh = Blender world origin (center ice, ice surface z = 0).
"""

import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

import ir_common as hc  # noqa: E402
import ir_env as eh  # noqa: E402
import ir_draw as dr  # noqa: E402
from ir_draw import Canvas  # noqa: E402
from ir_teams import TEAMS  # noqa: E402
from gen_rink import perimeter, point_at, perim_total, HX, HY, CR, BOARD_T, GLASS_TOP  # noqa: E402

RNG = np.random.default_rng(1205)
M = eh.MatLib("arena")

# Bowl layout (offsets are measured outward from the boards' inner face)
BOWL_D0 = 3.2              # front wall of the lower bowl
LOW_ROWS, LOW_DEPTH, LOW_RISE, LOW_Z0 = 17, 0.86, 0.40, 1.35
SUITE_H = 4.2              # height of the suite level wall
UP_ROWS, UP_DEPTH, UP_RISE = 13, 0.82, 0.56
SEAT_PITCH = 0.60
ROOF_Z = 36.0
JUMBO_BOTTOM = 16.0
N_ARC = 16


def low_row(i):
    return BOWL_D0 + i * LOW_DEPTH, LOW_Z0 + i * LOW_RISE


LOW_END_D, LOW_END_Z = low_row(LOW_ROWS)
SUITE_D = LOW_END_D + 0.6
UP_D0 = SUITE_D + 2.2
UP_Z0 = LOW_END_Z + SUITE_H


def up_row(i):
    return UP_D0 + i * UP_DEPTH, UP_Z0 + i * UP_RISE


UP_END_D, UP_END_Z = up_row(UP_ROWS)


# ---------------------------------------------------------------------------
# Materials + textures
# ---------------------------------------------------------------------------
def ribbon_texture():
    W, H = 2048, 128
    cv = Canvas(W, H, (0, 0, 16.0, 1.0), bg="#050A16")
    msgs = [("ICE RIOT", "#38B6FF"), ("FROSTBITE COLA", "#FF3B3B"), ("MAKE SOME NOISE!", "#FFD23F"),
            ("PUCK YEAH!", "#C6FF3A"), ("BLUE LINE BANK", "#5B8CFF"), ("GO GO GO!", "#FF6B12")]
    x = 0.0
    for txt, c in msgs:
        w = len(txt) * 0.36 + 0.6
        m = cv.text(txt, font=dr.FONT_IMPACT, center=(x + w / 2, 0.5), height=0.62, width=w - 0.5, shear=0.15)
        cv.put(cv.grow(m, 0.04), dr.shade(c, 0.35))
        cv.put(m, c)
        x += w
        cv.fill(cv.poly([(x - 0.15, 0.5), (x - 0.05, 0.75), (x + 0.05, 0.5), (x - 0.05, 0.25)]), "#FFFFFF")
    # LED pixel grid
    gx = np.abs(((cv.X / 16.0 * W / 4.0) % 1.0) - 0.5)
    gy = np.abs(((cv.Y * H / 4.0) % 1.0) - 0.5)
    led = np.clip(1.0 - np.maximum(gx, gy) * 1.4, 0.35, 1.0)
    cv.rgb *= led[..., None]
    cv.save(os.path.join(hc.TEX_DIR, "T_RibbonBoard.png"), opaque=True)


def jumbo_default_texture():
    W, H = 1024, 576
    cv = Canvas(W, H, (-1.0, -0.5625, 1.0, 0.5625), bg="#06142B")
    cv.put(np.ones((H, W), np.float32), cv.rgrad((0, 0), 1.3, "#1D4C8F", "#040A18"))
    p = os.path.join(hc.TEX_DIR, "T_LogoIceRiot.png")
    if os.path.exists(p):
        cv.stamp(eh.load_png(p), (0, 0.04), 1.55)
    gx = np.abs(((cv.X * W / 2 / 3.0) % 1.0) - 0.5)
    gy = np.abs(((cv.Y * W / 2 / 3.0) % 1.0) - 0.5)
    cv.rgb *= np.clip(1.0 - np.maximum(gx, gy) * 0.8, 0.6, 1.0)[..., None]
    cv.save(os.path.join(hc.TEX_DIR, "T_JumboDefault.png"), opaque=True)


def make_materials():
    m = {}
    m["floor"] = M.opaque("MI_ArenaFloor", eh.lin("#1B1E26"), roughness=0.8)
    m["wall"] = M.opaque("MI_BowlWall", eh.lin("#0E1B36"), roughness=0.6)
    m["tread"] = M.opaque("MI_BowlConcrete", eh.lin("#5A606B"), roughness=0.85)
    m["riser"] = M.opaque("MI_BowlRiser", eh.lin("#2A2F3A"), roughness=0.8)
    m["seat_lo"] = M.opaque("MI_SeatsLower", eh.lin("#1D47A8"), roughness=0.5)
    m["seat_up"] = M.opaque("MI_SeatsUpper", eh.lin("#14244A"), roughness=0.55)
    m["stairs"] = M.opaque("MI_Stairs", eh.lin("#8B919C"), roughness=0.8)
    m["rail"] = M.opaque("MI_Railing", eh.lin("#B8C0CC"), roughness=0.3, metallic=1.0)
    m["suite"] = M.opaque("MI_SuiteGlass", eh.lin("#2B2117"), roughness=0.08, emissive=eh.lin("#FFC27A"),
                          emissive_strength=2.0)
    m["fascia"] = M.opaque("MI_Fascia", eh.lin("#0A1430"), roughness=0.4)
    m["ribbon"] = M.emissive("MI_RibbonBoard", (1, 1, 1), emissive_strength=3.0, texture="T_RibbonBoard",
                             pan_u=0.02)
    m["roof"] = M.opaque("MI_Roof", eh.lin("#0B0E15"), roughness=0.9)
    m["truss"] = M.opaque("MI_Truss", eh.lin("#3A404C"), roughness=0.45, metallic=0.8)
    m["lamp"] = M.emissive("MI_ArenaLamp", eh.lin("#FFF4E0"), emissive_strength=30.0)
    m["bench"] = M.opaque("MI_Bench", eh.lin("#2A2E36"), roughness=0.6)
    m["benchfloor"] = M.opaque("MI_BenchFloor", eh.lin("#121418"), roughness=0.9)
    m["tunnel"] = M.opaque("MI_Tunnel", eh.lin("#050608"), roughness=0.95)
    m["sign"] = M.emissive("MI_ExitSign", eh.lin("#38FF7A"), emissive_strength=6.0)
    for t in TEAMS:
        m["banner_" + t["id"]] = M.masked("MI_Banner_" + t["id"], "T_Banner_" + t["id"], roughness=0.8)
    m["jumbo_frame"] = M.opaque("MI_JumboFrame", eh.lin("#15181F"), roughness=0.35, metallic=0.7)
    m["jumbo_screen"] = M.custom("MI_JumboScreen", "screen", texture="T_JumboDefault", color=[1, 1, 1],
                                 brightness=1.5)
    m["jumbo_ribbon"] = M.emissive("MI_JumboRibbon", (1, 1, 1), emissive_strength=3.0, texture="T_RibbonBoard",
                                   pan_u=-0.04)
    m["jumbo_trim"] = M.emissive("MI_JumboTrim", eh.lin("#38B6FF"), emissive_strength=8.0)
    m["crowd"] = M.crowd("MI_Crowd")
    return m


# ---------------------------------------------------------------------------
# Bowl geometry helpers (rings aligned across offsets: line steps are offset-invariant)
# ---------------------------------------------------------------------------
def ring(d, step=1.0):
    pts, _ = perimeter(d, step=step, n_arc=N_ARC)
    return [(Vector((p[0], p[1], 0.0)), Vector((p[2], p[3], 0.0))) for p in pts]


def hband(mb, d0, d1, z, mat, skip=None):
    """Horizontal band from offset d0 to d1 at height z (faces up)."""
    A, B = ring(d0), ring(d1)
    n = len(A)
    for i in range(n):
        j = (i + 1) % n
        if skip and skip(A[i][0], A[j][0], d0, d1):
            continue
        a0 = A[i][0] + Vector((0, 0, z))
        a1 = A[j][0] + Vector((0, 0, z))
        b0 = B[i][0] + Vector((0, 0, z))
        b1 = B[j][0] + Vector((0, 0, z))
        mb.quad(tuple(a0), tuple(b0), tuple(b1), tuple(a1), mat=mat)


def vband(mb, d, za, zb, mat, inward=True, skip=None, uv_scale=None):
    A = ring(d)
    n = len(A)
    s = 0.0
    for i in range(n):
        j = (i + 1) % n
        if skip and skip(A[i][0], A[j][0], d, d):
            continue
        p0, p1 = A[i][0], A[j][0]
        L = (p1 - p0).length
        q = [tuple(p0 + Vector((0, 0, za))), tuple(p1 + Vector((0, 0, za))), tuple(p1 + Vector((0, 0, zb))),
             tuple(p0 + Vector((0, 0, zb)))]
        uv = None
        if uv_scale:
            uv = [(s / uv_scale, 0), ((s + L) / uv_scale, 0), ((s + L) / uv_scale, 1), (s / uv_scale, 1)]
        if inward:
            mb.quad(*q, mat=mat, uv=uv)
        else:
            mb.quad(q[1], q[0], q[3], q[2], mat=mat,
                    uv=None if uv is None else [uv[1], uv[0], uv[3], uv[2]])
        s += L


def is_tunnel(p, row):
    """Lower-bowl vomitories: end centers (resurfacer + team tunnels) and 4 corner exits."""
    if row < 7 and abs(p.y) < 2.0 and abs(p.x) > HX:
        return True
    if row < 5 and abs(abs(p.x) - 15.0) < 1.2 and p.y < -HY:
        return True
    return False


def tunnel_skip_factory(row):
    def f(a, b, d0, d1):
        m = (a + b) * 0.5
        return is_tunnel(m, row)
    return f


def aisle_key(x, y):
    """Distance (m) to the nearest radial aisle at this bowl position."""
    ax, ay = HX - CR, HY - CR
    if abs(x) <= ax and abs(y) > ay:
        cands = [-14.0, -7.0, 0.0, 7.0, 14.0]
        return min(abs(x - c) for c in cands)
    if abs(y) <= ay and abs(x) > ax:
        return abs(abs(y) - 2.4)
    ang = math.degrees(math.atan2(abs(y) - ay, abs(x) - ax))
    r = math.hypot(abs(x) - ax, abs(y) - ay)
    return abs(ang - 45.0) / 57.3 * r


AISLE_HALF = 0.55


# ---------------------------------------------------------------------------
# Bowl
# ---------------------------------------------------------------------------
def build_bowl(m):
    mats = [m["floor"], m["wall"], m["tread"], m["riser"], m["seat_lo"], m["seat_up"], m["stairs"], m["rail"],
            m["suite"], m["fascia"], m["ribbon"], m["roof"], m["tunnel"], m["sign"]]
    I = {k: i for i, k in enumerate(["floor", "wall", "tread", "riser", "seat_lo", "seat_up", "stairs", "rail",
                                     "suite", "fascia", "ribbon", "roof", "tunnel", "sign"])}
    mb = eh.MeshBuilder()
    # concourse floor between the boards and the bowl
    hband(mb, BOARD_T, BOWL_D0, -0.02, I["floor"])
    # lower bowl front wall with an LED ribbon on top
    sk0 = tunnel_skip_factory(0)
    vband(mb, BOWL_D0, -0.02, LOW_Z0 - 0.35, I["wall"], skip=sk0)
    vband(mb, BOWL_D0, LOW_Z0 - 0.35, LOW_Z0, I["ribbon"], uv_scale=16.0, skip=sk0)
    # lower rows
    for i in range(LOW_ROWS):
        d, z = low_row(i)
        sk = tunnel_skip_factory(i)
        hband(mb, d, d + LOW_DEPTH, z, I["tread"], skip=sk)
        if i < LOW_ROWS - 1:
            vband(mb, d + LOW_DEPTH, z, z + LOW_RISE, I["riser"], skip=sk)
        # continuous seat band (fans sit on it); aisles stay open
        seat_band(mb, d + 0.12, z, I["seat_lo"], i, upper=False)
    # vomitories: open trenches through the lower rows (stepped side walls, dark mouth, exit sign)
    for sx in (-1, 1):
        trench(mb, I, axis="x", sign=sx, center=0.0, halfw=2.0, rows=7)
        trench(mb, I, axis="y", sign=-1, center=15.0 * sx, halfw=1.2, rows=5)
    # aisle stairs (two steps per row) on the lower bowl
    stairs(mb, I["stairs"], upper=False)
    # glass rail at the top of the lower bowl
    d, z = low_row(LOW_ROWS)
    hband(mb, d - LOW_DEPTH, SUITE_D, z, I["tread"])
    vband(mb, d - 0.1, z, z + 1.0, I["rail"])
    # suite level wall: glass windows + fascia + ribbon board
    vband(mb, SUITE_D, z, z + 0.4, I["fascia"])
    vband(mb, SUITE_D, z + 0.4, z + 2.6, I["suite"])
    vband(mb, SUITE_D, z + 2.6, z + 3.0, I["fascia"])
    vband(mb, SUITE_D, z + 3.0, z + 3.9, I["ribbon"], uv_scale=16.0)
    vband(mb, SUITE_D, z + 3.9, UP_Z0, I["fascia"])
    hband(mb, SUITE_D, UP_D0, UP_Z0, I["tread"])
    # upper deck
    vband(mb, UP_D0, UP_Z0, UP_Z0 + 1.0, I["fascia"])
    for i in range(UP_ROWS):
        d, z = up_row(i)
        hband(mb, d, d + UP_DEPTH, z + 1.0, I["tread"])
        vband(mb, d + UP_DEPTH, z + 1.0, z + 1.0 + UP_RISE, I["riser"])
        seat_band(mb, d + 0.12, z + 1.0, I["seat_up"], i, upper=True)
    stairs(mb, I["stairs"], upper=True)
    # back wall up to the roof
    d, z = up_row(UP_ROWS)
    vband(mb, d, z + 1.0, ROOF_Z, I["wall"])
    # roof ceiling (dark)
    hband_down(mb, 0.0, d, ROOF_Z, I["roof"])
    bowl = mb.build("Bowl", mats)
    eh.box_uv(bowl, 0.5)
    # restore ribbon UVs (box_uv overwrote them) -> rebuild the ribbon bands as their own object
    return bowl


def trench(mb, I, axis, sign, center, halfw, rows):
    """Vomitory cut through the first `rows` rows. axis='x': at the rink ends (runs along x, centered on
    y=center); axis='y': on the near/far sides (runs along y, centered on x=center)."""
    base = HX if axis == "x" else HY

    def P(d, lat, z):
        o = sign * (base + d)
        return (o, center + lat, z) if axis == "x" else (center + lat, o, z)
    d_end, z_end = low_row(rows)
    # floor
    mb.quad(P(BOWL_D0, -halfw, 0.0), P(BOWL_D0, halfw, 0.0), P(d_end, halfw, 0.0), P(d_end, -halfw, 0.0),
            mat=I["floor"])
    # stepped side walls (both faces)
    for i in range(rows):
        d0, z = low_row(i)
        d1 = d0 + LOW_DEPTH
        for lat in (-halfw, halfw):
            q = [P(d0, lat, 0.0), P(d1, lat, 0.0), P(d1, lat, z), P(d0, lat, z)]
            mb.quad(*q, mat=I["wall"])
            mb.quad(q[1], q[0], q[3], q[2], mat=I["wall"])
            # cap on top of the wall
            mb.quad(P(d0, lat - 0.06, z), P(d1, lat - 0.06, z), P(d1, lat + 0.06, z), P(d0, lat + 0.06, z),
                    mat=I["rail"])
    # dark tunnel mouth + lintel + exit sign
    mb.quad(P(d_end, -halfw, 0.0), P(d_end, halfw, 0.0), P(d_end, halfw, z_end), P(d_end, -halfw, z_end),
            mat=I["tunnel"])
    mb.quad(P(d_end - 0.01, -halfw, z_end - 0.45), P(d_end - 0.01, halfw, z_end - 0.45), P(d_end - 0.01, halfw, z_end),
            P(d_end - 0.01, -halfw, z_end), mat=I["fascia"])
    mb.quad(P(d_end - 0.02, -0.4, z_end - 0.38), P(d_end - 0.02, 0.4, z_end - 0.38), P(d_end - 0.02, 0.4, z_end - 0.08),
            P(d_end - 0.02, -0.4, z_end - 0.08), mat=I["sign"])


def hband_down(mb, d0, d1, z, mat):
    """Ceiling: a disc-ish cap from the inner rink rectangle outward, faces down."""
    A = ring(d1)
    n = len(A)
    # fill the inner rounded rectangle with a fan from the center (faces down)
    c = (0.0, 0.0, z)
    for i in range(n):
        j = (i + 1) % n
        mb.tri(c, tuple(A[j][0] + Vector((0, 0, z))), tuple(A[i][0] + Vector((0, 0, z))), mat=mat)


def seat_band(mb, d, z, mat, row, upper):
    """A row of seats as segmented blocks (seat pan + back), broken at aisles and tunnels."""
    pts, total = perimeter(d, step=0.6, n_arc=48 if not upper else 64)
    n = len(pts)
    for i in range(n):
        x, y, nx, ny, s = pts[i]
        x2, y2, nx2, ny2, s2 = pts[(i + 1) % n]
        mid = Vector(((x + x2) / 2, (y + y2) / 2, 0))
        if aisle_key(mid.x, mid.y) < AISLE_HALF + 0.1:
            continue
        if not upper and is_tunnel(mid, row):
            continue
        # seat block: from offset d to d+0.42, height 0.45, back up to 0.85 at the rear
        o0, o1 = 0.0, 0.42
        P = []
        for (px, py, qx, qy) in ((x, y, nx, ny), (x2, y2, nx2, ny2)):
            P.append([Vector((px + qx * o0, py + qy * o0, z)), Vector((px + qx * o1, py + qy * o1, z)),
                      Vector((px + qx * o0, py + qy * o0, z + 0.45)), Vector((px + qx * o1, py + qy * o1, z + 0.45)),
                      Vector((px + qx * (o1 + 0.06), py + qy * (o1 + 0.06), z + 0.88)),
                      Vector((px + qx * (o1 - 0.06), py + qy * (o1 - 0.06), z + 0.88))])
        a, b = P[0], P[1]
        T = lambda v: tuple(v)  # noqa: E731
        mb.quad(T(a[0]), T(b[0]), T(b[2]), T(a[2]), mat=mat)           # front
        mb.quad(T(a[2]), T(b[2]), T(b[3]), T(a[3]), mat=mat)           # seat pan
        mb.quad(T(a[3]), T(b[3]), T(b[5]), T(a[5]), mat=mat)           # back (front face)
        mb.quad(T(a[5]), T(b[5]), T(b[4]), T(a[4]), mat=mat)           # top
        mb.quad(T(a[4]), T(b[4]), T(b[1]), T(a[1]), mat=mat)           # rear


def stairs(mb, mat, upper):
    rows = UP_ROWS if upper else LOW_ROWS
    for i in range(rows):
        d, z = up_row(i) if upper else low_row(i)
        dep = UP_DEPTH if upper else LOW_DEPTH
        rise = UP_RISE if upper else LOW_RISE
        if upper:
            z += 1.0
        # sample aisle centers on this row's center line
        pts, _ = perimeter(d + dep * 0.5, step=0.1, n_arc=720)
        prev = False
        centers = []
        run = []
        for (x, y, nx, ny, s) in pts:
            inside = aisle_key(x, y) < AISLE_HALF
            if inside:
                run.append((x, y, nx, ny))
            elif run:
                centers.append(run[len(run) // 2])
                run = []
        for (x, y, nx, ny) in centers:
            if not upper and is_tunnel(Vector((x, y, 0)), i):
                continue
            t = Vector((-ny, nx, 0))
            nrm = Vector((nx, ny, 0))
            c = Vector((x, y, 0))
            # half-step in the middle of the tread
            p = c - nrm * dep * 0.25 + Vector((0, 0, z + rise * 0.25))
            mb.oriented_box(tuple(p), tuple(t), tuple(nrm), (0, 0, 1), AISLE_HALF, dep * 0.25, rise * 0.25, mat=mat,
                            skip=("-z",))


# ---------------------------------------------------------------------------
# Far-side benches + penalty boxes, roof truss, banners
# ---------------------------------------------------------------------------
def build_benches(m):
    mb = eh.MeshBuilder()
    mats = [m["bench"], m["benchfloor"], m["glass_b"], m["rail"]]
    y0 = HY + BOARD_T
    y1 = HY + BOWL_D0
    for (xa, xb) in ((-11.0, -3.6), (3.6, 11.0)):          # player benches
        mb.box((xa, y0, -0.02), (xb, y1, 0.12), mat=1, skip=("-z",))
        mb.box((xa, y1 - 0.55, 0.12), (xb, y1 - 0.05, 0.58), mat=0)                  # bench seat
        mb.box((xa, y1 - 0.12, 0.58), (xb, y1, 1.15), mat=0)                          # back
        for x in (xa, xb):
            mb.box((x - 0.05, y0, 0.0), (x + 0.05, y1, 1.07), mat=0)                  # partitions
        # glass behind the bench (protects fans)
        mb.quad((xa, y1, 1.15), (xb, y1, 1.15), (xb, y1, 2.2), (xa, y1, 2.2), mat=2)
    for (xa, xb) in ((-2.9, -1.0), (1.0, 2.9)):            # penalty boxes
        mb.box((xa, y0, -0.02), (xb, y1, 0.12), mat=1, skip=("-z",))
        mb.box((xa, y1 - 0.5, 0.12), (xb, y1 - 0.05, 0.55), mat=0)
        for x in (xa, xb):
            mb.box((x - 0.05, y0, 0.0), (x + 0.05, y1, 2.2), mat=0)
            mb.quad((x, y0, 1.07), (x, y1, 1.07), (x, y1, 2.2), (x, y0, 2.2), mat=2)
        mb.quad((xa, y1, 0.6), (xb, y1, 0.6), (xb, y1, 2.2), (xa, y1, 2.2), mat=2)
    # timekeeper table between the boxes
    mb.box((-0.9, y1 - 1.0, -0.02), (0.9, y1, 0.95), mat=0)
    o = mb.build("Benches", mats)
    eh.box_uv(o, 1.0)
    return o


def build_truss(m):
    mb = eh.MeshBuilder()
    mats = [m["truss"], m["lamp"]]
    # big rectangular light truss around the jumbotron + four radial arms
    for (hx, hy, z) in ((19.0, 9.0, 27.0), (12.0, 7.0, 29.5)):
        corners = [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
        for k in range(4):
            a = Vector((corners[k][0], corners[k][1], z))
            b = Vector((corners[(k + 1) % 4][0], corners[(k + 1) % 4][1], z))
            truss_beam(mb, a, b, 0.6, 0)
            # light fixtures along the beam, pointing down at the ice
            L = (b - a).length
            nl = int(L // 2.4)
            for i in range(1, nl):
                p = a.lerp(b, i / nl)
                mb.box((p.x - 0.22, p.y - 0.22, z - 0.75), (p.x + 0.22, p.y + 0.22, z - 0.35), mat=0)
                mb.box((p.x - 0.17, p.y - 0.17, z - 0.77), (p.x + 0.17, p.y + 0.17, z - 0.74), mat=1)
    for sx in (-1, 1):
        for sy in (-1, 1):
            truss_beam(mb, Vector((sx * 12.0, sy * 7.0, 29.5)), Vector((sx * 19.0, sy * 9.0, 27.0)), 0.5, 0)
    # roof girders spanning the arena
    d, z = up_row(UP_ROWS)
    for x in np.linspace(-(HX + d) + 4, (HX + d) - 4, 9):
        truss_beam(mb, Vector((x, -(HY + d) + 0.5, ROOF_Z - 1.2)), Vector((x, (HY + d) - 0.5, ROOF_Z - 1.2)), 1.6, 0)
    # cables up to the roof from the inner truss
    for (x, y) in ((-12, -7), (12, -7), (12, 7), (-12, 7)):
        mb.box((x - 0.04, y - 0.04, 29.5), (x + 0.04, y + 0.04, ROOF_Z - 0.6), mat=0)
    # catwalk ring lights near the roof (bowl lighting)
    for k in range(48):
        s = perim_total(UP_END_D - 6.0) * k / 48
        (x, y), (nx, ny) = point_at(UP_END_D - 6.0, s)
        mb.box((x - 0.25, y - 0.25, ROOF_Z - 2.2), (x + 0.25, y + 0.25, ROOF_Z - 1.9), mat=1)
    o = mb.build("Truss", mats)
    eh.box_uv(o, 1.0)
    return o


def truss_beam(mb, a, b, h, mat):
    """Square box truss: 4 chords + zig-zag diagonals."""
    d = (b - a)
    L = d.length
    t = d.normalized()
    up = Vector((0, 0, 1))
    side = t.cross(up).normalized()
    upv = side.cross(t).normalized()
    r = 0.05
    for sx in (-1, 1):
        for sz in (-1, 1):
            off = side * (sx * h / 2) + upv * (sz * h / 2)
            c = (a + b) / 2 + off
            mb.oriented_box(tuple(c), tuple(t), tuple(side), tuple(upv), L / 2, r, r, mat=mat)
    n = max(2, int(L / h))
    for i in range(n):
        p0 = a + d * (i / n)
        p1 = a + d * ((i + 1) / n)
        for sx in (-1, 1):
            q0 = p0 + side * (sx * h / 2) + upv * (-h / 2 if i % 2 == 0 else h / 2)
            q1 = p1 + side * (sx * h / 2) + upv * (h / 2 if i % 2 == 0 else -h / 2)
            dd = q1 - q0
            mb.oriented_box(tuple((q0 + q1) / 2), tuple(dd.normalized()), tuple(side),
                            tuple(dd.normalized().cross(side).normalized()), dd.length / 2, 0.03, 0.03, mat=mat)


def build_banners(m):
    """Team banners hanging from the far roof girders (+Y side), facing the main camera (-Y)."""
    objs = []
    d, z = up_row(UP_ROWS)
    y = HY + d - 3.0
    w, h = 3.2, 6.4
    xs = np.linspace(-19.0, 19.0, len(TEAMS))
    for x, t in zip(xs, TEAMS):
        mb = eh.MeshBuilder()
        top = ROOF_Z - 3.0
        mb.quad((x - w / 2, y, top - h), (x + w / 2, y, top - h), (x + w / 2, y, top), (x - w / 2, y, top),
                mat=0, uv=[(0, 0), (1, 0), (1, 1), (0, 1)])
        o = mb.build("Banner_" + t["id"], [m["banner_" + t["id"]]])
        objs.append(o)
        # hanging rod
        rod = eh.MeshBuilder()
        rod.box((x - w / 2 - 0.1, y - 0.04, top), (x + w / 2 + 0.1, y + 0.04, top + 0.08), mat=0)
        rod.box((x - 0.02, y - 0.02, top), (x + 0.02, y + 0.02, ROOF_Z - 1.2), mat=0)
        ro = rod.build("BannerRod", [m["truss"]])
        eh.box_uv(ro)
        objs.append(ro)
    # mirrored set at the near side (facing +Y, seen in reverse angles)
    return objs


# ---------------------------------------------------------------------------
# Crowd
# ---------------------------------------------------------------------------
ROLE_SHIRT, ROLE_PANTS, ROLE_SKIN, ROLE_HAIR, ROLE_SLEEVE, ROLE_PROP = range(6)


class Tpl:
    def __init__(self):
        self.v, self.f, self.r = [], [], []

    def frustum(self, c0, h0, c1, h1, roles, skip=("bot",)):
        base = len(self.v)
        for (c, h) in ((c0, h0), (c1, h1)):
            for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                self.v.append((c[0] + sx * h[0], c[1] + sy * h[1], c[2]))
        b = [base + i for i in range(4)]
        t = [base + 4 + i for i in range(4)]
        faces = {"s0": (b[0], b[1], t[1], t[0]), "s1": (b[1], b[2], t[2], t[1]), "s2": (b[2], b[3], t[3], t[2]),
                 "s3": (b[3], b[0], t[0], t[3]), "top": (t[0], t[1], t[2], t[3]), "bot": (b[3], b[2], b[1], b[0])}
        for k, f in faces.items():
            if k in skip:
                continue
            self.f.append(f)
            self.r.append(roles.get(k, roles.get("all", 0)))

    def obox(self, A, B, hw, roles, skip=("bot",)):
        A, B = Vector(A), Vector(B)
        a = (B - A).normalized()
        up = Vector((0, 0, 1)) if abs(a.z) < 0.95 else Vector((1, 0, 0))
        e1 = a.cross(up).normalized()
        e2 = a.cross(e1)
        base = len(self.v)
        for c in (A, B):
            for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                self.v.append(tuple(c + e1 * (sx * hw) + e2 * (sy * hw)))
        b = [base + i for i in range(4)]
        t = [base + 4 + i for i in range(4)]
        for f in ((b[0], b[1], t[1], t[0]), (b[1], b[2], t[2], t[1]), (b[2], b[3], t[3], t[2]),
                  (b[3], b[0], t[0], t[3])):
            self.f.append(f)
            self.r.append(roles.get("all", 0))

    def arrays(self):
        return np.array(self.v, np.float32), np.array(self.f, np.int32), np.array(self.r, np.int32)


def make_templates():
    """Fans face +Y in template space; seat front edge at y = 0, tread at z = 0."""
    T = {}

    def head(t, cx, cy, z0, s=1.0):
        t.frustum((cx, cy, z0), (0.085 * s, 0.095 * s), (cx, cy, z0 + 0.13 * s), (0.10 * s, 0.11 * s),
                  {"all": ROLE_SKIN}, skip=("bot", "top"))
        t.frustum((cx, cy, z0 + 0.13 * s), (0.10 * s, 0.11 * s), (cx, cy - 0.01, z0 + 0.25 * s), (0.07 * s, 0.08 * s),
                  {"all": ROLE_HAIR, "s2": ROLE_SKIN}, skip=("bot",))

    t = Tpl()      # seated
    t.frustum((0, -0.20, 0.42), (0.17, 0.14), (0, -0.25, 1.02), (0.21, 0.12), {"all": ROLE_SHIRT})
    t.frustum((0, 0.02, 0.0), (0.15, 0.20), (0, 0.02, 0.48), (0.17, 0.20), {"all": ROLE_PANTS}, skip=("bot", "s0"))
    head(t, 0, -0.24, 1.04)
    for sx in (-1, 1):
        t.obox((sx * 0.23, -0.24, 0.98), (sx * 0.19, 0.02, 0.62), 0.05, {"all": ROLE_SLEEVE})
    T["seated"] = t.arrays()

    def standing(hand):
        t = Tpl()
        t.frustum((0, 0.05, 0.0), (0.15, 0.10), (0, 0.05, 0.88), (0.17, 0.10), {"all": ROLE_PANTS})
        t.frustum((0, 0.05, 0.86), (0.16, 0.10), (0, 0.04, 1.44), (0.21, 0.11), {"all": ROLE_SHIRT}, skip=("bot",))
        head(t, 0, 0.04, 1.46)
        for sx in (-1, 1):
            t.obox((sx * 0.235, 0.04, 1.40), hand(sx), 0.05, {"all": ROLE_SLEEVE})
        return t
    T["standing"] = standing(lambda sx: (sx * 0.27, 0.07, 0.82)).arrays()
    T["clap"] = standing(lambda sx: (sx * 0.05, 0.33, 1.30)).arrays()
    T["armsup"] = standing(lambda sx: (sx * 0.48, 0.10, 2.02)).arrays()
    T["pump"] = standing(lambda sx: (0.30, 0.12, 2.05) if sx > 0 else (-0.27, 0.07, 0.82)).arrays()
    t = Tpl()
    t.frustum((0, 0.20, 1.80), (0.40, 0.012), (0, 0.20, 2.25), (0.40, 0.012), {"all": ROLE_PROP}, skip=("bot",))
    T["sign"] = t.arrays()
    return T


def instance(tpl, P, yaw, scale, role_cols, uv):
    V, F, R = tpl
    N = len(P)
    if N == 0:
        return None
    S = V[None, :, :] * scale[:, None, :]
    c, s = np.cos(yaw)[:, None], np.sin(yaw)[:, None]
    X = c * S[..., 0] - s * S[..., 1] + P[:, 0:1]
    Y = s * S[..., 0] + c * S[..., 1] + P[:, 1:2]
    Z = S[..., 2] + P[:, 2:3]
    verts = np.stack([X, Y, Z], -1).reshape(-1, 3).astype(np.float32)
    faces = (F[None, :, :] + (np.arange(N) * len(V))[:, None, None]).reshape(-1, 4).astype(np.int32)
    fc = role_cols[:, R, :]
    fc = np.repeat(fc[:, :, None, :], 4, axis=2).reshape(-1, 3)
    cols = np.concatenate([fc, np.ones((len(fc), 1), np.float32)], 1).astype(np.float32)
    uvs = np.repeat(uv[:, None, :], len(F) * 4, axis=1).reshape(-1, 2).astype(np.float32)
    return verts, faces, cols, uvs


def seat_positions():
    P, YAW, ROW, UPPER = [], [], [], []
    for upper in (False, True):
        rows = UP_ROWS if upper else LOW_ROWS
        for i in range(rows):
            d, z = up_row(i) if upper else low_row(i)
            if upper:
                z += 1.0
            pts, _ = perimeter(d + 0.12, step=SEAT_PITCH, n_arc=48 if not upper else 64)
            for (x, y, nx, ny, s) in pts:
                if aisle_key(x, y) < AISLE_HALF + 0.25:
                    continue
                if not upper and is_tunnel(Vector((x, y, 0)), i):
                    continue
                P.append((x, y, z))
                YAW.append(math.atan2(-ny, -nx) - math.pi / 2)
                ROW.append(i)
                UPPER.append(upper)
    return (np.array(P, np.float32), np.array(YAW, np.float32), np.array(ROW, np.int32), np.array(UPPER, bool))


def build_crowd(m):
    T = make_templates()
    P, YAW, ROW, UPPER = seat_positions()
    N = len(P)
    team_hex = [c for t in TEAMS for c in (t["primary"], t["secondary"])]
    misc = ["#F2F2F2", "#E6E6E6", "#1A1A1E", "#24262B", "#2B3A55", "#1F4E8C", "#3B7A3B", "#6B3FA0", "#8C8C8C",
            "#C9B79C", "#0F6E6A", "#A8324A", "#D9D2C5"]
    pants = ["#2B3A55", "#1A1A1E", "#3D5A80", "#55585E", "#7D6E55", "#2A2A2A", "#3B4A63"]
    skins = ["#FFDBAC", "#F1C27D", "#E0AC69", "#C68642", "#A86B3C", "#8D5524", "#6B3E1F", "#4A2A16"]
    hairs = ["#140D07", "#2B1A0F", "#3B2416", "#6A4E2E", "#A5793F", "#C9A45C", "#8C3A1A", "#9A9A9A", "#D9D3C7"]
    props = ["#FFD23F", "#38B6FF", "#FF3B3B", "#F7F4EE", "#C6FF3A"]

    def L(h):
        return np.array([eh.lin(x) for x in h], np.float32)
    teams, misc_c, pants_c, skins_c, hairs_c, props_c = map(L, (team_hex, misc, pants, skins, hairs, props))
    occ = RNG.random(N) < np.where(UPPER, 0.86, 0.93)
    energy = np.where(ROW < 4, 0.42, 0.26) * np.where(UPPER, 0.8, 1.0)
    r = RNG.random(N)
    pose = np.full(N, "seated", dtype=object)
    pose[r < energy] = "standing"
    r2 = RNG.random(N)
    st = pose == "standing"
    pose[st & (r2 < 0.30)] = "clap"
    pose[st & (r2 >= 0.30) & (r2 < 0.52)] = "armsup"
    pose[st & (r2 >= 0.52) & (r2 < 0.64)] = "pump"
    kind = RNG.random(N)
    shirt = np.where((kind < 0.55)[:, None], teams[RNG.integers(0, len(teams), N)], misc_c[RNG.integers(0, len(misc_c), N)])
    shirt = shirt * RNG.uniform(0.85, 1.1, (N, 1)).astype(np.float32)
    skin = skins_c[RNG.integers(0, len(skins_c), N)]
    hair = hairs_c[RNG.integers(0, len(hairs_c), N)]
    pant = pants_c[RNG.integers(0, len(pants_c), N)]
    prop = props_c[RNG.integers(0, len(props_c), N)]
    sleeve = np.where((RNG.random(N) < 0.6)[:, None], shirt, skin)
    role_cols = np.stack([shirt, pant, skin, hair, sleeve, prop], 1).astype(np.float32)
    hs = RNG.uniform(0.93, 1.07, N)
    ws = RNG.uniform(0.92, 1.16, N)
    scale = np.stack([ws, np.ones(N), hs], 1).astype(np.float32)
    yaw = YAW + RNG.normal(0, 0.10, N).astype(np.float32)
    jitter = RNG.uniform(-0.06, 0.06, N).astype(np.float32)
    Pj = P.copy()
    Pj[:, 0] += np.cos(YAW) * jitter
    Pj[:, 1] += np.sin(YAW) * jitter
    phase = RNG.random(N).astype(np.float32)
    amp = np.select([pose == "seated", pose == "standing", pose == "clap", pose == "pump", pose == "armsup"],
                    [RNG.uniform(0.05, 0.35, N), RNG.uniform(0.45, 0.8, N), RNG.uniform(0.5, 0.85, N),
                     RNG.uniform(0.65, 0.95, N), RNG.uniform(0.75, 1.0, N)]).astype(np.float32)
    uv = np.stack([phase, amp], 1)
    has_sign = (RNG.random(N) < 0.12) & (pose == "armsup")
    chunks = []
    for pname in ("seated", "standing", "clap", "armsup", "pump"):
        idx = np.nonzero(occ & (pose == pname))[0]
        chunks.append(instance(T[pname], Pj[idx], yaw[idx], scale[idx], role_cols[idx], uv[idx]))
    si = np.nonzero(occ & has_sign)[0]
    chunks.append(instance(T["sign"], Pj[si], yaw[si], scale[si], role_cols[si], uv[si]))
    chunks = [c for c in chunks if c is not None]
    off = 0
    V, F, C, U = [], [], [], []
    for v, f, c, u in chunks:
        V.append(v)
        F.append(f + off)
        off += len(v)
        C.append(c)
        U.append(u)
    o = eh.mesh_from_arrays("SM_Crowd", np.concatenate(V), np.concatenate(F), uvs=np.concatenate(U),
                            colors=np.concatenate(C), materials=[m["crowd"]])
    stats = dict(seats=int(N), fans=int(occ.sum()),
                 poses={k: int(((pose == k) & occ).sum()) for k in ("seated", "standing", "clap", "armsup", "pump")})
    return o, stats


# ---------------------------------------------------------------------------
# Jumbotron (center hung, 4 screens, each face UV 0..1)
# ---------------------------------------------------------------------------
def build_jumbotron(m):
    mats = [m["jumbo_frame"], m["jumbo_screen"], m["jumbo_ribbon"], m["jumbo_trim"]]
    mb = eh.MeshBuilder()
    hx, hy = 4.2, 3.0              # half sizes of the main box (screens on +-Y are 8 m wide, on +-X 5.6 m)
    z0 = JUMBO_BOTTOM
    zr0, zr1 = z0, z0 + 0.7         # lower LED ribbon ring
    zs0, zs1 = z0 + 0.9, z0 + 0.9 + 4.5
    zt = zs1 + 0.5
    # frame box
    mb.box((-hx - 0.15, -hy - 0.15, zr1), (hx + 0.15, hy + 0.15, zt), mat=0)
    mb.box((-hx + 0.2, -hy + 0.2, zt), (hx - 0.2, hy - 0.2, zt + 0.8), mat=0)       # crown
    # lower ribbon ring (slightly inset)
    rx, ry = hx - 0.3, hy - 0.3
    for (a, b, n) in (((-rx, -ry), (rx, -ry), (0, -1)), ((rx, -ry), (rx, ry), (1, 0)),
                      ((rx, ry), (-rx, ry), (0, 1)), ((-rx, ry), (-rx, -ry), (-1, 0))):
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        mb.quad((a[0], a[1], zr0), (b[0], b[1], zr0), (b[0], b[1], zr1), (a[0], a[1], zr1), mat=2,
                uv=[(0, 0), (L / 16.0 * 2, 0), (L / 16.0 * 2, 1), (0, 1)])
    mb.quad((-rx, ry, zr0), (rx, ry, zr0), (rx, -ry, zr0), (-rx, -ry, zr0), mat=0)       # underside
    # trim light strips
    for z in (zr1 + 0.05, zt - 0.08):
        for (a, b) in (((-hx - 0.16, -hy - 0.16), (hx + 0.16, -hy - 0.16)), ((hx + 0.16, -hy - 0.16), (hx + 0.16, hy + 0.16)),
                       ((hx + 0.16, hy + 0.16), (-hx - 0.16, hy + 0.16)), ((-hx - 0.16, hy + 0.16), (-hx - 0.16, -hy - 0.16))):
            mb.quad((a[0], a[1], z - 0.04), (b[0], b[1], z - 0.04), (b[0], b[1], z + 0.04), (a[0], a[1], z + 0.04), mat=3)
    # screens: each face UV 0..1, u to the viewer's right, v up
    e = 0.17
    W2y, W2x = 4.0, 2.8
    faces = [
        ((-W2y, -hy - e, zs0), (W2y, -hy - e, zs0), (W2y, -hy - e, zs1), (-W2y, -hy - e, zs1)),   # -Y face
        ((hx + e, -W2x, zs0), (hx + e, W2x, zs0), (hx + e, W2x, zs1), (hx + e, -W2x, zs1)),       # +X face
        ((W2y, hy + e, zs0), (-W2y, hy + e, zs0), (-W2y, hy + e, zs1), (W2y, hy + e, zs1)),       # +Y face
        ((-hx - e, W2x, zs0), (-hx - e, -W2x, zs0), (-hx - e, -W2x, zs1), (-hx - e, W2x, zs1)),   # -X face
    ]
    for q in faces:
        mb.quad(*q, mat=1, uv=[(0, 0), (1, 0), (1, 1), (0, 1)])
    # vertical corner light strips
    for cx_ in (-hx - 0.16, hx + 0.16):
        for cy_ in (-hy - 0.16, hy + 0.16):
            mb.box((cx_ - 0.06, cy_ - 0.06, zr1), (cx_ + 0.06, cy_ + 0.06, zt), mat=3)
    # screen bezels (frame lips around each screen)
    for q in faces:
        a, b_, c_, d_ = [Vector(v) for v in q]
        n = (b_ - a).cross(d_ - a).normalized()
        for (p0, p1) in ((a, b_), (d_, c_)):
            mid = (p0 + p1) / 2 + n * 0.04
            ax = (p1 - p0).normalized()
            mb.oriented_box(tuple(mid), tuple(ax), tuple(n), (0, 0, 1), (p1 - p0).length / 2 + 0.08, 0.05, 0.06, mat=0)
    # underbelly: smaller 4-sided screen ring below the main box
    ux, uy, uz0, uz1 = 2.6, 1.8, z0 - 1.6, z0 - 0.1
    mb.box((-ux, -uy, uz0 - 0.15), (ux, uy, uz1), mat=0)
    for (a, b_, n) in (((-ux + 0.1, -uy - 0.02), (ux - 0.1, -uy - 0.02), (0, -1)), ((ux + 0.02, -uy + 0.1), (ux + 0.02, uy - 0.1), (1, 0)),
                       ((ux - 0.1, uy + 0.02), (-ux + 0.1, uy + 0.02), (0, 1)), ((-ux - 0.02, uy - 0.1), (-ux - 0.02, -uy + 0.1), (-1, 0))):
        mb.quad((a[0], a[1], uz0 + 0.05), (b_[0], b_[1], uz0 + 0.05), (b_[0], b_[1], uz1 - 0.05), (a[0], a[1], uz1 - 0.05),
                mat=1, uv=[(0, 0.2), (1, 0.2), (1, 0.8), (0, 0.8)])
    mb.box((-0.3, -0.3, uz1), (0.3, 0.3, z0 + 0.02), mat=0)
    mb.box((-ux - 0.05, -uy - 0.05, uz0 - 0.22), (ux + 0.05, uy + 0.05, uz0 - 0.15), mat=3)
    # hanging cables
    for sx in (-1, 1):
        for sy in (-1, 1):
            mb.box((sx * 3.0 - 0.04, sy * 2.0 - 0.04, zt + 0.8), (sx * 3.0 + 0.04, sy * 2.0 + 0.04, ROOF_Z - 1.0), mat=0)
    o = mb.build("SM_Jumbotron", mats)
    # keep screen + ribbon UVs, box-map only the frame faces
    uvl = o.data.uv_layers.active
    for p in o.data.polygons:
        if p.material_index in (0, 3):
            for li in p.loop_indices:
                v = o.data.vertices[o.data.loops[li].vertex_index].co
                uvl.data[li].uv = (v.x * 0.5 + v.y * 0.5, v.z * 0.5)
    return o


# ---------------------------------------------------------------------------
def preview():
    eh.preview_scene(res=(1600, 900), samples=32, view="AgX", world=(0.02, 0.02, 0.03), world_strength=1.0)
    for i, x in enumerate((-16, -5, 5, 16)):
        eh.area_light("Key%d" % i, (x, 0, 26), (x, 0, 0), 30000, size=8.0)
    eh.area_light("BowlA", (0, -40, 30), (0, 0, 5), 60000, size=20)
    eh.area_light("BowlB", (0, 40, 30), (0, 0, 5), 60000, size=20)
    eh.area_light("BowlC", (50, 0, 30), (0, 0, 5), 40000, size=20)
    eh.area_light("BowlD", (-50, 0, 30), (0, 0, 5), 40000, size=20)
    cam = eh.look_cam("Cam", (0, -26, 13), (0, 1.5, 0), lens=24)
    eh.render_preview(os.path.join(hc.PREVIEW_DIR, "arena_gamecam.png"))
    cam.location = (0, -20, 7)
    cam.rotation_euler = hc.look_at_rotation(cam.location, (0, 10, 14))
    cam.data.lens = 18
    eh.render_preview(os.path.join(hc.PREVIEW_DIR, "arena_up.png"))
    cam.location = (38, -30, 26)
    cam.rotation_euler = hc.look_at_rotation(cam.location, (0, 0, 6))
    cam.data.lens = 22
    eh.render_preview(os.path.join(hc.PREVIEW_DIR, "arena_corner.png"))
    cam.location = (6, -12, 2.5)
    cam.rotation_euler = hc.look_at_rotation(cam.location, (0, 13, 3))
    cam.data.lens = 24
    eh.render_preview(os.path.join(hc.PREVIEW_DIR, "arena_benches.png"))


def main():
    hc.reset_scene()
    ribbon_texture()
    jumbo_default_texture()
    hc.reset_scene()
    m = make_materials()
    m["glass_b"] = M.glass("MI_BenchGlass", eh.lin("#DDEFFF"), opacity=0.14, roughness=0.04)
    M.write()
    bowl = build_bowl(m)
    # ribbon-board UVs (box_uv overwrote them): u = arc length / 16, v = height fraction within the band
    me = bowl.data
    uvl = me.uv_layers.active
    ri = [i for i, mt in enumerate(me.materials) if mt.name == "MI_RibbonBoard"][0]
    for p in me.polygons:
        if p.material_index != ri:
            continue
        zs = [me.vertices[me.loops[li].vertex_index].co.z for li in p.loop_indices]
        z0, z1 = min(zs), max(zs)
        for li in p.loop_indices:
            v = me.vertices[me.loops[li].vertex_index].co
            ang = math.atan2(v.y, v.x)
            uvl.data[li].uv = (-ang / (2 * math.pi) * 12.0, (v.z - z0) / max(1e-6, z1 - z0))
    benches = build_benches(m)
    truss = build_truss(m)
    banners = build_banners(m)
    arena = eh.join_objs([bowl, benches, truss] + banners, "SM_Arena")
    crowd, cstats = build_crowd(m)
    jumbo = build_jumbotron(m)
    stats = {}
    for o in (arena, crowd, jumbo):
        eh.bake_obj(o)
        stats[o.name] = eh.report_mesh(o)
        hc.export_static_fbx([o], o.name + ".fbx")
    stats["crowd"] = cstats
    stats["layout"] = dict(bowl_front=BOWL_D0, lower_rows=LOW_ROWS, lower_top=[LOW_END_D, LOW_END_Z],
                           upper_start=[UP_D0, UP_Z0], upper_top=[UP_END_D, UP_END_Z], roof_z=ROOF_Z,
                           jumbotron_bottom=JUMBO_BOTTOM)
    eh.write_manifest("arena", stats)
    hc.save_blend("arena.blend")
    # bring in the rink for the preview
    try:
        with bpy.data.libraries.load(os.path.join(hc.ROOT, "Art", "Blend", "rink.blend")) as (src, dst):
            dst.objects = [n for n in src.objects if n.startswith("SM_")]
        for o in dst.objects:
            if o is not None:
                bpy.context.scene.collection.objects.link(o)
                if o.name in ("SM_Net", "SM_GoalLight"):
                    cp = o.copy()
                    cp.scale = (-1, 1, 1)
                    bpy.context.scene.collection.objects.link(cp)
                if o.name == "SM_Puck":
                    o.hide_render = True
    except Exception as ex:
        print("no rink for preview", ex)
    preview()
    print("ARENA DONE", stats)


if __name__ == "__main__":
    main()
