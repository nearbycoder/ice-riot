"""
ICE RIOT -- arena crowd (formant-synthesized voices, claps, stomps, whistles, horns) and the
stadium organ (drawbar organ with percussion, key click, rotary speaker, arena room).
All melodies are original.
"""

import math

import numpy as np

from .dsp import (SR, TWO_PI, N, T, rng_for, midi_hz, mix_into, mix_circular, pan, unit, unitpeak, rms,
                  env_exp, env_pts, fade, smooth_random, m_lp, m_hp, m_bp, m_peak, m_tilt, fft_filter,
                  shaped_noise, biquad, iir, iir_circular, osc_saw, osc_sine, osc_pulse, burst, thump, modal,
                  add_reverb, convolve_circular, saturate, arena_ir, seamless_xfade, pad_to, echo, reverb_ir,
                  ir_cached)

# =============================================================================================
# Formant voices (STFT cascade-formant filter)
# =============================================================================================

VOWELS = {  # F1, F2, F3 (Hz), adult male; female voices scale by ~1.15-1.2.
    "a": (730, 1090, 2440), "ae": (660, 1720, 2410), "e": (530, 1840, 2480), "i": (300, 2250, 3000),
    "o": (570, 840, 2410), "u": (320, 870, 2240), "uh": (520, 1190, 2390), "oh": (460, 820, 2600),
    "er": (490, 1350, 1690),
}
F45 = (3350.0, 4200.0)
FBW = np.array([90.0, 110.0, 150.0, 220.0, 300.0])
NFFT, HOP = 1024, 256


def vowel_vec(v, fscale=1.0):
    f1, f2, f3 = VOWELS[v]
    return np.array([f1, f2, f3, F45[0], F45[1]], dtype=np.float64) * fscale


def _stft(x):
    win = np.sqrt(np.hanning(NFFT + 1)[:-1])
    xp = np.pad(x, (NFFT, 2 * NFFT))
    nfr = (xp.shape[0] - NFFT) // HOP + 1
    idx = HOP * np.arange(nfr)[:, None] + np.arange(NFFT)[None, :]
    return np.fft.rfft(xp[idx] * win, axis=1), win


def _istft(S, win, n):
    frames = np.fft.irfft(S, NFFT, axis=1) * win
    nfr, k = frames.shape[0], NFFT // HOP
    blocks = np.zeros((nfr + k, HOP))
    for j in range(k):
        blocks[j:j + nfr] += frames[:, j * HOP:(j + 1) * HOP]
    return blocks.reshape(-1)[NFFT:NFFT + n] / 2.0


def frame_times(n):
    nfr = (n + 2 * NFFT) // HOP + 1
    return (np.arange(nfr) * HOP - NFFT / 2) / SR


def formant_track(n, key_t, key_F):
    ft = frame_times(n)
    key_F = np.asarray(key_F, dtype=np.float64)
    return np.stack([np.interp(ft, key_t, key_F[:, j]) for j in range(key_F.shape[1])], axis=1)


def _formant_mag(freqs, F, bw_scale=1.0):
    f = freqs[None, :]
    H = np.ones((F.shape[0], freqs.shape[0]))
    for k in range(F.shape[1]):
        Fk = F[:, k:k + 1]
        Bk = FBW[k] * bw_scale
        H /= np.sqrt((1.0 - (f / Fk) ** 2) ** 2 + (f * Bk / Fk ** 2) ** 2)
    return H


def render_voice(r, f0, F_frames, amp, breath=0.2, tilt_db=0.0, bw_scale=1.0, noise_only=False):
    """Source-filter voice: band-limited glottal saw (+ breath noise) through time-varying formants."""
    n = amp.shape[0]
    exc = r.standard_normal(n) if noise_only else osc_saw(f0, n, r.random()) + breath * r.standard_normal(n)
    S, win = _stft(exc)
    freqs = np.fft.rfftfreq(NFFT, 1.0 / SR)
    H = _formant_mag(freqs, F_frames, bw_scale) * m_hp(freqs, 90.0, 2)[None, :]
    if tilt_db:
        H *= m_tilt(freqs, tilt_db, 500.0)[None, :]
    return _istft(S * H, win, n) * amp


