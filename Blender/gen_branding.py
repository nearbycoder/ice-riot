"""ICE RIOT branding textures (all original designs).

    blender -b --factory-startup --python-exit-code 1 -P Blender/gen_branding.py

Writes Art/Export/Textures/:
  T_Logo_<Id>.png      1024^2 RGBA team crests (8 teams)
  T_Banner_<Id>.png    1024x2048 hanging rafter banners
  T_LogoIceRiot.png    2048x1024 RGBA game logo
  T_BoardAds.png       2048x2048 atlas of 16 fictional sponsor ads (4:1 cells, 2 columns x 8 rows)
  T_Digits.png         2048x256 jersey digit atlas (R = fill, G = fill + outline)
and Art/Export/teams.json (linear RGB team colors) + contact sheets in Art/Previews.
"""

import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402

import ir_common as hc  # noqa: E402
import ir_env as eh  # noqa: E402
import ir_draw as dr  # noqa: E402
from ir_draw import Canvas, bez, path, arc, xf, shade, mixc  # noqa: E402
from ir_teams import TEAMS, BY_ID  # noqa: E402

TEX = hc.TEX_DIR
INK = "#0A0D14"           # universal dark outline
ONLY = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def want(key):
    return not ONLY or key in ONLY


# ---------------------------------------------------------------------------
# Shared crest pieces
# ---------------------------------------------------------------------------
def wordmark(cv, text, center, height, width, fill, outlines=((0.035, INK),), font=dr.FONT_IMPACT, shear=0.18,
             shadow=None, spacing=1.0, grad=None):
    m = cv.text(text, font=font, center=center, height=height, width=width, shear=shear, spacing=spacing)
    for w, c in sorted(outlines, key=lambda t: -t[0]):
        if shadow is not None and w == max(o[0] for o in outlines):
            sm = cv.text(text, font=font, center=(center[0] + shadow[0], center[1] + shadow[1]), height=height,
                         width=width, shear=shear, spacing=spacing)
            cv.put(cv.grow(sm, w), shadow[2])
        cv.put(cv.grow(m, w), c)
    if grad is not None:
        y0, y1 = center[1] - height * 0.6, center[1] + height * 0.6
        cv.put(m, cv.lgrad((0, y1), (0, y0), grad[0], grad[1]))
    else:
        cv.put(m, fill)
    return m


def star_pts(cx, cy, ro, ri, n=5, rot=math.pi / 2):
    pts = []
    for i in range(2 * n):
        r = ro if i % 2 == 0 else ri
        a = rot + math.pi * i / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def roundel(cv, top, bottom, ring, inner, edge, text_col, accent, font=dr.FONT_IMPACT, r_out=0.97, r_in=0.66):
    cv.fill(cv.circle(0, 0, r_out), edge)
    cv.fill(cv.circle(0, 0, r_out - 0.045), ring)
    # subtle inner shading on the ring
    cv.put(cv.cov(cv.circle(0, 0, r_out - 0.045)) * np.clip((cv.Y + 0.2) * 0.25, 0, 0.25), "#FFFFFF")
    cv.fill(cv.circle(0, 0, r_in + 0.04), edge)
    cv.fill(cv.circle(0, 0, r_in), inner)
    rm = (r_out - 0.045 + r_in + 0.04) * 0.5
    cap = (r_out - 0.045 - r_in - 0.04) * 0.62
    for txt, bottom_arc in ((top, False), (bottom, True)):
        if not txt:
            continue
        L = min(rm * 2.3, len(txt) * cap * 0.62)
        m = cv.text(txt, font=font, center=(0, (rm if not bottom_arc else -rm)), height=cap, width=L,
                    arc_r=rm, arc_bottom=bottom_arc, spacing=1.08)
        cv.put(m, text_col)
    for sx in (-1, 1):
        cv.layer(cv.poly(star_pts(sx * rm, 0, cap * 0.62, cap * 0.26)), accent, [(0.012, edge)])


def shield_pts(w=0.86, top=0.92, shoulder=0.55, bottom=-0.98):
    left = path(((0.0, top), (-w * 0.35, top), (-w * 0.75, top - 0.02), (-w, top - 0.10)),
                ((-w * 1.02, shoulder - 0.2), (-w * 1.0, shoulder - 0.6), (-w * 0.82, bottom * 0.45)),
                ((-w * 0.6, bottom * 0.85), (-w * 0.25, bottom * 0.92), (0.0, bottom)), n=24)
    right = [(-x, y) for x, y in reversed(left)]
    return left + right[1:-1]


def outline_stack(cv, sd, fill, widths):
    """widths: [(w, color)...] outermost first."""
    cv.layer(sd, fill, widths)


def noise_edge(pts, amp, freq, seed=1):
    rng = random.Random(seed)
    ph = [rng.random() * 6.28 for _ in range(3)]
    out = []
    n = len(pts)
    for i, (x, y) in enumerate(pts):
        a = pts[(i - 1) % n]
        b = pts[(i + 1) % n]
        tx, ty = b[0] - a[0], b[1] - a[1]
        L = math.hypot(tx, ty) + 1e-9
        nx, ny = ty / L, -tx / L
        t = i / n
        k = (math.sin(t * freq * 6.283 + ph[0]) * 0.6 + math.sin(t * freq * 2.1 * 6.283 + ph[1]) * 0.4)
        out.append((x + nx * amp * k, y + ny * amp * k))
    return out


def spikes(cx, cy, r_in, r_out, n, rot=0.0, jitter=0.0, seed=3, squash=1.0):
    rng = random.Random(seed)
    pts = []
    for i in range(2 * n):
        r = r_out if i % 2 == 0 else r_in
        r *= 1.0 + (rng.random() - 0.5) * jitter
        a = rot + math.pi * i / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a) * squash))
    return pts


def gloss(cv, sd, strength=0.22, y0=0.0, y1=1.0):
    """Top highlight on a filled shape."""
    t = np.clip((cv.Y - y0) / (y1 - y0), 0, 1)
    cv.put(cv.cov(sd + 0.03) * t * strength, "#FFFFFF")


