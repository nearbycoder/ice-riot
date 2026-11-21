"""
ICE RIOT -- original 90s-arcade rock / electronic music, synthesized.

A tiny tracker: every song is a fixed number of 16th-note bars; loops are sample-exact (every
event, echo and reverb tail wraps around the loop point), mastered to ~-14 LUFS with a -1 dBFS
ceiling. All riffs, progressions and melodies here are original.
"""

import math

import numpy as np

from .dsp import (SR, TWO_PI, N, T, rng_for, midi_hz, mix_into, mix_circular, pan, unit, unitpeak, rms, set_rms,
                  env_exp, env_pts, env_adsr, fade, smooth_random, m_lp, m_hp, m_bp, m_peak, fft_filter,
                  shaped_noise, biquad, iir, iir_circular, svf, osc_sine, osc_saw, osc_pulse, osc_tri, phase_acc,
                  modal, burst, thump, convolve, convolve_circular, reverb_ir, echo, saturate, compressor, limiter,
                  process_circular, normalize, loudness_lufs, dbamp, pad_to, ks_pluck, supersaw, add_reverb)
from .crowd import organ_note

NOTE_PC = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7,
           "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}


def note(name):
    """'E1' -> 28, 'C#5' -> 73, 'Bb4' -> 70 (MIDI, C4 = 60)."""
    return 12 * (int(name[-1]) + 1) + NOTE_PC[name[:-1]]


def seq(s):
    """'step:Note:len[:vel] ...' -> [(step, midi, len, vel)]."""
    out = []
    for tok in s.split():
        p = tok.split(":")
        out.append((float(p[0]), note(p[1]), float(p[2]), float(p[3]) if len(p) > 3 else 1.0))
    return out


DRUM_VEL = {"X": 1.0, "x": 0.72, "o": 0.42, "g": 0.25}


def grid(s):
    """16-char drum grid -> {step: velocity}."""
    return {k: DRUM_VEL[c] for k, c in enumerate(s.replace(" ", "")) if c in DRUM_VEL}


# =============================================================================================
# Song container
# =============================================================================================


class Song:
    def __init__(self, name, bpm, bars, swing=0.5, loop=True, tail=0.0):
        self.name, self.bpm, self.bars, self.swing, self.loop = name, bpm, bars, swing, loop
        self.r = rng_for("song_" + name)
        self.step = 60.0 / bpm / 4.0
        self.L = int(round(bars * 16 * self.step * SR))
        self.n = self.L if loop else self.L + N(tail)
        self.stems = {}

    def time(self, bar, step):
        t = (bar * 16 + step) * self.step
        if float(step).is_integer() and int(step) % 2 == 1:
            t += (self.swing - 0.5) * 2.0 * self.step
        return t

    def at(self, bar, step):
        return int(round(self.time(bar, step) * SR))

    def stem(self, key):
        if key not in self.stems:
            self.stems[key] = np.zeros((self.n, 2))
        return self.stems[key]

    def put(self, key, sig, bar, step, gain=1.0, p=0.0, offset=0.0):
        s = (pan(sig, p) if sig.ndim == 1 else sig) * gain
        pos = self.at(bar, step) + N(offset) if offset else self.at(bar, step)
        (mix_circular if self.loop else mix_into)(self.stem(key), s, pos)

    def put_abs(self, key, sig, sample, gain=1.0):
        (mix_circular if self.loop else mix_into)(self.stem(key), (pan(sig, 0.0) if sig.ndim == 1 else sig) * gain, sample)

    def secs(self, steps):
        return steps * self.step

    # filtering helpers that respect looping
    def filt(self, x, mag_fn):
        return fft_filter(x, mag_fn, circular=self.loop)

    def biq(self, x, *co):
        return iir_circular(x, *co) if self.loop else iir(x, *co)

    def verb(self, x, ir):
        return convolve_circular(x, ir) if self.loop else convolve(x, ir)[: x.shape[0]]

    def delay(self, x, steps, fb=0.3, wet=0.25, repeats=4, lp=4500, hp=300, pingpong=True):
        y = echo(x, steps * self.step, fb, wet, repeats, lp, hp, circular=self.loop, pingpong=pingpong)
        return y[: x.shape[0]]


# =============================================================================================
# Drums
# =============================================================================================


def kick(r, decay=0.28, punch=1.0):
    n = N(0.6)
    t = T(n)
    f = 52.0 + 110.0 * np.exp(-t / 0.035) + 300.0 * np.exp(-t / 0.004)
    body = osc_sine(f, n) * np.exp(-t / decay) * np.clip(t / 0.0008, 0.0, 1.0)
    click = 0.3 * punch * unitpeak(burst(r, 0.6, 0.002, lambda ff: m_bp(ff, 3500, 0.7)))
    knock = 0.25 * osc_sine(np.full(n, 180.0), n) * np.exp(-t / 0.012)
    return fade(saturate(body + click + knock, 2.0), 0.0, 0.05)


def snare(r, tight=1.0, body_hz=195.0, crack=1.0):
    n = N(0.5)
    t = T(n)
    body = 0.75 * osc_sine(body_hz * (1.0 + 0.3 * np.exp(-t / 0.008)), n) * np.exp(-t / 0.06)
    body += 0.35 * osc_sine(body_hz * 1.72, n) * np.exp(-t / 0.035)
    wires = unit(fft_filter(r.standard_normal(n), lambda f: m_bp(f, 4200, 0.45) * m_hp(f, 1100, 2), pad=0.0))
    wires *= np.exp(-t / (0.16 * tight))
    snap = unitpeak(burst(r, 0.5, 0.003, lambda f: m_hp(f, 1800, 1)))
    y = (0.85 * body + 0.42 * wires + 0.45 * crack * snap) * np.clip(t / 0.0004, 0.0, 1.0)
    return fade(saturate(y, 1.9), 0.0, 0.05)


def hat(r, open_=False, bright=1.0):
    n = N(0.7 if open_ else 0.12)
    t = T(n)
    base = 330.0 * r.uniform(0.98, 1.02)
    metal = sum(osc_pulse(base * k, n, 0.5, r.random()) for k in (1.0, 1.4471, 1.617, 1.9265, 2.5028, 2.6637))
    metal = unit(fft_filter(metal, lambda f: m_hp(f, 6500, 3) * (0.5 + m_bp(f, 9500 * bright, 0.8)), pad=0.0))
    air = unit(fft_filter(r.standard_normal(n), lambda f: m_hp(f, 7500, 2), pad=0.0))
    y = (0.6 * metal + 0.5 * air) * np.exp(-t / (0.28 if open_ else 0.028)) * np.clip(t / 0.0005, 0.0, 1.0)
    return fade(y, 0.0, 0.03)


def ride(r):
    n = N(1.4)
    t = T(n)
    ping = modal(n, [(r.uniform(2900, 3300), 1.0, 0.5), (r.uniform(4300, 4700), 0.6, 0.35), (r.uniform(6100, 6600), 0.5, 0.25),
                     (r.uniform(7900, 8600), 0.35, 0.2)])
    wash = unit(fft_filter(r.standard_normal(n), lambda f: m_hp(f, 5000, 2) * m_lp(f, 13000, 1), pad=0.0)) * np.exp(-t / 0.4)
    tip = unitpeak(burst(r, 1.4, 0.002, lambda f: m_hp(f, 4000, 2)))
    return fade(0.5 * unitpeak(ping) + 0.25 * wash + 0.3 * tip, 0.0, 0.2)


def crash(r, dur=2.6):
    n = N(dur)
    t = T(n)
    out = np.zeros((n, 2))
    for ch in range(2):
        partials = modal(n, [(r.uniform(2800, 11000), r.uniform(0.3, 1.0), r.uniform(0.5, 1.4), r.uniform(0, TWO_PI))
                             for _ in range(40)])
        hiss = unit(fft_filter(r.standard_normal(n), lambda f: m_hp(f, 3000, 2) * m_lp(f, 14000, 2), pad=0.0))
        y = 0.6 * unit(partials) * np.exp(-t / 0.8) + hiss * (0.7 * np.exp(-t / 0.75) + 0.6 * np.exp(-t / 0.05))
        out[:, ch] = y * np.clip(t / 0.001, 0.0, 1.0)
    return fade(out, 0.0, 0.4)