def babble_talker(r, n, female, excited=0.0):
    """One distant talker: syllable-rate vowels, intonation, phrase pauses, consonant hiss."""
    dur = n / SR
    fs = r.uniform(1.12, 1.22) if female else r.uniform(0.94, 1.06)
    base = (r.uniform(175, 250) if female else r.uniform(95, 145)) * (1.0 + 0.35 * excited)
    names = list(VOWELS)
    amp = np.zeros(n)
    kt, kF, ft, fv, cons = [], [], [], [], []
    t = r.uniform(-0.3, 0.8)
    phrase_t = t
    while t < dur + 0.3:
        if r.random() < 0.12 * (1.0 - 0.5 * excited):
            t += r.uniform(0.25, 1.1)
            phrase_t = t
            continue
        sd = r.uniform(0.11, 0.30)
        a = r.uniform(0.5, 1.0)
        Fv = vowel_vec(names[r.integers(len(names))], fs)
        kt += [t + 0.3 * sd, t + 0.7 * sd]
        kF += [Fv, Fv]
        decl = -2.5 * min((t - phrase_t) / 2.0, 1.0)
        ft.append(t + 0.5 * sd)
        fv.append(base * 2.0 ** ((decl + r.normal(0.0, 2.0 + 2.0 * excited)) / 12.0))
        L = N(1.3 * sd)
        mix_into(amp, a * np.sin(np.pi * np.linspace(0.0, 1.0, L)) ** 1.5, N(t - 0.15 * sd))
        if r.random() < 0.45:
            cons.append((t, r.uniform(0.02, 0.06), a))
        t += sd
    tt = T(n)
    f0 = np.interp(tt, ft, fv) * (1.0 + 0.012 * smooth_random(r, n, 25.0))
    y = render_voice(r, f0, formant_track(n, kt, kF), amp, breath=0.25)
    lvl = rms(y) + 1e-9
    for t0, d, a in cons:
        b = burst(r, d, d * 0.35, lambda f, c=r.uniform(2500, 4500): m_hp(f, c, 2), attack=0.004)
        mix_into(y, 0.6 * lvl * a * unit(b), N(t0))
    return y


CHEER_WORDS = {
    "yeah": [("i", 0.0), ("e", 0.2), ("ae", 0.45), ("a", 1.0)],
    "woo": [("u", 0.0), ("u", 1.0)],
    "hey": [("e", 0.0), ("e", 0.6), ("i", 1.0)],
    "ahh": [("a", 0.0), ("a", 1.0)],
    "oh": [("o", 0.0), ("oh", 1.0)],
    "ooh": [("u", 0.0), ("oh", 0.45), ("u", 1.0)],
    "aww": [("o", 0.0), ("o", 0.5), ("uh", 1.0)],
    "boo": [("u", 0.0), ("u", 0.7), ("oh", 1.0)],
    "go": [("uh", 0.0), ("o", 0.3), ("u", 1.0)],
}


def shout_voice(r, word, dur, base, fs, rise_st, fall_st, breath=0.45, attack=0.1, release=0.35,
                vib_rate=5.5, vib_depth=0.006, tilt_db=3.0, peak_at=0.3):
    """One crowd member shouting/singing a word with a rise-then-fall pitch contour."""
    n = N(dur + release + 0.05)
    t = T(n)
    rel = np.clip(t / dur, 0.0, 1.0)
    st = np.where(rel < peak_at, rise_st * np.sin(0.5 * np.pi * rel / peak_at),
                  rise_st - (rise_st + fall_st) * (np.maximum(rel - peak_at, 0.0) / (1.0 - peak_at)) ** 1.3)
    f0 = base * 2.0 ** (st / 12.0) * (1.0 + vib_depth * np.sin(TWO_PI * vib_rate * t + r.uniform(0, TWO_PI)))
    f0 *= 1.0 + 0.01 * smooth_random(r, n, 25.0)
    keys = CHEER_WORDS[word]
    F = formant_track(n, [k * dur for _, k in keys], [vowel_vec(v, fs) for v, _ in keys])
    amp = np.interp(t, [0.0, attack, dur, dur + release], [0.0, 1.0, 0.8, 0.0])
    amp *= 1.0 + 0.08 * smooth_random(r, n, 6.0)
    return render_voice(r, f0, F, amp, breath=breath, tilt_db=tilt_db)


def sung_voice(r, notes, vowel, base_shift, fs, breath=0.35, tilt_db=2.0):
    """A crowd member chanting a melodic vowel line: notes = [(t0, dur, midi)] (absolute times)."""
    end = max(t0 + d for t0, d, _ in notes) + 0.3
    n = N(end)
    t = T(n)
    tp, fp = [], []
    amp = np.zeros(n)
    for t0, d, m in notes:
        tp += [t0, t0 + d * 0.9]
        fp += [float(midi_hz(m)) * base_shift] * 2
        L = N(d)
        mix_into(amp, np.interp(T(L), [0, 0.04, d * 0.7, d], [0, 1, 0.85, 0]), N(t0))
    f0 = np.interp(t, tp, fp) * (1.0 + 0.006 * np.sin(TWO_PI * 5.0 * t + r.uniform(0, 6)))
    f0 *= 1.0 + 0.012 * smooth_random(r, n, 20.0)
    F = formant_track(n, [0, end], [vowel_vec(vowel, fs)] * 2)
    return render_voice(r, f0, F, amp, breath=breath, tilt_db=tilt_db)