# ---------------------------------------------------------------------------
# Team crests
# ---------------------------------------------------------------------------
def crest_NAR(cv, t):
    P, S, T = t["primary"], t["secondary"], t["trim"]
    roundel(cv, "NORTHPORT", "NARWHALS", S, mixc(S, "#000000", 0.25), INK, T, P)
    # waves inside the disc
    disc = cv.circle(0, 0, 0.66)
    for i, y in enumerate((-0.34, -0.47)):
        w = cv.Y - (y + 0.035 * np.sin(cv.X * 9 + i * 1.7))
        band = np.maximum(np.abs(w) - 0.028, disc)
        cv.fill(band, shade(P, 0.75 if i else 0.9), alpha=0.9)
    # narwhal body (swimming up-right)
    body = path(((0.44, 0.06), (0.43, 0.22), (0.30, 0.33), (0.12, 0.31)),
                ((-0.10, 0.29), (-0.30, 0.12), (-0.44, -0.12)),
                ((-0.50, -0.22), (-0.56, -0.24), (-0.66, -0.12)),     # upper fluke
                ((-0.74, -0.04), (-0.82, -0.08), (-0.86, -0.12)),
                ((-0.80, -0.26), (-0.70, -0.34), (-0.62, -0.36)),     # notch
                ((-0.70, -0.48), (-0.72, -0.58), (-0.66, -0.66)),     # lower fluke tip
                ((-0.58, -0.58), (-0.48, -0.44), (-0.42, -0.36)),
                ((-0.25, -0.26), (0.00, -0.17), (0.20, -0.14)),
                ((0.36, -0.11), (0.45, -0.06), (0.44, 0.06)), n=14)
    body = xf(body, 1.08, 0.02, 0.04)
    sd = cv.poly(body)
    # tusk first (behind the outline of the head)
    tusk_base, tusk_tip = (0.43, 0.15), (0.97, 0.74)
    dx, dy = tusk_tip[0] - tusk_base[0], tusk_tip[1] - tusk_base[1]
    L = math.hypot(dx, dy)
    nx, ny = -dy / L, dx / L
    tusk = [(tusk_base[0] + nx * 0.055, tusk_base[1] + ny * 0.055), tusk_tip,
            (tusk_base[0] - nx * 0.055, tusk_base[1] - ny * 0.055)]
    tsd = cv.poly(tusk)
    cv.fill(tsd, INK, grow=0.035)
    cv.fill(sd, INK, grow=0.045)
    cv.fill(tsd, "#F4EDD5")
    # spiral grooves on the tusk
    u = ((cv.X - tusk_base[0]) * dx + (cv.Y - tusk_base[1]) * dy) / L
    v = ((cv.X - tusk_base[0]) * nx + (cv.Y - tusk_base[1]) * ny)
    groove = np.abs(((u * 1.0 + v * 0.9) * 14.0) % 1.0 - 0.5) - 0.12
    cv.put(cv.cov(np.maximum(tsd, groove * 0.05)), "#B9AE8C")
    cv.fill(sd, P)
    # belly
    belly = np.maximum(sd + 0.004, -(cv.Y - (-0.06 + 0.18 * (cv.X + 0.1) - 0.25 * (cv.X - 0.1) ** 2)))
    cv.fill(belly, "#F2F7F7")
    # back highlight + spots
    hl = np.maximum(sd + 0.05, (cv.Y - 0.22 - 0.25 * cv.X) * -1)
    cv.fill(hl, shade(P, 1.25), alpha=0.6)
    for (sx, sy, r) in ((-0.05, 0.22, 0.03), (-0.18, 0.15, 0.025), (0.05, 0.27, 0.022), (-0.28, 0.02, 0.022),
                        (-0.12, 0.08, 0.018)):
        cv.fill(np.maximum(cv.circle(sx, sy, r), sd), shade(P, 0.7))
    # flipper
    fl = cv.poly(path(((0.10, -0.10), (0.02, -0.22), (-0.10, -0.30), (-0.14, -0.30)),
                      ((-0.10, -0.22), (-0.02, -0.12), (0.10, -0.10)), n=10))
    cv.layer(fl, shade(P, 0.8), [(0.025, INK)])
    # eye with angry brow
    cv.fill(cv.ellipse(0.30, 0.17, 0.055, 0.045, 0.3), "#FFFFFF")
    cv.fill(cv.circle(0.318, 0.165, 0.026), INK)
    cv.fill(cv.circle(0.326, 0.175, 0.008), "#FFFFFF")
    brow = cv.poly([(0.22, 0.24), (0.40, 0.19), (0.38, 0.235), (0.24, 0.275)])
    cv.fill(brow, INK)
    # grin
    cv.fill(cv.polyline(arc(0.40, 0.08, 0.10, -1.2, -2.2, 12), 0.012), INK)
    # sparkle on tusk tip
    cv.layer(cv.poly(star_pts(0.95, 0.72, 0.09, 0.025, 4, 0.2)), "#FFFFFF", [(0.015, INK)])


def flame_poly(cx, cy, w, h, tongues=5, seed=4, lean=0.0):
    rng = random.Random(seed)
    pts = []
    # left side from base up through tongues to the top, then down the right
    n = tongues
    base_y = cy - h * 0.45
    pts += path(((cx, base_y - h * 0.10), (cx - w * 0.55, base_y - h * 0.08), (cx - w * 0.62, base_y + h * 0.18),
                 (cx - w * 0.52, base_y + h * 0.40)), n=10)
    for i in range(n):
        f = i / (n - 1)
        x_tip = cx + (f - 0.5) * w * 1.15 + lean * h * 0.2
        y_tip = cy + h * (0.25 + 0.30 * math.sin(f * math.pi) + rng.uniform(-0.05, 0.05))
        x_val = cx + (f - 0.5) * w * 1.0 + w * 0.12
        y_val = cy + h * (0.05 + 0.18 * math.sin(f * math.pi))
        pts.append((x_tip, y_tip))
        if i < n - 1:
            pts.append((x_val, y_val))
    pts += path(((cx + w * 0.52, base_y + h * 0.40), (cx + w * 0.62, base_y + h * 0.18),
                 (cx + w * 0.55, base_y - h * 0.08), (cx, base_y - h * 0.10)), n=10)
    return pts


def smooth_poly(pts, iters=2):
    for _ in range(iters):
        n = len(pts)
        out = []
        for i in range(n):
            a, b = pts[i], pts[(i + 1) % n]
            out.append((0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]))
            out.append((0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1]))
        pts = out
    return pts


def crest_INF(cv, t):
    P, S, T = t["primary"], t["secondary"], t["trim"]
    sh = cv.poly(shield_pts(0.84, 0.90, 0.5, -0.98))
    cv.layer(sh, T, [(0.06, INK), (0.035, P)])
    cv.put(cv.cov(sh) * np.clip(0.5 - cv.Y * 0.4, 0, 1) * 0.35, P)
    # horns
    for sx in (-1, 1):
        horn = path(((sx * 0.16, 0.38), (sx * 0.30, 0.50), (sx * 0.42, 0.78), (sx * 0.30, 0.98)),
                    ((sx * 0.52, 0.80), (sx * 0.52, 0.48), (sx * 0.34, 0.26)), n=14)
        hsd = cv.poly(horn)
        cv.layer(hsd, "#F1E9DA", [(0.03, INK)])
        cv.fill(np.maximum(hsd, -(cv.X * sx - 0.36)), "#C9BDA6")
    # flame demon body
    outer = smooth_poly(flame_poly(0.0, 0.0, 1.05, 1.25, tongues=5, seed=7), 2)
    mid = smooth_poly(flame_poly(0.0, -0.06, 0.80, 0.98, tongues=4, seed=9), 2)
    core = smooth_poly(flame_poly(0.0, -0.14, 0.52, 0.66, tongues=3, seed=11), 2)
    so = cv.poly(outer)
    cv.layer(so, P, [(0.04, INK)])
    cv.fill(cv.poly(mid), S)
    cv.fill(cv.poly(core), "#FFD23F")
    # face: angry eyes + grin
    for sx in (-1, 1):
        eye = cv.poly([(sx * 0.05, -0.02), (sx * 0.30, 0.10), (sx * 0.26, -0.08), (sx * 0.10, -0.10)])
        cv.layer(eye, "#FFFFFF", [(0.03, INK)])
        cv.fill(cv.circle(sx * 0.15, -0.055, 0.035), INK)
    grin = cv.poly(path(((-0.26, -0.22), (-0.12, -0.30), (0.12, -0.30), (0.26, -0.22)),
                        ((0.18, -0.42), (-0.18, -0.42), (-0.26, -0.22)), n=12))
    cv.layer(grin, "#3A0A0A", [(0.03, INK)])
    for i in range(5):
        x = -0.18 + i * 0.09
        cv.fill(cv.poly([(x - 0.035, -0.255), (x + 0.035, -0.255), (x, -0.315)]), "#FFFFFF")
    wordmark(cv, "INFERNO", (0.0, -0.66), 0.30, 1.55, "#FFFFFF", ((0.075, INK), (0.045, P)), shear=0.2,
             shadow=(0.02, -0.03, INK))


