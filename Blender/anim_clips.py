"""ICE RIOT clip library: every A_<Name> from Docs/ASSET_SPEC.md authored as keyed pose parameters.

See anim_core.py for the parameter meanings.  Units: meters, degrees, seconds.
Character faces -Y, left = +X, right = -X.  Right-handed shooter: blade on the right (-X) side.
"""

import math

import ir_rig as rig
from anim_core import Clip

PH = rig.PUCK_HALF_T
CLIPS = {}
GOALIE = set()


def clip(name, length, loop=False, goalie=False, lag=None, **events):
    c = Clip(name, length, loop, events, lag)
    CLIPS[name] = c
    if goalie:
        GOALIE.add(name)
    return c


def M(*ds, **kw):
    out = {}
    for d in ds:
        for k, v in d.items():
            out[k] = list(v) if isinstance(v, list) else v
    out.update(kw)
    return out


def stk(C, butt, tilt=0.0):
    """Stick from a blade (cradle) point and the point the butt end should head toward."""
    dx, dy, dz = butt[0] - C[0], butt[1] - C[1], butt[2] - C[2]
    elev = math.degrees(math.atan2(dz, math.hypot(dx, dy)))
    return dict(sc=[C[0], C[1], C[2]], sa=[butt[0], butt[1], 1.0], st=[tilt, elev])


def flat(x, y, toward=(0.18, 0.02), tilt=0.0, elev=40.0):
    """Blade flat on the ice at (x, y)."""
    return dict(sc=[x, y, PH], sa=[toward[0], toward[1], 1.0], st=[tilt, elev])


# ---------------------------------------------------------------------------
# Base poses
# ---------------------------------------------------------------------------
LEAN_GAIN = 1.5


def body(crouch=0.17, lean=42.0, twist=0.0, side=0.0, dx=0.0, dy=0.06, nod=None, turn=0.0, tilt=0.0, ptilt=None):
    if lean > 0:
        lean *= LEAN_GAIN
    pr = lean * 0.48 if ptilt is None else ptilt
    return dict(pel=[dx, dy, -crouch, pr, twist * 0.35, side * 0.5], sp=[lean - pr, twist * 0.65, side * 0.5],
                hd=[(-lean * 0.72 if nod is None else nod), turn - twist * 0.5, tilt - side * 0.4])


def feet(w=0.21, stagger=0.0, yaw=14, edge=6, lw=None, rw=None, ly=None, ry=None, llift=0.0, rlift=0.0,
         lyaw=None, ryaw=None, lpitch=0.0, rpitch=0.0, ledge=None, redge=None):
    return dict(lf=[lw if lw is not None else w, ly if ly is not None else -stagger, llift,
                    lyaw if lyaw is not None else yaw, lpitch, ledge if ledge is not None else edge],
                rf=[rw if rw is not None else w, ry if ry is not None else stagger, rlift,
                    ryaw if ryaw is not None else yaw, rpitch, redge if redge is not None else edge])


HOLD = dict(mode=0, lhp=[1.0, 0.3, -0.3], rhp=[-1.0, 0.7, -0.1])


def ready(crouch=0.17, lean=42.0, w=0.21, bx=-0.26, by=-1.06, twist=0.0, nod=None, turn=0.0, stagger=0.0,
          tilt=0.0):
    return M(body(crouch, lean, twist, nod=nod, turn=turn), feet(w, stagger), HOLD, flat(bx, by, tilt=tilt))


def guard(crouch=0.14, lean=16.0, twist=-10.0, bounce=0.0):
    """Fight stance (gloves off): left foot forward, fists up. The game hides the stick."""
    return M(body(crouch + bounce, lean, twist, nod=-6), feet(0.17, ly=-0.20, ry=0.20, lyaw=6, ryaw=30, edge=0),
             dict(mode=1, lh=[0.17, -0.40, 1.52], rh=[-0.15, -0.28, 1.50],
                  lhp=[0.9, 0.3, -1.0], rhp=[-0.9, 0.4, -1.0], lhf=[-0.1, -0.55, 0.85], rhf=[0.1, -0.45, 0.9],
                  lpa=[-0.6, -0.2, 0.0], rpa=[0.6, -0.2, 0.0], sdir=[-0.15, 0.1, -1.0]))


def lying_supine(arms_out=1.0, knee=0.0):
    return M(dict(pel=[0.0, 0.24, -0.88, -88, 0, 0], sp=[-4, 0, 0], hd=[12, 18, 0], legrel=[1.0]),
             dict(lf=[0.18, -0.02 - knee * 0.2, 0.17 + knee * 0.25, 18, -10, 0],
                  rf=[0.15, -0.05 - knee * 0.1, 0.20 + knee * 0.15, 12, -10, 0], lkp=[0, 0, 0], rkp=[0, 0, 0]),
             dict(mode=1, lh=[0.55 * arms_out + 0.15, -0.05, 1.35 + 0.35 * arms_out], rh=[-0.55 * arms_out - 0.15, -0.05, 1.30 + 0.30 * arms_out],
                  lhp=[0.3, 0.6, -1.0], rhp=[-0.3, 0.6, -1.0], lhf=[0.5, 0.0, 0.8], rhf=[-0.5, 0.0, 0.8],
                  lpa=[0, -1, 0], rpa=[0, -1, 0], sdir=[-0.9, 0.25, 0.3]))


def lying_prone():
    return M(dict(pel=[0.0, -0.30, -0.86, 86, 0, 0], sp=[4, 0, 0], hd=[-55, 0, 0], legrel=[1.0]),
             dict(lf=[0.17, 0.10, 0.17, 10, 30, 0], rf=[0.15, 0.08, 0.20, 10, 30, 0]),
             dict(mode=1, lh=[0.28, -0.10, 2.02], rh=[-0.26, -0.12, 2.00], lhp=[0.6, 0.6, 0.2], rhp=[-0.6, 0.6, 0.2],
                  lhf=[0.0, -0.3, 1.0], rhf=[0.0, -0.3, 1.0], lpa=[0, 1, 0], rpa=[0, 1, 0], sdir=[0.0, -0.2, 1.0]))


# ---------------------------------------------------------------------------
# Locomotion
# ---------------------------------------------------------------------------
def stride_foot(u, push_out=0.47, push_back=0.36, lift=0.11, under=0.12, fwd=-0.18):
    """Hockey stride for one leg, u in [0,1): push out + back on the inside edge, then recover under the hips."""
    P = 0.56
    if u < P:
        k = u / P
        e = k * k * (3 - 2 * k)
        out = under + (push_out - under) * e
        y = fwd + (push_back - fwd) * (0.15 * k + 0.85 * e)
        return [out, y, 0.0, 10 + 36 * e, -6 * e * e, 16 + 18 * e]
    k = (u - P) / (1 - P)
    e = k * k * (3 - 2 * k)
    out = push_out + (under - push_out) * min(1.0, e * 1.35)
    y = push_back + (fwd - push_back) * e
    lf = lift * math.sin(math.pi * k) ** 0.8
    return [out, y, lf, 46 - 36 * e, 8 * math.sin(math.pi * k), 34 - 28 * e]