def tom(r, hz):
    n = N(0.8)
    t = T(n)
    f = hz * (1.0 + 0.35 * np.exp(-t / 0.03))
    y = osc_sine(f, n) * np.exp(-t / 0.22) + 0.3 * osc_sine(f * 1.6, n) * np.exp(-t / 0.08)
    y += 0.25 * unitpeak(burst(r, 0.8, 0.004, lambda ff: m_bp(ff, 2500, 0.8)))
    return fade(saturate(y, 1.6), 0.0, 0.1)


def timpani(r, hz):
    n = N(2.0)
    t = T(n)
    f = hz * (1.0 + 0.06 * np.exp(-t / 0.05))
    y = osc_sine(f, n) * np.exp(-t / 0.8) + 0.5 * osc_sine(f * 1.505, n) * np.exp(-t / 0.5) + 0.3 * osc_sine(f * 1.99, n) * np.exp(-t / 0.35)
    y += 0.4 * unitpeak(burst(r, 2.0, 0.015, lambda ff: m_bp(ff, 300, 0.7)))
    return fade(y * np.clip(t / 0.002, 0, 1), 0.0, 0.3)


def tambourine(r):
    n = N(0.25)
    t = T(n)
    jingles = modal(n, [(r.uniform(5000, 9000), 1.0, r.uniform(0.04, 0.1), r.uniform(0, 6)) for _ in range(12)])
    y = 0.6 * unitpeak(jingles) + 0.5 * unit(fft_filter(r.standard_normal(n), lambda f: m_hp(f, 6000, 2), pad=0.0)) * np.exp(-t / 0.05)
    return y * np.clip(t / 0.002, 0, 1)


class Kit:
    """Pre-rendered drum samples with round-robin variation."""

    def __init__(self, r, kick_decay=0.28, snare_tight=1.0, snare_hz=195.0):
        self.kicks = [kick(r, kick_decay) for _ in range(3)]
        self.snares = [snare(r, snare_tight, snare_hz) for _ in range(4)]
        self.hats = [hat(r) for _ in range(6)]
        self.ohats = [hat(r, True) for _ in range(2)]
        self.rides = [ride(r) for _ in range(3)]
        self.crashes = [crash(r) for _ in range(2)]
        self.toms = {k: tom(r, hz) for k, hz in (("hi", 196.0), ("mid", 147.0), ("lo", 98.0))}
        self.tamb = [tambourine(r) for _ in range(3)]
        self.r = r

    def pick(self, lst):
        return lst[self.r.integers(len(lst))]


def play_drums(song, kit, bar, pat):
    """pat: dict with optional 'K','S','H','O','R','C','T1','T2','T3','TB' 16-char grids."""
    r = song.r
    for s, v in grid(pat.get("K", "")).items():
        song.put("kick", kit.pick(kit.kicks), bar, s, v)
    for s, v in grid(pat.get("S", "")).items():
        song.put("snare", kit.pick(kit.snares), bar, s, v * r.uniform(0.93, 1.04), 0.04)
    hs = grid(pat.get("H", ""))
    os_ = grid(pat.get("O", ""))
    for s, v in hs.items():
        song.put("hats", kit.pick(kit.hats), bar, s, v * r.uniform(0.85, 1.08), 0.3)
    for s, v in os_.items():
        nxt = [k for k in hs if k > s]
        sig = kit.pick(kit.ohats)
        if nxt:                                               # choked by the next closed hat
            gap = song.at(bar, nxt[0]) - song.at(bar, s)
            sig = fade(sig[:gap], 0.0, 0.01)
        song.put("hats", sig, bar, s, 0.6 * v, 0.3)
    for s, v in grid(pat.get("R", "")).items():
        song.put("cym", kit.pick(kit.rides), bar, s, 0.55 * v * r.uniform(0.9, 1.05), -0.35)
    for s, v in grid(pat.get("C", "")).items():
        song.put("cym", kit.pick(kit.crashes), bar, s, 0.8 * v)
    for key, name, p in (("T1", "hi", -0.3), ("T2", "mid", 0.0), ("T3", "lo", 0.35)):
        for s, v in grid(pat.get(key, "")).items():
            song.put("toms", kit.toms[name], bar, s, v, p)
    for s, v in grid(pat.get("TB", "")).items():
        song.put("perc", kit.pick(kit.tamb), bar, s, 0.6 * v, 0.45)


# =============================================================================================
# Pitched instruments
# =============================================================================================


def power_chord(root, kind="o"):
    return [root, root + 7] if kind == "m" else [root, root + 7, root + 12]


def guitar_note(r, notes, dur, mute=False, vel=1.0):
    """Clean signal of a strummed power chord (KS strings); distortion is applied on the stem."""
    ring = dur + (0.03 if mute else 0.06)
    y = np.zeros(N(ring))
    for k, m in enumerate(notes):
        f = float(midi_hz(m)) * 2.0 ** (r.uniform(-5, 5) / 1200.0)
        s = ks_pluck(r, f, ring, damp=0.92 if mute else 0.55, bright=0.95, decay=0.985 if mute else 0.9993)
        mix_into(y, s * (0.8 if k else 1.0), N(0.003 * k + r.uniform(0, 0.002)))
    rel = 0.025 if mute else 0.05
    return vel * y * env_pts(y.shape[0], [(0, 1), (max(dur, 0.01), 1), (dur + rel, 0)])


def distort_guitar(song, x, drive=7.0):
    """Amp + cab on a (n, 2) clean guitar stem."""
    x = song.biq(x, biquad("hp", 110, 0.7), biquad("lp", 3500, 0.7), biquad("peak", 900, 0.8, 3.0))
    x = saturate(drive * x / (np.max(np.abs(x)) + 1e-9), 1.0)
    x = saturate(1.6 * x, 1.4, asym=0.15)
    return song.biq(x, biquad("hp", 80, 0.7), biquad("peak", 2300, 1.0, 3.5), biquad("peak", 400, 1.2, -2.5),
                    biquad("lp", 5200, 0.9), biquad("lp", 7000, 0.7))


def bass_note(r, midi, dur, vel=1.0, bright=0.8):
    """Picked electric bass: KS string + sine fundamental, slight drive."""
    f = float(midi_hz(midi))
    ring = dur + 0.04
    n = N(ring)
    t = T(n)
    s = ks_pluck(r, f, ring, damp=0.35, bright=bright, decay=0.9985)
    sub = osc_sine(f, n) * np.exp(-t / 1.2)
    y = 0.8 * unitpeak(s) + 0.6 * sub
    y = svf(y, 600 + 2500 * bright * np.exp(-t / 0.08), 0.8, "lp")
    y *= env_pts(n, [(0, 0), (0.002, 1), (dur, 0.9), (ring, 0)])
    return vel * saturate(1.2 * y, 1.6)


def synth_bass(r, midi, dur, vel=1.0, res=1.5, env_amt=2600.0, decay=0.12):
    """Saw/pulse synth bass with a resonant filter blip (acid-ish when res is high)."""
    f = float(midi_hz(midi))
    n = N(dur + 0.04)
    t = T(n)
    y = 0.6 * osc_saw(f, n, r.random()) + 0.5 * osc_pulse(f * 0.5, n, 0.5, r.random()) * 0.6
    y = svf(y, 180 + env_amt * vel * np.exp(-t / decay), res, "lp")
    y = y + 0.4 * osc_sine(f, n)
    y *= env_pts(n, [(0, 0), (0.002, 1), (dur, 0.85), (dur + 0.035, 0)])
    return vel * saturate(y, 1.8)


