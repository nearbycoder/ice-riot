"""ICE RIOT - Unreal audio import (editor Python, run headless via the pythonscript commandlet).

Imports every WAV listed in Art/Export/Audio/manifest.json (written by Tools/gen_audio.py) as a
SoundWave at /Game/IceRiot/Audio/<Category>/<Name>, flags the loops, and builds the mix:

  /Game/IceRiot/Audio/Classes/SC_Master  (parent of)
      SC_Music, SC_SFX, SC_Crowd, SC_Announcer, SC_UI
  /Game/IceRiot/Audio/Classes/SM_Default         base mix (all adjusters 1.0; for options sliders)
  /Game/IceRiot/Audio/Classes/SM_AnnouncerDuck   ducks Music/Crowd/SFX while the announcer talks;
                                                 activated passively by SC_Announcer

Category -> class: Sfx -> SC_SFX, Crowd -> SC_Crowd, Music -> SC_Music, UI -> SC_UI,
Announcer -> SC_Announcer.

Run:  Tools/import_audio.sh   (report: Saved/ue_import_audio_report.txt)
"""

import json
import os
import traceback

import unreal

PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
ART = os.path.join(PROJECT, "Art", "Export", "Audio")
REPORT = os.path.join(PROJECT, "Saved", "ue_import_audio_report.txt")
os.makedirs(os.path.dirname(REPORT), exist_ok=True)
_rep = open(REPORT, "w")

AT = unreal.AssetToolsHelpers.get_asset_tools()
EAL = unreal.EditorAssetLibrary
BASE = "/Game/IceRiot/Audio"
D_CLASSES = BASE + "/Classes"
CLASS_OF = {"Sfx": "SC_SFX", "Crowd": "SC_Crowd", "Music": "SC_Music", "UI": "SC_UI", "Announcer": "SC_Announcer"}
CHILDREN = ["SC_Music", "SC_SFX", "SC_Crowd", "SC_Announcer", "SC_UI"]
DUCK = {"SC_Music": 0.55, "SC_Crowd": 0.6, "SC_SFX": 0.85}


def log(*a):
    _rep.write(" ".join(str(x) for x in a) + "\n")
    _rep.flush()


def asset_path(folder, name):
    return "%s/%s.%s" % (folder, name, name)


def load(folder, name):
    p = asset_path(folder, name)
    return unreal.load_asset(p) if EAL.does_asset_exist(p) else None


def ensure(folder, name, cls, factory):
    a = load(folder, name)
    if a is None:
        a = AT.create_asset(name, folder, cls, factory())
        log("CREATED", folder + "/" + name)
    return a


def import_wav(filename, dest, name):
    t = unreal.AssetImportTask()
    t.filename = filename
    t.destination_path = dest
    t.destination_name = name
    t.automated = True
    t.save = False
    t.replace_existing = True
    AT.import_asset_tasks([t])
    return list(t.imported_object_paths)


def build_classes():
    classes = {}
    master = ensure(D_CLASSES, "SC_Master", unreal.SoundClass, unreal.SoundClassFactory)
    classes["SC_Master"] = master
    for n in CHILDREN:
        classes[n] = ensure(D_CLASSES, n, unreal.SoundClass, unreal.SoundClassFactory)
    master.set_editor_property("child_classes", [classes[n] for n in CHILDREN])
    for n in CHILDREN:
        parent = classes[n].get_editor_property("parent_class")
        log("CLASS", n, "parent =", parent.get_name() if parent else None)
    # base mix
    mix = ensure(D_CLASSES, "SM_Default", unreal.SoundMix, unreal.SoundMixFactory)
    adj = []
    for n in ["SC_Master"] + CHILDREN:
        a = unreal.SoundClassAdjuster()
        a.set_editor_property("sound_class_object", classes[n])
        a.set_editor_property("volume_adjuster", 1.0)
        a.set_editor_property("pitch_adjuster", 1.0)
        a.set_editor_property("apply_to_children", n == "SC_Master")
        adj.append(a)
    mix.set_editor_property("sound_class_effects", adj)
    # announcer duck (passive: active whenever an SC_Announcer sound is audible)
    duck = ensure(D_CLASSES, "SM_AnnouncerDuck", unreal.SoundMix, unreal.SoundMixFactory)
    adj = []
    for n, v in DUCK.items():
        a = unreal.SoundClassAdjuster()
        a.set_editor_property("sound_class_object", classes[n])
        a.set_editor_property("volume_adjuster", v)
        a.set_editor_property("pitch_adjuster", 1.0)
        adj.append(a)
    duck.set_editor_property("sound_class_effects", adj)
    duck.set_editor_property("fade_in_time", 0.08)
    duck.set_editor_property("fade_out_time", 0.45)
    duck.set_editor_property("duration", -1.0)
    pm = unreal.PassiveSoundMixModifier()
    pm.set_editor_property("sound_mix", duck)
    pm.set_editor_property("min_volume_threshold", 0.0)
    pm.set_editor_property("max_volume_threshold", 10.0)
    classes["SC_Announcer"].set_editor_property("passive_sound_mix_modifiers", [pm])
    got = classes["SC_Announcer"].get_editor_property("passive_sound_mix_modifiers")
    log("PASSIVE SC_Announcer ->", [m.get_editor_property("sound_mix").get_name() for m in got])
    for a in list(classes.values()) + [mix, duck]:
        EAL.save_loaded_asset(a, False)
    log("MIX SM_Default + SM_AnnouncerDuck", {k: v for k, v in DUCK.items()})
    return classes


def import_all(classes):
    with open(os.path.join(ART, "manifest.json")) as fh:
        files = json.load(fh)["files"]
    counts, loops, failed = {}, [], []
    for e in files:
        cat, name = e["category"], e["name"]
        src = os.path.join(ART, e["file"])
        dest = "%s/%s" % (BASE, cat)
        if not os.path.exists(src):
            failed.append(name)
            log("MISSING", src)
            continue
        import_wav(src, dest, name)
        sw = load(dest, name)
        if not isinstance(sw, unreal.SoundWave):
            failed.append(name)
            log("IMPORT FAILED", name)
            continue
        loop = bool(e.get("loop"))
        sw.set_editor_property("looping", loop)
        sw.set_editor_property("sound_class_object", classes[CLASS_OF[cat]])
        if loop:
            sw.set_editor_property("virtualization_mode", unreal.VirtualizationMode.PLAY_WHEN_SILENT)
            loops.append(name)
        EAL.save_loaded_asset(sw, False)
        dur = sw.get_editor_property("duration")
        ch = sw.get_editor_property("num_channels") if hasattr(sw, "get_editor_property") else "?"
        counts[cat] = counts.get(cat, 0) + 1
        log("WAVE", "%s/%s" % (dest, name), "dur=%.3f" % dur, "ch=%s" % ch, "loop" if loop else "", CLASS_OF[cat])
    log("COUNTS", counts, "total", sum(counts.values()), "loops", len(loops), loops)
    if failed:
        log("FAILED", len(failed), failed)
    return failed


def main():
    log("ICE RIOT audio import ->", BASE)
    failed = ["<exception>"]
    try:
        classes = build_classes()
        failed = import_all(classes)
    except Exception:
        log("EXCEPTION", traceback.format_exc())
    EAL.save_directory(BASE, only_if_is_dirty=True, recursive=True)
    log("AUDIO IMPORT DONE", "OK" if not failed else "WITH ERRORS")


main()
