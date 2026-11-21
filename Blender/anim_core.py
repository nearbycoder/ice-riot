"""ICE RIOT animation framework (used by gen_anims.py).

A clip is a list of keys (time_s, pose_dict). Every numeric pose parameter is interpolated with a
tension-controlled Catmull-Rom spline (cyclic for loops), optionally with per-group lag (overlap /
follow-through), then the full body is solved with IK every frame and baked.

Pose parameters (meters / degrees, character faces -Y, character-left = +X):
  pel  [dx, dy, dz, rx, ry, rz]     pelvis offset + rotation (rx>0 tips forward, ry>0 twists left, rz>0 leans right)
  sp   [bend, twist, lean]          spread over spine_01..03
  hd   [nod, turn, tilt]            nod>0 looks down, turn>0 looks left
  cl   [shrug_l, fwd_l, shrug_r, fwd_r]
  lf/rf [out, y, lift, yaw_out, pitch, edge_in]   skate: ankle x (outward magnitude), y, height above
         the ice contact, toe-out yaw, toe-down pitch, inside-edge roll.  (legrel=1: out/y/lift are
         pelvis-relative rest-space ankle coords x_out, y, z)
  lkp/rkp [x, y, z]                 extra knee pole offset (added to the default forward pole)
  mode  0 = both hands on the stick (blade target), 1 = stick follows the right hand (free hands),
        3 = only the right hand on the stick (blade target), left hand free
  sc   [x, y, z]                    stick cradle (puck center) target, world
  sa   [x, y, z]                    the shaft heads (horizontally) from the cradle toward this point
  st   [tilt, elev]                 blade face roll about the shaft (deg), shaft elevation (42 = blade flat)
  lh/rh [x, y, z]                   free hand wrist targets, chest-relative rest space
  lhp/rhp [x, y, z]                 elbow poles (chest-relative)
  lhf/rhf [x, y, z]                 finger direction (chest-relative), lpa/rpa palm direction
  sdir [x, y, z]                    mode 1: shaft direction (grip -> blade), chest-relative
  fist [l, r]                       0..1 (unused by the mesh, kept for future finger bones)
"""

import math
import bpy
from mathutils import Vector, Matrix, Euler, Quaternion

import ir_rig as rig

S = 100.0
REST_ANKLE_Z = rig._leg_pts(1)[2].z
F0 = (rig._leg_pts(1)[3] - rig._leg_pts(1)[2]).normalized()        # rest foot bone direction
CONTACTS = [Vector((0.0, -0.155, -0.161)), Vector((0.0, 0.070, -0.161))]  # runner contact points rel. ankle

DEFAULT = dict(
    pel=[0, 0, 0, 0, 0, 0], sp=[0, 0, 0], hd=[0, 0, 0], cl=[0, 0, 0, 0],
    lf=[0.15, 0.0, 0.0, 8, 0, 0], rf=[0.15, 0.0, 0.0, 8, 0, 0], lkp=[0, 0, 0], rkp=[0, 0, 0],
    sc=[-0.35, -0.75, rig.PUCK_HALF_T], sa=[0.10, -0.05, 1.0], st=[0.0, 42.0],
    lh=[0.28, -0.25, 1.05], rh=[-0.28, -0.25, 1.05],
    lhp=[0.6, 0.6, -0.3], rhp=[-0.6, 0.6, -0.3],
    lhf=[0.0, -0.4, -0.9], rhf=[0.0, -0.4, -0.9], lpa=[-1, 0, 0], rpa=[1, 0, 0],
    sdir=[-0.2, -0.5, -0.85], fist=[1, 1],
)
DISCRETE = ("mode",)


def merged(p):
    out = {k: list(v) for k, v in DEFAULT.items()}
    out["mode"] = 0
    out["legrel"] = [0.0]
    for k, v in p.items():
        out[k] = list(v) if isinstance(v, (list, tuple)) else v
    if not isinstance(out["legrel"], list):
        out["legrel"] = [float(out["legrel"])]
    return out