def mono_line(song, notes, voice="lead", glide=0.03, gain=1.0):
    """Monophonic legato line with glide, delayed vibrato and per-note filter envelope.
    notes: [(bar, step, midi, len_steps, vel)]. Returns a (n_total, 2) stem (wrapped if looping)."""
    r = song.r
    tail = N(1.0)
    n = song.n + tail
    starts = [song.at(b, s) for b, s, _, _, _ in notes]
    order = np.argsort(starts)
    f = np.zeros(n)
    amp = np.zeros(n)
    fenv = np.zeros(n)
    vib = np.zeros(n)
    prev_f, prev_end = None, -10 ** 9
    g = N(glide)
    for k in order:
        b, s, m, ln, vel = notes[k]
        a = starts[k]
        d = N(song.secs(ln) * 0.95)
        e = min(n, a + d)
        fr = float(midi_hz(m))
        if prev_f is not None and a - prev_end < N(0.04):
            ramp = np.linspace(prev_f, fr, min(g, e - a))
            f[a:a + ramp.shape[0]] = ramp
            f[a + ramp.shape[0]:e] = fr
        else:
            if voice == "glead":                              # guitar-style scoop into the note
                sc = min(N(0.05), e - a)
                f[a:a + sc] = fr * 2.0 ** (np.linspace(-0.9, 0.0, sc) / 12.0)
                f[a + sc:e] = fr
            else:
                f[a:e] = fr
        rel = N(0.06 if voice != "bell" else 0.4)
        L = e - a + rel
        en = env_adsr(L, 0.005, 0.25, 0.8, (e - a) / SR, rel / SR / 3)
        seg = slice(a, min(n, a + L))
        amp[seg] = np.maximum(amp[seg], vel * en[: seg.stop - seg.start])
        fe = np.exp(-T(L) / 0.25)
        fenv[seg] = np.maximum(fenv[seg], vel * fe[: seg.stop - seg.start])
        vd = np.clip((T(e - a) - 0.18) / 0.25, 0.0, 1.0)
        vib[a:e] = np.maximum(vib[a:e], vd)
        f[e:min(n, e + rel)] = fr
        prev_f, prev_end = fr, e
    # hold frequency through gaps
    idx = np.nonzero(f > 0)[0]
    if idx.size == 0:
        return np.zeros((song.n, 2))
    f = np.interp(np.arange(n), idx, f[idx])
    t = T(n)
    if voice == "lead":
        fv = f * (1.0 + 0.006 * vib * np.sin(TWO_PI * 5.6 * t))
        pw = 0.33 + 0.1 * np.sin(TWO_PI * 0.6 * t)
        y = 0.65 * osc_pulse(fv, n, pw, r.random()) + 0.45 * osc_saw(fv * 1.004, n, r.random()) + 0.3 * osc_saw(fv * 0.996, n, r.random())
        y = svf(y, 1400.0 + 5200.0 * fenv, 1.1, "lp")
        y = saturate(0.7 * y, 1.3)
    elif voice == "glead":
        fv = f * (1.0 + 0.011 * vib * np.sin(TWO_PI * 5.8 * t))
        y = osc_saw(fv, n, r.random()) + 0.6 * osc_saw(fv * 2.003, n, r.random()) + 0.3 * osc_pulse(fv, n, 0.3, r.random())
        y = iir(y, biquad("hp", 250, 0.7), biquad("peak", 1000, 0.8, 4.0))
        y = saturate(8.0 * y / (np.max(np.abs(y)) + 1e-9), 1.0)
        y = iir(y, biquad("peak", 2500, 1.0, 4.0), biquad("lp", 5500, 0.8), biquad("lp", 7500, 0.7))
    elif voice == "bell":
        fv = f
        y = np.sin(TWO_PI * phase_acc(fv, n) + 1.8 * fenv * np.sin(TWO_PI * phase_acc(fv * 3.5, n)))
    else:  # "square" chip-ish lead
        fv = f * (1.0 + 0.005 * vib * np.sin(TWO_PI * 6.0 * t))
        y = osc_pulse(fv, n, 0.25, r.random())
        y = svf(y, 2500.0 + 4000.0 * fenv, 0.8, "lp")
    y = iir(y, biquad("hp", 110, 0.7)) * amp * gain
    out = np.zeros((song.n, 2))
    st = np.stack([y, y], axis=1) * 0.7071
    (mix_circular if song.loop else mix_into)(out, st, 0)
    return out


def pad_chord(r, notes, dur, bright=0.5, attack=0.25):
    n = N(dur + 0.6)
    t = T(n)
    L = np.zeros(n)
    R = np.zeros(n)
    for m in notes:
        f = float(midi_hz(m))
        L += supersaw(f, n, r, 5, 14.0)
        R += supersaw(f, n, r, 5, 14.0)
    cut = 900 + 3500 * bright
    L = iir(L, biquad("lp", cut, 0.7), biquad("hp", 150, 0.7))
    R = iir(R, biquad("lp", cut, 0.7), biquad("hp", 150, 0.7))
    env = env_adsr(n, attack, 0.5, 0.85, dur, 0.18)
    return np.stack([L, R], axis=1) * env[:, None] / (2.0 * len(notes))


def pluck(r, midi, dur, vel=1.0, bright=1.0):
    """Arp pluck: detuned pulse/saw with a fast filter decay."""
    n = N(dur + 0.08)
    t = T(n)
    f = float(midi_hz(midi))
    y = 0.6 * osc_pulse(f, n, 0.3, r.random()) + 0.5 * osc_saw(f * 1.005, n, r.random())
    y = svf(y, 600 + 6000 * bright * np.exp(-t / 0.06), 1.0, "lp")
    return vel * y * env_pts(n, [(0, 0), (0.002, 1), (dur, 0.6), (dur + 0.06, 0)])


def brass_stab(r, chord, dur, vel=1.0):
    n = N(dur + 0.2)
    t = T(n)
    out = np.zeros((n, 2))
    scoop = 2.0 ** ((-30.0 / 1200.0) * np.exp(-t / 0.025))
    for m in chord:
        for k, det in enumerate((-9.0, -3.0, 4.0, 10.0)):
            f = float(midi_hz(m)) * 2.0 ** (det / 1200.0) * scoop
            out += pan(osc_saw(f, n, r.random()), -0.6 + 0.4 * k)
    cut = 500.0 + 4200.0 * vel * (1.0 - np.exp(-t / 0.012)) * (0.55 + 0.45 * np.exp(-t / 0.12))
    out = np.stack([svf(out[:, c], cut, 0.9, "lp") for c in range(2)], axis=1)
    out *= env_adsr(n, 0.008, 0.08, 0.7, dur, 0.07)[:, None]
    return vel * saturate(out / (2.0 * len(chord)), 1.3)


def epiano(r, chord, dur, vel=1.0, t_abs=0.0):
    """FM electric piano chord with tremolo (stereo)."""
    n = N(dur + 0.35)
    t = T(n)
    y = np.zeros(n)
    for m in chord:
        f = float(midi_hz(m))
        I = (0.8 + 2.0 * vel) * np.exp(-t / 0.2) + 0.25
        y += np.sin(TWO_PI * f * t + I * np.sin(TWO_PI * f * t + r.uniform(0, 0.3)))
        if f * 7.0 < 18000:
            y += 0.1 * vel * np.sin(TWO_PI * f * 7.0 * t) * np.exp(-t / 0.03)
    amp = np.exp(-t / 1.4) * np.clip(t / 0.002, 0.0, 1.0) * np.interp(t, [0, dur, dur + 0.2], [1, 1, 0])
    y = vel * y * amp / len(chord)
    lfo = np.sin(TWO_PI * 4.8 * (t + t_abs))
    return np.stack([y * (1 + 0.3 * lfo), y * (1 - 0.3 * lfo)], axis=1)


def clean_chop(r, chord, dur, wah=0.5):
    """Muted clean-guitar 'chk' chop with a wah sweep."""
    ring = dur + 0.03
    y = np.zeros(N(ring))
    for k, m in enumerate(chord):
        s = ks_pluck(r, float(midi_hz(m)), ring, damp=0.6, bright=1.0, decay=0.995)
        mix_into(y, s, N(0.004 * k))
    n = y.shape[0]
    t = T(n)
    fc = 500 + 2200 * wah * (1.0 - np.exp(-t / 0.03)) * np.exp(-t / 0.15) + 400 * wah
    y = svf(y, fc, 2.5, "bp") * 1.5 + 0.3 * y
    return unitpeak(y) * env_pts(n, [(0, 1), (dur, 1), (ring, 0)])