# =============================================================================================
# Claps, whistles, stomps, horns
# =============================================================================================


def clap_bank(r, count=32):
    bank = []
    for _ in range(count):
        L = N(0.08)
        fc, q = r.uniform(900, 2400), r.uniform(0.7, 1.6)
        x = fft_filter(r.standard_normal(L), lambda f: m_bp(f, fc, q) + 0.25 * m_bp(f, fc * 2.2, 1.0), pad=0.0)
        e = env_exp(L, r.uniform(0.005, 0.011), attack=0.0006)
        c = unitpeak(x) * e + 0.3 * modal(L, [(r.uniform(250, 450), 1.0, 0.01)])
        bank.append(unitpeak(c))
    return bank


def applause(r, n, bank, clappers, start, stop, rate, env_fn, circular=False):
    out = np.zeros((n, 2))
    put = mix_circular if circular else mix_into
    for _ in range(clappers):
        p, g = r.uniform(-0.95, 0.95), r.uniform(0.3, 1.0)
        hz, t, t_end = r.uniform(*rate), r.uniform(*start), r.uniform(*stop)
        sig = bank[r.integers(len(bank))]
        while t < t_end:
            put(out, pan(sig * g * env_fn(t) * r.uniform(0.7, 1.0), p), N(t))
            t += r.uniform(0.85, 1.15) / hz
    return out


def finger_whistle(r, dur):
    n = N(dur)
    t = T(n)
    f = np.interp(t, [0, 0.15 * dur, 0.7 * dur, dur], [2300, 2900, 2750, 2200]) * r.uniform(0.85, 1.15)
    f *= 1.0 + 0.006 * np.sin(TWO_PI * 5.5 * t) + 0.004 * smooth_random(r, n, 30.0)
    y = osc_sine(f, n) + 0.05 * osc_sine(2.0 * f, n)
    y += 0.08 * unit(fft_filter(r.standard_normal(n), lambda ff: m_bp(ff, float(np.mean(f)), 3.0), pad=0.0))
    return y * env_pts(n, [(0, 0), (0.03, 1), (0.7 * dur, 0.9), (dur, 0)])


def fan_horn(r, dur):
    """Hand-held fan air horn 'BRAAP' (distant, in the stands)."""
    n = N(dur)
    t = T(n)
    f = r.uniform(380, 480) * (1.0 - 0.04 * np.exp(-t / 0.04))
    y = osc_pulse(f, n, 0.3) + 0.5 * osc_saw(f * 1.5, n)
    y = iir(y, biquad("hp", 300, 0.7), biquad("peak", 1400, 1.4, 6.0), biquad("lp", 4500, 0.7))
    return saturate(unitpeak(y), 2.0) * env_pts(n, [(0, 0), (0.02, 1), (dur - 0.05, 0.9), (dur, 0)])


def stomp(r, dur=0.35):
    """Many feet on concrete/bleachers at once: deep thud + scuffle."""
    n = N(dur)
    y = thump(n, 95, 45, 0.02, 0.07) + 0.5 * thump(n, 160, 70, 0.008, 0.03)
    y += 0.4 * unitpeak(burst(r, dur, 0.03, lambda f: m_bp(f, 300, 0.7), attack=0.004))
    y += 0.15 * unitpeak(burst(r, dur, 0.04, lambda f: m_bp(f, 2500, 0.8), attack=0.006))
    return y


def crowd_stomp(r, jitter=0.03, people=14):
    out = np.zeros((N(0.45), 2))
    for _ in range(people):
        mix_into(out, pan(stomp(r) * r.uniform(0.5, 1.0), r.uniform(-0.9, 0.9)), N(r.uniform(0, jitter)))
    return out


def crowd_clap(r, bank, jitter=0.035, people=40):
    out = np.zeros((N(0.15), 2))
    for _ in range(people):
        mix_into(out, pan(bank[r.integers(len(bank))] * r.uniform(0.4, 1.0), r.uniform(-0.95, 0.95)), N(r.uniform(0, jitter)))
    return out


# =============================================================================================
# Crowd reactions
# =============================================================================================


