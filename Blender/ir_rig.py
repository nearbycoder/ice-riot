"""ICE RIOT skater skeleton (SK_Skater_Skeleton) + IK pose builder.

Built in meters, character facing -Y (Blender front), character-left = +X.  Bone frames:

* vertical bones (root, pelvis, spine_*, neck, head): Y = up, Z = forward (-Y)
      rx > 0 bends forward, rz > 0 leans to the character's right, ry > 0 twists to the left
* arm bones: Y along the limb, Z = backward (+Y) in rest; elbow pole is "+Z"
* leg bones: Y along the limb (down), Z = backward; knees bend toward -Z (forward)
* feet: Y toward the toes, Z = down
* stick: child of hand_r, head at the bottom-hand grip, Y runs DOWN the shaft toward the blade
* stick_blade: child of stick, head = where the puck CENTER sits when cradled on the forehand
  (1.27 cm above the blade bottom, in front of the forehand face), local X along the blade toward the toe,
  Y = forehand face normal, Z = blade up.  The blade is flat on the ice when the shaft is at 42 deg.

Proportions: 1.95 m on skates (blade bottom z = 0), chunky arcade build.
"""

import bpy
import math
from mathutils import Vector, Matrix, Euler

ARM_ABDUCTION = math.radians(40.0)
UPPER_ARM = 0.30
FOREARM = 0.28
HAND = 0.17

SHOULDER_Z = 1.50
HIP_Z = 0.98

# stick geometry (rest pose, meters)
STICK_LIE = math.radians(62.0)            # shaft angle above the ice in the bind pose
STICK_LIE_PLAY = math.radians(42.0)       # shaft angle at which the blade sits flat on the ice
STICK_HEADING = Vector((-0.26, -1.0, 0.0)).normalized()   # horizontal direction from grip toward the blade
STICK_ABOVE_GRIP = 0.42                    # butt end above the bottom-hand grip
BLADE_LEN = 0.32
BLADE_H = 0.075
BLADE_T = 0.014
PUCK_R = 0.038
PUCK_HALF_T = 0.0127
CRADLE_ALONG = 0.14                        # puck center along the blade from the heel


def _arm_pts(side):
    shoulder = Vector((0.205 * side, 0.012, SHOULDER_Z))
    d = Vector((math.sin(ARM_ABDUCTION) * side, 0.0, -math.cos(ARM_ABDUCTION)))
    elbow = shoulder + d * UPPER_ARM
    wrist = elbow + d * FOREARM
    tip = wrist + d * HAND
    return shoulder, elbow, wrist, tip, d


def _leg_pts(side):
    hip = Vector((0.11 * side, 0.0, HIP_Z))
    knee = Vector((0.12 * side, -0.02, 0.565))
    ankle = Vector((0.125 * side, 0.025, 0.165))
    ball = Vector((0.125 * side, -0.105, 0.085))
    toe = Vector((0.125 * side, -0.19, 0.085))
    return hip, knee, ankle, ball, toe


def grip_point(side="r"):
    sh, el, wr, tip, d = _arm_pts(-1 if side == "r" else 1)
    return wr + d * 0.075