def string_stab(r, chord, dur, vel=1.0):
    """Synth string section (staccato or held)."""
    n = N(dur + 0.25)
    out = np.zeros((n, 2))
    for m in chord:
        f = float(midi_hz(m))
        for c in range(2):
            v = supersaw(f, n, r, 4, 10.0)
            out[:, c] += v
    out = np.stack([iir(out[:, c], biquad("lp", 3800, 0.7), biquad("hp", 180, 0.7), biquad("peak", 1500, 1.0, 2.0)) for c in range(2)], axis=1)
    return vel * out * env_adsr(n, 0.012, 0.15, 0.75, dur, 0.08)[:, None] / (2.0 * len(chord))


def riser(r, dur, f0=400.0, f1=8000.0):
    n = N(dur)
    t = T(n)
    fc = f0 * (f1 / f0) ** (t / dur)
    y = unit(svf(r.standard_normal(n), fc, 2.0, "bp")) * (t / dur) ** 2
    return np.stack([y, np.roll(y, 37)], axis=1) * 0.7


def reverse_crash(kit, length_s):
    c = kit.crashes[0]
    M = min(N(length_s), c.shape[0])
    return fade(c[::-1][-M:], 0.3 * length_s, 0.0)


# =============================================================================================
# Mixing / mastering
# =============================================================================================


def mixdown(song, levels, sends, ir_kw, lp_master=None):
    st = song.stems
    for k, d in levels.items():
        if k in st:
            st[k] = set_rms(st[k], d)
    send = sum(g * st[k] for k, g in sends.items() if k in st)
    ir = reverb_ir(rng_for(song.name + "_ir"), **ir_kw)
    wet = song.verb(send, ir) if song.loop or True else None
    mix = sum(st.values()) + 0.5 * wet
    if lp_master:
        mix = song.filt(mix, lambda f: m_lp(f, lp_master, 1))
    return mix


def master(song, mix, target_lufs=-14.0, ceiling_db=-1.0):
    """Glue compression + look-ahead limiting to target loudness, loop-safe when looping."""
    circ = song.loop
    mix = fft_filter(mix, lambda f: m_hp(f, 28.0, 2) * m_peak(f, 9500.0, 0.6, 1.5) * m_peak(f, 60.0, 1.0, 1.0),
                     circular=circ, pad=0.5)
    comp = lambda x: compressor(x, -16.0, 2.0, 0.012, 0.16, 6.0)
    mix = process_circular(mix, comp) if circ else comp(mix)
    gain_db = target_lufs - loudness_lufs(mix)
    out = mix
    for _ in range(4):
        y = mix * float(dbamp(gain_db))
        lim = lambda x: limiter(x, ceiling_db - 0.3, 0.0025, 0.07)
        out = process_circular(y, lim) if circ else lim(y)
        err = target_lufs - loudness_lufs(out)
        if abs(err) < 0.15:
            break
        gain_db += err
    return out


# =============================================================================================
# Music_Title -- 144 BPM, 36 bars (60.0 s), E minor driving rock + synth lead
# =============================================================================================

G_ROOT = {"E": 40, "F": 41, "F#": 42, "G": 43, "G#": 44, "A": 45, "Bb": 46, "B": 47, "C": 48, "C#": 49, "D": 50, "Eb": 51}

RIFF_A = [(0, "E", 2, "o"), (2, "E", 1, "m"), (3, "E", 1, "m"), (4, "G", 2, "o"), (6, "E", 1, "m"), (7, "E", 1, "m"),
          (8, "A", 2, "o"), (10, "E", 1, "m"), (11, "E", 1, "m"), (12, "Bb", 1, "o"), (13, "A", 1, "o"), (14, "G", 2, "o")]
RIFF_B = [(0, "E", 2, "o"), (2, "E", 1, "m"), (3, "E", 1, "m"), (4, "D", 2, "o"), (6, "E", 1, "m"), (7, "E", 1, "m"),
          (8, "C", 3, "o"), (11, "E", 1, "m"), (12, "D", 4, "o")]

TITLE_HOOK = [
    "0:B4:2 2:E5:2 4:G5:3 7:F#5:1 8:E5:2 10:D5:2 12:E5:4",
    "0:B4:2 2:D5:2 4:E5:2 6:G5:2 8:A5:4 12:G5:2 14:F#5:2",
    "0:G5:2 2:B5:2 4:A5:3 7:G5:1 8:E5:2 10:D5:2 12:E5:4",
    "0:D5:2 2:E5:2 4:G5:2 6:A5:2 8:B5:6 14:A5:1 15:B5:1",
    "0:B4:2 2:E5:2 4:G5:3 7:F#5:1 8:E5:2 10:D5:2 12:E5:4",
    "0:B4:2 2:D5:2 4:E5:2 6:G5:2 8:A5:4 12:G5:2 14:F#5:2",
    "0:C6:3 3:B5:1 4:A5:2 6:G5:2 8:A5:2 10:B5:2 12:G5:2 14:F#5:2",
    "0:E5:8 12:B4:1 13:D5:1 14:E5:1 15:F#5:1",
]
TITLE_CHORUS = [
    "0:G5:4 4:E5:2 6:G5:2 8:A5:4 12:G5:4",
    "0:F#5:4 4:D5:2 6:F#5:2 8:A5:4 12:B5:4",
    "0:B5:6 6:A5:2 8:G5:4 12:E5:4",
    "0:E5:2 2:F#5:2 4:G5:4 8:B5:4 12:D6:4",
    "0:E6:4 4:D6:2 6:C6:2 8:B5:4 12:G5:4",
    "0:A5:4 4:F#5:2 6:A5:2 8:D6:4 12:C6:2 14:B5:2",
    "0:B5:8 8:A5:2 10:G5:2 12:F#5:4",
    "0:D#6:8 8:B5:4 12:F#5:4",
]
TITLE_SOLO = [
    "0:E5:1 1:G5:1 2:A5:1 3:B5:1 4:D6:2 6:B5:1 7:A5:1 8:B5:4 12:A5:1 13:G5:1 14:E5:2",
    "0:G5:1 1:A5:1 2:B5:2 4:A5:1 5:G5:1 6:E5:2 8:D5:2 10:E5:2 12:G5:2 14:A5:2",
    "0:B5:2 2:D6:2 4:E6:4 8:D6:1 9:B5:1 10:A5:1 11:B5:1 12:D6:2 14:B5:2",
    "0:E6:2 2:D6:1 3:B5:1 4:A5:1 5:G5:1 6:A5:2 8:B5:6 14:G5:1 15:A5:1",
    "0:B5:1 1:D6:1 2:E6:1 3:G6:1 4:E6:2 6:D6:1 7:B5:1 8:D6:4 12:B5:1 13:A5:1 14:G5:2",
    "0:A5:1 1:B5:1 2:D6:2 4:B5:1 5:A5:1 6:G5:2 8:E5:2 10:G5:2 12:A5:2 14:B5:2",
    "0:E6:3 3:D6:1 4:E6:2 6:G6:2 8:F#6:2 10:E6:2 12:D6:2 14:B5:2",
    "0:E6:8 8:D6:1 9:E6:1 10:D6:1 11:B5:1 12:A5:2 14:B5:2",
]
TITLE_TURN = [
    "0:E5:2 2:G5:2 4:C6:4 8:B5:2 10:G5:2 12:E5:4",
    "0:F#5:2 2:A5:2 4:D6:4 8:C6:2 10:A5:2 12:F#5:4",
    "0:B5:16",
    "0:D#6:8 8:F#6:8",
]

ROCK_A = {"K": "X.....x.X.x.....", "S": "....X.......X...", "H": "X.x.X.x.X.x.X.x."}
ROCK_A2 = {"K": "X.....x.X.x...x.", "S": "....X.......X..o", "H": "X.x.X.x.X.x.X.x."}
ROCK_CH = {"K": "X..x..x.X..x..x.", "S": "....X.......X...", "R": "X.x.X.x.X.x.X.x."}
FILL_1 = {"K": "X.....x.X.......", "S": "....X.......XxXx", "H": "X.x.X.x.X.x....."}
FILL_TOMS = {"K": "X.......X.......", "S": "....X...", "H": "X.x.X.x.", "T1": "........Xx......",
             "T2": "..........Xx....", "T3": "............XxXX"}
HALF = {"K": "X.........x.....", "S": "........X.......", "H": "x.o.x.o.x.o.x.o."}