# ---------------------------------------------------------------------------
# Interpolation
# ---------------------------------------------------------------------------
class Clip:
    def __init__(self, name, length, loop=False, events=None, lag=None):
        self.name = name
        self.length = length
        self.loop = loop
        self.events = events or {}
        self.keys = []          # (t, pose, tension)
        self.lag = lag or {"hd": 0.05, "cl": 0.03, "lh": 0.02, "rh": 0.02}
        self.post = None        # optional fn(t, pose) -> pose (procedural layers)

    def key(self, t, pose, tension=1.0):
        self.keys.append((t, merged(pose), tension))
        return self

    def _segment(self, t):
        ks = self.keys
        if self.loop:
            t = t % self.length
        if t <= ks[0][0] and not self.loop:
            return 0, 0, 0.0
        for i in range(len(ks) - 1):
            if ks[i][0] <= t <= ks[i + 1][0]:
                d = ks[i + 1][0] - ks[i][0]
                return i, i + 1, 0.0 if d <= 0 else (t - ks[i][0]) / d
        if self.loop:
            # between the last key and the first key + length
            i = len(ks) - 1
            d = ks[0][0] + self.length - ks[i][0]
            return i, 0, 0.0 if d <= 0 else (t - ks[i][0]) / d
        return len(ks) - 1, len(ks) - 1, 0.0

    def _val(self, idx, k, comp):
        return self.keys[idx][1][k][comp]

    def sample_param(self, t, k):
        ks = self.keys
        n = len(ks)
        if n == 1:
            return list(ks[0][1][k])
        i0, i1, u = self._segment(t)
        if self.loop:
            im, i2 = (i0 - 1) % n, (i1 + 1) % n
        else:
            im, i2 = max(i0 - 1, 0), min(i1 + 1, n - 1)

        def kt(i):
            return ks[i][0]
        t0, t1 = kt(i0), kt(i1)
        if self.loop and t1 <= t0:
            t1 += self.length
        tm, t2 = kt(im), kt(i2)
        if self.loop:
            if tm >= t0:
                tm -= self.length
            if t2 <= t1:
                t2 += self.length
        out = []
        dur = max(1e-6, t1 - t0)
        ta = ks[i0][2]
        tb = ks[i1][2]
        for c in range(len(ks[i0][1][k])):
            p0, p1 = ks[i0][1][k][c], ks[i1][1][k][c]
            pm, p2 = ks[im][1][k][c], ks[i2][1][k][c]
            m0 = ta * ((p1 - pm) / max(1e-6, t1 - tm)) * dur if im != i0 else 0.0
            m1 = tb * ((p2 - p0) / max(1e-6, t2 - t0)) * dur if i2 != i1 else 0.0
            if not self.loop and i0 == 0:
                m0 = ta * (p1 - p0) if False else m0
            h00 = 2 * u ** 3 - 3 * u ** 2 + 1
            h10 = u ** 3 - 2 * u ** 2 + u
            h01 = -2 * u ** 3 + 3 * u ** 2
            h11 = u ** 3 - u ** 2
            out.append(h00 * p0 + h10 * m0 + h01 * p1 + h11 * m1)
        return out

    def sample(self, t):
        pose = {}
        for k in self.keys[0][1]:
            if k in DISCRETE:
                i0, i1, u = self._segment(t)
                pose[k] = self.keys[i0][1][k]
                continue
            lag = self.lag.get(k, 0.0)
            tt = t - lag
            if not self.loop:
                tt = max(0.0, tt)
            pose[k] = self.sample_param(tt, k)
        if self.post:
            pose = self.post(t, pose)
        return pose