def crowd_reaction(seed, dur, voices, words, rise, fall, vdur, onset, female=0.42, breath=(0.35, 0.6),
                   clappers=0, whistles=0, noise_vowel=None, noise_level=0.0, stomps=0, peak_at=0.3,
                   male_f0=(150, 240), female_f0=(260, 420), attack=(0.06, 0.2), release=(0.25, 0.5), horns=0,
                   reverb=0.55):
    """Generic crowd reaction (cheer / ooh / aww / boo): many shouted voices + applause + whistles,
    optional vowel-formant-filtered noise 'body', all in a big arena reverb (stereo)."""
    r = rng_for(seed)
    n = N(dur)
    mix = np.zeros((n, 2))
    wk, wp = zip(*words)
    wp = np.asarray(wp, dtype=np.float64) / np.sum(wp)
    for _ in range(voices):
        fem = r.random() < female
        base = r.uniform(*(female_f0 if fem else male_f0))
        fs = r.uniform(1.12, 1.22) if fem else r.uniform(0.94, 1.06)
        word = wk[r.choice(len(wk), p=wp)]
        t0 = r.uniform(*onset[0]) if r.random() < onset[2] else r.uniform(*onset[1])
        d = min(r.uniform(*vdur), dur - t0 - 0.2)
        if d < 0.2:
            continue
        v = shout_voice(r, word, d, base, fs, r.uniform(*rise), r.uniform(*fall), breath=r.uniform(*breath),
                        attack=r.uniform(*attack), release=r.uniform(*release), peak_at=peak_at)
        mix_into(mix, pan(unit(v) * r.uniform(0.35, 1.0), r.uniform(-0.9, 0.9)), N(t0))
    mix /= rms(mix) + 1e-9
    if noise_vowel is not None:
        keys, env = noise_vowel
        for ch in range(2):
            F = formant_track(n, [k * dur for _, k in keys], [vowel_vec(v, 1.08) for v, _ in keys])
            body = render_voice(r, None, F, env_pts(n, env), noise_only=True, bw_scale=2.5)
            mix[:, ch] += noise_level * unit(body) * np.sqrt(np.mean(env_pts(n, env) ** 2) + 1e-9)
    if clappers:
        cl = applause(r, n, clap_bank(r), clappers, (0.04, 0.3), (0.55 * dur, 0.9 * dur), (3.5, 6.0),
                      lambda tt: min(1.0, 0.5 + tt / 0.2) * max(0.0, 1.0 - tt / dur) ** 0.6)
        mix += 0.55 * cl / (rms(cl) + 1e-9)
    for _ in range(whistles):
        w = finger_whistle(r, r.uniform(0.4, 0.9))
        mix_into(mix, pan(0.5 * unitpeak(w), r.uniform(-0.8, 0.8)), N(r.uniform(0.05, 0.45 * dur)))
    for _ in range(horns):
        h = fan_horn(r, r.uniform(0.35, 0.8))
        h = iir(h, biquad("lp", 3000, 0.7))
        mix_into(mix, pan(0.35 * h, r.uniform(-0.8, 0.8)), N(r.uniform(0.1, 0.5 * dur)))
    for k in range(stomps):
        mix_into(mix, 0.6 * crowd_stomp(r, people=8), N(0.25 + k * 0.42 + r.uniform(0, 0.03)))
    wet = add_reverb(mix, arena_ir(), wet=reverb, dry=0.8)[:n]
    wet = iir(wet, biquad("hp", 70, 0.7), biquad("peak", 3000, 0.8, 1.5))
    return fade(wet, 0.0, min(0.8, dur * 0.25))


def crowd_cheer_big():
    return crowd_reaction("bigcheer", 6.0, 150, [("yeah", 3), ("woo", 3), ("ahh", 3), ("hey", 1), ("oh", 1)],
                          rise=(3, 8), fall=(2, 6), vdur=(1.8, 4.6), onset=((0.0, 0.15), (0.15, 1.8), 0.7),
                          attack=(0.03, 0.12), clappers=70, whistles=7, stomps=8, horns=3,
                          noise_vowel=([("ae", 0.0), ("a", 0.35), ("o", 1.0)],
                                       [(0, 0), (0.15, 0.7), (0.35, 1), (4.0, 0.8), (6.0, 0)]),
                          noise_level=0.55)


def crowd_cheer_small():
    return crowd_reaction("smallcheer", 2.5, 60, [("yeah", 3), ("woo", 2), ("hey", 2), ("ahh", 2)],
                          rise=(3, 7), fall=(2, 5), vdur=(0.8, 1.7), attack=(0.04, 0.12),
                          onset=((0.0, 0.12), (0.12, 0.5), 0.8), clappers=30, whistles=2,
                          noise_vowel=([("ae", 0.0), ("a", 0.5), ("o", 1.0)], [(0, 0), (0.2, 1), (1.4, 0.6), (2.5, 0)]),
                          noise_level=0.35)


