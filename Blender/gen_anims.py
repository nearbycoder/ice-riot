"""ICE RIOT animations (all on SK_Skater_Skeleton, 30 fps, in place).

    blender -b --factory-startup --python-exit-code 1 -P Blender/gen_anims.py [-- Name1 Name2 ...]

Opens Art/Blend/character.blend (rig in cm), authors every clip with anim_core (keyed pose parameters ->
IK every frame), exports Art/Export/Anims/A_<Name>.fbx, writes Art/Export/Manifests/anims.json
(length, loop, event times) and renders frame strips to Art/Previews/anim_<Name>.png.
Passing names limits the preview renders (all clips are always exported).
"""

import bpy
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ir_common as hc  # noqa: E402
import ir_rig as rig  # noqa: E402
from anim_core import Solver, S  # noqa: E402
from mathutils import Vector  # noqa: E402

BLEND = os.path.join(hc.ROOT, "Art", "Blend", "character.blend")
bpy.ops.wm.open_mainfile(filepath=BLEND)
ARM = bpy.data.objects["Armature"]
SOL = Solver(ARM)
FPS = 30
WIDE = {"Dive", "HitFall", "Flip", "GetUp", "FightKO", "Celebrate2", "Celebrate3", "Stop"}
PH = rig.PUCK_HALF_T


import anim_clips  # noqa: E402

CLIPS, GOALIE_CLIPS = anim_clips.build_all()


def unify_modes(c):
    """Clips mixing free-hand (mode 1) keys with stick-hold keys: convert the stick-hold keys to mode 1."""
    modes = {k[1]["mode"] for k in c.keys}
    if 1 not in modes or len(modes) == 1:
        return
    for i, (t, p, ten) in enumerate(c.keys):
        if p["mode"] in (0, 3):
            c.keys[i] = (t, SOL.to_mode1(p), ten)
    print("UNIFIED", c.name)


for _c in CLIPS.values():
    unify_modes(_c)


# ---------------------------------------------------------------------------
# Bake / export / preview
# ---------------------------------------------------------------------------
def bake(c):
    act = SOL.P.begin_action("A_" + c.name)
    SOL.max_err = 0.0
    n = int(math.ceil(c.length * FPS - 1e-6))
    for f in range(n + 1):
        t = f / FPS
        SOL.apply(c.sample(t))
        SOL.P.key(f)
    for ev, tm in c.events.items():
        act.pose_markers.new(ev).frame = int(round(tm * FPS))
    return n


def export(c, n):
    act = bpy.data.actions["A_" + c.name]
    ARM.animation_data.action = act
    try:
        ARM.animation_data.action_slot = act.slots[0]
    except Exception:
        pass
    sc = bpy.context.scene
    sc.frame_start = 0
    sc.frame_end = n
    hc.export_anim_fbx(ARM, "A_%s.fbx" % c.name)


def set_deform(enabled):
    for o in bpy.data.objects:
        if o.type == "MESH":
            for md in o.modifiers:
                if md.type == "ARMATURE":
                    md.show_viewport = enabled
                    md.show_render = enabled


def setup_preview():
    hc.setup_preview_render(res=(300, 340), samples=6)
    bpy.context.scene.view_settings.view_transform = "AgX"
    hc.add_sun("Key", rotation=(math.radians(50), 0, math.radians(-35)), energy=3.5)
    hc.add_sun("Fill", rotation=(math.radians(65), 0, math.radians(150)), energy=1.2)
    cam = hc.add_camera("Cam", (2.2 * S, -3.3 * S, 1.5 * S), (0, -0.35 * S, 0.75 * S), lens=42)
    cam.data.clip_end = 100000
    fl = hc.box("PrevFloor", (8 * S, 8 * S, 0.02 * S), location=(0, 0, -0.01 * S),
                mat=hc.material("PrevIce", (0.82, 0.88, 0.94, 1), 0.15))
    pk = hc.cylinder("PrevPuck", rig.PUCK_R * S, 0.0254 * S, verts=20, mat=hc.material("PrevPuckM", (0.02, 0.02, 0.02, 1), 0.5))
    return cam, pk


