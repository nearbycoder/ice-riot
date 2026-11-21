#!/usr/bin/env python3
"""
ICE RIOT -- procedural audio generator.

Synthesizes every sound effect, crowd bed / reaction, organ stinger, music loop and UI sound for the
game, and (through macOS `say`) every announcer line. Contract: Docs/AUDIO_SPEC.md. Notes: Docs/AUDIO_NOTES.md.

Output: 16-bit PCM WAV @ 48 kHz in Art/Export/Audio/<Category>/<Name>.wav
        (Sfx, Crowd, Music, UI, Announcer) + Art/Export/Audio/manifest.json
        + verification PNGs in Art/Export/Audio/_Previews/.
Everything is original and deterministic (fixed seeds): re-running reproduces the same files
(announcer lines depend on the installed `say` voice).

Run with any Python 3.9+ that has numpy, e.g. Blender's bundled interpreter:
    /Applications/Blender.app/Contents/Resources/5.3/python/bin/python3.13 Tools/gen_audio.py

Options:
    --only Shot_,VO_Goal     regenerate only assets whose name starts with one of these prefixes
    --category Music         regenerate only one category (Sfx, Crowd, Music, UI, Announcer)
    --no-vo                  skip announcer lines (they need macOS `say` + `afconvert`)
    --no-previews            skip the PNG previews
    --check                  only re-verify the WAVs listed in the manifest
    --jobs N                 worker processes (default: CPU count - 2)
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
import zlib
from concurrent.futures import ProcessPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import numpy as np  # noqa: E402

from audio import crowd, music, sfx, vo  # noqa: E402
from audio.dsp import (SR, N, as2d, finalize_oneshot, normalize, loudness_lufs, dbamp, peak, limiter,  # noqa: E402
                       process_circular, read_wav, write_wav, amp2db)
from audio.preview import analyze, preview_pairs, preview_seams, preview_music  # noqa: E402

ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(ROOT, "Art", "Export", "Audio")
PREVIEW_DIR = os.path.join(OUT_DIR, "_Previews")
UE_BASE = "/Game/IceRiot/Audio"
SOUND_CLASS = {"Sfx": "SC_SFX", "Crowd": "SC_Crowd", "Music": "SC_Music", "UI": "SC_UI", "Announcer": "SC_Announcer"}
CATEGORIES = list(SOUND_CLASS)

# =============================================================================================
# Catalog
# =============================================================================================


def catalog():
    C = []

    def add(name, cat, fn, desc, loop=False, fin=None, mode=None, **extra):
        C.append(dict(name=name, category=cat, fn=fn, description=desc, loop=loop, fin=fin or {},
                      mode=mode or ("loop" if loop else "oneshot"), extra=extra))

    def var(base, count, cat, fnmaker, desc, fin=None, **kw):
        for i in range(count):
            add("%s_%02d" % (base, i + 1), cat, (lambda i=i: fnmaker(i)), desc, fin=fin, **kw)

    S = "Sfx"
    var("Skate_Stride", 6, S, sfx.sfx_skate_stride, "Crisp ice carve, one skating stride", dict(fade_out=0.05))
    var("Skate_Stop", 3, S, sfx.sfx_skate_stop, "Hockey stop: blade spray / scrape", dict(fade_out=0.15, limit_db=2.0))
    add("Skate_Turbo", S, sfx.sfx_skate_turbo, "Turbo burst: hard strides + rising whoosh + power hum", fin=dict(fade_out=0.15))
    var("Stick_Handle", 4, S, sfx.sfx_stick_handle, "Light puck taps on the blade", dict(fade_out=0.04))
    var("Shot_Wrist", 3, S, sfx.sfx_shot_wrist, "Snappy wrist shot", dict(fade_out=0.15, limit_db=3.0))
    var("Shot_Slap", 3, S, sfx.sfx_shot_slap, "Huge slap shot crack (stick on ice + puck)", dict(fade_out=0.3, limit_db=4.0))
    add("Shot_Power", S, sfx.sfx_shot_power, "Arcade power shot: massive slap + fiery whoosh + sub boom",
        fin=dict(fade_out=0.5, limit_db=4.0))
    add("Shot_Charge", S, sfx.sfx_shot_charge, "Rising charge-up tone (Shepard glissando), seamless loop", loop=True)
    var("Pass", 3, S, sfx.sfx_pass, "Sharp sweep pass", dict(fade_out=0.1, limit_db=2.0))
    var("Puck_Post", 2, S, sfx.sfx_puck_post, "Metallic PING off the goal post", dict(fade_out=0.4, limit_db=2.0))
    add("Puck_Crossbar", S, sfx.sfx_puck_crossbar, "Higher metallic ring off the crossbar", fin=dict(fade_out=0.4, limit_db=2.0))
    var("Puck_Boards", 4, S, sfx.sfx_puck_boards, "Hollow thud off the dasher boards", dict(fade_out=0.15, limit_db=2.0))
    var("Puck_Glass", 2, S, sfx.sfx_puck_glass, "Puck thunk off the glass (+ panel rattle)", dict(fade_out=0.2, limit_db=2.0))
    var("Puck_Ice", 3, S, sfx.sfx_puck_ice, "Puck landing flat on the ice", dict(fade_out=0.1))
    add("Net_Ripple", S, sfx.sfx_net_ripple, "Puck hitting the back of the net mesh", fin=dict(fade_out=0.2))
    var("Check", 4, S, sfx.sfx_check, "Body check thud (pads)", dict(fade_out=0.15, limit_db=3.0))
    add("Check_Power", S, sfx.sfx_check_power, "Enormous power-check crunch + boards + glass rattle",
        fin=dict(fade_out=0.6, limit_db=4.0))
    var("Boards_Slam", 2, S, sfx.sfx_boards_slam, "Player slammed into the boards, glass shakes", dict(fade_out=0.4, limit_db=3.0))
    var("Fall_Ice", 3, S, sfx.sfx_fall_ice, "Body hitting the ice + slide", dict(fade_out=0.25, limit_db=2.0))
    var("Stick_Clack", 3, S, sfx.sfx_stick_clack, "Sticks clashing (pokes, hooks)", dict(fade_out=0.1, limit_db=2.0))
    var("Save_Pad", 3, S, sfx.sfx_save_pad, "Puck off the goalie leg pad", dict(fade_out=0.12, limit_db=2.0))
    add("Save_Glove", S, sfx.sfx_save_glove, "Glove snag: leather pop", fin=dict(fade_out=0.12, limit_db=2.0))
    add("Save_Blocker", S, sfx.sfx_save_blocker, "Blocker deflection", fin=dict(fade_out=0.12, limit_db=2.0))
    add("Save_Power", S, sfx.sfx_save_power, "'Brick wall' power save: stone thud + magic shimmer", fin=dict(fade_out=0.5, limit_db=3.0))
    add("Whistle_Short", S, sfx.sfx_whistle_short, "Referee whistle, short blast", fin=dict(fade_out=0.2))
    add("Whistle_Long", S, sfx.sfx_whistle_long, "Referee whistle, tweet + long blast", fin=dict(fade_out=0.3))
    add("Goal_Horn", S, sfx.sfx_goal_horn, "Deep arena goal horn (~4 s, stereo)", fin=dict(fade_out=0.8, limit_db=2.0))
    add("Period_Buzzer", S, sfx.sfx_period_buzzer, "End-of-period buzzer (stereo)", fin=dict(fade_out=0.5, limit_db=1.5))
    add("Faceoff_Drop", S, sfx.sfx_faceoff_drop, "Puck slapped onto the ice at the face-off", fin=dict(fade_out=0.1, limit_db=2.0))
    var("Fight_Jab", 3, S, sfx.sfx_fight_jab, "Fight: quick jab", dict(fade_out=0.1, limit_db=3.0))
    var("Fight_Punch", 3, S, sfx.sfx_fight_punch, "Fight: hard punch", dict(fade_out=0.15, limit_db=3.0))
    add("Fight_Uppercut", S, sfx.sfx_fight_uppercut, "Fight: big uppercut", fin=dict(fade_out=0.3, limit_db=4.0))
    add("Fight_Block", S, sfx.sfx_fight_block, "Fight: forearm block", fin=dict(fade_out=0.1, limit_db=2.0))
    add("Fight_Grab", S, sfx.sfx_fight_grab, "Fight: jersey tug", fin=dict(fade_out=0.1))
    add("Gloves_Drop", S, sfx.sfx_gloves_drop, "Gloves and stick hitting the ice", fin=dict(fade_out=0.2, limit_db=2.0))
    add("Ambulance_Siren", S, sfx.sfx_ambulance, "Comedic siren racing past L->R with doppler (~3.3 s, stereo)",
        fin=dict(fade_out=0.4, lead_db=-40.0, fade_in=0.01))
    add("Flame_Burst", S, sfx.sfx_flame_burst, "Net bursts into flame", fin=dict(fade_out=0.4, limit_db=3.0))
    add("Fire_Loop", S, sfx.sfx_fire_loop, "Crackling fire, seamless 6 s loop", loop=True)
    add("Hat_Rain", S, sfx.sfx_hat_rain, "Hats raining onto the ice (stereo)", fin=dict(fade_out=0.5, lead_db=-40.0, fade_in=0.005))
    add("Glass_Rattle", S, sfx.sfx_glass_rattle, "Rink glass rattling in its frame", fin=dict(fade_out=0.3, limit_db=2.0))

    Cr = "Crowd"
    crowd_fin = dict(fade_out=0.6, lead_db=-30.0, fade_in=0.002)
    add("Crowd_Ambience", Cr, crowd.crowd_ambience, "Indoor arena murmur, seamless 30 s loop", loop=True, mode="bed", lufs=-23.0)
    add("Crowd_Excited", Cr, crowd.crowd_excited, "Energetic crowd, seamless 30 s loop (crossfade with ambience)",
        loop=True, mode="bed", lufs=-20.0)
    add("Crowd_Cheer_Big", Cr, crowd.crowd_cheer_big, "Goal eruption (6 s)", fin=crowd_fin)
    add("Crowd_Cheer_Small", Cr, crowd.crowd_cheer_small, "Small cheer (2.5 s)", fin=crowd_fin)
    add("Crowd_Ooh", Cr, crowd.crowd_ooh, "Near-miss 'ooh'", fin=crowd_fin)
    add("Crowd_Aah", Cr, crowd.crowd_aah, "Disappointed 'aww'", fin=crowd_fin)
    add("Crowd_Boo", Cr, crowd.crowd_boo, "Boo (3 s)", fin=crowd_fin)
    add("Crowd_Chant", Cr, crowd.crowd_chant, "Stomp-stomp-clap x3 with 'hey!' answers and a wordless chant",
        fin=dict(fade_out=0.8, lead_db=-40.0, fade_in=0.001))
    org_fin = dict(fade_out=1.0, lead_db=-40.0, fade_in=0.001)
    add("Organ_Charge", Cr, crowd.organ_charge, "Stadium organ rising 'charge'-style build (original)", fin=org_fin)
    var("Organ_Riff", 4, Cr, crowd.organ_riff, "Short arena-organ stinger (original)", org_fin)
    add("Organ_Clap", Cr, crowd.organ_clap, "Organ call + crowd clap answers", fin=org_fin)

    M = "Music"
    add("Music_Title", M, music.music_title, "Title: 144 BPM driving E-minor rock riff + synth lead, 36 bars, seamless loop",
        loop=True, mode="music")
    add("Music_Menu", M, music.music_menu, "Menus: 128 BPM A-dorian funk-rock groove, 24 bars, seamless loop",
        loop=True, mode="music")
    add("Music_Intermission", M, music.music_intermission, "Intermission: 96 BPM D-minor big-beat + stadium organ, 18 bars, seamless loop",
        loop=True, mode="music")
    add("Music_Victory", M, music.music_victory, "Victory sting: E-major fanfare, 8 s", mode="music")
    add("Music_Overtime", M, music.music_overtime, "Overtime: 144 BPM C-minor tense loop, 12 bars (20 s)", loop=True, mode="music")

    U = "UI"
    ui_fin = dict(fade_out=0.02)
    add("UI_Move", U, sfx.ui_move, "Menu cursor move", fin=ui_fin)
    add("UI_Select", U, sfx.ui_select, "Menu select / confirm", fin=dict(fade_out=0.05))
    add("UI_Back", U, sfx.ui_back, "Menu back / cancel", fin=ui_fin)
    add("UI_Start", U, sfx.ui_start, "Big press-start hit (stereo)", fin=dict(fade_out=0.4, limit_db=2.0))
    add("UI_Join", U, sfx.ui_join, "Player joined", fin=dict(fade_out=0.08))
    add("UI_Error", U, sfx.ui_error, "Error / not allowed", fin=ui_fin)
    add("UI_Tick", U, sfx.ui_tick, "Countdown tick", fin=ui_fin)
    add("UI_Whoosh", U, sfx.ui_whoosh, "Banner swipe whoosh", fin=dict(fade_out=0.05, lead_db=-40.0, fade_in=0.002))
    add("UI_Impact", U, sfx.ui_impact, "Logo slam (stereo)", fin=dict(fade_out=0.5, limit_db=3.0))

    for name, text in vo.VO_LINES:
        add(name, "Announcer", None, "Announcer: \"%s\"" % text, mode="vo", text=text)
    return C


CATALOG = None


def get_catalog():
    global CATALOG
    if CATALOG is None:
        CATALOG = {it["name"]: it for it in catalog()}
    return CATALOG


# =============================================================================================
# Build (runs in worker processes)
# =============================================================================================


def loop_to_lufs(x, target, ceiling_db=-1.0):
    g = float(dbamp(target - loudness_lufs(x)))
    y = x * g
    if peak(y) > float(dbamp(ceiling_db)):
        y = process_circular(y, lambda s: limiter(s, ceiling_db, 0.002, 0.1))
    return y


def build(name, tmpdir):
    it = get_catalog()[name]
    cat, mode = it["category"], it["mode"]
    extra = dict(it["extra"])
    t0 = time.time()
    if mode == "vo":
        rate = vo.vo_rate(extra["text"])
        x = vo.vo_process(vo.render_line(extra["text"], tmpdir, name))
        extra["text"] = extra["text"].replace(" | ", " ")
        extra.update(voice=vo.VO_VOICE, rate=rate)
    elif mode == "music":
        x, song = it["fn"]()
        extra.update(bpm=song.bpm, bars=song.bars)
        if it["loop"]:
            extra.update(loop_start_sample=0, loop_end_sample=int(x.shape[0]))
    elif mode == "bed":
        x = loop_to_lufs(it["fn"](), extra.pop("lufs"))
        extra.update(loop_start_sample=0, loop_end_sample=int(x.shape[0]))
    elif mode == "loop":
        x = normalize(it["fn"](), -3.0)
        extra.update(loop_start_sample=0, loop_end_sample=int(x.shape[0]))
    else:
        x = finalize_oneshot(it["fn"](), **it["fin"])
    folder = os.path.join(OUT_DIR, cat)
    os.makedirs(folder, exist_ok=True)
    rel = "%s/%s.wav" % (cat, name)
    write_wav(os.path.join(OUT_DIR, rel), x, seed=zlib.crc32(name.encode("utf-8")))
    e = dict(name=name, file=rel, category=cat, unreal_path="%s/%s/%s" % (UE_BASE, cat, name),
             sound_class=SOUND_CLASS[cat], duration=round(x.shape[0] / SR, 4), samples=int(x.shape[0]),
             channels=1 if x.ndim == 1 else int(x.shape[1]), loop=bool(it["loop"]), description=it["description"])
    e.update(extra)
    e["build_s"] = round(time.time() - t0, 1)
    return e


def _worker(name):
    import traceback
    try:
        with tempfile.TemporaryDirectory(prefix="iceriot_vo_") as tmp:
            return build(name, tmp)
    except Exception:
        return dict(name=name, error=traceback.format_exc())


# =============================================================================================
# Verification + previews
# =============================================================================================


def verify_entry(e):
    x, sr = read_wav(os.path.join(OUT_DIR, e["file"]))
    probs = []
    ch = 1 if x.ndim == 1 else x.shape[1]
    if sr != SR:
        probs.append("sample rate %d" % sr)
    if ch != e["channels"]:
        probs.append("channels %d != %d" % (ch, e["channels"]))
    info = analyze(x, e["loop"])
    if info["clipped_samples"] > 0:
        probs.append("%d clipped samples" % info["clipped_samples"])
    if info["peak_dbfs"] > -0.5:
        probs.append("peak too hot")
    if e["loop"] and info["seam_jump_ratio"] > 1.0:
        probs.append("loop seam discontinuity")
    if not e["loop"] and info["onset_ms"] > 2.0 and e["category"] in ("Sfx", "UI") and "lead_db" not in str(e.get("fin", "")):
        if e["name"] not in ("Ambulance_Siren", "Hat_Rain", "UI_Whoosh"):
            probs.append("leading silence %.1f ms" % info["onset_ms"])
    if abs(x.shape[0] / SR - e["duration"]) > 1e-3:
        probs.append("duration mismatch")
    return x, info, probs


def render_previews(files, signals):
    def sub(e):
        s = "%.2fS %dCH PK %.1f LUFS %.1f" % (e["duration"], e["channels"], e["peak_dbfs"], e["lufs"])
        return s + ("  LOOP" if e["loop"] else "")

    def items(pred):
        return [(e["name"], signals[e["name"]], sub(e)) for e in files if pred(e) and e["name"] in signals]

    out = []
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    groups = [
        ("sfx_1", "SFX 1/3", lambda e: e["category"] == "Sfx" and e["name"][:4] in ("Skat", "Stic", "Shot", "Pass", "Puck")),
        ("sfx_2", "SFX 2/3", lambda e: e["category"] == "Sfx" and e["name"][:4] in ("Net_", "Chec", "Boar", "Fall", "Save", "Whis", "Goal", "Peri", "Face")),
        ("sfx_3", "SFX 3/3", lambda e: e["category"] == "Sfx" and e["name"][:4] in ("Figh", "Glov", "Ambu", "Flam", "Fire", "Hat_", "Glas")),
        ("ui", "UI", lambda e: e["category"] == "UI"),
        ("crowd", "CROWD + ORGAN", lambda e: e["category"] == "Crowd"),
        ("vo_1", "ANNOUNCER 1/2", lambda e: e["category"] == "Announcer" and e["name"] < "VO_Hit"),
        ("vo_2", "ANNOUNCER 2/2", lambda e: e["category"] == "Announcer" and e["name"] >= "VO_Hit"),
    ]
    for key, title, pred in groups:
        it = items(pred)
        if it:
            out.append(os.path.join(PREVIEW_DIR, "audio_%s.png" % key))
            preview_pairs(out[-1], title + " (WAVEFORM | SPECTROGRAM 40HZ-20KHZ)", it)
    mus = [(e["name"], signals[e["name"]], sub(e) + "  %d BPM %d BARS" % (e["bpm"], e["bars"]), e["bars"])
           for e in files if e["category"] == "Music" and e["name"] in signals]
    if mus:
        out.append(os.path.join(PREVIEW_DIR, "audio_music.png"))
        preview_music(out[-1], mus)
    loops = items(lambda e: e["loop"])
    if loops:
        out.append(os.path.join(PREVIEW_DIR, "audio_loop_seams.png"))
        preview_seams(out[-1], [(n, s, t + "  SEAM %.2f" % next(e["seam_jump_ratio"] for e in files if e["name"] == n))
                                for n, s, t in loops])
    return out


# =============================================================================================
# Main
# =============================================================================================


def main():
    ap = argparse.ArgumentParser(description="ICE RIOT procedural audio generator")
    ap.add_argument("--only", default="", help="comma-separated name prefixes to (re)generate")
    ap.add_argument("--category", default="", help="only this category (Sfx, Crowd, Music, UI, Announcer)")
    ap.add_argument("--no-vo", action="store_true", help="skip announcer lines")
    ap.add_argument("--no-previews", action="store_true", help="skip PNG previews")
    ap.add_argument("--check", action="store_true", help="only verify existing files")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    mpath = os.path.join(OUT_DIR, "manifest.json")
    entries = {}
    if os.path.exists(mpath):
        with open(mpath) as fh:
            entries = {e["name"]: e for e in json.load(fh).get("files", [])}
    cat = get_catalog()
    order = {name: k for k, name in enumerate(cat)}
    entries = {k: v for k, v in entries.items() if k in cat}
    errors = []
    if not args.check:
        prefixes = [p.strip() for p in args.only.split(",") if p.strip()]
        todo = [n for n, it in cat.items() if (not prefixes or any(n.startswith(p) for p in prefixes))
                and (not args.category or it["category"].lower() == args.category.lower())]
        if args.no_vo:
            todo = [n for n in todo if cat[n]["mode"] != "vo"]
        if any(cat[n]["mode"] == "vo" for n in todo) and not (shutil.which("say") and shutil.which("afconvert")):
            sys.exit("macOS `say`/`afconvert` not found -- rerun with --no-vo")
        cost = {"music": 0, "bed": 1}
        todo.sort(key=lambda n: (cost.get(cat[n]["mode"], 2), order[n]))
        t_all = time.time()
        done = 0
        errors = []

        def report(e):
            nonlocal done
            done += 1
            if "error" in e:
                errors.append(e)
                print("[%3d/%d] %-20s FAILED\n%s" % (done, len(todo), e["name"], e["error"]), flush=True)
                return
            entries[e["name"]] = e
            print("[%3d/%d] %-20s %7.3f s %d ch%s  (%.1f s)" % (done, len(todo), e["name"], e["duration"], e["channels"],
                  "  loop" if e["loop"] else "", e["build_s"]), flush=True)

        if args.jobs <= 1:
            for n in todo:
                report(_worker(n))
        else:
            with ProcessPoolExecutor(max_workers=args.jobs) as ex:
                for f in as_completed([ex.submit(_worker, n) for n in todo]):
                    report(f.result())
        print("generated %d assets in %.1f s%s" % (len(todo) - len(errors), time.time() - t_all,
              ("  -- %d FAILED: %s" % (len(errors), ", ".join(e["name"] for e in errors))) if errors else ""))

    files = sorted(entries.values(), key=lambda e: (order.get(e["name"], 10 ** 6), e["name"]))
    signals, failures = {}, 0
    print("\n%-20s %8s %2s %4s %7s %7s  %s" % ("name", "dur(s)", "ch", "loop", "peak", "LUFS", "checks"))
    for e in files:
        x, info, probs = verify_entry(e)
        signals[e["name"]] = x
        e["peak_dbfs"], e["rms_dbfs"], e["lufs"] = info["peak_dbfs"], info["rms_dbfs"], info["lufs"]
        if e["loop"]:
            e["seam_jump_ratio"] = info["seam_jump_ratio"]
            check = "seam %.2f (<=1 ok), seam rms delta %.1f dB" % (info["seam_jump_ratio"], info["seam_rms_db_delta"])
        else:
            check = "onset %.2f ms" % info["onset_ms"]
        failures += bool(probs)
        print("%-20s %8.3f %2d %4s %7.2f %7.2f  %s%s" % (e["name"], e["duration"], e["channels"], "yes" if e["loop"] else "",
              info["peak_dbfs"], info["lufs"], check, ("  !! " + "; ".join(probs)) if probs else ""))
    manifest = {
        "generator": "Tools/gen_audio.py (procedural; deterministic)",
        "format": {"container": "wav", "encoding": "pcm_s16le", "sample_rate": SR},
        "unreal_base": UE_BASE,
        "sound_classes": SOUND_CLASS,
        "conventions": {
            "one_shots": "start at sample 0 (leading silence trimmed) -- trigger exactly at the impact",
            "loops": "sample-accurate: loop the whole file",
            "levels": "SFX/UI/crowd one-shots/organ/VO peak -1 dBFS; Shot_Charge/Fire_Loop peak -3 dBFS; "
                      "Crowd_Ambience -23 LUFS, Crowd_Excited -20 LUFS; music -14 LUFS (-13 for the victory sting), "
                      "ceiling -1 dBFS",
            "channels": "mono SFX + VO (spatialize in engine) except Goal_Horn, Period_Buzzer, Ambulance_Siren, Hat_Rain, "
                        "UI_Start, UI_Impact; stereo crowd + organ + music (2D)",
        },
        "count": len(files),
        "files": files,
    }
    with open(mpath, "w") as fh:
        json.dump(manifest, fh, indent=2)
    print("\nwrote %s (%d files)%s" % (mpath, len(files), "" if not failures else "  -- %d with problems" % failures))
    if not args.no_previews:
        for p in render_previews(files, signals):
            print("preview:", p)
    return 1 if failures or (not args.check and errors) else 0


if __name__ == "__main__":
    sys.exit(main())