def crowd_ooh():
    return crowd_reaction("ooh", 2.0, 70, [("ooh", 1)], rise=(3, 5), fall=(6, 9), vdur=(1.1, 1.5),
                          onset=((0.0, 0.1), (0.08, 0.22), 0.8), breath=(0.4, 0.6), peak_at=0.32,
                          male_f0=(130, 190), female_f0=(230, 330), attack=(0.08, 0.16), release=(0.25, 0.4),
                          noise_vowel=([("u", 0.0), ("oh", 0.4), ("u", 1.0)], [(0, 0), (0.25, 1), (0.8, 0.8), (2.0, 0)]),
                          noise_level=0.6)


def crowd_aah():
    return crowd_reaction("aah", 2.2, 70, [("aww", 1)], rise=(0.5, 2), fall=(7, 10), vdur=(1.1, 1.6),
                          onset=((0.0, 0.12), (0.1, 0.25), 0.8), breath=(0.4, 0.65), peak_at=0.15,
                          male_f0=(115, 165), female_f0=(200, 290), attack=(0.08, 0.15), release=(0.25, 0.4),
                          noise_vowel=([("o", 0.0), ("o", 0.5), ("uh", 1.0)], [(0, 0), (0.15, 1), (0.9, 0.7), (2.2, 0)]),
                          noise_level=0.6)


def crowd_boo():
    return crowd_reaction("boo", 3.0, 80, [("boo", 1)], rise=(-0.5, 1.0), fall=(1, 4), vdur=(1.6, 2.6),
                          onset=((0.0, 0.15), (0.1, 0.6), 0.7), breath=(0.45, 0.7), peak_at=0.2,
                          male_f0=(95, 150), female_f0=(180, 260), female=0.3, attack=(0.1, 0.25), release=(0.3, 0.5),
                          noise_vowel=([("u", 0.0), ("u", 0.7), ("oh", 1.0)], [(0, 0), (0.25, 1), (2.2, 0.8), (3.0, 0)]),
                          noise_level=0.55, whistles=1)


def crowd_chant():
    """Stomp-stomp-clap x3 with 'HEY!' answers and a wordless 'oh-oh-oh' chant melody on top."""
    r = rng_for("chant")
    beat = 0.6
    cycles = 3
    dur = cycles * 4 * beat + 1.6
    n = N(dur)
    mix = np.zeros((n, 2))
    bank = clap_bank(r)
    for c in range(cycles):
        t0 = c * 4 * beat
        mix_into(mix, 1.0 * crowd_stomp(r, people=18), N(t0))
        mix_into(mix, 1.0 * crowd_stomp(r, people=18), N(t0 + beat))
        mix_into(mix, 0.55 * crowd_clap(r, bank, people=60), N(t0 + 2 * beat))
    # 'HEY!' shouts on beat 4 of cycles 2 and 3
    voices = np.zeros((n, 2))
    for c in (1, 2):
        for _ in range(30):
            fem = r.random() < 0.4
            base = r.uniform(*((240, 380) if fem else (150, 230)))
            v = shout_voice(r, "hey", r.uniform(0.25, 0.35), base, 1.17 if fem else 1.0, r.uniform(1, 3), r.uniform(2, 4),
                            breath=0.5, attack=0.02, release=0.15)
            mix_into(voices, pan(unit(v) * r.uniform(0.4, 1.0), r.uniform(-0.9, 0.9)), N(c * 4 * beat + 3 * beat + r.uniform(-0.02, 0.04)))
    # sung 'oh' line (wordless), D major-ish: answers the stomps
    line = [(0.0, 0.5, 62), (0.6, 0.5, 62), (1.2, 0.9, 66), (2.4, 0.5, 64), (3.0, 0.5, 62), (3.6, 1.1, 59)]
    sung = np.zeros((n, 2))
    for c in range(1, cycles):
        for _ in range(26):
            fem = r.random() < 0.4
            notes = [(c * 4 * beat + t0 + r.uniform(-0.03, 0.05), d, m - (0 if fem else 12)) for t0, d, m in line]
            v = sung_voice(r, notes, "oh", 1.0, 1.17 if fem else 1.0)
            mix_into(sung, pan(unit(v) * r.uniform(0.3, 0.9), r.uniform(-0.9, 0.9)), 0)
    voices /= np.max(np.abs(voices)) + 1e-9
    sung /= np.max(np.abs(sung)) + 1e-9
    mix = saturate(2.0 * mix / (np.max(np.abs(mix)) + 1e-9), 1.5)
    out = 1.0 * mix + 0.45 * voices + 0.35 * sung
    out = add_reverb(out, arena_ir(), wet=0.45, dry=0.85)[:n]
    out = iir(out, biquad("hp", 45, 0.7))
    return fade(out, 0.0, 0.8)