def crest_YET(cv, t):
    P, S, T = t["primary"], t["secondary"], t["trim"]
    # mountain badge
    sh = cv.poly(shield_pts(0.86, 0.80, 0.45, -0.98))
    cv.layer(sh, "#0E2A44", [(0.06, INK), (0.035, T)])
    peaks = [(-0.9, -0.2), (-0.5, 0.35), (-0.3, 0.12), (0.05, 0.62), (0.35, 0.18), (0.55, 0.40), (0.9, -0.1),
             (0.9, -1.0), (-0.9, -1.0)]
    psd = np.maximum(cv.poly(peaks), sh)
    cv.fill(psd, mixc(P, "#0E2A44", 0.35))
    snow = np.maximum(psd, -(cv.Y - 0.25 - 0.08 * np.sin(cv.X * 20)))
    cv.fill(snow, "#EAF6FF")
    # stars
    for (x, y, r) in ((-0.55, 0.58, 0.04), (0.6, 0.62, 0.035), (-0.25, 0.70, 0.025)):
        cv.fill(np.maximum(cv.poly(star_pts(x, y, r, r * 0.4, 4)), sh), "#FFFFFF")
    # yeti head: shaggy fur
    head = spikes(0.0, 0.02, 0.50, 0.62, 22, rot=0.1, jitter=0.25, seed=5, squash=0.92)
    head = smooth_poly(head, 1)
    hsd = cv.poly(head)
    cv.layer(hsd, "#F7FBFF", [(0.045, INK)])
    cv.fill(cv.circle(0.0, 0.08, 0.48), "#FFFFFF", alpha=0.0)
    # fur shading strokes
    for i in range(14):
        a = i / 14 * 6.283
        p0 = (0.40 * math.cos(a), 0.02 + 0.38 * math.sin(a))
        p1 = (0.52 * math.cos(a + 0.12), 0.02 + 0.48 * math.sin(a + 0.12))
        cv.fill(np.maximum(cv.seg(p0, p1, 0.012), hsd), "#B9CEDF")
    # face plate
    face = path(((0.0, 0.30), (0.20, 0.30), (0.36, 0.18), (0.34, -0.05)),
                ((0.32, -0.30), (0.15, -0.42), (0.0, -0.43)), n=14)
    face = face + [(-x, y) for x, y in reversed(face)][1:-1]
    fsd = cv.poly(face)
    cv.layer(fsd, P, [(0.03, INK)])
    gloss(cv, fsd, 0.25, -0.1, 0.35)
    # brows
    for sx in (-1, 1):
        brow = cv.poly([(sx * 0.02, 0.12), (sx * 0.34, 0.26), (sx * 0.33, 0.15), (sx * 0.05, 0.05)])
        cv.layer(brow, "#FFFFFF", [(0.025, INK)])
        eye = cv.ellipse(sx * 0.15, 0.03, 0.065, 0.04, -sx * 0.35)
        cv.layer(eye, "#FFF27A", [(0.022, INK)])
        cv.fill(cv.circle(sx * 0.14, 0.025, 0.022), INK)
    # nose
    cv.fill(cv.ellipse(0.0, -0.06, 0.07, 0.045), INK)
    # roaring mouth
    mouth = path(((-0.22, -0.16), (-0.10, -0.12), (0.10, -0.12), (0.22, -0.16)),
                 ((0.20, -0.36), (-0.20, -0.36), (-0.22, -0.16)), n=12)
    msd = cv.poly(mouth)
    cv.layer(msd, "#2B0F1F", [(0.028, INK)])
    cv.fill(np.maximum(cv.ellipse(0.0, -0.33, 0.12, 0.05), msd), "#C2365A")
    for sx in (-1, 1):
        cv.fill(np.maximum(cv.poly([(sx * 0.20, -0.15), (sx * 0.12, -0.14), (sx * 0.16, -0.27)]), msd - 0.01), "#FFFFFF")
        cv.fill(np.maximum(cv.poly([(sx * 0.17, -0.36), (sx * 0.09, -0.36), (sx * 0.13, -0.26)]), msd - 0.01), "#FFFFFF")
    wordmark(cv, "YETIS", (0.0, -0.70), 0.30, 1.2, "#FFFFFF", ((0.075, INK), (0.045, P)), shear=0.15,
             shadow=(0.02, -0.03, INK), grad=("#FFFFFF", "#BFE6FF"))


def crest_HAM(cv, t):
    P, S, T = t["primary"], t["secondary"], t["trim"]
    hexa = [(0.92 * math.cos(math.pi / 6 + i * math.pi / 3), 0.92 * math.sin(math.pi / 6 + i * math.pi / 3))
            for i in range(6)]
    hsd = cv.poly(hexa)
    cv.layer(hsd, P, [(0.07, INK), (0.045, S)])
    inner = cv.poly([(0.78 * math.cos(math.pi / 6 + i * math.pi / 3), 0.78 * math.sin(math.pi / 6 + i * math.pi / 3))
                     for i in range(6)])
    cv.fill(np.abs(inner) - 0.008, shade(S, 0.8))
    # brushed steel radial burst
    ang = np.arctan2(cv.Y, cv.X)
    burst = np.maximum(hsd + 0.02, np.abs(((ang / 6.283) * 24) % 1.0 - 0.5) * 0.3 - 0.06)
    cv.fill(burst, "#2A2C31")
    for (x, y) in hexa:
        cv.layer(cv.circle(x * 0.86, y * 0.86, 0.035), "#D9D9D9", [(0.015, INK)])

    def hammer(rot):
        c, s = math.cos(rot), math.sin(rot)

        def R(pts):
            return [(x * c - y * s, x * s + y * c) for x, y in pts]
        handle = cv.poly(R([(-0.045, -0.80), (0.045, -0.80), (0.055, 0.40), (-0.055, 0.40)]))
        cv.layer(handle, "#8B5A2B", [(0.035, INK)])
        grip = cv.poly(R([(-0.05, -0.80), (0.05, -0.80), (0.055, -0.45), (-0.055, -0.45)]))
        cv.fill(grip, S)
        for k in range(4):
            yy = -0.78 + k * 0.09
            cv.fill(cv.poly(R([(-0.055, yy), (0.055, yy + 0.03), (0.055, yy + 0.05), (-0.055, yy + 0.02)])),
                    shade(S, 0.7))
        headp = R([(-0.30, 0.38), (0.30, 0.38), (0.33, 0.42), (0.33, 0.66), (0.30, 0.70), (-0.30, 0.70),
                   (-0.33, 0.66), (-0.33, 0.42)])
        hs = cv.poly(headp)
        cv.layer(hs, "#C9CDD3", [(0.04, INK)])
        # bevel shading
        top = cv.poly(R([(-0.30, 0.60), (0.30, 0.60), (0.30, 0.70), (-0.30, 0.70)]))
        cv.fill(np.maximum(top, hs), "#EEF1F4")
        bot = cv.poly(R([(-0.30, 0.38), (0.30, 0.38), (0.30, 0.45), (-0.30, 0.45)]))
        cv.fill(np.maximum(bot, hs), "#8E949C")
        band = cv.poly(R([(-0.07, 0.38), (0.07, 0.38), (0.07, 0.70), (-0.07, 0.70)]))
        cv.fill(np.maximum(band, hs), S)
    hammer(math.radians(38))
    hammer(math.radians(-38))
    # sparks at the cross
    cv.layer(cv.poly(star_pts(0.0, 0.42, 0.16, 0.05, 8, 0.1)), "#FFF3B0", [(0.025, INK)])
    # banner
    ban = cv.poly([(-0.98, -0.42), (0.98, -0.42), (0.88, -0.56), (0.98, -0.72), (-0.98, -0.72), (-0.88, -0.56)])
    cv.layer(ban, S, [(0.04, INK)])
    wordmark(cv, "HAMMERS", (0.0, -0.57), 0.22, 1.50, P, ((0.025, "#FFFFFF"),), shear=0.0, font=dr.FONT_IMPACT)
    m = cv.text("STEEL VALLEY", font=dr.FONT_DIN, center=(0, 0.80), height=0.10, width=0.62)
    cv.put(cv.grow(m, 0.02), INK)
    cv.put(m, S)