def music_title():
    s = Song("title", 144, 36, swing=0.5)
    kit = Kit(s.r, 0.17, 1.0, 190.0)
    r = s.r
    # ---------------- arrangement map ----------------
    def section(bar):
        if bar < 4:
            return "intro"
        if bar < 12:
            return "verse"
        if bar < 20:
            return "chorus"
        if bar < 24:
            return "break"
        if bar < 32:
            return "solo"
        return "turn"

    CH_PROG = ["C", "D", "E", "E", "C", "D", "B", "B"]
    BRK_PROG = [("E", "min"), ("C", "maj"), ("A", "min"), ("B", "maj")]
    TURN_PROG = ["C", "D", "B", "B"]

    for bar in range(36):
        sec = section(bar)
        # ---------------- drums ----------------
        if sec in ("intro", "verse", "solo"):
            pat = dict(ROCK_A2 if bar % 2 else ROCK_A)
            if bar in (3, 11, 31):
                pat = FILL_TOMS
            elif bar % 4 == 3:
                pat = FILL_1
        elif sec == "chorus":
            pat = dict(ROCK_CH)
            if bar == 19:
                pat = FILL_TOMS
        elif sec == "break":
            pat = dict(HALF)
            if bar == 23:
                pat = {"K": "X.......X.......", "S": "........X.x.XxXX", "H": "x.o.x.o."}
        else:
            pat = dict(ROCK_CH)
            if bar == 34:
                pat = {"K": "X...X...X...X...", "S": "X.x.X.x.X.x.X.x.", "C": "X..............."}
            if bar == 35:
                pat = {"K": "X...X...X...X...", "S": "xxxxXxXxXXXXXXXX", "T3": "............X.X."}
        if bar in (0, 4, 12, 20, 24, 32):
            pat = dict(pat)
            pat["C"] = "X..............."
            pat["K"] = "X" + pat.get("K", "................")[1:]
        if sec == "chorus" and bar in (14, 16, 18):
            pat = dict(pat)
            pat["C"] = "X..............."
        play_drums(s, kit, bar, pat)
        if sec in ("verse", "solo", "chorus"):
            for st_ in (2, 6, 10, 14):
                s.put("perc", kit.pick(kit.tamb), bar, st_, 0.35, 0.5)

        # ---------------- guitars + bass ----------------
        if sec in ("intro", "verse", "solo"):
            riff = RIFF_B if bar % 2 else RIFF_A
            for st_, rn, ln, kind in riff:
                root = G_ROOT[rn]
                notes = power_chord(root, kind)
                dur = s.secs(ln) * (0.9 if kind == "m" else 0.97)
                for side, p in (("gtrL", -0.85), ("gtrR", 0.85)):
                    s.put(side, guitar_note(r, notes, dur, mute=(kind == "m"), vel=0.8 if kind == "m" else 1.0), bar, st_, 1.0, p,
                          offset=r.uniform(0.0, 0.006))
                bn = root - 12 if kind == "o" else 28
                s.put("bass", bass_note(r, bn, dur * 0.95, 1.0 if kind == "o" else 0.85), bar, st_)
        elif sec in ("chorus", "turn"):
            prog = CH_PROG if sec == "chorus" else TURN_PROG
            rn = prog[(bar - 12) % 8] if sec == "chorus" else prog[bar - 32]
            root = G_ROOT[rn]
            hits = [(0, 6), (6, 2), (8, 6), (14, 2)] if not (sec == "turn" and bar >= 34) else [(k, 1) for k in range(0, 16, 2)]
            for st_, ln in hits:
                for side, p in (("gtrL", -0.85), ("gtrR", 0.85)):
                    s.put(side, guitar_note(r, power_chord(root, "o"), s.secs(ln) * 0.97, False, 1.0), bar, st_, 1.0, p,
                          offset=r.uniform(0.0, 0.006))
            for st_ in range(0, 16, 2):
                s.put("bass", bass_note(r, root - 12, s.secs(2) * 0.9, 0.95 if st_ % 4 else 1.0), bar, st_)
            # pad
            pc = {"C": [60, 64, 67], "D": [62, 66, 69], "E": [64, 67, 71], "B": [63, 66, 71]}[rn]
            s.put("pad", pad_chord(r, pc, s.secs(16) * 0.98, 0.45, 0.15), bar, 0)
        else:  # breakdown
            rn, q = BRK_PROG[bar - 20]
            root = G_ROOT[rn]
            for side, p in (("gtrL", -0.85), ("gtrR", 0.85)):
                s.put(side, guitar_note(r, power_chord(root, "o"), s.secs(15), False, 0.8), bar, 0, 1.0, p)
            s.put("bass", bass_note(r, root - 12, s.secs(7), 1.0), bar, 0)
            s.put("bass", bass_note(r, root - 12, s.secs(7), 0.85), bar, 8)
            iv = [0, 3, 7] if q == "min" else [0, 4, 7]
            tones = [root + 24 + i for i in iv] + [root + 36 + i for i in iv]
            pat_ = tones + tones[-2:0:-1]
            for st_ in range(16):
                s.put("arp", pluck(r, pat_[st_ % len(pat_)], s.secs(1) * 0.8, 0.8 if st_ % 4 == 0 else 0.55), bar, st_, 1.0,
                      0.4 if st_ % 2 else -0.4)
            s.put("pad", pad_chord(r, [root + 24 + i for i in iv], s.secs(16) * 0.98, 0.3, 0.4), bar, 0)

    # ---------------- leads ----------------
    lead = []
    for k, ph in enumerate(TITLE_HOOK):
        lead += [(4 + k, st_, m, ln, 0.9 * v) for st_, m, ln, v in seq(ph)]
    for k, ph in enumerate(TITLE_CHORUS):
        lead += [(12 + k, st_, m, ln, 0.95 * v) for st_, m, ln, v in seq(ph)]
    for k, ph in enumerate(TITLE_TURN):
        lead += [(32 + k, st_, m, ln, 0.95 * v) for st_, m, ln, v in seq(ph)]
    s.stems["lead"] = mono_line(s, lead, "lead")
    solo = []
    for k, ph in enumerate(TITLE_SOLO):
        solo += [(24 + k, st_, m, ln, v) for st_, m, ln, v in seq(ph)]
    s.stems["glead"] = mono_line(s, solo, "glead")
    # octave-down double of the chorus melody
    dbl = [(b, st_, m - 12, ln, 0.6 * v) for b, st_, m, ln, v in lead if 12 <= b < 20]
    s.stems["lead2"] = mono_line(s, dbl, "square")

    # FX: riser into the chorus / loop point, reverse crash into bar 0
    s.put("fx", riser(r, s.secs(32)), 10, 0)
    s.put("fx", riser(r, s.secs(32)), 34, 0)
    rc = reverse_crash(kit, s.secs(16))
    s.put_abs("fx", rc, s.L - rc.shape[0])

    # ---------------- mix ----------------
    gl = distort_guitar(s, s.stems.pop("gtrL"))
    gr = distort_guitar(s, s.stems.pop("gtrR"))
    s.stems["gtr"] = gl + gr
    s.stems["lead"] = s.delay(s.stems["lead"], 3, 0.3, 0.22, lp=4000, hp=500)
    s.stems["glead"] = s.delay(s.stems["glead"], 3, 0.3, 0.2, lp=3500, hp=500)
    s.stems["arp"] = s.delay(s.stems["arp"], 3, 0.35, 0.3)
    levels = {"kick": -15.0, "snare": -17.5, "hats": -27.0, "cym": -26.0, "toms": -21.0, "perc": -33.0,
              "gtr": -16.5, "bass": -17.0, "lead": -18.0, "glead": -18.5, "lead2": -27.0, "pad": -27.0, "arp": -24.0,
              "fx": -30.0}
    mix = mixdown(s, levels, {"snare": 0.25, "toms": 0.2, "lead": 0.25, "glead": 0.2, "pad": 0.3, "arp": 0.25, "cym": 0.1},
                  dict(rt60=1.4, length=1.7, predelay=0.02))
    return master(s, mix), s


# =============================================================================================
# Music_Menu -- 128 BPM, 24 bars (45.0 s), A dorian funk-rock groove
# =============================================================================================