# =============================================================================================
# Crowd beds (seamless 30 s loops)
# =============================================================================================


def crowd_bed(seed, seconds, talkers, excited):
    """Seamless stereo arena bed. excited in [0, 1]: 0 = between-whistles murmur, 1 = rocking crowd."""
    r = rng_for(seed)
    L, X = N(seconds), N(2.0)
    n = L + X
    mix = np.zeros((n, 2))
    for _ in range(talkers):
        y = babble_talker(r, n, female=r.random() < 0.45, excited=excited * r.uniform(0.5, 1.0))
        dist = r.uniform(0.0, 1.0)
        y = fft_filter(y, lambda f, c=6500.0 - 4000.0 * dist: m_lp(f, c, 1), pad=0.0)
        mix += pan(unit(y) * (0.25 + 0.75 * (1.0 - dist)), r.uniform(-0.95, 0.95))
    mix = seamless_xfade(mix, L, X)
    mix /= rms(mix) + 1e-9
    bank = clap_bank(r)
    claps = np.zeros((L, 2))
    t = 0.0
    rate = 5.0 + 20.0 * excited
    while True:
        t += r.exponential(1.0 / rate)
        if t >= L / SR:
            break
        mix_circular(claps, pan(bank[r.integers(len(bank))] * r.uniform(0.2, 1.0), r.uniform(-0.95, 0.95)), N(t))
    pockets = 3 + int(6 * excited)
    for _ in range(pockets):
        c0 = r.uniform(0.0, L / SR)
        claps += applause(r, L, bank, 4 + int(12 * excited), (c0, c0 + 0.3), (c0 + 1.5, c0 + 3.5 + 3 * excited),
                          (3.6, 4.4), lambda tt: 1.0, circular=True)
    mix += (0.3 + 0.3 * excited) * claps / (rms(claps) + 1e-9)
    # shouts
    shouts = np.zeros((L, 2))
    count = int(4 + 70 * excited)
    for _ in range(count):
        word = ["woo", "yeah", "hey", "ahh", "go"][r.integers(5)]
        fem = r.random() < 0.45
        d = r.uniform(0.5, 1.4)
        v = shout_voice(r, word, d, r.uniform(*((250, 420) if fem else (140, 240))), 1.16 if fem else 1.0,
                        r.uniform(3, 8), r.uniform(2, 5), breath=0.5, attack=r.uniform(0.04, 0.15), release=0.35, tilt_db=0.0)
        dist = r.uniform(0.0, 1.0)
        v = fft_filter(v, lambda f, c=5500.0 - 3000.0 * dist: m_lp(f, c, 1), pad=0.0)
        mix_circular(shouts, pan(unit(v) * (0.3 + 0.7 * (1 - dist)), r.uniform(-0.9, 0.9)), N(r.uniform(0, L / SR)))
    mix += (0.35 + 0.35 * excited) * shouts / (rms(shouts) + 1e-9)
    for _ in range(int(1 + 6 * excited)):
        w = finger_whistle(r, r.uniform(0.4, 0.9))
        mix_circular(mix, pan(0.25 * unitpeak(w), r.uniform(-0.8, 0.8)), N(r.uniform(0, L / SR)))
    if excited > 0.5:
        for _ in range(4):
            h = iir(fan_horn(r, r.uniform(0.3, 0.7)), biquad("lp", 2500, 0.7))
            mix_circular(mix, pan(0.18 * h, r.uniform(-0.8, 0.8)), N(r.uniform(0, L / SR)))
        # vowel-noise 'roar' body that swells and recedes (periodic in L)
        for ch in range(2):
            body = shaped_noise(r, L, lambda f: m_bp(f, 650, 0.6) + 0.6 * m_bp(f, 1200, 0.8) + 0.3 * m_bp(f, 2600, 1.0))
            swell = 0.75 + 0.25 * smooth_random(r, L, 0.25)
            mix[:, ch] += 0.45 * body * swell
    room = np.stack([shaped_noise(r, L, lambda f: m_tilt(f, -3.0, 200.0) * m_lp(f, 500, 2) * m_hp(f, 35, 2))
                     for _ in range(2)], axis=1)
    mix += 0.12 * room
    wet = 0.5 * mix + 0.85 * convolve_circular(mix, arena_ir())
    return iir_circular(wet, biquad("hp", 45, 0.7))