def skate_clip(name, length, turbo=False, carry=False):
    c = clip(name, length, loop=True)
    n = 8
    for i in range(n):
        u = i / n
        ph = 2 * math.pi * u
        crouch = 0.24 if turbo else 0.20
        lean = 54 if turbo else 46
        dx = (0.075 if turbo else 0.06) * math.sin(ph + 0.6)
        bob = 0.028 * math.cos(2 * ph)
        twist = (10 if turbo else 6) * math.sin(ph + 0.3)
        p = M(body(crouch + bob, lean, twist, side=-dx * 70, dx=dx, dy=0.08),
              dict(lf=stride_foot(u, push_out=0.50 if turbo else 0.47),
                   rf=stride_foot((u + 0.5) % 1.0, push_out=0.50 if turbo else 0.47)))
        if turbo:
            sw = math.sin(ph + 0.4)
            p.update(mode=3, rhp=[-1.0, 0.6, -0.2], lh=[0.28, -0.28 - 0.48 * sw, 1.02 + 0.30 * max(0.0, sw)],
                     lhp=[0.5, 1.0, -0.2], lhf=[0.0, -0.6, 0.3 + 0.5 * sw], lpa=[-1, 0, 0])
            p.update(flat(-0.40 - 0.08 * sw, -1.12, toward=(0.0, 0.1), elev=38))
        elif carry:
            sweep = math.sin(2 * ph)
            p.update(HOLD)
            p.update(flat(-0.12 - 0.26 * sweep, -1.08 + 0.05 * abs(sweep), toward=(0.22, 0.0), tilt=-14 * sweep))
        else:
            sw = math.sin(ph + 0.4)
            p.update(HOLD)
            p.update(flat(-0.24 - 0.12 * sw, -1.10, toward=(0.22 - 0.06 * sw, 0.0)))
        c.key(length * u, p)
    return c


def anim_idle():
    c = clip("Idle", 2.0, loop=True)
    for t in (0.0, 0.5, 1.0, 1.5):
        ph = 2 * math.pi * t / 2.0
        p = ready(crouch=0.16 + 0.015 * math.sin(ph), lean=40 + 2.5 * math.sin(ph), bx=-0.26 + 0.03 * math.sin(ph),
                  turn=12 * math.sin(ph))
        p["pel"][0] = 0.02 * math.sin(ph)
        c.key(t, p)


def anim_glide():
    c = clip("Glide", 1.2, loop=True)
    for t in (0.0, 0.3, 0.6, 0.9):
        ph = 2 * math.pi * t / 1.2
        p = M(body(0.15 + 0.012 * math.cos(ph), 36, 4 * math.sin(ph), dx=0.025 * math.sin(ph), side=-2 * math.sin(ph)),
              feet(0.17, stagger=0.07, yaw=4, edge=2), HOLD, flat(-0.22 + 0.06 * math.sin(ph), -1.06))
        c.key(t, p)


def back_foot(u, out_max=0.40, under=0.13):
    """Backward C-cut: the foot pushes out and FORWARD in an arc with the toe turned in, then recovers."""
    P = 0.55
    if u < P:
        k = u / P
        e = k * k * (3 - 2 * k)
        out = under + (out_max - under) * math.sin(math.pi * 0.5 * e)
        y = 0.08 - 0.42 * e
        return [out, y, 0.0, -10 - 22 * math.sin(math.pi * k), 0, 22]
    k = (u - P) / (1 - P)
    e = k * k * (3 - 2 * k)
    out = out_max + (under - out_max) * e
    y = -0.34 + 0.42 * e
    return [out, y, 0.05 * math.sin(math.pi * k), -10 + 8 * math.sin(math.pi * k), 0, 22 - 14 * e]


def anim_skate_back():
    c = clip("SkateBack", 1.0, loop=True)
    n = 8
    for i in range(n):
        u = i / n
        ph = 2 * math.pi * u
        dx = 0.05 * math.sin(ph + 0.4)
        p = M(body(0.24 + 0.02 * math.cos(2 * ph), 26, -4 * math.sin(ph), dx=dx, side=-dx * 60, dy=0.10, nod=-18),
              dict(lf=back_foot(u), rf=back_foot((u + 0.5) % 1.0)), HOLD,
              flat(-0.10 - 0.14 * math.sin(ph), -1.05, toward=(0.15, 0.05)))
        c.key(1.0 * u, p)


def anim_stop():
    c = clip("Stop", 0.45, lag={"hd": 0.04, "lh": 0.03})
    sk = M(body(0.20, 46, 0, dy=0.08), dict(lf=stride_foot(0.75), rf=stride_foot(0.25)), HOLD, flat(-0.24, -1.10))
    c.key(0.00, sk)
    # unweight: pop up a little, both skates come together
    c.key(0.08, M(body(0.10, 30, 20, dy=0.05), feet(0.14, llift=0.04, rlift=0.03, yaw=30), HOLD,
                  flat(-0.30, -1.0, toward=(0.25, 0.05))), 0.7)
    # turn 90 and dig in, leaning back against the slide, chest still toward the travel direction
    dig = M(dict(pel=[0.0, 0.14, -0.27, 14, 78, -16], sp=[24, -46, -12], hd=[-30, -38, 8]),
            dict(lf=[0.04, 0.26, 0.0, 82, 0, -22], rf=[0.06, -0.24, 0.0, -96, 0, 26]),
            dict(mode=3, rhp=[-1.0, 0.5, -0.2], lh=[0.38, -0.28, 1.10], lhp=[0.8, 0.4, -0.4], lhf=[0.4, -0.5, 0.4]),
            flat(-0.55, -0.70, toward=(0.0, 0.2), elev=38))
    c.key(0.20, dig, 0.6)
    deep = M(dig, pel=[0.0, 0.18, -0.30, 16, 84, -20], sp=[26, -50, -14])
    c.key(0.32, deep, 0.6)
    c.key(0.45, M(deep, pel=[0.0, 0.10, -0.22, 12, 82, -8], sp=[22, -46, -6], hd=[-28, -40, 4]))


# ---------------------------------------------------------------------------
# Shots and passes
# ---------------------------------------------------------------------------
BUTT_HIP = (0.16, -0.02, 0.98)


def anim_shot_wrist():
    c = clip("ShotWrist", 0.55, release=0.22, lag={"hd": 0.04, "lh": 0.02})
    c.key(0.00, ready(twist=-10))
    # load: puck drawn back beside the back (right) foot, weight back, eyes on the target
    c.key(0.10, M(body(0.20, 40, -30, dx=-0.06, turn=30), feet(0.22, ly=-0.14, ry=0.12, ryaw=24), HOLD,
                  flat(-0.52, -0.38, toward=(0.30, 0.25), tilt=-10)), 0.7)
    # snap: blade whips forward through the release point in front of the front foot
    c.key(0.22, M(body(0.17, 44, 14, dx=0.05, dy=0.0, turn=-6), feet(0.22, ly=-0.16, ry=0.14, ryaw=34, rpitch=8),
                  HOLD, stk((-0.10, -1.02, 0.03), (0.22, -0.05, 0.95), tilt=14)), 0.45)
    # follow-through: blade high toward the target, toe-drag on the back skate
    c.key(0.36, M(body(0.12, 40, 30, dx=0.08, dy=-0.02, turn=-18), feet(0.22, ly=-0.18, ry=0.18, ryaw=38, rpitch=26,
                                                                         rlift=0.06),
                  HOLD, stk((0.10, -1.08, 0.62), (0.20, -0.20, 0.88), tilt=30)), 0.7)
    c.key(0.55, M(body(0.15, 42, 12, dx=0.03, turn=-8), feet(0.21, ly=-0.12, ry=0.10, ryaw=20), HOLD,
                  stk((-0.10, -1.05, 0.20), (0.18, -0.05, 0.98), tilt=10)))


WINDUP = M(body(0.15, 30, -38, dx=-0.08, turn=36, side=6), feet(0.25, ly=-0.18, ry=0.14, ryaw=28, lyaw=8),
           HOLD, dict(rhp=[-0.8, 0.6, -0.6], lhp=[0.9, -0.2, -0.6]),
           stk((-0.92, 0.55, 2.05), (0.02, -0.42, 1.30), tilt=-10))


def anim_slap_windup():
    c = clip("SlapWindup", 0.40, lag={"hd": 0.03})
    c.key(0.00, ready(twist=-10))
    c.key(0.16, M(body(0.18, 36, -26, dx=-0.05, turn=26), feet(0.24, ly=-0.17, ry=0.13, ryaw=26), HOLD,
                  stk((-0.75, -0.10, 1.05), (0.10, -0.30, 1.15), tilt=-6)), 0.8)
    c.key(0.40, WINDUP)