def crest_BRW(cv, t):
    P, S, T = t["primary"], t["secondary"], t["trim"]
    roundel(cv, "BAYOU", "BRAWLERS", S, shade(P, 0.55), INK, T, P)
    # swamp reeds
    for i, x in enumerate((-0.52, -0.42, 0.44, 0.54)):
        cv.fill(np.maximum(cv.seg((x, -0.6), (x + 0.03 * (1 if i % 2 else -1), 0.05 + 0.1 * (i % 2)), 0.018),
                           cv.circle(0, 0, 0.66)), shade(P, 0.35))
    # gator head profile, facing right, jaws open
    upper = path(((-0.62, 0.10), (-0.50, 0.34), (-0.25, 0.40), (-0.05, 0.30)),
                 ((0.20, 0.22), (0.55, 0.20), (0.78, 0.17)),
                 ((0.90, 0.16), (0.92, 0.07), (0.84, 0.04)),
                 ((0.55, 0.03), (0.10, -0.02), (-0.20, -0.02)),
                 ((-0.45, -0.02), (-0.62, 0.0), (-0.62, 0.10)), n=12)
    lower = path(((-0.50, -0.10), (-0.20, -0.12), (0.30, -0.20), (0.72, -0.30)),
                 ((0.82, -0.34), (0.80, -0.42), (0.70, -0.42)),
                 ((0.30, -0.40), (-0.20, -0.36), (-0.48, -0.28)),
                 ((-0.60, -0.24), (-0.62, -0.12), (-0.50, -0.10)), n=12)
    ush = cv.poly(xf(upper, 1.0, -0.05, 0.06))
    lsh = cv.poly(xf(lower, 1.0, -0.05, 0.06))
    mouth = cv.poly(xf([(-0.40, 0.0), (0.82, 0.04), (0.72, -0.28), (-0.40, -0.12)], 1.0, -0.05, 0.06))
    cv.fill(np.minimum(np.minimum(ush, lsh), mouth), INK, grow=0.045)
    cv.fill(mouth, "#5A0E14")
    # teeth
    for i in range(8):
        x = -0.25 + i * 0.13
        cv.fill(cv.poly([(x - 0.04, 0.04), (x + 0.04, 0.035), (x + 0.005, -0.06)]), "#FFFFFF")
        x2 = -0.20 + i * 0.12
        y2 = -0.10 - 0.025 * i
        cv.fill(cv.poly([(x2 - 0.035, y2 - 0.02), (x2 + 0.035, y2 - 0.03), (x2, y2 + 0.07)]), "#FFFFFF")
    cv.layer(lsh, shade(P, 1.05), [(0.0, INK)])
    cv.fill(np.maximum(lsh, -(cv.Y + 0.26 - 0.12 * cv.X)), "#E8D9A0")
    cv.fill(ush, P)
    # scutes
    for i in range(6):
        x = -0.50 + i * 0.12
        cv.fill(np.maximum(cv.circle(x, 0.36 - i * 0.015, 0.045), ush - 0.005), shade(P, 0.7))
    cv.fill(np.maximum(ush, -(cv.Y - 0.13 + 0.05 * cv.X)), shade(P, 1.2), alpha=0.5)
    # eye bump + eye
    cv.layer(cv.ellipse(-0.28, 0.40, 0.13, 0.09), P, [(0.035, INK)])
    cv.fill(cv.ellipse(-0.27, 0.40, 0.075, 0.055), "#FFE14D")
    cv.fill(cv.ellipse(-0.26, 0.40, 0.018, 0.05), INK)
    cv.fill(cv.poly([(-0.42, 0.50), (-0.12, 0.42), (-0.14, 0.48), (-0.40, 0.56)]), INK)
    cv.fill(cv.circle(0.74, 0.22, 0.03), INK)