def stick_rest():
    """World-space rest frame of the stick (bind pose). The blade is built flat for a 42 deg shaft; in the
    steeper bind pose its toe is tipped up by (62 - 42) deg about the face normal."""
    G = grip_point("r")
    down = Vector((STICK_HEADING.x * math.cos(STICK_LIE), STICK_HEADING.y * math.cos(STICK_LIE),
                   -math.sin(STICK_LIE)))
    N = Vector((0, 0, 1)).cross(STICK_HEADING).normalized()      # forehand face normal (+X side, right shot)
    tip = Matrix.Rotation(STICK_LIE - STICK_LIE_PLAY, 3, N)
    B = tip @ STICK_HEADING
    if B.z < 0:
        tip = Matrix.Rotation(-(STICK_LIE - STICK_LIE_PLAY), 3, N)
        B = tip @ STICK_HEADING
    up = (tip @ Vector((0, 0, 1))).normalized()
    L_grip_heel = (G.z - 0.03) / math.sin(STICK_LIE)
    heel = G + down * L_grip_heel                 # where the shaft meets the blade, 3 cm above its bottom
    heel_bottom = heel - up * 0.03
    butt = G - down * STICK_ABOVE_GRIP
    cradle = heel_bottom + B * CRADLE_ALONG + N * (PUCK_R + BLADE_T * 0.5 + 0.004) + up * PUCK_HALF_T
    return dict(grip=G, down=down, heel=heel, heel_bottom=heel_bottom, B=B, N=N, up=up, butt=butt,
                cradle=cradle, L_grip_heel=L_grip_heel)


def bone_table():
    """(name, head, tail, parent, connected, z_reference / roll spec, deform)"""
    fwd = Vector((0, -1, 0))
    back = Vector((0, 1, 0))
    up = Vector((0, 0, 1))
    down = Vector((0, 0, -1))
    t = [
        ("root", (0, 0, 0), (0, 0, 0.25), None, False, fwd, False),
        ("pelvis", (0, 0, 1.01), (0, 0, 1.11), "root", False, fwd, True),
        ("spine_01", (0, 0, 1.11), (0, 0.005, 1.26), "pelvis", True, fwd, True),
        ("spine_02", (0, 0.005, 1.26), (0, 0.010, 1.41), "spine_01", True, fwd, True),
        ("spine_03", (0, 0.010, 1.41), (0, 0.010, 1.555), "spine_02", True, fwd, True),
        ("neck", (0, 0.006, 1.555), (0, -0.004, 1.665), "spine_03", False, fwd, True),
        ("head", (0, -0.004, 1.665), (0, -0.004, 1.93), "neck", True, fwd, True),
    ]
    for side, s in (("l", 1), ("r", -1)):
        sh, el, wr, tip, d = _arm_pts(s)
        t += [
            ("clavicle_" + side, (0.035 * s, 0.0, 1.50), (0.19 * s, 0.012, SHOULDER_Z + 0.005), "spine_03", False, up,
             True),
            ("upperarm_" + side, tuple(sh), tuple(el), "clavicle_" + side, False, back, True),
            ("lowerarm_" + side, tuple(el), tuple(wr), "upperarm_" + side, True, back, True),
            ("hand_" + side, tuple(wr), tuple(tip), "lowerarm_" + side, True, back, True),
        ]
        hip, knee, ankle, ball, toe = _leg_pts(s)
        t += [
            ("thigh_" + side, tuple(hip), tuple(knee), "pelvis", False, back, True),
            ("calf_" + side, tuple(knee), tuple(ankle), "thigh_" + side, True, back, True),
            ("foot_" + side, tuple(ankle), tuple(ball), "calf_" + side, True, down, True),
            ("toe_" + side, tuple(ball), tuple(toe), "foot_" + side, True, down, True),
        ]
    st = stick_rest()
    t.append(("stick", tuple(st["grip"]), tuple(st["grip"] + st["down"] * 0.5), "hand_r", False, ("X", st["N"]),
              True))
    c = st["cradle"]
    t.append(("stick_blade", tuple(c), tuple(c + st["N"] * 0.06), "stick", False, ("X", st["B"]), True))
    return t


DEFORM_BONES = [b[0] for b in bone_table() if b[6] and b[0] not in ("stick", "stick_blade")]
BODY_BONES = DEFORM_BONES