def slap_down(c, t_imp, impact_y=-0.78):
    """Impact (blade on the ice at the puck, slightly behind the front foot) then a high follow-through."""
    c.key(t_imp, M(body(0.20, 44, 6, dx=0.04, turn=0), feet(0.25, ly=-0.18, ry=0.16, ryaw=36, rpitch=10),
                   HOLD, stk((-0.12, impact_y, PH), (0.25, 0.02, 0.92), tilt=6)), 0.35)
    c.key(t_imp + 0.14, M(body(0.12, 34, 34, dx=0.08, turn=-20), feet(0.25, ly=-0.20, ry=0.20, ryaw=40, rpitch=28,
                                                                      rlift=0.08),
                          HOLD, stk((0.30, -1.15, 1.05), (0.12, -0.25, 0.95), tilt=24)), 0.7)


def anim_slap_release():
    c = clip("SlapRelease", 0.50, impact=0.10, lag={"hd": 0.03, "lh": 0.02})
    c.key(0.00, WINDUP)
    slap_down(c, 0.10)
    c.key(0.50, M(body(0.14, 38, 16, dx=0.04, turn=-8), feet(0.23, ly=-0.12, ry=0.12, ryaw=24), HOLD,
                  stk((0.0, -1.10, 0.35), (0.16, -0.08, 0.98), tilt=10)))


def anim_one_timer():
    c = clip("OneTimer", 0.55, impact=0.18, lag={"hd": 0.03})
    c.key(0.00, ready(twist=-12, turn=20))
    c.key(0.09, M(body(0.17, 34, -30, dx=-0.06, turn=30), feet(0.25, ly=-0.17, ry=0.14, ryaw=26), HOLD,
                  dict(rhp=[-0.8, 0.6, -0.6]), stk((-0.85, 0.28, 1.25), (0.05, -0.35, 1.22), tilt=-8)), 0.6)
    slap_down(c, 0.18, impact_y=-0.82)
    c.key(0.55, M(body(0.14, 38, 16, dx=0.04, turn=-8), feet(0.23, ly=-0.12, ry=0.12, ryaw=24), HOLD,
                  stk((0.0, -1.10, 0.30), (0.16, -0.08, 0.98), tilt=10)))


def anim_pass():
    c = clip("Pass", 0.45, release=0.16, lag={"hd": 0.03})
    c.key(0.00, ready(twist=-6))
    c.key(0.07, M(body(0.19, 40, -20, dx=-0.04, turn=10), feet(0.22, ly=-0.10, ry=0.10, ryaw=20), HOLD,
                  flat(-0.56, -0.62, toward=(0.30, 0.20), tilt=-6)), 0.7)
    c.key(0.16, M(body(0.18, 42, 8, dx=0.03, turn=-4), feet(0.22, ly=-0.12, ry=0.12, ryaw=26), HOLD,
                  flat(-0.12, -1.06, toward=(0.24, 0.02), tilt=8)), 0.5)
    c.key(0.28, M(body(0.16, 40, 20, dx=0.05, turn=-10), feet(0.22, ly=-0.12, ry=0.14, ryaw=28, rpitch=12), HOLD,
                  stk((0.20, -1.14, 0.18), (0.20, -0.10, 0.98), tilt=16)), 0.7)
    c.key(0.45, M(ready(twist=6), stk((-0.05, -1.08, 0.05), (0.20, -0.04, 0.98), tilt=6)))


# ---------------------------------------------------------------------------
# Checks / stick checks
# ---------------------------------------------------------------------------
TUCK = dict(mode=3, rhp=[-1.0, 0.5, -0.3], lh=[0.20, -0.22, 1.36], lhp=[1.0, -0.6, -0.2], lhf=[-0.4, -0.5, 0.5],
            lpa=[0, -1, 0])


def anim_check():
    c = clip("Check", 0.55, contact=0.18, lag={"hd": 0.04})
    c.key(0.00, ready())
    c.key(0.08, M(body(0.25, 36, 18, dx=0.04), feet(0.24, ly=-0.08, ry=0.14, ryaw=30), TUCK,
                  flat(-0.40, -0.80, toward=(0.1, 0.2))), 0.7)
    # lunge: left shoulder drives forward and up, right leg extends behind
    c.key(0.18, M(body(0.12, 30, -36, dx=0.02, dy=-0.30, turn=24, side=-8), feet(0.22, ly=-0.30, ry=0.38, ryaw=40,
                                                                                   rpitch=20, rlift=0.03),
                  TUCK, dict(lh=[0.30, -0.36, 1.40], lhp=[1.0, -0.2, 0.4]), flat(-0.55, -0.95, toward=(0.0, 0.1))), 0.4)
    c.key(0.30, M(body(0.14, 32, -30, dy=-0.26, turn=20, side=-6), feet(0.22, ly=-0.28, ry=0.34, ryaw=36), TUCK,
                  dict(lh=[0.28, -0.32, 1.38]), flat(-0.50, -0.95, toward=(0.0, 0.1))), 0.8)
    c.key(0.55, ready())


def anim_power_check():
    c = clip("PowerCheck", 0.70, contact=0.22, lag={"hd": 0.05, "lh": 0.03, "rh": 0.03})
    c.key(0.00, ready())
    # big coil: sink low, arms cocked back
    c.key(0.11, M(body(0.32, 48, 14, dy=0.10), feet(0.26, ly=-0.04, ry=0.16, ryaw=34, edge=20),
                  dict(mode=1, lh=[0.30, 0.08, 1.12], rh=[-0.30, 0.10, 1.10], lhp=[0.8, 0.6, -0.4], rhp=[-0.8, 0.6, -0.4],
                       lhf=[0.0, -0.6, 0.6], rhf=[0.0, -0.6, 0.6], sdir=[0.4, -0.7, -0.6])), 0.6)
    # explode: whole body launches forward and up, both gloves (and stick) drive through the target
    hit = M(body(-0.02, 18, -10, dy=-0.42, nod=-8, turn=8), feet(0.20, ly=-0.20, ry=0.40, ryaw=36, rpitch=34, rlift=0.14,
                                                                  llift=0.03),
            dict(mode=1, lh=[0.20, -0.62, 1.46], rh=[-0.10, -0.62, 1.42], lhp=[1.0, 0.2, -0.3], rhp=[-1.0, 0.2, -0.3],
                 lhf=[0.0, -0.5, 0.85], rhf=[0.0, -0.5, 0.85], lpa=[0, -1, 0], rpa=[0, -1, 0], sdir=[0.95, -0.05, -0.15]))
    c.key(0.22, hit, 0.35)
    c.key(0.38, M(hit, pel=[0.0, -0.40, -0.06, 20, -6, 0], lh=[0.22, -0.58, 1.40], rh=[-0.12, -0.58, 1.36]), 0.8)
    c.key(0.70, ready())


def anim_poke_check():
    c = clip("PokeCheck", 0.45, poke=0.15, lag={"hd": 0.03})
    c.key(0.00, ready())
    c.key(0.06, M(body(0.20, 42, -6), feet(0.22, ly=-0.06, ry=0.10), dict(mode=3, rhp=[-1.0, 0.4, -0.2],
                  lh=[0.30, -0.10, 1.10], lhp=[0.6, 0.8, -0.2]), flat(-0.24, -0.92, toward=(-0.1, 0.2))), 0.6)
    jab = M(body(0.20, 58, 12, dy=-0.12, nod=-52), feet(0.22, ly=-0.28, ry=0.30, ryaw=30, rpitch=14),
            dict(mode=3, rhp=[-1.0, 0.3, -0.1], lh=[0.42, 0.20, 1.16], lhp=[0.6, 0.8, -0.2], lhf=[0.4, 0.5, -0.4]),
            flat(-0.18, -1.78, toward=(-0.15, 0.2), elev=26))
    c.key(0.15, jab, 0.4)
    c.key(0.26, M(jab, sc=[-0.20, -1.70, PH]), 0.8)
    c.key(0.45, ready())