MENU_CH = {"Am7": [57, 60, 64, 67], "D9": [54, 57, 60, 64], "Fmaj7": [53, 57, 60, 64], "G6": [55, 59, 62, 64],
           "Em7": [52, 55, 59, 62], "E7": [52, 56, 59, 62]}
MENU_BASS = {
    "Am7": "0:A1:2 3:A2:1 4:A1:1 6:G2:1 7:A2:1 8:C3:1 10:A1:2 12:E2:1 14:G2:1 15:G#2:1",
    "D9": "0:D2:2 3:D3:1 4:D2:1 6:C3:1 7:D3:1 8:F#2:1 10:D2:2 12:A2:1 14:B2:1 15:G#2:1",
    "Fmaj7": "0:F1:3 3:F2:1 6:F1:1 8:C2:2 10:F2:1 12:E2:1 14:F2:2",
    "G6": "0:G1:3 3:G2:1 6:G1:1 8:D2:2 10:G2:1 12:F#2:1 14:G2:2",
    "Em7": "0:E1:3 3:E2:1 6:E1:1 8:B1:2 10:E2:1 12:D2:1 14:E2:2",
    "E7": "0:E1:2 2:E2:1 4:G#1:2 6:B1:1 8:D2:2 10:E2:1 12:B1:1 14:G#1:1 15:G#2:1",
}
MENU_FORM = (["Am7", "D9"] * 4) + ["Fmaj7", "G6", "Em7", "Am7", "Fmaj7", "G6", "Em7", "E7"] + (["Am7", "D9"] * 4)
MENU_LEAD_B = [
    "0:A5:3 3:G5:1 4:E5:2 6:C5:2 8:D5:3 11:E5:1 12:C5:4",
    "0:B4:2 2:D5:2 4:G5:3 7:F#5:1 8:G5:2 10:A5:2 12:B5:4",
    "0:G5:3 3:E5:1 4:B4:2 6:D5:2 8:E5:4 12:G5:2 14:A5:2",
    "0:C6:2 2:B5:2 4:A5:4 8:E5:2 10:G5:2 12:A5:4",
    "0:A5:3 3:G5:1 4:E5:2 6:C5:2 8:D5:3 11:E5:1 12:C5:4",
    "0:B4:2 2:D5:2 4:G5:3 7:F#5:1 8:G5:2 10:A5:2 12:B5:4",
    "0:G5:2 2:A5:2 4:B5:4 8:D6:2 10:B5:2 12:G5:4",
    "0:G#5:4 4:B5:2 6:D6:2 8:E6:6 14:D6:1 15:B5:1",
]
MENU_LEAD_A = [
    "4:E5:1 5:G5:1 6:A5:2 8:C6:2 10:A5:2 12:G5:2 14:E5:2",
    "0:F#5:3 3:E5:1 4:D5:2 6:E5:6",
    "4:E5:1 5:G5:1 6:A5:2 8:D6:2 10:C6:2 12:A5:2 14:G5:2",
    "0:A5:3 3:G5:1 4:E5:2 6:D5:2 8:E5:8",
    "4:E5:1 5:G5:1 6:A5:2 8:C6:2 10:A5:2 12:G5:2 14:E5:2",
    "0:F#5:3 3:E5:1 4:D5:2 6:E5:6",
    "4:G5:1 5:A5:1 6:C6:2 8:E6:2 10:D6:2 12:C6:2 14:A5:2",
    "0:A5:4 4:C6:4 8:B5:2 10:G5:2 12:A5:4",
]
FUNK_A = {"K": "X.....x...X..x..", "S": "....X..o.o..X..o", "H": "xoXoxoXoxoXoxoXo", "O": "..............X."}
FUNK_B = {"K": "X..x..x...X.....", "S": "....X..o.o..X.o.", "H": "xoXoxoXoxoXoxoXo"}


def music_menu():
    s = Song("menu", 128, 24, swing=0.56)
    kit = Kit(s.r, 0.2, 0.85, 205.0)
    r = s.r
    for bar, ch in enumerate(MENU_FORM):
        sec_b = 8 <= bar < 16
        pat = dict(FUNK_B if bar % 2 else FUNK_A)
        if bar in (7, 15, 23):
            pat = {"K": "X.....x...X.....", "S": "....X..o.oX.XxXX", "H": "xoXoxoXoxo......", "T2": "..........x.....",
                   "T3": "...........x...."}
        if bar in (0, 8, 16):
            pat["C"] = "X..............."
        if sec_b:
            pat["R"] = "x.x.x.x.x.x.x.x."
            pat["H"] = "....o.......o..."
        play_drums(s, kit, bar, pat)
        for st_, m, ln, v in seq(MENU_BASS[ch]):
            s.put("bass", synth_bass(r, m, s.secs(ln) * 0.85, 0.95 * v, res=1.3, env_amt=1800.0, decay=0.08), bar, st_)
        # chops on the off-beats (clean wah guitar)
        cv = [m + 12 for m in MENU_CH[ch][1:]]
        for st_ in (2, 6, 10, 14) if not sec_b else (2, 7, 10, 15):
            s.put("chop", clean_chop(r, cv, s.secs(1) * 0.7, wah=r.uniform(0.4, 0.9)), bar, st_, 0.8, 0.55)
        # e-piano comping
        for st_, ln, v in ((0, 3, 0.75), (6, 2, 0.6), (11, 4, 0.7)):
            s.put("keys", epiano(r, MENU_CH[ch], s.secs(ln), v, s.time(bar, st_)), bar, st_)
        # brass stabs in the A sections
        if not sec_b and bar % 2 == 1:
            for st_, ln, v in ((10, 1, 0.9), (12, 2, 1.0)):
                s.put("brass", brass_stab(r, [m + 12 for m in MENU_CH[ch]], s.secs(ln) * 0.8, v), bar, st_)
        if sec_b:
            s.put("pad", pad_chord(r, [m + 12 for m in MENU_CH[ch]], s.secs(16) * 0.98, 0.35, 0.3), bar, 0)
    lead = []
    for k, ph in enumerate(MENU_LEAD_B):
        lead += [(8 + k, st_, m, ln, 0.9 * v) for st_, m, ln, v in seq(ph)]
    for k, ph in enumerate(MENU_LEAD_A):
        lead += [(16 + k, st_, m, ln, 0.85 * v) for st_, m, ln, v in seq(ph)]
    s.stems["lead"] = mono_line(s, lead, "lead")
    bell = [(b, st_, m + 12, ln, 0.5 * v) for b, st_, m, ln, v in lead if b >= 16]
    s.stems["bell"] = mono_line(s, bell, "bell")
    rc = reverse_crash(kit, s.secs(8))
    s.put_abs("fx", rc, s.L - rc.shape[0])
    s.put_abs("fx", reverse_crash(kit, s.secs(8)), s.at(8, 0) - rc.shape[0])
    s.stems["lead"] = s.delay(s.stems["lead"], 3, 0.3, 0.22, lp=4500, hp=500)
    s.stems["bell"] = s.delay(s.stems["bell"], 3, 0.35, 0.3)
    s.stems["chop"] = s.delay(s.stems["chop"], 2, 0.25, 0.18)
    levels = {"kick": -15.5, "snare": -18.5, "hats": -26.0, "cym": -27.0, "toms": -22.0, "perc": -32.0,
              "bass": -15.5, "chop": -24.0, "keys": -21.5, "brass": -21.0, "pad": -27.0, "lead": -18.5, "bell": -27.0,
              "fx": -30.0}
    mix = mixdown(s, levels, {"snare": 0.25, "keys": 0.3, "brass": 0.3, "lead": 0.25, "pad": 0.3, "bell": 0.4, "chop": 0.2},
                  dict(rt60=1.3, length=1.6, predelay=0.02))
    return master(s, mix), s


# =============================================================================================
# Music_Intermission -- 96 BPM, 18 bars (45.0 s), D minor big-beat with stadium organ
# =============================================================================================