def crest_VIP(cv, t):
    P, S, T = t["primary"], t["secondary"], t["trim"]
    dia = cv.box(0, 0, 0.64, 0.64, 0.10, math.pi / 4)
    cv.layer(dia, "#1B0B33", [(0.08, INK), (0.055, P), (0.03, INK)])
    # neon grid
    g = np.maximum(dia + 0.05, np.minimum(np.abs((cv.X * 6) % 1 - 0.5), np.abs((cv.Y * 6) % 1 - 0.5)) * 0.17 - 0.075)
    cv.fill(g, S, alpha=0.45)
    # coiled body: thick S curve
    coil = path(((-0.55, -0.55), (-0.10, -0.85), (0.60, -0.55), (0.40, -0.15)),
                ((0.20, 0.20), (-0.55, 0.05), (-0.40, 0.40)), n=40)
    bsd = cv.polyline(coil, 0.11)
    cv.fill(bsd, INK, grow=0.04)
    cv.fill(bsd, S)
    # belly scales along the coil
    stripes = np.abs(((cv.X * 0.7 + cv.Y) * 9) % 1 - 0.5) - 0.16
    cv.fill(np.maximum(bsd + 0.03, stripes * 0.05), shade(S, 1.35))
    # head: wide spade-shaped viper head seen from the front, brow plates, slit eyes, fangs + forked tongue
    hc_ = (-0.30, 0.36)
    half = path(((0.0, 0.34), (0.14, 0.34), (0.30, 0.30), (0.36, 0.16)),
                ((0.40, 0.04), (0.34, -0.06), (0.22, -0.16)),
                ((0.14, -0.23), (0.07, -0.27), (0.0, -0.27)), n=12)
    head = half + [(-x, y) for x, y in reversed(half)][1:-1]
    head = xf(head, 1.05, hc_[0], hc_[1])
    hsd = cv.poly(head)
    # fangs + tongue under the snout (drawn first, the head overlaps their roots)
    for sx in (-1, 1):
        fx = hc_[0] + sx * 0.085
        fang = cv.poly([(fx - 0.03, hc_[1] - 0.20), (fx + 0.03, hc_[1] - 0.20), (fx + sx * 0.005, hc_[1] - 0.42)])
        cv.layer(fang, "#FFFFFF", [(0.022, INK)])
    tongue = cv.polyline([(hc_[0], hc_[1] - 0.22), (hc_[0], hc_[1] - 0.40)], 0.016)
    tongue = np.minimum(tongue, cv.seg((hc_[0], hc_[1] - 0.40), (hc_[0] - 0.05, hc_[1] - 0.50), 0.015))
    tongue = np.minimum(tongue, cv.seg((hc_[0], hc_[1] - 0.40), (hc_[0] + 0.05, hc_[1] - 0.50), 0.015))
    cv.layer(tongue, "#FF2A55", [(0.018, INK)])
    cv.layer(hsd, P, [(0.045, INK)])
    # scale pattern + gloss
    sc = np.abs(((cv.X - hc_[0]) * 11 + (cv.Y - hc_[1]) * 11) % 1 - 0.5) + np.abs(((cv.X - hc_[0]) * 11 - (cv.Y - hc_[1]) * 11) % 1 - 0.5)
    cv.fill(np.maximum(hsd + 0.03, (sc - 0.62) * 0.05), dr.shade(P, 0.78), alpha=0.7)
    gloss(cv, hsd, 0.28, hc_[1] - 0.05, hc_[1] + 0.36)
    # snout plate + nostrils
    snout = cv.poly(xf([(-0.12, -0.05), (0.12, -0.05), (0.07, -0.24), (-0.07, -0.24)], 1.05, hc_[0], hc_[1]))
    cv.fill(np.maximum(snout, hsd + 0.01), dr.shade(P, 1.18))
    for sx in (-1, 1):
        cv.fill(cv.ellipse(hc_[0] + sx * 0.04, hc_[1] - 0.19, 0.016, 0.01, sx * 0.5), INK)
    # brow plates and angry slit eyes
    for sx in (-1, 1):
        brow = cv.poly(xf([(sx * 0.05, 0.10), (sx * 0.36, 0.22), (sx * 0.33, 0.12), (sx * 0.07, 0.03)], 1.05,
                          hc_[0], hc_[1]))
        cv.layer(brow, S, [(0.02, INK)])
        eye = cv.poly(xf([(sx * 0.09, 0.02), (sx * 0.31, 0.10), (sx * 0.27, -0.03)], 1.05, hc_[0], hc_[1]))
        cv.layer(eye, "#C6FF3A", [(0.02, INK)])
        cv.fill(cv.ellipse(hc_[0] + sx * 0.21, hc_[1] + 0.035, 0.011, 0.040), INK)
    wordmark(cv, "VIPERS", (0.12, -0.56), 0.28, 1.25, "#FFFFFF", ((0.07, INK), (0.045, S)), shear=0.22,
             grad=("#FFFFFF", shade(P, 1.4)))


def crest_GRZ(cv, t):
    P, S, T = t["primary"], t["secondary"], t["trim"]
    sh = cv.poly(shield_pts(0.86, 0.92, 0.5, -0.98))
    cv.layer(sh, T, [(0.065, INK), (0.04, S)])
    # pines
    for (x, s) in ((-0.62, 0.9), (-0.45, 1.1), (0.48, 1.05), (0.64, 0.85)):
        pine = [(x, 0.62 * s - 0.1), (x + 0.13 * s, 0.1 * s - 0.1), (x + 0.05 * s, 0.12 * s - 0.1),
                (x + 0.16 * s, -0.25 * s - 0.1), (x - 0.16 * s, -0.25 * s - 0.1), (x - 0.05 * s, 0.12 * s - 0.1),
                (x - 0.13 * s, 0.1 * s - 0.1)]
        cv.fill(np.maximum(cv.poly(pine), sh), mixc(T, P, 0.35))
    # ears
    for sx in (-1, 1):
        cv.layer(cv.circle(sx * 0.40, 0.48, 0.17), P, [(0.04, INK)])
        cv.fill(cv.circle(sx * 0.40, 0.47, 0.09), shade(S, 0.85))
    # head with fur cheeks
    head = smooth_poly(spikes(0.0, 0.06, 0.50, 0.56, 16, rot=-math.pi / 2, jitter=0.12, seed=2, squash=0.9), 1)
    hsd = cv.poly(head)
    cv.layer(hsd, P, [(0.045, INK)])
    gloss(cv, hsd, 0.18, 0.0, 0.5)
    # muzzle
    mz = cv.ellipse(0.0, -0.16, 0.27, 0.22)
    cv.layer(mz, T, [(0.03, INK)])
    # brows/eyes
    for sx in (-1, 1):
        brow = cv.poly([(sx * 0.04, 0.12), (sx * 0.33, 0.26), (sx * 0.32, 0.16), (sx * 0.06, 0.04)])
        cv.fill(brow, INK)
        eye = cv.poly([(sx * 0.08, 0.06), (sx * 0.28, 0.14), (sx * 0.25, 0.02)])
        cv.layer(eye, S, [(0.018, INK)])
        cv.fill(cv.circle(sx * 0.18, 0.06, 0.022), INK)
    # nose
    nose = cv.poly(path(((-0.11, -0.02), (-0.05, 0.03), (0.05, 0.03), (0.11, -0.02)),
                        ((0.06, -0.10), (-0.06, -0.10), (-0.11, -0.02)), n=10))
    cv.fill(nose, INK)
    cv.fill(cv.ellipse(-0.03, 0.0, 0.03, 0.015), "#5A5A5A")
    # roaring mouth
    mouth = path(((-0.19, -0.16), (-0.08, -0.13), (0.08, -0.13), (0.19, -0.16)),
                 ((0.16, -0.38), (-0.16, -0.38), (-0.19, -0.16)), n=12)
    msd = cv.poly(mouth)
    cv.layer(msd, "#3A0B0B", [(0.025, INK)])
    cv.fill(np.maximum(cv.ellipse(0.0, -0.34, 0.10, 0.05), msd), "#D2475A")
    for sx in (-1, 1):
        cv.fill(np.maximum(cv.poly([(sx * 0.17, -0.15), (sx * 0.09, -0.14), (sx * 0.13, -0.26)]), msd - 0.005), "#FFFFFF")
        cv.fill(np.maximum(cv.poly([(sx * 0.14, -0.37), (sx * 0.07, -0.37), (sx * 0.11, -0.28)]), msd - 0.005), "#FFFFFF")
    ban = cv.poly([(-0.98, -0.50), (0.98, -0.50), (0.88, -0.63), (0.98, -0.78), (-0.98, -0.78), (-0.88, -0.63)])
    cv.layer(ban, S, [(0.04, INK)])
    wordmark(cv, "GRIZZLIES", (0.0, -0.64), 0.20, 1.55, "#FFFFFF", ((0.03, INK),), shear=0.0)