def anim_hook():
    c = clip("Hook", 0.60, hook=0.20, lag={"hd": 0.03})
    c.key(0.00, ready())
    c.key(0.08, M(body(0.20, 44, -10), feet(0.22), dict(mode=3, rhp=[-1.0, 0.4, -0.2], lh=[0.30, -0.12, 1.08]),
                  flat(-0.40, -0.95, toward=(0.0, 0.2))), 0.6)
    reach = M(body(0.20, 50, 26, dy=-0.06, turn=-10), feet(0.24, ly=-0.22, ry=0.24, lyaw=30),
              dict(mode=3, rhp=[-0.6, 0.6, -0.6], lh=[0.38, 0.18, 1.10], lhp=[0.8, 0.6, -0.2]),
              flat(0.55, -1.42, toward=(-0.3, 0.2), tilt=-30, elev=30))
    c.key(0.20, reach, 0.45)
    c.key(0.38, M(reach, body(0.20, 46, 10, turn=0), flat(0.05, -0.90, toward=(-0.3, 0.3), tilt=-40, elev=34)), 0.6)
    c.key(0.60, ready())


# ---------------------------------------------------------------------------
# Falls, dives, get up
# ---------------------------------------------------------------------------
def anim_dive():
    c = clip("Dive", 1.2, lag={"hd": 0.05, "lh": 0.04, "rh": 0.04})
    c.key(0.00, M(ready(), dict(legrel=[0.0])))
    c.key(0.14, M(body(0.30, 50, 0), feet(0.22, ly=-0.12, ry=0.20, ryaw=30), HOLD, flat(-0.26, -1.10), legrel=[0.0]),
          0.6)
    air = M(dict(pel=[0.0, -0.40, -0.52, 70, 0, 0], sp=[8, 0, 0], hd=[-62, 0, 0], legrel=[1.0]),
            dict(lf=[0.15, 0.10, 0.12, 10, 20, 0], rf=[0.14, 0.16, 0.20, 10, 30, 0]),
            dict(mode=1, lh=[0.26, -0.20, 1.98], rh=[-0.24, -0.22, 1.96], lhp=[0.6, 0.6, 0.2], rhp=[-0.6, 0.6, 0.2],
                 lhf=[0.0, -0.3, 1.0], rhf=[0.0, -0.3, 1.0], lpa=[0, 1, 0], rpa=[0, 1, 0], sdir=[0.0, -0.3, 1.0]))
    c.key(0.34, air, 0.7)
    land = lying_prone()
    land["pel"] = [0.0, -0.36, -0.84, 84, 0, 0]
    c.key(0.52, land, 0.5)
    c.key(0.64, M(land, pel=[0.0, -0.32, -0.80, 82, 0, 0], hd=[-50, 0, 0]), 0.8)
    c.key(1.20, M(lying_prone(), hd=[-48, 6, 0]))


def anim_hit_fall():
    c = clip("HitFall", 1.1, lag={"hd": 0.06, "lh": 0.05, "rh": 0.05})
    start = M(body(0.17, 40), feet(0.21), dict(mode=1, lh=[0.18, -0.38, 1.08], rh=[-0.24, -0.34, 1.00],
                                               lhp=[1.0, 0.3, -0.3], rhp=[-1.0, 0.6, -0.2], sdir=[-0.25, -0.7, -0.65]),
              legrel=[0.0])
    c.key(0.00, start)
    # hit: chest snaps back, arms fly up, feet start to go
    c.key(0.10, M(body(0.10, -12, 14, dy=0.18, nod=-30), feet(0.21, ly=-0.12, llift=0.06, rlift=0.03),
                  dict(mode=1, lh=[0.55, -0.20, 1.70], rh=[-0.55, -0.15, 1.65], lhp=[0.6, 0.6, -0.6], rhp=[-0.6, 0.6, -0.6],
                       lhf=[0.5, 0.0, 0.8], rhf=[-0.5, 0.0, 0.8], sdir=[-0.6, -0.5, 0.6]), legrel=[0.3]), 0.6)
    c.key(0.30, M(dict(pel=[0.0, 0.18, -0.35, -48, 16, 6], sp=[-12, 10, 0], hd=[22, 10, 0], legrel=[1.0]),
                  dict(lf=[0.18, -0.30, 0.10, 14, -20, 0], rf=[0.15, -0.22, 0.14, 10, -10, 0]),
                  dict(mode=1, lh=[0.62, -0.10, 1.68], rh=[-0.62, -0.10, 1.62], lhp=[0.6, 0.6, -0.6], rhp=[-0.6, 0.6, -0.6],
                       lhf=[0.6, 0.0, 0.7], rhf=[-0.6, 0.0, 0.7], sdir=[-0.7, -0.4, 0.5])), 0.7)
    sup = lying_supine(arms_out=1.0, knee=0.2)
    c.key(0.50, M(sup, pel=[0.0, 0.24, -0.86, -92, 6, 0], hd=[-8, 10, 0]), 0.4)
    c.key(0.64, M(sup, pel=[0.0, 0.24, -0.82, -82, 4, 0], hd=[20, 12, 0], lf=[0.18, -0.10, 0.30, 18, -10, 0]), 0.8)
    c.key(1.10, lying_supine(arms_out=1.0))


def anim_flip():
    c = clip("Flip", 1.2, lag={"hd": 0.06, "lh": 0.05, "rh": 0.05})
    flail = dict(mode=1, lh=[0.62, -0.05, 1.70], rh=[-0.62, -0.05, 1.70], lhp=[0.6, 0.6, -0.6], rhp=[-0.6, 0.6, -0.6],
                 lhf=[0.6, 0.0, 0.7], rhf=[-0.6, 0.0, 0.7], sdir=[-0.7, -0.3, 0.6])
    legs_spread = dict(lf=[0.40, -0.05, 0.25, 30, -10, 0], rf=[0.40, 0.10, 0.20, 30, 10, 0], legrel=[1.0])
    c.key(0.00, M(body(0.15, 30), feet(0.21), flail, legrel=[0.0]))
    c.key(0.12, M(dict(pel=[0.0, 0.10, 0.0, -40, 0, 30], sp=[-15, 10, 10], hd=[20, 0, 0]), legs_spread, flail), 0.8)
    c.key(0.40, M(dict(pel=[0.0, 0.0, 0.05, -170, 0, 150], sp=[-10, -10, 10], hd=[10, 0, 0]), legs_spread, flail), 1.0)
    c.key(0.68, M(dict(pel=[0.0, 0.0, -0.05, -300, 0, 280], sp=[-5, 10, -10], hd=[15, 0, 0]), legs_spread, flail), 1.0)
    sup = lying_supine(arms_out=1.0, knee=0.3)
    c.key(0.92, M(sup, pel=[0.0, 0.24, -0.82, -440, 0, 360], hd=[-10, 15, 0]), 0.5)
    c.key(1.05, M(sup, pel=[0.0, 0.24, -0.84, -445, 0, 360]), 0.8)
    c.key(1.20, M(lying_supine(arms_out=1.0), pel=[0.0, 0.24, -0.88, -448, 0, 360]))