# ---------------------------------------------------------------------------
# Solver
# ---------------------------------------------------------------------------
class Solver:
    def __init__(self, arm):
        self.arm = arm
        self.P = rig.Poser(arm, S=S)
        st = rig.stick_rest()
        pb = arm.pose.bones["stick"]
        R0 = pb.bone.matrix_local.to_3x3().normalized()
        G0 = pb.bone.head_local / S
        self.stick_R0 = R0
        self.c_l = R0.transposed() @ (st["cradle"] - G0)
        self.b_l = R0.transposed() @ (st["butt"] - G0)
        self.z_l = R0.transposed() @ st["up"]
        self.down_l = R0.transposed() @ st["down"]
        self.max_err = 0.0
        self.min_blade = 0.0

    # -- spaces ------------------------------------------------------------
    def carried(self, bone, pt_m):
        pb = self.P.pb[bone]
        M = pb.matrix @ pb.bone.matrix_local.inverted()
        return (M @ (Vector(pt_m) * S)) / S

    def cdir(self, bone, d):
        pb = self.P.pb[bone]
        R = pb.matrix.to_3x3() @ pb.bone.matrix_local.to_3x3().inverted()
        return (R @ Vector(d)).normalized()

    # -- body --------------------------------------------------------------
    def apply(self, p):
        P = self.P
        P.reset()
        p["sc"][2] = max(rig.PUCK_HALF_T, p["sc"][2])
        pe = p["pel"]
        P.pelvis(pe[0], pe[1], pe[2], pe[3], pe[4], pe[5])
        P.spine(*p["sp"])
        P.head(*p["hd"])
        c = p["cl"]
        P.clavicle("l", c[0], c[1])
        P.clavicle("r", c[2], c[3])
        P.update()
        self.legs(p)
        mode = int(p["mode"])
        if mode in (0, 3):
            self.stick_by_blade(p, two_hands=(mode == 0))
            if mode == 3:
                self.free_arm("l", p)
        else:
            self.free_arm("r", p)
            self.free_arm("l", p)
            self.stick_follow(p)
        P.update()

    def legs(self, p):
        w = max(0.0, min(1.0, p["legrel"][0]))
        Rp = (self.P.pb["pelvis"].matrix.to_3x3().normalized() @
              self.P.pb["pelvis"].bone.matrix_local.to_3x3().inverted())
        for side, s in (("l", 1), ("r", -1)):
            out, y, lift, yaw, pitch, edge = p[side + "f"]
            R = (Matrix.Rotation(math.radians(yaw * s), 3, "Z") @ Matrix.Rotation(math.radians(pitch), 3, "X") @
                 Matrix.Rotation(math.radians(-edge * s), 3, "Y"))
            fdir = R @ F0
            fside = R @ Vector((1, 0, 0))
            kp = Vector(p[side + "kp"])
            kp.x *= s
            pole = Matrix.Rotation(math.radians(yaw * s), 3, "Z") @ Vector((0.18 * s, -1.0, 0.0)) + kp
            cz = max(-(R @ o).z for o in CONTACTS)
            ank_w = Vector((out * s, y, cz + max(0.0, lift)))
            if w > 0.0:
                ank_r = self.carried("pelvis", (out * s, y, lift))
                ank = ank_w.lerp(ank_r, w)
                fdir = fdir.lerp(Rp @ fdir, w).normalized()
                fside = fside.lerp(Rp @ fside, w).normalized()
                pole = pole.lerp(Rp @ pole, w)
            else:
                ank = ank_w
            self.P.leg(side, ank, knee_pole=pole, foot_dir=fdir, foot_side=fside)
            self._check("calf_" + side, ank, tail=True)

    def _check(self, bone, target_m, tail=True):
        pb = self.P.pb[bone]
        pos = (pb.tail if tail else pb.head) / S
        self.max_err = max(self.max_err, (pos - Vector(target_m)).length)

    # -- stick ---------------------------------------------------------------
    def stick_frame(self, C, aim, tilt, elev=42.0):
        C = Vector(C)
        h = Vector(aim) - C
        h.z = 0.0
        h = h.normalized() if h.length > 1e-5 else Vector((0, 1, 0))
        e = math.radians(elev)
        u_w = (h * math.cos(e) + Vector((0, 0, 1)) * math.sin(e)).normalized()
        u_l = (self.b_l - self.c_l).normalized()
        e1 = u_l
        e2 = (self.z_l - e1 * e1.dot(self.z_l)).normalized()
        e3 = e1.cross(e2)
        U = Vector((0, 0, 1))
        f1 = u_w
        f2 = U - f1 * f1.dot(U)
        if f2.length < 1e-4:
            f2 = Vector((0, -1, 0)) - f1 * f1.y
        f2.normalize()
        if tilt:
            f2 = Matrix.Rotation(math.radians(tilt), 3, f1) @ f2
        f3 = f1.cross(f2)
        Rw = Matrix((f1, f2, f3)).transposed() @ Matrix((e1, e2, e3))
        G = C - Rw @ self.c_l
        butt = G + Rw @ self.b_l
        return Rw, G, butt, u_w

    def hand_on_shaft(self, side, grip, shaft_up, pole):
        """Place a hand so its grip point (wrist + fingers*0.075) lies on the shaft at `grip`."""
        s = 1 if side == "l" else -1
        sh = self.P.pb["upperarm_" + side].head / S
        away = (Vector(grip) - sh)
        Y = away - shaft_up * away.dot(shaft_up)
        if Y.length < 1e-4:
            Y = Vector((0, -1, 0))
        Y.normalize()
        # thumb up the shaft for the bottom hand, down the shaft for the top hand
        Z = shaft_up if side == "r" else -shaft_up
        X = Y.cross(Z).normalized()
        wrist = Vector(grip) - Y * 0.075
        self.P.arm(side, wrist, elbow_pole=pole, fingers=Y, palm=X * (-s))
        self._check("lowerarm_" + side, wrist)

    def stick_by_blade(self, p, two_hands=True):
        Rw, G, butt, u_w = self.stick_frame(p["sc"], p["sa"], p["st"][0], p["st"][1])
        sh_r = self.P.pb["upperarm_r"].head / S
        self.hand_on_shaft("r", G, u_w, Vector(p["rhp"]) if p.get("rhp_world") else self.cdir("spine_03", p["rhp"]))
        if two_hands:
            top = butt - u_w * 0.07
            self.hand_on_shaft("l", top, u_w, self.cdir("spine_03", p["lhp"]))
        self.P.set_world_matrix3("stick", Rw)
        # keep the stick in the hand: pivot it through the actual grip so the blade stays on its target line
        self.P.update()
        Ga = self.P.pb["stick"].head / S
        C = Vector(p["sc"])
        v1 = Rw @ self.c_l
        v2 = C - Ga
        if v2.length > 1e-4:
            q = v1.rotation_difference(v2)
            self.P.set_world_matrix3("stick", q.to_matrix() @ Rw)
        self.blade_err = max(getattr(self, "blade_err", 0.0), (Ga - G).length)

    def _place_stick_head(self, G):
        """Translate the stick bone so its head sits exactly at G (absorbs the IK residual)."""
        self.P.update()
        pb = self.P.pb["stick"]
        cur = pb.head / S
        delta = Vector(G) - cur
        if delta.length > 1e-5:
            parent_R = pb.parent.matrix.to_3x3().normalized()
            rest_rel = (pb.parent.bone.matrix_local.inverted() @ pb.bone.matrix_local).to_3x3()
            local = (parent_R @ rest_rel).inverted() @ (delta * S)
            pb.location = pb.location + local
            self.P.update()

    def stick_follow(self, p):
        d = self.cdir("spine_03", p["sdir"])
        hand = self.P.pb["hand_r"]
        # blade 'up' = chest forward x shaft, roughly
        fwd = self.cdir("spine_03", (0, -1, 0))
        u_w = -d
        u_l = (self.b_l - self.c_l).normalized()
        e1 = u_l
        e2 = (self.z_l - e1 * e1.dot(self.z_l)).normalized()
        e3 = e1.cross(e2)
        f1 = u_w
        U = Vector((0, 0, 1)) if abs(u_w.z) < 0.9 else fwd
        f2 = (U - f1 * f1.dot(U)).normalized()
        f3 = f1.cross(f2)
        Rw = Matrix((f1, f2, f3)).transposed() @ Matrix((e1, e2, e3))
        self.P.set_world_matrix3("stick", Rw)

    def to_mode1(self, p):
        """Solve a stick-hold pose (mode 0/3) and re-express the arms + stick as an equivalent mode-1 pose,
        so clips that switch hold modes interpolate without pops."""
        import copy
        q = copy.deepcopy(p)
        self.apply(q)
        self.P.update()
        sp = self.P.pb["spine_03"]
        M = sp.matrix @ sp.bone.matrix_local.inverted()
        Mi = M.inverted()
        Ri = M.to_3x3().normalized().inverted()
        out = copy.deepcopy(p)
        out["mode"] = 1
        for side, s in (("l", 1), ("r", -1)):
            if p["mode"] == 3 and side == "l":
                continue
            ua = self.P.pb["upperarm_" + side]
            la = self.P.pb["lowerarm_" + side]
            hd = self.P.pb["hand_" + side]
            sh, el, wr = ua.head / S, la.head / S, hd.head / S
            out[side + "h"] = list((Mi @ (wr * S)) / S)
            pole = el - (sh + wr) * 0.5
            out[side + "hp"] = list((Ri @ pole).normalized())
            R = hd.matrix.to_3x3().normalized()
            Y = Vector((R[0][1], R[1][1], R[2][1]))
            X = Vector((R[0][0], R[1][0], R[2][0]))
            out[side + "hf"] = list((Ri @ Y).normalized())
            out[side[0] + "pa"] = list((Ri @ (X * (-s))).normalized())
        st = self.P.pb["stick"].matrix.to_3x3().normalized()
        Ys = Vector((st[0][1], st[1][1], st[2][1]))
        out["sdir"] = list((Ri @ Ys).normalized())
        return out

    def free_arm(self, side, p):
        s = 1 if side == "l" else -1
        w = self.carried("spine_03", p[side + "h"])
        pole = self.cdir("spine_03", p[side + "hp"])
        fingers = self.cdir("spine_03", p[side + "hf"])
        palm = self.cdir("spine_03", p[side[0] + "pa"])
        self.P.arm(side, w, elbow_pole=pole, fingers=fingers, palm=palm)
        self._check("lowerarm_" + side, w)