def crest_COM(cv, t):
    P, S, T = t["primary"], t["secondary"], t["trim"]
    cv.fill(cv.circle(0, 0, 0.90), INK)
    cv.fill(cv.circle(0, 0, 0.86), T)
    cv.fill(cv.circle(0, 0, 0.80), P)
    disc = cv.circle(0, 0, 0.80)
    cv.put(cv.cov(disc) * np.clip(0.6 - np.hypot(cv.X - 0.3, cv.Y - 0.3), 0, 1) * 0.5, "#6FA0FF")
    # starfield
    rng = random.Random(8)
    for i in range(28):
        x, y = rng.uniform(-0.75, 0.75), rng.uniform(-0.75, 0.75)
        if x * x + y * y < 0.6:
            r = rng.uniform(0.008, 0.02)
            cv.fill(np.maximum(cv.poly(star_pts(x, y, r * 2.2, r * 0.7, 4)), disc), "#FFFFFF", alpha=0.85)
    # orbit ring
    orb = cv.ellipse(0.0, 0.0, 0.98, 0.34, 0.35)
    ring = np.abs(orb) - 0.03
    cv.fill(np.maximum(ring, -(cv.Y * 0.3 + cv.X * 0.0 + 0.0) + 0.0 - 1.0), INK, grow=0.025)
    cv.fill(ring, S)
    # tail swooshes (lower-left to the comet head at upper right)
    head_c = (0.34, 0.30)
    for i, (c, w) in enumerate(((S, 0.20), (T, 0.13), (P, 0.07))):
        tail = []
        for k in range(30):
            u = k / 29
            ang = math.radians(215 + 10 * math.sin(u * 2.5))
            r = 0.05 + 1.05 * u
            cx = head_c[0] + r * math.cos(ang)
            cy = head_c[1] + r * math.sin(ang) + 0.12 * math.sin(u * 3.0)
            tail.append((cx, cy, w * (1 - u) ** 0.8))
        left = [(x - math.sin(math.radians(215)) * ww, y + math.cos(math.radians(215)) * ww) for x, y, ww in tail]
        right = [(x + math.sin(math.radians(215)) * ww, y - math.cos(math.radians(215)) * ww) for x, y, ww in tail]
        tsd = cv.poly(left + list(reversed(right)))
        if i == 0:
            cv.fill(tsd, INK, grow=0.04)
        cv.fill(tsd, c)
    hsd = cv.circle(head_c[0], head_c[1], 0.19)
    cv.layer(hsd, "#FFFFFF", [(0.04, INK)])
    cv.fill(cv.circle(head_c[0] + 0.05, head_c[1] + 0.05, 0.10), "#FFF6C9")
    cv.layer(cv.poly(star_pts(head_c[0] + 0.03, head_c[1] + 0.02, 0.13, 0.05, 5)), "#FFD23F", [(0.0, INK)])
    wordmark(cv, "COMETS", (0.0, -0.60), 0.30, 1.40, "#FFFFFF", ((0.07, INK), (0.045, S)), shear=0.22,
             shadow=(0.025, -0.03, INK))
    m = cv.text("ROCKET CITY", font=dr.FONT_DIN, center=(0, 0.66), height=0.10, width=0.55)
    cv.put(cv.grow(m, 0.02), INK)
    cv.put(m, "#FFFFFF")


CRESTS = {"NAR": crest_NAR, "INF": crest_INF, "YET": crest_YET, "HAM": crest_HAM, "BRW": crest_BRW,
          "VIP": crest_VIP, "GRZ": crest_GRZ, "COM": crest_COM}


def make_logo(t, res=1024):
    cv = Canvas(res, res, (-1.0, -1.0, 1.0, 1.0))
    CRESTS[t["id"]](cv, t)
    return cv


# ---------------------------------------------------------------------------
# Banners
# ---------------------------------------------------------------------------
def make_banner(t, logo_rgba):
    W, H = 1024, 2048
    cv = Canvas(W, H, (-0.5, -1.0, 0.5, 1.0))
    P, S, T = t["primary"], t["secondary"], t["trim"]
    bg = P if t["id"] not in ("YET",) else "#123B5E"
    body = cv.poly([(-0.48, 1.0), (0.48, 1.0), (0.48, -0.78), (0.0, -0.98), (-0.48, -0.78)])
    cv.fill(body, bg)
    cv.put(cv.cov(body) * np.clip(0.25 - cv.Y * 0.15, 0, 0.4), "#000000")
    # side stripes
    for sx in (-1, 1):
        st = np.maximum(body, np.abs(cv.X - sx * 0.40) - 0.025)
        cv.fill(st, S)
        st2 = np.maximum(body, np.abs(cv.X - sx * 0.355) - 0.01)
        cv.fill(st2, T)
    # top header
    cv.fill(cv.box(0, 0.94, 0.5, 0.06), INK)
    cv.stamp(logo_rgba, (0.0, 0.40), 0.78)
    m = cv.text(t["city"], font=dr.FONT_DIN, center=(0, -0.10), height=0.07, width=0.70)
    cv.put(cv.grow(m, 0.012), INK)
    cv.put(m, T if t["id"] != "HAM" else S)
    wordmark(cv, t["name"], (0, -0.24), 0.14, 0.78, "#FFFFFF", ((0.03, INK), (0.018, S)), shear=0.15)
    for i, yr in enumerate(("CHAMPIONS", "2019  •  2023")):
        m = cv.text(yr, font=dr.FONT_IMPACT if i == 0 else dr.FONT_DIN, center=(0, -0.44 - i * 0.12),
                    height=0.08 if i == 0 else 0.07, width=0.62)
        cv.put(cv.grow(m, 0.01), INK)
        cv.put(m, S if i == 0 else "#FFFFFF")
    for sx in (-0.2, 0.0, 0.2):
        cv.layer(cv.poly(star_pts(sx, -0.70, 0.05, 0.02)), S, [(0.01, INK)])
    # edge trim on the pennant tip
    edge = np.abs(body) - 0.006
    cv.fill(np.maximum(edge, -(cv.Y - 0.88)), T)
    return cv