def anim_get_up():
    c = clip("GetUp", 0.9, lag={"hd": 0.04})
    c.key(0.00, lying_supine(arms_out=1.0))
    # sit up, knees come up
    c.key(0.22, M(dict(pel=[0.0, 0.18, -0.80, -10, 0, 0], sp=[30, 0, 0], hd=[-10, 0, 0], legrel=[0.6]),
                  dict(lf=[0.20, -0.45, 0.30, 15, 0, 0], rf=[0.18, -0.40, 0.25, 15, 0, 0]),
                  dict(mode=1, lh=[0.35, -0.30, 1.00], rh=[-0.35, -0.10, 0.95], lhp=[0.8, 0.6, -0.4], rhp=[-0.8, 0.6, -0.4],
                       sdir=[-0.5, -0.8, -0.2])), 0.7)
    # onto the right knee, left skate planted
    c.key(0.45, M(dict(pel=[0.0, 0.10, -0.46, 22, 0, 0], sp=[18, 0, 0], hd=[-30, 0, 0], legrel=[0.0]),
                  dict(lf=[0.18, -0.38, 0.0, 10, 0, 0], rf=[0.16, 0.30, 0.0, 10, 50, 0], rkp=[0, 0, -0.6]),
                  dict(mode=3, rhp=[-1.0, 0.6, -0.2], lh=[0.30, -0.42, 0.90], lhp=[0.9, 0.4, -0.3]),
                  flat(-0.45, -0.85, toward=(0.0, 0.2))), 0.7)
    c.key(0.68, M(body(0.26, 46), feet(0.22, ly=-0.12, ry=0.12), HOLD, flat(-0.30, -1.02)), 0.8)
    c.key(0.90, ready())


# ---------------------------------------------------------------------------
# Celebrations / emotes
# ---------------------------------------------------------------------------
def raised_stick(lh_up=True, t=0.0):
    return dict(mode=1, rh=[-0.30, -0.12, 2.00], rhp=[-1.0, 0.2, -0.3], rhf=[0.0, -0.3, 1.0], rpa=[1, 0, 0],
                sdir=[-0.35, 0.15, 1.0],
                lh=[0.22, -0.30, 1.95] if lh_up else [0.28, -0.40, 1.30], lhp=[1.0, 0.2, -0.4],
                lhf=[0.0, -0.3, 1.0], lpa=[-1, 0, 0])


def anim_celebrate1():
    c = clip("Celebrate1", 2.4, lag={"hd": 0.06, "lh": 0.04, "rh": 0.05})
    c.key(0.00, M(body(0.15, 36), feet(0.18, stagger=0.06, yaw=6), HOLD, flat(-0.22, -1.06)))
    c.key(0.18, M(body(0.22, 30, nod=-10), feet(0.20, stagger=0.06, yaw=8), raised_stick(False)), 0.6)
    for i, t in enumerate((0.42, 0.70, 0.98, 1.26)):
        up = i % 2 == 0
        c.key(t, M(body(0.10 if up else 0.16, 4 if up else 14, -10 if up else 8, nod=-30 if up else -18, turn=10 if up else -10),
                   feet(0.20, stagger=0.06, yaw=8), raised_stick(up)), 0.6)
    c.key(1.65, M(body(0.02, -4, 0, nod=-38), feet(0.20, stagger=0.06, yaw=8, llift=0.02),
                  raised_stick(True), dict(lh=[0.30, -0.20, 2.08])), 0.6)
    c.key(2.05, M(body(0.12, 18, 0, nod=-20), feet(0.19, stagger=0.06, yaw=6), raised_stick(False)), 0.8)
    c.key(2.40, M(body(0.15, 32), feet(0.18, stagger=0.06, yaw=6), HOLD, flat(-0.24, -1.06)))


def anim_celebrate2():
    c = clip("Celebrate2", 2.4, lag={"hd": 0.05, "lh": 0.03, "rh": 0.03})
    c.key(0.00, M(body(0.15, 36), feet(0.18, stagger=0.06), HOLD, flat(-0.22, -1.06)))
    c.key(0.22, M(body(0.32, 30), feet(0.20, ly=-0.25, ry=0.10, ryaw=20), HOLD, flat(-0.30, -0.95)), 0.6)
    # knee slide: right knee on the ice, leaning back, stick played like a guitar
    kneel = dict(pel=[0.0, 0.12, -0.55, 0, 20, 0], legrel=[0.0],
                 lf=[0.20, -0.42, 0.0, 15, 0, 0], rf=[0.16, 0.42, 0.0, 15, 62, 0], rkp=[0, 0, -0.8])
    for i, t in enumerate((0.45, 0.70, 0.95, 1.20, 1.45, 1.70, 1.95)):
        k = i % 2
        strum = 0.06 if k else -0.04
        guitar = stk((-0.80, -0.34, 0.03 + strum * 0.5), (0.30, -0.50, 1.12 + strum), tilt=80)
        c.key(t, M(kneel, dict(sp=[-26, 22, 0], hd=[14 if k else -22, -10, 8 if k else -8]), HOLD,
                   dict(rhp=[-0.6, 0.8, -0.6], lhp=[0.8, -0.2, -0.6]), guitar), 0.7)
    c.key(2.40, M(kneel, dict(sp=[-10, 30, 0], hd=[-28, -14, 0]), raised_stick(True)))


def anim_celebrate3():
    c = clip("Celebrate3", 2.4, lag={"hd": 0.06, "lh": 0.04, "rh": 0.04})
    c.key(0.00, M(body(0.15, 36), feet(0.18, stagger=0.06), HOLD, flat(-0.22, -1.06)))
    c.key(0.22, M(body(0.30, 40, nod=-20), feet(0.20, stagger=0.04, yaw=10), raised_stick(False),
                  dict(rh=[-0.30, -0.05, 1.10], lh=[0.30, -0.05, 1.10])), 0.5)
    jump = M(dict(pel=[0.0, -0.22, 0.32, 4, 0, 0], sp=[-6, 0, 0], hd=[-24, 0, 0]),
             feet(0.18, stagger=0.04, yaw=10, llift=0.36, rlift=0.30, lpitch=30, rpitch=34),
             raised_stick(True), dict(lh=[0.45, -0.25, 2.05], rh=[-0.42, -0.20, 2.02]))
    c.key(0.42, jump, 0.6)
    # pressed against the glass in front, arms spread up
    glass = M(dict(pel=[0.0, -0.34, 0.26, 2, 0, 0], sp=[-4, 0, 0], hd=[-10, 10, 0]),
              feet(0.18, stagger=0.04, yaw=10, llift=0.30, rlift=0.24, lpitch=40, rpitch=44),
              raised_stick(True), dict(lh=[0.55, -0.40, 2.02], rh=[-0.50, -0.38, 1.98]))
    c.key(0.62, glass, 0.6)
    c.key(1.10, M(glass, pel=[0.0, -0.32, 0.20, 2, 4, 0], hd=[-16, -10, 0]), 0.8)
    c.key(1.45, M(body(0.24, 28, nod=-24), feet(0.20, stagger=0.04, yaw=10), raised_stick(True)), 0.5)
    c.key(1.80, M(body(0.08, 6, 0, nod=-36), feet(0.20, stagger=0.04, yaw=10), raised_stick(True)), 0.7)
    c.key(2.40, M(body(0.15, 30), feet(0.18, stagger=0.06), raised_stick(False)))


def anim_dejected():
    c = clip("Dejected", 2.0, loop=True, lag={"hd": 0.12})
    for t in (0.0, 0.5, 1.0, 1.5):
        ph = 2 * math.pi * t / 2.0
        c.key(t, M(body(0.10 + 0.01 * math.cos(ph), 18, 3 * math.sin(ph), dx=0.02 * math.sin(ph), nod=38, turn=8 * math.sin(ph),
                        side=-3 * math.sin(ph)),
                   dict(cl=[-12, 10, -12, 10]), feet(0.16, stagger=0.05, yaw=4, edge=2),
                   dict(mode=3, rhp=[-0.6, 0.8, -0.2], lh=[0.26, 0.02, 0.88], lhp=[0.4, 1.0, 0.0], lhf=[0.0, 0.0, -1.0],
                        lpa=[-1, 0, 0]),
                   flat(-0.42, -0.70 + 0.02 * math.sin(ph), toward=(-0.1, 0.3), elev=30)))