INT_FORM = ["Dm", "Dm", "Dm", "Dm", "Bb", "C", "Dm", "Dm", "Bb", "C", "Gm", "Gm", "A7", "A7", "Dm", "Dm", "Bb", "A7"]
INT_ROOT = {"Dm": 38, "Bb": 34, "C": 36, "Gm": 43, "A7": 33}
INT_CH = {"Dm": [62, 65, 69], "Bb": [62, 65, 70], "C": [64, 67, 72], "Gm": [62, 67, 70], "A7": [61, 64, 67, 69]}
INT_ORGAN = {
    2: "0:D5:2 2:F5:2 4:G5:1 5:G#5:1 6:A5:2 8:C6:2 10:A5:2 12:G5:2 14:F5:2",
    3: "0:D5:4 4:F5:1 5:D5:1 6:C5:2 8:D5:6 14:A4:1 15:C5:1",
    4: "0:D5:2 2:F5:2 4:Bb5:3 7:A5:1 8:G5:2 10:F5:2 12:D5:4",
    5: "0:E5:2 2:G5:2 4:C6:3 7:Bb5:1 8:A5:2 10:G5:2 12:E5:4",
    6: "0:D5:2 2:F5:2 4:G5:1 5:G#5:1 6:A5:2 8:D6:2 10:C6:2 12:A5:2 14:G5:2",
    7: "0:A5:6 6:G5:1 7:F5:1 8:D5:8",
    10: "0:G5:3 3:Bb5:1 4:D6:4 8:C6:2 10:Bb5:2 12:G5:4",
    11: "0:A5:2 2:Bb5:2 4:A5:2 6:G5:2 8:F5:2 10:G5:2 12:D5:4",
    12: "0:C#6:4 4:E6:4 8:G6:4 12:E6:4",
    13: "0:A6:8 8:G6:2 10:E6:2 12:C#6:4",
    14: "0:D6:2 2:A5:2 4:F5:2 6:D5:2 8:F5:2 10:A5:2 12:D6:4",
    15: "0:F6:4 4:E6:2 6:D6:2 8:C6:2 10:A5:2 12:F5:4",
    16: "0:Bb5:4 4:D6:4 8:F6:8",
    17: "0:E6:4 4:C#6:4 8:A5:4 12:E5:2 14:G5:2",
}
BIGBEAT = {"K": "X.....X...X..x..", "S": "....X..o.o..X..o", "H": "x.xox.xox.xox.xo", "TB": "....x.......x..."}
BIGBEAT2 = {"K": "X.x...X...X.....", "S": "....X..o.o..X.o.", "H": "x.xox.xox.xox.xo", "TB": "....x.......x..."}


def music_intermission():
    s = Song("intermission", 96, 18, swing=0.57)
    kit = Kit(s.r, 0.24, 0.9, 180.0)
    r = s.r
    for bar, ch in enumerate(INT_FORM):
        root = INT_ROOT[ch]
        if bar < 2:
            pat = {"K": "X.........X.....", "S": "....X.......X...", "H": "x.x.x.x.x.x.x.x."}
            if bar == 1:
                pat["S"] = "....X.......XxXX"
        else:
            pat = dict(BIGBEAT2 if bar % 2 else BIGBEAT)
            if bar in (9, 17):
                pat = {"K": "X.....X...X.....", "S": "....X..o.oXxXxXX", "H": "x.xox.xox.......", "T3": "..........X.X..."}
        if bar in (0, 2, 10):
            pat["C"] = "X..............."
        play_drums(s, kit, bar, pat)
        # acid-ish synth bass: 8ths with octave pops
        for st_ in range(0, 16, 2):
            m = root + (12 if st_ in (6, 14) else 0)
            vel = 1.0 if st_ % 4 == 0 else 0.8
            s.put("bass", synth_bass(r, m, s.secs(1.6), vel, res=2.6 if bar >= 10 else 1.6,
                                     env_amt=3200.0 if bar >= 10 else 2000.0, decay=0.07), bar, st_)
        # organ comping stabs (stadium organ)
        for st_, ln in ((0, 2), (3, 1), (6, 2), (10, 2), (14, 1)):
            notes = INT_CH[ch]
            y = sum(organ_note(r, m, s.secs(ln) * 0.85, 0.7, perc=True) for m in notes)
            s.put("organ", y / len(notes), bar, st_, 1.0, -0.2)
        # distorted guitar stabs in B section
        if bar >= 10:
            for st_, ln in ((0, 3), (6, 2), (10, 4)):
                g = guitar_note(r, power_chord(root + 12, "o"), s.secs(ln) * 0.9, False, 1.0)
                s.put("gtrL", g, bar, st_, 1.0, -0.8)
                s.put("gtrR", guitar_note(r, power_chord(root + 12, "o"), s.secs(ln) * 0.9, False, 1.0), bar, st_, 1.0, 0.8,
                      offset=0.004)
        if bar < 2:
            s.put("pad", pad_chord(r, [m - 12 for m in INT_CH[ch]], s.secs(16), 0.3, 1.0), bar, 0)
    # organ melody (stadium organ lead)
    org = np.zeros(1)
    for bar, ph in INT_ORGAN.items():
        for st_, m, ln, v in seq(ph):
            y = organ_note(r, m, s.secs(ln) * 0.92, 0.9 * v, perc=True) + 0.5 * organ_note(r, m - 12, s.secs(ln) * 0.92, 0.9 * v, perc=False)
            s.put("olead", y, bar, st_, 1.0, 0.1)
    # rotary swirl on the organ stems (circular-safe: LFO periodic in the loop: 6 Hz * 45 s = 270 cycles)
    t = T(s.n)
    lfo = np.sin(TWO_PI * 6.0 * t)
    for k in ("organ", "olead"):
        x = s.stems[k]
        x = saturate(1.6 * x / (np.max(np.abs(x)) + 1e-9), 1.6)
        s.stems[k] = np.stack([x[:, 0] * (1 + 0.25 * lfo), x[:, 1] * (1 - 0.25 * lfo)], axis=1)
    gl = distort_guitar(s, s.stems.pop("gtrL"))
    gr = distort_guitar(s, s.stems.pop("gtrR"))
    s.stems["gtr"] = gl + gr
    s.put("fx", riser(r, s.secs(16)), 9, 0)
    rc = reverse_crash(kit, s.secs(8))
    s.put_abs("fx", rc, s.L - rc.shape[0])
    s.stems["olead"] = s.delay(s.stems["olead"], 3, 0.25, 0.18, lp=4000, hp=400)
    levels = {"kick": -14.5, "snare": -17.0, "hats": -26.0, "cym": -26.0, "toms": -21.0, "perc": -29.0,
              "bass": -16.5, "organ": -22.0, "olead": -18.5, "gtr": -20.0, "pad": -24.0, "fx": -30.0}
    mix = mixdown(s, levels, {"snare": 0.3, "organ": 0.35, "olead": 0.35, "pad": 0.3, "gtr": 0.1},
                  dict(rt60=1.8, length=2.0, predelay=0.025))
    return master(s, mix), s


# =============================================================================================
# Music_Overtime -- 144 BPM, 12 bars (20.0 s), C minor tense loop
# =============================================================================================

OT_FORM = ["Cm", "Cm", "Cm", "Cm", "Ab", "Bb", "Ab", "Bb", "Cm", "Db", "Cm", "G7"]
OT_ROOT = {"Cm": 36, "Ab": 32, "Bb": 34, "Db": 37, "G7": 31}
OT_CH = {"Cm": [60, 63, 67], "Ab": [60, 63, 68], "Bb": [62, 65, 70], "Db": [61, 65, 68], "G7": [59, 62, 65, 67]}
OT_OST = {"Cm": ["C5", "D5", "Eb5", "D5"], "Ab": ["C5", "Eb5", "Ab5", "Eb5"], "Bb": ["D5", "F5", "Bb5", "F5"],
          "Db": ["Db5", "F5", "Ab5", "F5"], "G7": ["B4", "D5", "F5", "G5"]}
OT_LEAD = {4: "0:Eb5:8 8:D5:8", 5: "0:F5:16", 6: "0:Eb5:8 8:C5:8", 7: "0:D5:8 8:F5:8",
           8: "0:G5:16", 9: "0:Ab5:16", 10: "0:G5:8 8:Eb5:8", 11: "0:D5:4 4:F5:4 8:B5:8"}