# ---------------------------------------------------------------------------
# Game logo
# ---------------------------------------------------------------------------
def make_game_logo():
    W, H = 2048, 1024
    cv = Canvas(W, H, (-2.0, -1.0, 2.0, 1.0))
    NAVY = "#06142B"
    # crossed sticks behind
    for sx in (-1, 1):
        a = (sx * 1.45, -0.85)
        b = (-sx * 0.95, 0.92)
        shaft = cv.seg(a, b, 0.05)
        cv.layer(shaft, "#E9E2D0", [(0.04, NAVY)])
        blade = cv.poly([(a[0], a[1]), (a[0] + sx * 0.42, a[1] - 0.02), (a[0] + sx * 0.46, a[1] + 0.10),
                         (a[0] + sx * 0.05, a[1] + 0.12)])
        cv.layer(blade, "#1E1E22", [(0.04, NAVY)])
        tape = np.maximum(cv.seg((b[0] - (b[0] - a[0]) * 0.10, b[1] - (b[1] - a[1]) * 0.10), b, 0.055), -1)
        cv.fill(tape, "#16161A")
    # ice shard burst behind the wordmark
    rng = random.Random(3)
    burst = []
    for i in range(36):
        ang = 2 * math.pi * i / 36
        r = (1.05 if i % 2 == 0 else 0.62) * rng.uniform(0.85, 1.15)
        burst.append((r * 1.75 * math.cos(ang), r * 0.82 * math.sin(ang)))
    bsd = cv.poly(burst)
    cv.layer(bsd, cv.rgrad((0, 0), 1.6, "#FFFFFF", "#7FD3FF"), [(0.05, NAVY)])
    for i in range(0, 36, 2):
        ang = 2 * math.pi * i / 36
        cv.fill(np.maximum(cv.seg((0, 0), (1.7 * math.cos(ang), 0.8 * math.sin(ang)), 0.006), bsd), "#9EDCFF")
    # ICE (icy gradient) + RIOT (hot gradient)
    ice = cv.text("ICE", font=dr.FONT_IMPACT, center=(-0.86, 0.06), height=0.98, width=1.5, shear=0.18)
    riot = cv.text("RIOT", font=dr.FONT_IMPACT, center=(0.80, 0.06), height=0.98, width=1.95, shear=0.18)
    both = np.maximum(ice, riot)
    cv.put(cv.grow(both, 0.10), NAVY)
    cv.put(cv.grow(both, 0.065), "#FFFFFF")
    cv.put(cv.grow(both, 0.035), NAVY)
    cv.put(ice, cv.lgrad((0, 0.55), (0, -0.45), "#FFFFFF", "#38B6FF"))
    cv.put(riot, cv.lgrad((0, 0.55), (0, -0.45), "#FFE14A", "#FF2A12"))
    # gloss band on the letters
    band = np.clip((cv.Y - 0.10) * 6, 0, 1) * (cv.Y < 0.45)
    cv.put(both * band * 0.35, "#FFFFFF")
    # cracks in ICE
    for (p0, p1) in (((-1.25, 0.4), (-1.05, 0.05)), ((-1.05, 0.05), (-1.15, -0.3)), ((-0.65, 0.45), (-0.55, 0.0)),
                     ((-0.55, 0.0), (-0.40, -0.25))):
        cv.fill(np.maximum(cv.seg(p0, p1, 0.012), cv.cov_sd(ice)), "#1A6FB8")
    # tagline ribbon
    rib = cv.poly([(-1.25, -0.62), (1.25, -0.62), (1.15, -0.74), (1.25, -0.86), (-1.25, -0.86), (-1.15, -0.74)])
    cv.layer(rib, "#E0182D", [(0.035, NAVY)])
    m = cv.text("ARCADE HOCKEY MAYHEM", font=dr.FONT_DIN, center=(0, -0.74), height=0.12, width=2.0, spacing=1.12)
    cv.put(m, "#FFFFFF")
    # puck
    pk = cv.ellipse(0.0, -0.40, 0.26, 0.09)
    cv.layer(pk, "#111114", [(0.03, "#FFFFFF"), (0.055, NAVY)])
    cv.fill(cv.ellipse(0.0, -0.37, 0.26, 0.07), "#2A2A30")
    return cv


# ---------------------------------------------------------------------------
# Board ads (fictional sponsors)
# ---------------------------------------------------------------------------
ADS = [
    dict(text="FROSTBITE COLA", sub="SO COLD IT HURTS", bg="#C8102E", fg="#FFFFFF", acc="#79C7F2", style="wave"),
    dict(text="PUCK YEAH!", sub="ENERGY DRINK", bg="#111111", fg="#C6FF3A", acc="#FF2A55", style="bolt"),
    dict(text="TOOTHLESS DENTAL", sub="WE'LL FIX THAT SMILE", bg="#FFFFFF", fg="#1F4FD8", acc="#E0182D", style="tooth"),
    dict(text="PENALTY BOX PIZZA", sub="2 MINUTES OR IT'S FREE", bg="#F2B705", fg="#3A0B0B", acc="#C8102E", style="stripe"),
    dict(text="MOOSEJAW INSURANCE", sub="COVERED FROM CHECK TO CHECK", bg="#0B2545", fg="#FFFFFF", acc="#F2B705", style="plain"),
    dict(text="BLUE LINE BANK", sub="WE NEVER GO OFFSIDE", bg="#1F4FD8", fg="#FFFFFF", acc="#79C7F2", style="lines"),
    dict(text="ICY DOGS", sub="HOT DOGS SERVED COLD", bg="#79C7F2", fg="#0B2545", acc="#E0182D", style="wave"),
    dict(text="BIG LUMBER", sub="HARDWARE & HOCKEY STICKS", bg="#6B3D1F", fg="#F3E5C4", acc="#F27F1B", style="stripe"),
    dict(text="GLOVE DROP", sub="DATING APP - FIGHT FOR LOVE", bg="#E6007E", fg="#FFFFFF", acc="#7B2CFF", style="heart"),
    dict(text="SLAPSHOT SODA", sub="CRACK ONE OPEN", bg="#FF6B12", fg="#FFFFFF", acc="#111111", style="bolt"),
    dict(text="GOON SQUAD", sub="SECURITY SERVICES", bg="#17181B", fg="#F2B705", acc="#FFFFFF", style="plain"),
    dict(text="MAPLE CRUNCH", sub="BREAKFAST OF ENFORCERS", bg="#F3E5C4", fg="#8E1B12", acc="#C8102E", style="leaf"),
    dict(text="SLUSH BUCKET", sub="FROZEN TREATS - EXTRA BRAIN FREEZE", bg="#3E7B27", fg="#FFFFFF", acc="#E3B22B", style="lines"),
    dict(text="5-HOLE DONUTS", sub="SLIPS RIGHT THROUGH", bg="#FFB3D1", fg="#7A1040", acc="#FFFFFF", style="ring"),
    dict(text="ICE RIOT", sub="ARCADE HOCKEY MAYHEM", bg="#06142B", fg="#FFFFFF", acc="#38B6FF", style="logo"),
    dict(text="SNOWPLOW TRUCKS", sub="BUILT FOR THE CORNERS", bg="#A9B4C0", fg="#17181B", acc="#E0182D", style="stripe"),
]