def anim_faceoff_ready():
    c = clip("FaceoffReady", 1.0, loop=True)
    for t in (0.0, 0.25, 0.5, 0.75):
        ph = 2 * math.pi * t
        c.key(t, M(body(0.30 + 0.015 * math.sin(ph), 56, 0, nod=-56), feet(0.28, yaw=18, edge=10), HOLD,
                   dict(lhp=[1.0, 0.2, -0.4], rhp=[-1.0, 0.4, -0.2]),
                   flat(0.0 + 0.02 * math.sin(ph * 2), -0.86, toward=(0.20, 0.0), elev=38)))


def anim_faceoff_win():
    c = clip("FaceoffWin", 0.40, sweep=0.10, lag={"hd": 0.03})
    base = M(body(0.30, 56, 0, nod=-56), feet(0.28, yaw=18, edge=10), HOLD,
             dict(lhp=[1.0, 0.2, -0.4], rhp=[-1.0, 0.4, -0.2]))
    c.key(0.00, M(base, flat(0.0, -0.86, toward=(0.20, 0.0), elev=38)))
    c.key(0.10, M(base, body(0.28, 50, -20, nod=-50), flat(-0.38, -0.40, toward=(0.30, 0.20), tilt=-25, elev=38)), 0.4)
    c.key(0.22, M(base, body(0.24, 46, -24, nod=-44), flat(-0.50, -0.18, toward=(0.30, 0.30), tilt=-20, elev=36)), 0.7)
    c.key(0.40, ready(twist=-8))


# ---------------------------------------------------------------------------
# Fighting (stick hidden by the game)
# ---------------------------------------------------------------------------
def anim_fight_idle():
    c = clip("FightIdle", 1.0, loop=True, lag={"hd": 0.05, "lh": 0.04, "rh": 0.06})
    for t in (0.0, 0.25, 0.5, 0.75):
        ph = 2 * math.pi * t * 2
        g = guard(bounce=0.03 * (0.5 + 0.5 * math.cos(ph)), twist=-8 + 4 * math.sin(ph * 0.5))
        g["lh"][2] += 0.03 * math.sin(ph * 0.5)
        g["rh"][2] += 0.03 * math.sin(ph * 0.5 + 1.5)
        g["pel"][0] = 0.025 * math.sin(ph * 0.5)
        c.key(t, g)


def anim_fight_jab():
    c = clip("FightJab", 0.35, hit=0.12, lag={"hd": 0.04})
    c.key(0.00, guard())
    c.key(0.12, M(guard(twist=-26, lean=18), dict(lh=[0.06, -0.70, 1.58], lhp=[1.0, 0.0, -0.2], lhf=[0.0, -1.0, 0.1],
                                                  lpa=[0, 0, -1])), 0.4)
    c.key(0.35, guard())


def anim_fight_punch():
    c = clip("FightPunch", 0.55, hit=0.25, lag={"hd": 0.05})
    c.key(0.00, guard())
    c.key(0.12, M(guard(twist=-24, crouch=0.14), dict(rh=[-0.28, 0.06, 1.52], rhp=[-1.0, 0.6, 0.2], rhf=[0.0, -0.3, 0.9])),
          0.6)
    c.key(0.25, M(guard(twist=38, lean=22, crouch=0.08), dict(rh=[-0.02, -0.72, 1.56], rhp=[-1.0, 0.3, 0.4],
                                                              rhf=[0.0, -1.0, 0.1], rpa=[0, 0, -1],
                                                              lh=[0.18, -0.20, 1.52])), 0.35)
    c.key(0.36, M(guard(twist=34, lean=24, crouch=0.10), dict(rh=[0.06, -0.60, 1.44], lh=[0.18, -0.22, 1.50])), 0.8)
    c.key(0.55, guard())


def anim_fight_uppercut():
    c = clip("FightUppercut", 0.70, hit=0.32, lag={"hd": 0.05})
    c.key(0.00, guard())
    c.key(0.16, M(guard(twist=-22, crouch=0.26, lean=20), dict(rh=[-0.20, -0.22, 1.02], rhp=[-1.0, 0.2, -0.6],
                                                               rhf=[0.0, -0.3, 1.0], rpa=[1, 0, 0])), 0.6)
    c.key(0.32, M(guard(twist=30, crouch=-0.02, lean=-4), dict(rh=[-0.04, -0.46, 1.82], rhp=[-1.0, 0.2, -1.0],
                                                               rhf=[0.0, -0.2, 1.0], lh=[0.16, -0.22, 1.50])), 0.35)
    c.key(0.46, M(guard(twist=26, crouch=0.0, lean=0), dict(rh=[-0.02, -0.40, 1.86], lh=[0.16, -0.22, 1.50])), 0.8)
    c.key(0.70, guard())


def anim_fight_grab():
    c = clip("FightGrab", 0.60, grab=0.25, lag={"hd": 0.05})
    c.key(0.00, guard())
    c.key(0.25, M(guard(twist=-20, lean=24, crouch=0.12), dict(lh=[0.02, -0.66, 1.38], lhp=[1.0, 0.2, -0.4],
                                                               lhf=[0.0, -1.0, 0.0], lpa=[0, 0, -1])), 0.45)
    c.key(0.42, M(guard(twist=12, lean=-6, crouch=0.10), dict(lh=[0.10, -0.40, 1.36], rh=[-0.26, 0.0, 1.50],
                                                              rhp=[-1.0, 0.6, 0.0])), 0.7)
    c.key(0.60, M(guard(twist=6, lean=4), dict(lh=[0.10, -0.42, 1.40])))


def anim_fight_block():
    c = clip("FightBlock", 0.50, lag={"hd": 0.04})
    c.key(0.00, guard())
    blk = M(guard(crouch=0.16, lean=20, twist=-4), dict(hd=[22, 0, 0], lh=[0.09, -0.24, 1.72], rh=[-0.09, -0.23, 1.70],
                                                         lhp=[0.3, -1.0, -0.3], rhp=[-0.3, -1.0, -0.3],
                                                         lhf=[-0.2, -0.1, 1.0], rhf=[0.2, -0.1, 1.0]))
    c.key(0.12, blk, 0.5)
    c.key(0.50, M(blk, pel=[0.0, 0.07, -0.17, 8, -1, 0]))


def anim_fight_hit():
    c = clip("FightHit", 0.45, lag={"hd": 0.02, "lh": 0.04, "rh": 0.04})
    c.key(0.00, guard())
    c.key(0.08, M(guard(lean=-14, twist=14, crouch=0.06), dict(hd=[-38, 26, -14], lh=[0.30, -0.20, 1.62],
                                                               rh=[-0.34, -0.12, 1.55], pel=[0.03, 0.12, -0.06, -8, 5, 0])),
          0.4)
    c.key(0.22, M(guard(lean=-4, twist=6, crouch=0.12), dict(hd=[-6, 10, -4], pel=[0.0, 0.10, -0.12, 0, 2, 0])), 0.7)
    c.key(0.45, guard())