def crowd_ambience():
    return crowd_bed("crowd_amb", 30.0, 60, 0.0)


def crowd_excited():
    return crowd_bed("crowd_exc", 30.0, 70, 1.0)


# =============================================================================================
# Stadium organ
# =============================================================================================

DRAWBARS = ((0.5, 0.75), (1.0, 1.0), (1.5, 0.75), (2.0, 0.8), (3.0, 0.45), (4.0, 0.55), (5.0, 0.2),
            (6.0, 0.3), (8.0, 0.35))


def organ_note(r, midi, dur, vel=1.0, perc=True, t_abs=0.0):
    """Drawbar organ voice (mono pair L/R through a rotary-speaker swirl)."""
    n = N(dur + 0.06)
    t = T(n)
    f = float(midi_hz(midi))
    y = np.zeros(n)
    for h, a in DRAWBARS:
        if f * h < 16000:
            y += a * np.sin(TWO_PI * f * h * t + r.uniform(0, TWO_PI))
    if perc:
        y += 0.9 * np.sin(TWO_PI * f * 3.0 * t) * np.exp(-t / 0.22) + 0.4 * np.sin(TWO_PI * f * 2.0 * t) * np.exp(-t / 0.3)
    y *= env_pts(n, [(0, 0), (0.004, 1), (dur, 1), (dur + 0.04, 0)])
    click = unitpeak(burst(r, n / SR, 0.003, lambda ff: m_hp(ff, 2500, 2))) * 0.35
    y = y + click
    return vel * y


def organ_phrase(r, events, total, bpm, swirl=6.5, drive=1.8):
    """events: [(beat_time, midi_list, beats_len, vel)] -> stereo organ in an arena."""
    spb = 60.0 / bpm
    n = N(total)
    mono = np.zeros(n)
    for bt, notes, ln, vel in events:
        for m in notes:
            mix_into(mono, organ_note(r, m, ln * spb * 0.92, vel, perc=True), N(bt * spb))
    mono = saturate(mono / (np.max(np.abs(mono)) + 1e-9) * 1.2, drive)
    t = T(n)
    lfo = np.sin(TWO_PI * swirl * t)
    # rotary: AM + small doppler (via tiny time-varying delay) with L/R in quadrature
    L = mono * (1.0 + 0.22 * lfo)
    R = mono * (1.0 - 0.22 * lfo)
    idx = np.arange(n) - 0.00025 * SR * (1 + np.sin(TWO_PI * swirl * t + 1.2))
    R = np.interp(idx, np.arange(n), R)
    st = np.stack([L, R], axis=1)
    st = np.stack([iir(st[:, c], biquad("hp", 70, 0.7), biquad("peak", 2500, 1.0, 2.5), biquad("lp", 7500, 0.7))
                   for c in range(2)], axis=1)
    # arena PA: slap from the far end + big hall
    slap = np.zeros_like(st)
    k = N(0.16)
    slap[k:] = st[:-k][:, ::-1] * 0.18
    st = st + slap
    return add_reverb(st, arena_ir(), wet=0.42, dry=1.0)


def chord(root, kind="maj", inv=0):
    iv = {"maj": [0, 4, 7], "min": [0, 3, 7], "7": [0, 4, 7, 10], "dim": [0, 3, 6], "sus": [0, 5, 7],
          "m7": [0, 3, 7, 10], "maj7": [0, 4, 7, 11], "aug": [0, 4, 8]}[kind]
    notes = [root + i for i in iv]
    for _ in range(inv):
        notes = notes[1:] + [notes[0] + 12]
    return notes


def organ_charge():
    """Rising block-chord build (Bb -> C -> D -> Eb -> F, staccato, accelerating) into a held F7
    with a trill, resolving to a big Bb chord. Original."""
    r = rng_for("org_charge")
    bpm = 150
    ev = []
    b = 0.0
    seq = [(58, "maj"), (60, "min"), (62, "min"), (63, "maj"), (65, "maj")]
    for k, (root, kind) in enumerate(seq):
        c = chord(root, kind, 1) + [root - 12]
        ev.append((b, c, 0.45, 0.85 + 0.03 * k))
        b += 1.0 if k < 2 else 0.5
        if k >= 2:
            ev.append((b, c, 0.45, 0.9))
            b += 0.5
    # held F7 with top-note trill
    ev.append((b, [53, 57, 60, 63], 3.0, 1.0))
    for j in range(12):
        ev.append((b + j * 0.25, [72 if j % 2 == 0 else 74], 0.24, 0.8))
    b += 3.0
    ev.append((b, [46, 58, 62, 65, 70], 2.2, 1.0))
    ev.append((b, [74], 2.2, 0.9))
    total = (b + 2.2) * 60.0 / bpm + 2.2
    return organ_phrase(r, ev, total, bpm)