def draw_ad(cv, ad, cx, cy, w, h, game_logo=None):
    x0, x1, y0, y1 = cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2
    cell = cv.box(cx, cy, w / 2, h / 2)
    cv.fill(cell, ad["bg"])
    st = ad["style"]
    acc = ad["acc"]
    if st == "wave":
        wv = np.maximum(cell, (cv.Y - (y0 + h * 0.18 + h * 0.08 * np.sin((cv.X - x0) / w * 18))))
        cv.fill(wv, acc)
    elif st == "bolt":
        for k in (0.07, 0.93):
            bx = x0 + w * k
            cv.fill(cv.poly([(bx - h * 0.10, y1 - h * 0.1), (bx + h * 0.12, y1 - h * 0.1), (bx + h * 0.02, cy + h * 0.02),
                             (bx + h * 0.14, cy + h * 0.02), (bx - h * 0.12, y0 + h * 0.08), (bx - h * 0.02, cy - h * 0.06),
                             (bx - h * 0.14, cy - h * 0.06)]), acc)
    elif st == "stripe":
        for k in (0.10, 0.16):
            cv.fill(np.maximum(cell, np.abs(cv.Y - (y0 + h * k)) - h * 0.025), acc)
            cv.fill(np.maximum(cell, np.abs(cv.Y - (y1 - h * k)) - h * 0.025), acc)
    elif st == "lines":
        sl = np.abs(((cv.X - cv.Y * 0.6) / (h * 0.25)) % 1 - 0.5) - 0.18
        cv.fill(np.maximum(np.maximum(cell, sl * h * 0.1), -(cv.X - (x1 - w * 0.18))), acc, alpha=0.8)
    elif st == "tooth":
        tx = x0 + w * 0.09
        tooth = path(((tx - h * 0.2, cy + h * 0.25), (tx - h * 0.2, cy + h * 0.38), (tx + h * 0.2, cy + h * 0.38),
                      (tx + h * 0.2, cy + h * 0.25)),
                     ((tx + h * 0.2, cy - h * 0.1), (tx + h * 0.12, cy - h * 0.35), (tx + h * 0.06, cy - h * 0.35)),
                     ((tx, cy - h * 0.05), (tx, cy - h * 0.05), (tx - h * 0.06, cy - h * 0.35)),
                     ((tx - h * 0.12, cy - h * 0.35), (tx - h * 0.2, cy - h * 0.1), (tx - h * 0.2, cy + h * 0.25)), n=8)
        cv.layer(cv.poly(tooth), "#FFFFFF", [(h * 0.03, ad["fg"])])
        cv.fill(np.maximum(cell, (cv.Y - (y0 + h * 0.10))), acc)
    elif st == "heart":
        hx = x0 + w * 0.09
        heart = cv.poly(path(((hx, cy - h * 0.32), (hx - h * 0.4, cy), (hx - h * 0.25, cy + h * 0.38), (hx, cy + h * 0.18)),
                             ((hx + h * 0.25, cy + h * 0.38), (hx + h * 0.4, cy), (hx, cy - h * 0.32)), n=12))
        cv.layer(heart, acc, [(h * 0.03, "#FFFFFF")])
    elif st == "leaf":
        lx = x0 + w * 0.09
        leaf = [(lx + 0.33 * h * math.cos(a) * (0.55 + 0.45 * abs(math.cos(2.5 * a))),
                 cy + 0.33 * h * math.sin(a) * (0.55 + 0.45 * abs(math.cos(2.5 * a)))) for a in
                np.linspace(0, 2 * math.pi, 80, endpoint=False)]
        cv.fill(cv.poly(leaf), acc)
    elif st == "ring":
        rx = x0 + w * 0.09
        cv.fill(cv.ring(rx, cy, h * 0.24, h * 0.18), "#C8803A")
        cv.fill(cv.ring(rx, cy, h * 0.24, h * 0.12), acc)
    # border
    cv.fill(np.maximum(cell, -(cell + h * 0.035)), ad["fg"] if st != "logo" else acc)
    if st == "logo" and game_logo is not None:
        cv.stamp(game_logo, (cx, cy), w * 0.42)
        return
    has_icon = st in ("tooth", "heart", "leaf", "ring")
    tx = cx + (w * 0.06 if has_icon else 0.0)
    m = cv.text(ad["text"], font=dr.FONT_IMPACT, center=(tx, cy + h * 0.10), height=h * 0.48,
                width=w * (0.70 if has_icon else 0.78), shear=0.12)
    cv.put(cv.grow(m, h * 0.025), mixc(ad["bg"], "#000000", 0.45))
    cv.put(m, ad["fg"])
    m = cv.text(ad["sub"], font=dr.FONT_DIN, center=(tx, cy - h * 0.29), height=h * 0.15, width=w * 0.62,
                spacing=1.1)
    cv.put(m, ad["fg"] if st not in ("wave",) else "#FFFFFF")


def make_board_ads(game_logo):
    W = H = 2048
    cv = Canvas(W, H, (0.0, 0.0, 2.0, 2.0))
    cw, ch = 1.0, 0.25
    for i, ad in enumerate(ADS):
        c, r = i % 2, i // 2
        # row 0 at the TOP of the image
        cx = c * cw + cw / 2
        cy = 2.0 - (r * ch + ch / 2)
        draw_ad(cv, ad, cx, cy, cw * 0.995, ch * 0.985, game_logo)
    return cv


# ---------------------------------------------------------------------------
# Jersey digits
# ---------------------------------------------------------------------------
def make_digits():
    W, H = 2048, 256
    cv = Canvas(W, H, (0.0, 0.0, 10.0, 1.25))
    fill = np.zeros((H, W), np.float32)
    outl = np.zeros((H, W), np.float32)
    for d in range(10):
        m = cv.text(str(d), font=dr.FONT_IMPACT, center=(d + 0.5, 0.625), height=1.0, width=0.80)
        fill = np.maximum(fill, m)
        outl = np.maximum(outl, cv.grow(m, 0.075))
    img = np.zeros((H, W, 4), np.float32)
    img[..., 0] = fill
    img[..., 1] = outl
    img[..., 3] = 1.0
    return img


# ---------------------------------------------------------------------------
def main():
    hc.reset_scene()
    out = {}
    logos = {}
    if want("teams"):
        teams_json = {}
        for t in TEAMS:
            teams_json[t["id"]] = {
                "city": t["city"], "name": t["name"],
                "primary": eh.rnd_list(eh.lin(t["primary"])), "secondary": eh.rnd_list(eh.lin(t["secondary"])),
                "trim": eh.rnd_list(eh.lin(t["trim"])),
                "primary_srgb": t["primary"], "secondary_srgb": t["secondary"], "trim_srgb": t["trim"],
                "logo": "T_Logo_" + t["id"], "banner": "T_Banner_" + t["id"],
            }
        with open(os.path.join(hc.EXPORT_DIR, "teams.json"), "w") as f:
            json.dump({"teams": teams_json, "order": [t["id"] for t in TEAMS],
                       "referee": {"jersey": eh.rnd_list(eh.lin("#F2F2F2")), "stripe": eh.rnd_list(eh.lin("#111111"))}},
                      f, indent=2)
        print("WROTE teams.json")
    for t in TEAMS:
        if want("logos") or want(t["id"]):
            cv = make_logo(t)
            p = os.path.join(TEX, "T_Logo_%s.png" % t["id"])
            cv.save(p)
            logos[t["id"]] = cv.rgba()
        else:
            p = os.path.join(TEX, "T_Logo_%s.png" % t["id"])
            if os.path.exists(p):
                logos[t["id"]] = eh.load_png(p)
    if want("banners"):
        for t in TEAMS:
            if t["id"] in logos:
                make_banner(t, logos[t["id"]]).save(os.path.join(TEX, "T_Banner_%s.png" % t["id"]), opaque=False)
    game_logo = None
    if want("gamelogo"):
        cv = make_game_logo()
        cv.save(os.path.join(TEX, "T_LogoIceRiot.png"))
        game_logo = cv.rgba()
    else:
        p = os.path.join(TEX, "T_LogoIceRiot.png")
        if os.path.exists(p):
            game_logo = eh.load_png(p)
    if want("ads"):
        make_board_ads(game_logo).save(os.path.join(TEX, "T_BoardAds.png"), opaque=True)
    if want("digits"):
        eh.save_png(make_digits(), os.path.join(TEX, "T_Digits.png"))
    # contact sheet of crests on grey
    if logos:
        sheet = np.zeros((2 * 512, 4 * 512, 4), np.float32)
        sheet[..., :3] = 0.35
        sheet[..., 3] = 1
        for i, t in enumerate(TEAMS):
            if t["id"] not in logos:
                continue
            img = eh.downsample(logos[t["id"]], 2)
            r, c = divmod(i, 4)
            y0 = (1 - r) * 512
            x0 = c * 512
            a = img[..., 3:4]
            sheet[y0:y0 + 512, x0:x0 + 512, :3] = sheet[y0:y0 + 512, x0:x0 + 512, :3] * (1 - a) + img[..., :3] * a
        eh.save_png(sheet, os.path.join(hc.PREVIEW_DIR, "branding_crests.png"))
    eh.cleanup_tmp()
    print("BRANDING DONE")


if __name__ == "__main__":
    main()