def anim_fight_ko():
    c = clip("FightKO", 1.6, lag={"hd": 0.10, "lh": 0.08, "rh": 0.08})
    c.key(0.00, M(guard(), legrel=[0.0]))
    c.key(0.25, M(guard(lean=-6, twist=20, crouch=0.08), dict(hd=[-30, 30, 20], lh=[0.30, -0.15, 1.30],
                                                              rh=[-0.30, -0.10, 1.25], pel=[0.06, 0.06, -0.08, -4, 10, 8])),
          0.7)
    c.key(0.55, M(guard(lean=10, twist=-16, crouch=0.20), dict(hd=[30, -20, -25], lh=[0.30, -0.05, 1.05],
                                                               rh=[-0.32, 0.0, 1.00], pel=[-0.08, 0.02, -0.20, 6, -10, -10],
                                                               lf=[0.20, -0.10, 0.0, 30, 0, -10])), 0.7)
    # knees buckle
    c.key(0.85, M(dict(pel=[0.0, 0.0, -0.50, 10, 0, 4], sp=[20, 6, 0], hd=[40, 10, 10], legrel=[0.0]),
                  dict(lf=[0.22, -0.30, 0.0, 20, 0, 0], rf=[0.18, 0.30, 0.0, 14, 55, 0], rkp=[0, 0, -0.7]),
                  dict(mode=1, lh=[0.30, -0.05, 0.95], rh=[-0.32, 0.0, 0.95], lhp=[0.6, 0.6, -0.4], rhp=[-0.6, 0.6, -0.4],
                       lhf=[0.0, 0.0, -1.0], rhf=[0.0, 0.0, -1.0], sdir=[-0.3, 0.0, -1.0])), 0.6)
    c.key(1.15, M(dict(pel=[0.0, 0.20, -0.72, -50, 10, 6], sp=[-6, 0, 0], hd=[30, 20, 0], legrel=[0.7]),
                  dict(lf=[0.20, -0.30, 0.20, 20, 0, 0], rf=[0.16, -0.15, 0.25, 14, 0, 0]),
                  dict(mode=1, lh=[0.50, -0.05, 1.40], rh=[-0.50, -0.05, 1.35], lhp=[0.3, 0.6, -1.0], rhp=[-0.3, 0.6, -1.0],
                       sdir=[-0.8, -0.3, 0.3])), 0.5)
    c.key(1.35, M(lying_supine(arms_out=1.0, knee=0.3), pel=[0.0, 0.24, -0.84, -90, 4, 0]), 0.6)
    c.key(1.60, lying_supine(arms_out=1.0))


# ---------------------------------------------------------------------------
# Goalie
# ---------------------------------------------------------------------------
GLOVE_OPEN = dict(lh=[0.46, -0.36, 1.02], lhp=[1.0, 0.6, -0.4], lhf=[0.15, -0.35, 1.0], lpa=[0, -1, 0])


def gready(crouch=0.30, lean=40, w=0.31, bx=-0.04, by=-0.78, dx=0.0, twist=0.0):
    return M(body(crouch, lean, twist, dx=dx, nod=-lean * 0.9), feet(w, yaw=20, edge=16),
             dict(lkp=[-0.45, 0, 0], rkp=[-0.45, 0, 0], mode=3, rhp=[-1.0, 0.5, -0.4]), GLOVE_OPEN,
             flat(bx, by, toward=(-0.40, -0.10), elev=34))


def anim_goalie_ready():
    c = clip("GoalieReady", 2.0, loop=True, goalie=True)
    for t in (0.0, 0.5, 1.0, 1.5):
        ph = 2 * math.pi * t / 2.0
        g = gready(crouch=0.30 + 0.012 * math.sin(ph), dx=0.015 * math.sin(ph))
        g["hd"][1] = 8 * math.sin(ph)
        g["lh"][2] += 0.02 * math.sin(ph + 1)
        c.key(t, g)


def anim_goalie_shuffle(name, side):
    """side = +1: shuffle toward the goalie's own left (+X)."""
    c = clip(name, 0.6, loop=True, goalie=True)
    for i in range(6):
        u = i / 6
        ph = 2 * math.pi * u
        g = gready(dx=0.05 * side * math.sin(ph), crouch=0.30 + 0.02 * math.cos(2 * ph))
        lead = "lf" if side > 0 else "rf"
        trail = "rf" if side > 0 else "lf"
        g[lead][0] = 0.31 + 0.10 * max(0.0, math.sin(ph))
        g[lead][2] = 0.04 * max(0.0, math.sin(ph)) ** 2
        g[trail][0] = 0.31 - 0.08 * max(0.0, math.sin(ph))
        g[trail][5] = 16 + 14 * max(0.0, math.sin(ph))
        c.key(0.6 * u, g)


BUTTERFLY = M(dict(pel=[0.0, 0.10, -0.60, 12, 0, 0], sp=[18, 0, 0], hd=[-28, 0, 0], legrel=[0.0]),
              dict(lf=[0.56, 0.10, 0.0, 82, 62, 8], rf=[0.56, 0.10, 0.0, 82, 62, 8],
                   lkp=[-0.3, -2.6, -0.5], rkp=[-0.3, -2.6, -0.5]),
              dict(mode=3, rhp=[-1.0, 0.5, -0.4]), dict(lh=[0.50, -0.36, 1.05], lhp=[1.0, 0.6, -0.4],
                                                        lhf=[0.15, -0.35, 1.0], lpa=[0, -1, 0]),
              flat(-0.04, -0.62, toward=(-0.40, 0.0), elev=26))


def anim_goalie_butterfly():
    c = clip("GoalieButterfly", 0.6, goalie=True, lag={"hd": 0.03})
    c.key(0.00, gready())
    c.key(0.18, M(BUTTERFLY, pel=[0.0, 0.08, -0.52, 14, 0, 0]), 0.5)
    c.key(0.30, M(BUTTERFLY, pel=[0.0, 0.10, -0.63, 12, 0, 0]), 0.6)
    c.key(0.60, BUTTERFLY)


def anim_goalie_glove_high():
    c = clip("GoalieGloveHigh", 0.5, goalie=True, lag={"hd": 0.02})
    c.key(0.00, gready())
    save = M(gready(crouch=0.20, lean=20), dict(pel=[0.12, 0.05, -0.18, 6, 10, -10], sp=[12, 14, -14], hd=[-18, 30, -10]),
             feet(0.31, rw=0.38, llift=0.10, yaw=20, edge=12),
             dict(lh=[0.78, -0.42, 1.82], lhp=[1.0, 0.2, -0.6], lhf=[0.4, -0.2, 1.0], lpa=[0, -1, 0]))
    c.key(0.16, save, 0.45)
    c.key(0.50, M(save, lh=[0.70, -0.40, 1.72], pel=[0.10, 0.05, -0.20, 6, 8, -8]))


def anim_goalie_blocker_high():
    c = clip("GoalieBlockerHigh", 0.5, goalie=True, lag={"hd": 0.02})
    c.key(0.00, M(gready(), dict(mode=1, rh=[-0.42, -0.36, 1.00], rhp=[-1.0, 0.5, -0.4], rhf=[-0.1, -0.4, 1.0],
                                 rpa=[0, -1, 0], sdir=[0.25, -0.55, -0.8])))
    save = M(gready(crouch=0.20, lean=20), dict(pel=[-0.12, 0.05, -0.18, 6, -10, 10], sp=[12, -14, 14], hd=[-18, -30, 10]),
             feet(0.31, lw=0.38, rlift=0.10, yaw=20, edge=12),
             dict(mode=1, rh=[-0.80, -0.38, 1.80], rhp=[-1.0, 0.2, -0.6], rhf=[-0.4, -0.2, 1.0], rpa=[0, -1, 0],
                  sdir=[0.3, -0.3, -0.9]))
    c.key(0.16, save, 0.45)
    c.key(0.50, M(save, rh=[-0.72, -0.36, 1.70], pel=[-0.10, 0.05, -0.20, 6, -8, 8]))


def anim_goalie_pad(name, side):
    c = clip(name, 0.5, goalie=True, lag={"hd": 0.02})
    c.key(0.00, gready())
    kick = "lf" if side > 0 else "rf"
    knee = "rf" if side > 0 else "lf"
    p = M(gready(), dict(pel=[0.22 * side, 0.08, -0.52, 10, 10 * side, -14 * side], sp=[14, 12 * side, -10 * side],
                         hd=[-24, 24 * side, 0]))
    p[kick] = [0.88, -0.10, 0.0, 70, 0, -20]
    p[knee] = [0.14, 0.32, 0.0, 30, 60, 0]
    p["lkp" if side < 0 else "rkp"] = [0, 0, -0.8]
    p["lkp" if side > 0 else "rkp"] = [0, -0.5, 0.6]
    p.update(flat(0.20 * side - 0.04, -0.62, toward=(-0.40, 0.0), elev=26))
    c.key(0.16, p, 0.45)
    c.key(0.50, M(p, pel=[0.20 * side, 0.08, -0.54, 10, 8 * side, -12 * side]))