ORGAN_RIFFS = [
    # 1: bluesy chromatic slide-down that lands on a stab (G)
    (132, [(0, [79], 0.5, 0.9), (0.5, [78], 0.5, 0.85), (1, [77], 0.5, 0.85), (1.5, [76], 0.5, 0.85),
           (2, [74], 0.75, 0.9), (3, [70], 0.5, 0.85), (3.5, [71], 0.5, 0.9), (4, [55, 59, 62, 67], 0.5, 1.0),
           (5, [55, 59, 62, 67, 71], 1.6, 1.0)]),
    # 2: bright staccato arpeggio climbing two octaves, big C major hit
    (160, [(0, [60], 0.4, 0.8), (0.5, [64], 0.4, 0.8), (1, [67], 0.4, 0.85), (1.5, [72], 0.4, 0.85),
           (2, [76], 0.4, 0.9), (2.5, [79], 0.4, 0.9), (3, [84], 0.9, 0.95),
           (4, [48, 60, 64, 67, 72], 0.4, 1.0), (4.5, [48, 60, 64, 67, 72], 0.4, 1.0), (5, [48, 60, 64, 67, 72, 76], 2.0, 1.0)]),
    # 3: tense minor riff (D minor) - for the visitors' power play
    (120, [(0, [62, 65], 0.5, 0.9), (0.75, [62, 65], 0.25, 0.8), (1, [69], 0.5, 0.9), (1.5, [68], 0.5, 0.9),
           (2, [69], 0.5, 0.9), (2.5, [72], 0.5, 0.9), (3, [70], 0.5, 0.85), (3.5, [69], 0.5, 0.85),
           (4, [50, 62, 65, 69], 1.8, 1.0)]),
    # 4: syncopated rally hits with a pickup (F major)
    (144, [(0, [60, 65, 69], 0.4, 1.0), (0.75, [60, 65, 69], 0.4, 0.9), (1.5, [62, 67, 70], 0.4, 1.0),
           (2.5, [64, 67, 72], 0.25, 0.9), (2.75, [64, 67, 72], 0.25, 0.9), (3, [65, 69, 72], 0.5, 1.0),
           (3.5, [67, 70, 74], 0.5, 1.0), (4, [53, 65, 69, 72, 77], 1.8, 1.0)]),
]


def organ_riff(i):
    r = rng_for("org_riff%d" % i)
    bpm, ev = ORGAN_RIFFS[i]
    end = max(b + ln for b, _, ln, _ in ev)
    return organ_phrase(r, ev, end * 60.0 / bpm + 2.0, bpm)


def organ_clap():
    """Organ call, crowd answers with claps: (organ 'da da da-da-da', clap clap) x2, then a rising
    tag with three claps and a final organ hit."""
    r = rng_for("org_clap")
    bpm = 132
    spb = 60.0 / bpm
    ev = []
    calls = [
        [(0, [67], 0.5), (1, [67], 0.5), (2, [69], 0.25), (2.5, [71], 0.25), (3, [72], 0.5)],
        [(8, [72], 0.5), (9, [72], 0.5), (10, [71], 0.25), (10.5, [69], 0.25), (11, [67], 0.5)],
        [(16, [64, 67], 0.5), (17, [65, 69], 0.5), (18, [67, 71], 0.5), (19, [69, 72], 0.5)],
    ]
    for ph in calls:
        for bt, notes, ln in ph:
            ev.append((bt, notes + [notes[0] - 12], ln, 0.95))
    ev.append((23, [48, 60, 64, 67, 72], 2.0, 1.0))
    total = 25 * spb + 2.0
    org = organ_phrase(r, ev, total, bpm)
    n = org.shape[0]
    bank = clap_bank(r)
    claps = np.zeros((n, 2))
    for bt in (4, 5, 12, 13, 20, 21, 22):
        mix_into(claps, crowd_clap(r, bank, people=70, jitter=0.04), N(bt * spb))
    claps = add_reverb(claps, arena_ir(), wet=0.5, dry=0.8)[:n]
    return 0.85 * org / (np.max(np.abs(org)) + 1e-9) + 0.8 * claps / (np.max(np.abs(claps)) + 1e-9)