def music_overtime():
    s = Song("overtime", 144, 12, swing=0.5)
    kit = Kit(s.r, 0.17, 1.0, 190.0)
    r = s.r
    timp = {k: timpani(r, float(midi_hz(v))) for k, v in OT_ROOT.items()}
    for bar, ch in enumerate(OT_FORM):
        root = OT_ROOT[ch]
        pat = {"K": "X.......X.......", "S": "....X.......X...", "H": "xoxoxoxoxoxoxoxo"}
        if bar >= 8:
            pat["K"] = "X.x.X.x.X.x.X.x."
        if bar == 11:
            pat = {"K": "X...X...X...X...", "S": "x.x.xxxxXxXxXXXX", "H": "xoxoxoxo........", "T3": "............X.X."}
        if bar in (0, 4, 8):
            pat["C"] = "X..............."
        play_drums(s, kit, bar, pat)
        for st_ in (0, 8):
            s.put("timp", timp[ch], bar, st_, 1.0 if st_ == 0 else 0.7)
        # palm-muted 8th chugs (16ths in the last 4 bars)
        step = 1 if bar >= 8 else 2
        for st_ in range(0, 16, step):
            accent = st_ % 8 == 0
            for side, p in (("gtrL", -0.85), ("gtrR", 0.85)):
                s.put(side, guitar_note(r, power_chord(root + 12, "m" if not accent else "o"), s.secs(step) * 0.85,
                                        mute=not accent, vel=1.0 if accent else 0.8), bar, st_, 1.0, p, offset=r.uniform(0, 0.005))
            s.put("bass", bass_note(r, root, s.secs(step) * 0.85, 1.0 if accent else 0.8), bar, st_)
        # strings ostinato 16ths
        ost = [note(x) for x in OT_OST[ch]]
        for st_ in range(16):
            s.put("str", string_stab(r, [ost[st_ % 4]], s.secs(1) * 0.7, 0.9 if st_ % 4 == 0 else 0.65), bar, st_, 1.0,
                  -0.3 if st_ % 2 else 0.3)
        if bar >= 4:
            s.put("pad", pad_chord(r, [m - 12 for m in OT_CH[ch]], s.secs(16) * 0.98, 0.3, 0.3), bar, 0)
        if bar in (4, 6, 8, 10):
            s.put("brass", brass_stab(r, [m for m in OT_CH[ch]], s.secs(3), 1.0), bar, 0)
    lead = []
    for bar, ph in OT_LEAD.items():
        lead += [(bar, st_, m, ln, 0.85 * v) for st_, m, ln, v in seq(ph)]
    s.stems["lead"] = mono_line(s, lead, "glead")
    s.put("fx", riser(r, s.secs(16)), 11, 0)
    gl = distort_guitar(s, s.stems.pop("gtrL"), 9.0)
    gr = distort_guitar(s, s.stems.pop("gtrR"), 9.0)
    s.stems["gtr"] = gl + gr
    s.stems["lead"] = s.delay(s.stems["lead"], 3, 0.3, 0.2, lp=3500, hp=500)
    levels = {"kick": -15.0, "snare": -18.0, "hats": -27.0, "cym": -27.0, "toms": -21.0, "timp": -18.5,
              "gtr": -17.0, "bass": -17.5, "str": -21.0, "pad": -26.0, "brass": -21.0, "lead": -19.0, "fx": -29.0}
    mix = mixdown(s, levels, {"snare": 0.25, "timp": 0.3, "str": 0.3, "brass": 0.3, "lead": 0.25, "pad": 0.3},
                  dict(rt60=1.6, length=1.8, predelay=0.02))
    return master(s, mix), s


# =============================================================================================
# Music_Victory -- 8 s sting, E major fanfare (not looping)
# =============================================================================================

VIC_LEAD = ["0:B4:2 2:E5:2 4:G#5:2 6:B5:6 12:G#5:2 14:B5:2",
            "0:C#6:4 4:B5:2 6:A5:2 8:G#5:2 10:A5:2 12:B5:4",
            "0:E6:16"]


def music_victory():
    bpm = 140
    s = Song("victory", bpm, 3, swing=0.5, loop=False, tail=8.0)
    s.n = N(8.0)
    s.stems = {}
    kit = Kit(s.r, 0.2, 1.0, 195.0)
    r = s.r
    # bar 0: E, bar 1: A (beats 1-2) -> B (3-4), bar 2: E held
    play_drums(s, kit, 0, {"K": "X.....X.X.....X.", "S": "....X.......X.X.", "C": "X...............", "H": "x.x.x.x.x.x.x.x."})
    play_drums(s, kit, 1, {"K": "X.....X.X.....X.", "S": "....X.......XxXX", "C": "X.......X.......", "H": "x.x.x.x."})
    play_drums(s, kit, 2, {"K": "X...............", "C": "X...............", "T3": "X..............."})
    # final drum roll swell (snare 32nds under the held chord)
    for k in range(24):
        s.put("snare", kit.pick(kit.snares), 2, 2 + k * 0.5, 0.15 + 0.5 * (k / 24) ** 2)
    s.put("snare", kit.pick(kit.snares), 2, 14, 1.0)
    s.put("cym", kit.crashes[1], 2, 14, 1.0)
    s.put("kick", kit.kicks[0], 2, 14, 1.0)
    chords = [(0, 0, "E", 6), (0, 6, "E", 2), (0, 8, "E", 6), (0, 14, "E", 2), (1, 0, "A", 8), (1, 8, "B", 8),
              (2, 0, "E", 14), (2, 14, "E", 30)]
    triad = {"E": [64, 68, 71], "A": [64, 69, 73], "B": [63, 66, 71]}
    for bar, st_, rn, ln in chords:
        root = G_ROOT[rn] if rn != "E" else 40
        dur = s.secs(ln) * 0.97 if ln < 30 else 3.0
        for side, p in (("gtrL", -0.85), ("gtrR", 0.85)):
            s.put(side, guitar_note(r, power_chord(root, "o"), dur, False, 1.0), bar, st_, 1.0, p, offset=r.uniform(0, 0.005))
        s.put("bass", bass_note(r, root - 12, dur, 1.0), bar, st_)
        s.put("brass", brass_stab(r, [m for m in triad[rn]] + [triad[rn][0] + 12], min(dur, 2.5), 1.0), bar, st_)
    lead = []
    for k, ph in enumerate(VIC_LEAD):
        lead += [(k, st_, m, ln, 1.0 * v) for st_, m, ln, v in seq(ph)]
    lead.append((2, 14, note("E6"), 24, 1.0))
    s.stems["lead"] = mono_line(s, lead, "lead")
    s.stems["lead2"] = mono_line(s, [(b, st_, m - 12, ln, 0.7 * v) for b, st_, m, ln, v in lead], "glead")
    s.put("fx", np.stack([fm_sparkle(r, 2.5)] * 2, axis=1), 2, 14, 0.5)
    gl = distort_guitar(s, s.stems.pop("gtrL"))
    gr = distort_guitar(s, s.stems.pop("gtrR"))
    s.stems["gtr"] = gl + gr
    s.stems["lead"] = s.delay(s.stems["lead"], 3, 0.3, 0.2, lp=4500, hp=500)
    levels = {"kick": -15.0, "snare": -18.0, "hats": -27.0, "cym": -24.0, "toms": -20.0, "gtr": -16.5, "bass": -17.5,
              "brass": -19.0, "lead": -17.5, "lead2": -23.0, "fx": -28.0}
    mix = mixdown(s, levels, {"snare": 0.25, "brass": 0.3, "lead": 0.3, "lead2": 0.2, "cym": 0.15},
                  dict(rt60=2.0, length=2.4, predelay=0.025))
    mix = fade(mix, 0.0, 1.2)
    return master(s, mix, -13.0), s


def fm_sparkle(r, dur):
    n = N(dur)
    y = np.zeros(n)
    for k, m in enumerate([88, 92, 95, 100, 104]):
        L = N(1.5)
        t = T(L)
        f = float(midi_hz(m))
        b = np.sin(TWO_PI * f * t + 1.5 * np.exp(-t / 0.2) * np.sin(TWO_PI * 3.5 * f * t)) * env_exp(L, 0.5, 0.001)
        mix_into(y, (0.6 - 0.08 * k) * b, N(0.07 * k))
    return y