def preview(c, n, cam, puck, cols=6):
    act = bpy.data.actions["A_" + c.name]
    ARM.animation_data.action = act
    try:
        ARM.animation_data.action_slot = act.slots[0]
    except Exception:
        pass
    goalie = c.name in GOALIE_CLIPS
    for o in bpy.data.objects:
        if o.type == "MESH" and o.name.startswith("SK_"):
            o.hide_render = (o.name == "SK_Goalie") != goalie
    frames = [round(n * i / (cols - 1)) for i in range(cols)]
    for ev, tm in c.events.items():
        frames[min(range(cols), key=lambda i: abs(frames[i] - tm * FPS))] = int(round(tm * FPS))
    rows = []
    views = [((2.2 * S, -3.3 * S, 1.5 * S), (0, -0.35 * S, 0.75 * S)), ((-4.0 * S, -0.5 * S, 1.2 * S), (0, -0.3 * S, 0.75 * S))]
    if c.name in WIDE or c.name.startswith("GoalieDive"):
        views = [((2.8 * S, -4.4 * S, 2.0 * S), (0, -0.2 * S, 0.6 * S)), ((-5.2 * S, -0.5 * S, 1.6 * S), (0, -0.2 * S, 0.6 * S))]
    for vi, (loc, tgt) in enumerate(views):
        cam.location = loc
        cam.rotation_euler = hc.look_at_rotation(loc, tgt)
        paths = []
        for i, f in enumerate(sorted(set(frames))):
            bpy.context.scene.frame_set(f)
            pb = ARM.pose.bones["stick_blade"]
            puck.location = ARM.matrix_world @ pb.head
            path = os.path.join(hc.PREVIEW_DIR, "tmp_anim_%d_%02d.png" % (vi, i))
            hc.render_to(path)
            paths.append(path)
        rows.append(paths)
    paths = rows[0] + rows[1]
    # compose strip
    import numpy as np
    imgs = []
    for p in paths:
        im = bpy.data.images.load(p)
        w, h = im.size
        a = np.empty(w * h * 4, np.float32)
        im.pixels.foreach_get(a)
        imgs.append(a.reshape(h, w, 4))
        bpy.data.images.remove(im)
    k = len(imgs) // 2
    strip = np.concatenate([np.concatenate(imgs[k:], axis=1), np.concatenate(imgs[:k], axis=1)], axis=0)
    out = bpy.data.images.new("strip", strip.shape[1], strip.shape[0], alpha=True)
    out.pixels.foreach_set(strip.ravel())
    out.filepath_raw = os.path.join(hc.PREVIEW_DIR, "anim_%s.png" % c.name)
    out.file_format = "PNG"
    out.save()
    bpy.data.images.remove(out)
    print("STRIP", c.name, frames)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    set_deform(False)
    manifest = {}
    lengths = {}
    for name, c in CLIPS.items():
        n = bake(c)
        lengths[name] = n
        manifest[name] = {"length": round(n / FPS, 4), "frames": n, "fps": FPS, "loop": c.loop,
                          "events": {k: v for k, v in c.events.items()}}
        print("BAKED %-18s frames=%3d  ik_err=%.3f m  grip_err=%.3f m" % (name, n, SOL.max_err, getattr(SOL, "blade_err", 0.0)))
        SOL.blade_err = 0.0
    for name, c in CLIPS.items():
        export(c, lengths[name])
    with open(os.path.join(hc.MANIFEST_DIR, "anims.json"), "w") as fp:
        json.dump(manifest, fp, indent=2)
    set_deform(True)
    cam, puck = setup_preview()
    for name, c in CLIPS.items():
        if argv and name not in argv:
            continue
        preview(c, lengths[name], cam, puck)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(hc.ROOT, "Art", "Blend", "character_anims.blend"), copy=True)
    print("ANIMS DONE", len(CLIPS))


if __name__ == "__main__":
    main()