def build_armature(name="Armature"):
    data = bpy.data.armatures.new(name)
    arm = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(arm)
    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = data.edit_bones
    for name_, head, tail, parent, connected, zref, deform in bone_table():
        b = eb.new(name_)
        b.head = head
        b.tail = tail
        if parent:
            b.parent = eb[parent]
            b.use_connect = connected
        if isinstance(zref, tuple) and zref[0] == "X":
            # align the bone's local X with a given world vector
            b.align_roll(Vector(zref[1]).cross(b.y_axis) * -1.0)
            # verify: roll so that x_axis ~ zref; brute force the sign
            target = Vector(zref[1]).normalized()
            best, bestd = 0.0, -2
            for k in range(0, 360, 2):
                b.roll = math.radians(k)
                dd = b.x_axis.dot(target)
                if dd > bestd:
                    best, bestd = b.roll, dd
            b.roll = best
        else:
            b.align_roll(zref)
        b.use_deform = deform
    bpy.ops.object.mode_set(mode="OBJECT")
    data.display_type = "STICK"
    return arm


# ---------------------------------------------------------------------------
# Pose builder
# ---------------------------------------------------------------------------
def _frame_from_yz(y, zref):
    y = Vector(y).normalized()
    z = Vector(zref) - y * Vector(zref).dot(y)
    if z.length < 1e-6:
        z = Vector((0, 1, 0)) - y * y.y
        if z.length < 1e-6:
            z = Vector((0, 0, 1)) - y * y.z
    z.normalize()
    x = y.cross(z)
    x.normalize()
    return Matrix((x, y, z)).transposed()


def _frame_from_yx(y, xref):
    y = Vector(y).normalized()
    x = Vector(xref) - y * Vector(xref).dot(y)
    if x.length < 1e-6:
        x = Vector((1, 0, 0)) - y * y.x
    x.normalize()
    z = x.cross(y)
    z.normalize()
    return Matrix((x, y, z)).transposed()