def anim_goalie_dive(name, side):
    c = clip(name, 0.9, goalie=True, lag={"hd": 0.04, "lh": 0.03, "rh": 0.03})
    c.key(0.00, M(gready(), legrel=[0.0]))
    c.key(0.12, M(gready(crouch=0.36), dict(pel=[0.06 * side, 0.05, -0.36, 10, 0, 6 * side]), legrel=[0.0]), 0.6)
    stretch = dict(pel=[0.62 * side, 0.05, -0.50, 10, 0, -72 * side], sp=[4, 0, -16 * side], hd=[-10, 0, 20 * side],
                   legrel=[1.0], lf=[0.24, -0.04, 0.16, 10, 20, 0], rf=[0.18, 0.04, 0.17, 10, 20, 0])
    if side > 0:
        arms = dict(mode=3, rhp=[-1.0, 0.5, -0.4], lh=[0.35, -0.25, 2.00], lhp=[1.0, 0.2, 0.0], lhf=[0.2, -0.3, 1.0],
                    lpa=[0, -1, 0])
        arms.update(flat(0.40, -0.80, toward=(0.10, 0.10), elev=10))
    else:
        arms = dict(mode=1, rh=[-0.35, -0.25, 2.00], rhp=[-1.0, 0.2, 0.0], rhf=[-0.2, -0.3, 1.0], rpa=[0, -1, 0],
                    sdir=[-0.2, -0.5, 0.8], lh=[0.40, -0.30, 1.30], lhp=[1.0, 0.6, -0.4], lhf=[0.15, -0.35, 1.0],
                    lpa=[0, -1, 0])
    c.key(0.36, M(stretch, arms), 0.6)
    land = M(stretch, arms, dict(pel=[0.80 * side, 0.05, -0.80, 6, 0, -86 * side]))
    c.key(0.56, land, 0.5)
    c.key(0.90, M(land, hd=[-14, 0, 12 * side]))


def anim_goalie_poke():
    c = clip("GoaliePoke", 0.5, goalie=True, poke=0.18, lag={"hd": 0.03})
    c.key(0.00, gready())
    c.key(0.08, M(gready(crouch=0.32), flat(-0.10, -0.70, toward=(-0.40, 0.0), elev=30)), 0.6)
    jab = M(gready(crouch=0.30, lean=54), dict(pel=[0.0, -0.08, -0.32, 22, 0, 0]),
            dict(rhp=[-1.0, 0.3, -0.2]), flat(-0.10, -1.62, toward=(-0.30, 0.0), elev=22))
    c.key(0.18, jab, 0.4)
    c.key(0.30, M(jab, sc=[-0.10, -1.55, PH]), 0.8)
    c.key(0.50, gready())


def anim_goalie_cover():
    c = clip("GoalieCover", 0.6, goalie=True, lag={"hd": 0.03})
    c.key(0.00, gready())
    c.key(0.20, M(BUTTERFLY, pel=[0.0, 0.0, -0.56, 30, 0, 0], sp=[30, 0, 0]), 0.6)
    cover = M(BUTTERFLY, dict(pel=[0.0, -0.10, -0.64, 50, 0, 0], sp=[34, 0, 0], hd=[-40, 0, 0],
                              lh=[0.06, -0.62, 1.30], lhp=[1.0, 0.0, -0.6], lhf=[-0.3, -0.6, -0.6], lpa=[0, 0, -1]),
              flat(-0.12, -0.70, toward=(-0.40, 0.10), elev=22))
    c.key(0.40, cover, 0.6)
    c.key(0.60, M(cover, pel=[0.0, -0.10, -0.66, 52, 0, 0]))


# ---------------------------------------------------------------------------
# Referee (uses SK_Skater with the stick hidden)
# ---------------------------------------------------------------------------
def ref_stand(lean=6.0):
    return M(body(0.04, lean, 0, nod=-8), feet(0.16, yaw=8, edge=0),
             dict(mode=1, lh=[0.27, -0.02, 0.98], rh=[-0.27, -0.02, 0.98], lhp=[0.3, 1.0, 0.0], rhp=[-0.3, 1.0, 0.0],
                  lhf=[0.0, 0.0, -1.0], rhf=[0.0, 0.0, -1.0], sdir=[0.0, 0.2, -1.0]))


def anim_ref_drop():
    c = clip("RefDrop", 1.0, drop=0.55, lag={"hd": 0.05})
    c.key(0.00, ref_stand())
    bend = M(body(0.14, 62, 0, nod=-40, dy=0.10), feet(0.22, yaw=10, edge=0),
             dict(mode=1, rh=[-0.05, -0.66, 1.36], rhp=[-1.0, 0.4, -0.2], rhf=[0.0, -0.6, -0.8], rpa=[0, 0, -1],
                  lh=[0.30, 0.10, 1.05], lhp=[0.4, 1.0, 0.0], lhf=[0.2, 0.3, -1.0], sdir=[0.0, 0.3, -1.0]))
    c.key(0.30, bend, 0.7)
    c.key(0.52, M(bend, rh=[-0.05, -0.68, 1.37]), 0.6)
    c.key(0.58, M(bend, rh=[-0.05, -0.60, 1.46], rhf=[0.0, -0.3, -0.9]), 0.4)
    c.key(0.78, M(body(0.10, 30, 0, nod=-20, dy=0.16), feet(0.20, yaw=8, edge=0), bend,
                  dict(rh=[-0.24, -0.20, 1.05])), 0.7)
    c.key(1.00, ref_stand(10))


def anim_ref_signal():
    c = clip("RefSignal", 1.5, lag={"hd": 0.05})
    c.key(0.00, ref_stand())
    point = M(ref_stand(2), dict(hd=[-6, -10, 0], sp=[-2, -14, 0],
                                 rh=[-0.30, -0.66, 1.60], rhp=[-1.0, 0.4, -0.4], rhf=[-0.2, -1.0, 0.2], rpa=[0, 0, -1]))
    c.key(0.20, point, 0.4)
    c.key(0.45, M(point, rh=[-0.30, -0.44, 1.46]), 0.6)
    c.key(0.65, M(point, rh=[-0.32, -0.70, 1.64]), 0.4)
    c.key(1.20, M(point, rh=[-0.32, -0.68, 1.62]), 0.8)
    c.key(1.50, M(point, rh=[-0.30, -0.62, 1.55]))


# ---------------------------------------------------------------------------
def build_all():
    anim_idle()
    skate_clip("Skate", 0.80)
    skate_clip("SkateTurbo", 0.60, turbo=True)
    anim_glide()
    anim_skate_back()
    skate_clip("Carry", 0.80, carry=True)
    anim_stop()
    anim_shot_wrist()
    anim_slap_windup()
    anim_slap_release()
    anim_one_timer()
    anim_pass()
    anim_check()
    anim_power_check()
    anim_poke_check()
    anim_hook()
    anim_dive()
    anim_hit_fall()
    anim_flip()
    anim_get_up()
    anim_celebrate1()
    anim_celebrate2()
    anim_celebrate3()
    anim_dejected()
    anim_faceoff_ready()
    anim_faceoff_win()
    anim_fight_idle()
    anim_fight_jab()
    anim_fight_punch()
    anim_fight_uppercut()
    anim_fight_grab()
    anim_fight_block()
    anim_fight_hit()
    anim_fight_ko()
    anim_goalie_ready()
    anim_goalie_shuffle("GoalieShuffleL", 1)
    anim_goalie_shuffle("GoalieShuffleR", -1)
    anim_goalie_butterfly()
    anim_goalie_glove_high()
    anim_goalie_blocker_high()
    anim_goalie_pad("GoaliePadL", 1)
    anim_goalie_pad("GoaliePadR", -1)
    anim_goalie_dive("GoalieDiveL", 1)
    anim_goalie_dive("GoalieDiveR", -1)
    anim_goalie_poke()
    anim_goalie_cover()
    anim_ref_drop()
    anim_ref_signal()
    return CLIPS, GOALIE