class Poser:
    """Sets pose-bone rotations from intuitive targets (meters, armature space, character facing -Y).
    S = armature units per meter (100 after the rig is converted to centimeters)."""

    def __init__(self, arm, S=1.0):
        self.obj = arm
        self.S = S
        self.pb = arm.pose.bones
        for p in self.pb:
            p.rotation_mode = "QUATERNION"
        self._prev = {}

    def reset(self):
        for p in self.pb:
            p.location = (0, 0, 0)
            p.rotation_quaternion = (1, 0, 0, 0)
            p.scale = (1, 1, 1)
        self.update()

    def update(self):
        bpy.context.view_layer.update()

    def v(self, p):
        return Vector(p) * self.S

    def euler(self, name, rx=0.0, ry=0.0, rz=0.0):
        q = Euler((math.radians(rx), math.radians(ry), math.radians(rz)), "XYZ").to_quaternion()
        self.pb[name].rotation_quaternion = q

    def pelvis(self, dx=0.0, dy=0.0, dz=0.0, rx=0.0, ry=0.0, rz=0.0):
        pb = self.pb["pelvis"]
        rest = pb.bone.matrix_local.to_3x3()
        pb.location = rest.inverted() @ self.v((dx, dy, dz))
        self.euler("pelvis", rx, ry, rz)

    def root(self, dx=0.0, dy=0.0, dz=0.0, rx=0.0, ry=0.0, rz=0.0):
        pb = self.pb["root"]
        rest = pb.bone.matrix_local.to_3x3()
        pb.location = rest.inverted() @ self.v((dx, dy, dz))
        self.euler("root", rx, ry, rz)

    def spine(self, bend=0.0, twist=0.0, lean=0.0, weights=(0.3, 0.35, 0.35)):
        for name, w in zip(("spine_01", "spine_02", "spine_03"), weights):
            self.euler(name, bend * w, twist * w, lean * w)

    def head(self, nod=0.0, turn=0.0, tilt=0.0):
        self.euler("neck", nod * 0.4, turn * 0.4, tilt * 0.4)
        self.euler("head", nod * 0.6, turn * 0.6, tilt * 0.6)

    def _set_world_rot(self, name, R):
        pb = self.pb[name]
        R_rest = pb.bone.matrix_local.to_3x3()
        if pb.parent:
            Mp = pb.parent.matrix.to_3x3().normalized()
            Rp_rest = pb.parent.bone.matrix_local.to_3x3()
            base = Mp @ Rp_rest.inverted() @ R_rest
        else:
            base = R_rest
        basis = base.inverted() @ R
        pb.rotation_quaternion = basis.to_quaternion()

    def set_world_matrix3(self, name, R):
        self._set_world_rot(name, R)
        self.update()

    def aim(self, name, direction, zref):
        self._set_world_rot(name, _frame_from_yz(direction, zref))
        self.update()

    def aim_x(self, name, direction, xref):
        self._set_world_rot(name, _frame_from_yx(direction, xref))
        self.update()

    def _two_bone(self, upper, lower, target, pole, zsign):
        self.update()
        pu = self.pb[upper]
        pl = self.pb[lower]
        S0 = pu.head.copy()
        L1 = (pu.bone.tail_local - pu.bone.head_local).length
        L2 = (pl.bone.tail_local - pl.bone.head_local).length
        T = Vector(target)
        D = T - S0
        dist = max(min(D.length, (L1 + L2) * 0.9995), abs(L1 - L2) + 1e-4)
        Dn = D.normalized()
        a = (L1 * L1 - L2 * L2 + dist * dist) / (2.0 * dist)
        h = math.sqrt(max(L1 * L1 - a * a, 0.0))
        P = Vector(pole)
        P = P - Dn * P.dot(Dn)
        if P.length < 1e-6:
            P = Vector((0, 1, 0)) - Dn * Dn.y
        P.normalize()
        E = S0 + Dn * a + P * h
        W = S0 + Dn * dist
        self.aim(upper, E - S0, P * zsign)
        self.aim(lower, W - E, P * zsign)
        return E, W

    def arm(self, side, hand, elbow_pole=(0, 1, 0), fingers=None, palm=None):
        s = 1 if side == "l" else -1
        E, W = self._two_bone("upperarm_" + side, "lowerarm_" + side, self.v(hand), Vector(elbow_pole), +1)
        if fingers is None:
            fingers = (W - E).normalized()
        if palm is None:
            palm = Vector((-s, 0, 0))
        self.aim_x("hand_" + side, Vector(fingers), Vector(palm) * (-s))
        return W

    def leg(self, side, ankle, knee_pole=(0, -1, 0), foot_dir=None, foot_side=None, toe_bend=0.0):
        self._two_bone("thigh_" + side, "calf_" + side, self.v(ankle), Vector(knee_pole), -1)
        if foot_dir is None:
            foot_dir = (0.0, -0.84, -0.54)
        self.aim_x("foot_" + side, Vector(foot_dir), Vector(foot_side) if foot_side else Vector((1, 0, 0)))
        self.euler("toe_" + side, toe_bend, 0, 0)

    def clavicle(self, side, shrug=0.0, forward=0.0):
        s = 1 if side == "l" else -1
        self.euler("clavicle_" + side, shrug, 0.0, -forward * s)

    def key(self, frame, bones=None):
        self.update()
        for pb in self.pb:
            if bones and pb.name not in bones:
                continue
            q = pb.rotation_quaternion.copy()
            prev = self._prev.get(pb.name)
            if prev is not None and prev.dot(q) < 0:
                q.negate()
                pb.rotation_quaternion = q
            self._prev[pb.name] = q.copy()
            pb.keyframe_insert("rotation_quaternion", frame=frame)
            if pb.name in ("pelvis", "root"):
                pb.keyframe_insert("location", frame=frame)
            if pb.name == "stick":
                pb.keyframe_insert("location", frame=frame)
                pb.keyframe_insert("scale", frame=frame)

    def begin_action(self, name):
        ad = self.obj.animation_data or self.obj.animation_data_create()
        act = bpy.data.actions.new(name)
        act.use_fake_user = True
        ad.action = act
        self._prev = {}
        return act
