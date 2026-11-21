"""
ICE RIOT -- sound effects (Sfx/) and interface sounds (UI/), all synthesized.

Each public function returns a float signal (mono (n,) or stereo (n, 2)) before mastering;
Tools/gen_audio.py trims, fades and normalizes it.
"""

import math

import numpy as np

from .dsp import (SR, TWO_PI, N, T, rng_for, dbamp, midi_hz, mix_into, mix_circular, pan, unit, unitpeak,
                  env_exp, env_pts, env_adsr, fade, smooth_random, m_lp, m_hp, m_bp, m_peak, m_tilt, fft_filter,
                  shaped_noise, biquad, iir, iir_circular, svf, osc_sine, osc_saw, osc_pulse, osc_tri, phase_acc,
                  modal, burst, thump, add_reverb, convolve_circular, echo, saturate, compressor, limiter,
                  rink_ir, arena_ir, arena_ir_mono, ir_cached, to_stereo, normalize, pad_to, supersaw, ks_pluck)


# =============================================================================================
# Building blocks
# =============================================================================================


def puck_thock(r, n, hard=1.0, pitch=1.0):
    """Vulcanized-rubber puck hitting something hard: dense, short 'tok'."""
    modes = [(820 * pitch, 1.0, 0.007), (1460 * pitch, 0.65, 0.005), (2380 * pitch, 0.45, 0.0035),
             (3550 * pitch, 0.25, 0.0025)]
    body = modal(n, [(f * r.uniform(0.97, 1.03), a, tau, r.uniform(0, TWO_PI)) for f, a, tau in modes])
    click = unitpeak(burst(r, n / SR, 0.0009 + 0.0006 * (1.0 - hard), lambda f: m_hp(f, 1800, 2) * m_lp(f, 14000, 1)))
    return unitpeak(body) * 0.8 + 0.55 * hard * click


def stick_modes(r, f0=520.0, decay=1.0, bright=1.0):
    """Hollow composite stick shaft: free-free beam flexural modes (ratios 1, 2.76, 5.40, 8.93...)."""
    ratios = [1.0, 2.756, 5.404, 8.933, 13.34]
    amps = [1.0, 0.8, 0.55, 0.35, 0.2]
    taus = [0.07, 0.05, 0.03, 0.02, 0.012]
    out = []
    for k, (q, a, tau) in enumerate(zip(ratios, amps, taus)):
        out.append((f0 * q * r.uniform(0.98, 1.02), a * bright ** k * r.uniform(0.7, 1.2), tau * decay, r.uniform(0, TWO_PI)))
    return out


def metal_tube(r, n, f0, decay=1.0, bright=1.0):
    """Steel goal-frame tube: beam modes with slightly detuned doublets (shimmering 'PING')."""
    ratios = [1.0, 2.756, 5.404, 8.933, 13.34, 18.64]
    amps = [0.35, 1.0, 0.95, 0.7, 0.45, 0.28]
    taus = [0.9, 1.1, 0.8, 0.55, 0.36, 0.22]
    modes = []
    for k, (q, a, tau) in enumerate(zip(ratios, amps, taus)):
        f = f0 * q * r.uniform(0.995, 1.005)
        a = a * bright ** k
        modes.append((f, a, tau * decay, r.uniform(0, TWO_PI)))
        modes.append((f * r.uniform(1.002, 1.009), a * r.uniform(0.4, 0.7), tau * decay * 0.9, r.uniform(0, TWO_PI)))
    return modal(n, modes, attack=0.0002)


def board_modes(r, scale=1.0):
    """Dasher board panel (HDPE over a frame): low hollow modes."""
    table = [(118, 1.0, 0.13), (176, 0.85, 0.1), (247, 0.7, 0.08), (331, 0.55, 0.06), (446, 0.42, 0.05),
             (590, 0.3, 0.04), (780, 0.2, 0.03), (1040, 0.12, 0.022)]
    return [(f * scale * r.uniform(0.97, 1.03), a, tau, r.uniform(0, TWO_PI)) for f, a, tau in table]


def glass_panel_modes(r, scale=1.0, decay=1.0):
    """Rink glass panel (thick tempered/acrylic sheet in a frame)."""
    table = [(74, 1.0, 0.35), (121, 0.8, 0.3), (189, 0.7, 0.24), (268, 0.55, 0.2), (372, 0.42, 0.15),
             (515, 0.3, 0.11), (690, 0.2, 0.08), (1180, 0.12, 0.05), (1730, 0.08, 0.035)]
    return [(f * scale * r.uniform(0.97, 1.03), a, tau * decay, r.uniform(0, TWO_PI)) for f, a, tau in table]


def rattle(r, n, t0, t1, rate, tau, pitch=1.0):
    """Loose hardware / glass clips rattling: decaying train of tiny bright ticks."""
    y = np.zeros(n)
    t = t0
    while t < t1:
        a = math.exp(-(t - t0) / tau) * r.uniform(0.35, 1.0)
        f = r.uniform(1300.0, 3400.0) * pitch
        L = N(0.03)
        tick = modal(L, [(f, 1.0, 0.006), (f * 1.53, 0.6, 0.004), (f * 2.41, 0.35, 0.003)])
        tick = unitpeak(tick) + 0.4 * unitpeak(burst(r, 0.03, 0.0015, lambda ff: m_hp(ff, 2000, 2)))
        mix_into(y, a * tick, N(t))
        t += r.uniform(0.6, 1.4) / rate
    return y


def grains(r, n, t0, t1, rate_fn, fc=(3000, 9000), tau=(0.0006, 0.002), amp_fn=None):
    """Sparse granular ticks (ice chips, gravel, sparks)."""
    y = np.zeros(n)
    dur = n / SR
    rmax = max(rate_fn(tt) for tt in np.linspace(t0, t1, 64)) + 1e-6
    t = t0
    while True:
        t += r.exponential(1.0 / rmax)
        if t >= min(t1, dur):
            break
        if r.random() > rate_fn(t) / rmax:
            continue
        L = N(0.02)
        ev = r.standard_normal(L) * env_exp(L, r.uniform(*tau))
        ev = unitpeak(iir(ev, biquad("bp", r.uniform(*fc), r.uniform(0.8, 2.0))))
        a = r.uniform(0.3, 1.0) * (amp_fn(t) if amp_fn else 1.0)
        mix_into(y, a * ev, N(t))
    return y


def crackles(r, n, rate_fn, big_prob=0.12, circular=False):
    """Poisson fire crackles (rate_fn(t) events/s), small bright snaps plus occasional bigger pops."""
    y = np.zeros(n)
    dur = n / SR
    rmax = max(rate_fn(tt) for tt in np.linspace(0.0, dur, 64)) + 1e-6
    t = 0.0
    while True:
        t += r.exponential(1.0 / rmax)
        if t >= dur:
            break
        if r.random() > rate_fn(t) / rmax:
            continue
        if r.random() < big_prob:
            L, fc, tau, a = N(0.04), r.uniform(500, 1600), r.uniform(0.006, 0.015), r.uniform(0.6, 1.0)
        else:
            L, fc, tau, a = N(0.012), r.uniform(1500, 7000), r.uniform(0.0008, 0.003), min(1.0, r.exponential(0.35))
        ev = r.standard_normal(L) * env_exp(L, tau)
        ev = unitpeak(iir(ev, biquad("bp", fc, r.uniform(0.8, 2.0))))
        (mix_circular if circular else mix_into)(y, a * ev, N(t))
    return y


def sweep_noise(r, n, fc_pts, q=1.0, env=None, mode="bp"):
    """Noise through a time-varying SVF whose cutoff follows (t, hz) points."""
    t = T(n)
    ts, fs = zip(*fc_pts)
    fc = np.interp(t, ts, fs)
    y = unit(svf(r.standard_normal(n), fc, q, mode))
    if env is not None:
        y *= env_pts(n, env)
    return y


def whoosh(r, dur, f0, f1, q=1.2, peak_at=0.6, f_mid=None):
    """Air swish: band-passed noise sweep with a swelling envelope."""
    n = N(dur)
    fm = f_mid if f_mid is not None else 0.5 * (f0 + f1)
    return sweep_noise(r, n, [(0, f0), (dur * peak_at, fm), (dur, f1)], q,
                       env=[(0, 0), (dur * peak_at, 1.0), (dur, 0.0)]) * np.linspace(0.5, 1.0, n)


def ice_carve(r, dur, f_lo, f_hi, grit=1.0, attack=0.012):
    """Blade carving the ice: bright band-limited scrape with chip grain and a faint blade 'zing'."""
    n = N(dur + 0.05)
    t = T(n)
    fc = np.interp(t, [0, 0.04, dur * 0.6, dur], [f_lo, f_hi, f_hi * 0.92, f_lo * 1.1])
    carve = unit(svf(r.standard_normal(n), fc, 1.1, "bp"))
    rough = np.clip(0.75 + 0.35 * smooth_random(r, n, 260.0), 0.15, None)       # scrape roughness
    env = np.interp(t, [0, attack, 0.06, dur * 0.7, dur, dur + 0.05], [0, 1.0, 0.85, 0.55, 0.0, 0.0])
    hiss = unit(fft_filter(r.standard_normal(n), lambda f: m_hp(f, 6500, 2) * m_lp(f, 15000, 1), pad=0.0))
    chips = unitpeak(grains(r, n, 0.0, dur, lambda tt: 160.0 * grit, fc=(4000, 10000)))
    zf = np.interp(t, [0, dur], [r.uniform(2300, 3200), r.uniform(2700, 3800)])
    zing = osc_sine(zf, n) * 0.5 + 0.2 * osc_sine(2.01 * zf, n)
    y = (carve * rough + 0.45 * hiss * rough + 0.06 * zing) * env + 0.35 * grit * chips * env
    bite = thump(n, 260, 120, 0.006, 0.018)                      # blade biting into the ice
    return y + 0.5 * bite


def body_thump(r, n, f0=130.0, f1=52.0, tau=0.07, crunch=0.5):
    """Padded body impact: pitch-dropping low thud + pad shell crunch + cloth slap."""
    th = thump(n, f0, f1, 0.025, tau)
    whump = unitpeak(burst(r, n / SR, tau * 0.6, lambda f: m_bp(f, 260, 0.8), attack=0.002))
    cr = unitpeak(burst(r, n / SR, 0.03, lambda f: m_bp(f, 1300, 0.7), attack=0.001))
    cr *= np.clip(0.6 + 0.6 * smooth_random(r, n, 400.0), 0.0, None)
    slap = unitpeak(burst(r, n / SR, 0.006, lambda f: m_bp(f, 2600, 0.9)))
    return 1.0 * th + 0.45 * whump + crunch * 0.35 * cr + 0.25 * slap


# =============================================================================================
# Skating
# =============================================================================================


def sfx_skate_stride(i):
    r = rng_for("stride%d" % i)
    dur = (0.26, 0.3, 0.23, 0.33, 0.28, 0.25)[i]
    lo = (2200, 2500, 2000, 2700, 2300, 2600)[i]
    hi = (5200, 5800, 4800, 6200, 5500, 6000)[i]
    y = ice_carve(r, dur, lo, hi, grit=(1.0, 0.8, 1.2, 0.9, 1.1, 0.85)[i], attack=(0.012, 0.016, 0.01, 0.02, 0.014, 0.011)[i])
    return add_reverb(y, rink_ir(), wet=0.1)[:N(dur + 0.08)]


def sfx_skate_stop(i):
    """Hockey stop: blades turned sideways shaving the ice: a big 'KSSHHHH' spray."""
    r = rng_for("stop%d" % i)
    dur = (0.62, 0.72, 0.55)[i]
    n = N(dur + 0.35)
    t = T(n)
    fc = np.interp(t, [0, 0.03, 0.2, dur, dur + 0.3], [3000, 6500, 5200, 3800, 3000]) * (1.0, 0.92, 1.08)[i]
    spray = unit(svf(r.standard_normal(n), fc, 0.55, "bp"))
    hiss = unit(fft_filter(r.standard_normal(n), lambda f: m_hp(f, 5000, 2), pad=0.0))
    chatter = 1.0 + 0.35 * np.sin(TWO_PI * r.uniform(28, 40) * t) * np.exp(-t / 0.25)   # blade chatter
    rough = np.clip(0.8 + 0.3 * smooth_random(r, n, 180.0), 0.2, None)
    env = np.interp(t, [0, 0.015, 0.08, dur * 0.75, dur, dur + 0.3], [0, 1.0, 0.92, 0.65, 0.18, 0.0])
    chips = unitpeak(grains(r, n, 0.0, dur + 0.25, lambda tt: 420.0 * math.exp(-tt / 0.4), fc=(3500, 11000)))
    rumble = unit(fft_filter(r.standard_normal(n), lambda f: m_bp(f, 220, 0.9), pad=0.0)) * np.exp(-t / 0.18)
    y = (spray * chatter * rough + 0.6 * hiss * rough) * env + 0.45 * chips + 0.25 * rumble
    y += 0.4 * thump(n, 200, 90, 0.01, 0.04)
    y = saturate(0.7 * unitpeak(y), 1.3)
    return add_reverb(y, rink_ir(), wet=0.14)[:n]


def sfx_skate_turbo():
    """Turbo burst: two hard strides + rising whoosh + power hum."""
    r = rng_for("turbo")
    n = N(1.1)
    t = T(n)
    y = np.zeros(n)
    mix_into(y, 0.9 * ice_carve(r, 0.22, 2600, 6200, grit=1.2, attack=0.006), 0)
    mix_into(y, 0.8 * ice_carve(r, 0.25, 2800, 6600, grit=1.2, attack=0.006), N(0.13))
    air = sweep_noise(r, n, [(0, 400), (0.35, 2600), (0.8, 4200), (1.1, 3000)], 0.9,
                      env=[(0, 0), (0.08, 0.4), (0.3, 1.0), (0.7, 0.5), (1.1, 0)])
    hf = np.interp(t, [0, 0.35, 1.1], [70, 120, 150])
    hum = saturate(osc_saw(hf, n) * 0.6 + osc_saw(hf * 1.007, n) * 0.6, 2.0)
    hum = iir(hum, biquad("lp", 900, 0.9)) * np.interp(t, [0, 0.05, 0.3, 1.0, 1.1], [0, 0.6, 1.0, 0.2, 0])
    zap = osc_sine(np.interp(t, [0, 0.4], [600, 2400]), n) * np.interp(t, [0, 0.05, 0.35, 0.5], [0, 0.4, 0.15, 0])
    y = y + 0.55 * air + 0.22 * hum + 0.06 * zap
    return add_reverb(y, rink_ir(), wet=0.12)[:n]


# =============================================================================================
# Stick / puck
# =============================================================================================


def stick_tap(r, n, hard=1.0):
    blade = unitpeak(modal(n, stick_modes(r, r.uniform(560, 700), decay=0.4, bright=1.1)))
    return 0.7 * puck_thock(r, n, hard, r.uniform(0.95, 1.08)) + 0.45 * blade


def sfx_stick_handle(i):
    r = rng_for("handle%d" % i)
    n = N(0.32)
    y = np.zeros(n)
    hits = [[(0.0, 0.8)], [(0.0, 0.75), (0.105, 0.6)], [(0.0, 0.6), (0.085, 0.8)], [(0.0, 0.7), (0.07, 0.45), (0.15, 0.6)]][i]
    for t0, a in hits:
        L = N(0.15)
        tap = stick_tap(r, L, hard=r.uniform(0.6, 0.9)) * a
        scrape = unit(fft_filter(r.standard_normal(L), lambda f: m_bp(f, 3200, 0.8), pad=0.0)) * env_exp(L, 0.025, 0.003)
        mix_into(y, tap + 0.08 * scrape, N(t0))
    y = iir(y, biquad("hp", 180, 0.7))
    return add_reverb(y, rink_ir(), wet=0.08)[:n]


def shot_core(r, n, power=1.0, pitch=1.0):
    """Stick-on-puck impact: crack + shaft flex ring + puck thock + body."""
    crack = unitpeak(burst(r, n / SR, 0.0025 * power, lambda f: m_hp(f, 700, 2) * m_lp(f, 16000, 1)))
    thwack = unitpeak(burst(r, n / SR, 0.009 * power, lambda f: m_bp(f, 1500 * pitch, 0.7)))
    shaft = unitpeak(modal(n, stick_modes(r, 180 * pitch, decay=1.6 * power, bright=0.9)))
    body = thump(n, 220 * pitch, 80 * pitch, 0.012, 0.04 * power)
    puck = puck_thock(r, n, 1.0, pitch)
    return 0.9 * crack + 0.6 * thwack + 0.35 * shaft + 0.65 * body + 0.5 * puck


def sfx_shot_wrist(i):
    r = rng_for("wrist%d" % i)
    pre = (0.06, 0.07, 0.05)[i]
    n = N(0.75)
    y = np.zeros(n)
    sw = whoosh(r, pre + 0.02, 700, 2600, q=1.2, peak_at=0.85)
    mix_into(y, 0.35 * sw, 0)
    L = n - N(pre)
    core = shot_core(r, L, power=0.7, pitch=(1.0, 1.08, 0.94)[i])
    blade_drag = unit(fft_filter(r.standard_normal(L), lambda f: m_bp(f, 4200, 0.8), pad=0.0)) * env_exp(L, 0.03, 0.002)
    tail = sweep_noise(r, L, [(0, 2600), (0.3, 900)], 1.4, env=[(0, 0), (0.01, 0.6), (0.12, 0.25), (0.35, 0)])
    mix_into(y, 0.9 * core + 0.2 * blade_drag + 0.25 * tail, N(pre))
    y = saturate(0.8 * unitpeak(y), 1.8)
    return add_reverb(y, rink_ir(), wet=0.14)[:n]


def slap_layers(r, n, scale=1.0, pitch=1.0):
    """The big slap shot: stick slams the ice (sub thwack), puck crack, shaft twang, ice spray."""
    t = T(n)
    ice_hit = thump(n, 150 * pitch, 42, 0.02, 0.11 * scale)
    ice_crack = unitpeak(burst(r, n / SR, 0.004, lambda f: m_hp(f, 300, 1) * m_lp(f, 12000, 1)))
    core = shot_core(r, n, power=1.3 * scale, pitch=pitch)
    snap = unitpeak(burst(r, n / SR, 0.0015, lambda f: m_hp(f, 2500, 2)))
    twang = unitpeak(modal(n, stick_modes(r, 150 * pitch, decay=3.0, bright=0.85)))
    twang *= 1.0 + 0.4 * np.sin(TWO_PI * 18 * t)
    spray = unit(fft_filter(r.standard_normal(n), lambda f: m_bp(f, 6000, 0.6), pad=0.0)) * env_exp(n, 0.07, 0.003)
    chips = unitpeak(grains(r, n, 0.0, 0.25, lambda tt: 500 * math.exp(-tt / 0.08), fc=(4000, 11000)))
    flight = sweep_noise(r, n, [(0, 3500), (0.15, 1800), (0.5, 700)], 1.3,
                         env=[(0, 0), (0.01, 0.5), (0.1, 0.35), (0.5, 0)])
    return (1.0 * ice_hit + 0.55 * ice_crack + 0.9 * core + 0.6 * snap + 0.3 * twang + 0.22 * spray + 0.25 * chips
            + 0.22 * flight)


def sfx_shot_slap(i):
    r = rng_for("slap%d" % i)
    pre = 0.09
    n = N(1.6)
    y = np.zeros(n)
    mix_into(y, 0.3 * whoosh(r, pre + 0.01, 400, 1800, q=1.0, peak_at=0.9), 0)
    mix_into(y, slap_layers(r, n - N(pre), 1.0, (1.0, 1.06, 0.93)[i]), N(pre))
    y = saturate(1.1 * unitpeak(y), 2.2)
    y = compressor(y, -14, 3.0, 0.001, 0.08)
    y = add_reverb(y, rink_ir(), wet=0.12)
    return add_reverb(y, arena_ir_mono(), wet=0.22)[:n]


def sfx_shot_power():
    """Arcade power shot: massive slap + sub boom + fiery whoosh trailing away + crackles."""
    r = rng_for("powershot")
    pre = 0.1
    n = N(2.6)
    t = T(n)
    y = np.zeros(n)
    mix_into(y, 0.35 * whoosh(r, pre + 0.02, 300, 2400, q=0.9, peak_at=0.9), 0)
    L = n - N(pre)
    tl = T(L)
    slap = slap_layers(r, L, 1.3, 0.92)
    boom = thump(L, 95, 28, 0.06, 0.45)
    fire_cut = np.interp(tl, [0, 0.05, 0.4, 1.2, 2.4], [6000, 8000, 3500, 1200, 500])
    fire = unit(svf(r.standard_normal(L), fire_cut, 0.7, "lp")) * np.interp(tl, [0, 0.02, 0.25, 1.0, 2.4], [0, 1, 0.8, 0.35, 0])
    fire *= 0.8 + 0.25 * smooth_random(r, L, 18.0)
    roar = unit(fft_filter(r.standard_normal(L), lambda f: m_tilt(f, -4, 200) * m_lp(f, 700, 2) * m_hp(f, 50, 2), pad=0.0))
    roar *= np.interp(tl, [0, 0.05, 0.5, 2.0], [0, 1, 0.5, 0])
    dop = np.interp(tl, [0, 0.12, 1.4], [5200, 2600, 500])
    streak = unit(svf(r.standard_normal(L), dop, 3.0, "bp")) * np.interp(tl, [0, 0.03, 0.4, 1.4], [0, 1, 0.4, 0])
    crk = unitpeak(crackles(r, L, lambda tt: 70.0 * math.exp(-tt / 0.6), big_prob=0.2))
    zap = saturate(osc_saw(np.interp(tl, [0, 0.6], [900, 110]), L) * np.interp(tl, [0, 0.01, 0.4, 0.6], [0, 1, 0.3, 0]), 3.0)
    zap = iir(zap, biquad("lp", 3000, 0.7))
    core = 1.0 * slap + 0.9 * boom + 0.35 * fire + 0.35 * roar + 0.25 * streak + 0.3 * crk + 0.12 * zap
    mix_into(y, core, N(pre))
    y = saturate(1.2 * unitpeak(y), 2.4)
    y = compressor(y, -16, 3.0, 0.001, 0.12)
    return add_reverb(y, arena_ir_mono(), wet=0.25)[:n]


def sfx_shot_charge():
    """Seamless 2 s 'charging' loop that always sounds like it is rising: Shepard-Risset glissando
    (one octave per loop, phase-matched so the wrap is sample-continuous) + electric fizz."""
    r = rng_for("charge")
    L = N(2.0)
    t = T(L)
    y = np.zeros(L)
    f_base = 55.0
    octaves = 8
    center, width = math.log2(440.0), 1.35
    for layer, (mult, lvl) in enumerate(((1.0, 1.0), (1.5, 0.45))):
        ph = 0.0
        for k in range(octaves):
            f = f_base * mult * 2.0 ** (k + t / (L / SR))
            cyc = phase_acc(f, L) + ph
            acc_end = cyc[-1] + f[-1] / SR - ph           # phase advanced over the whole loop
            lf = np.log2(f)
            amp = np.exp(-0.5 * ((lf - center) / width) ** 2)
            tone = np.sin(TWO_PI * cyc) + 0.35 * np.sin(2 * TWO_PI * cyc) + 0.18 * np.sin(3 * TWO_PI * cyc)
            y += lvl * amp * tone
            ph = (ph + acc_end) % 1.0                     # next octave starts where this one ends
    trem = 1.0 + 0.25 * np.sin(TWO_PI * 16.0 * t)        # 32 whole cycles per loop
    fizz = shaped_noise(r, L, lambda f: m_bp(f, 5000, 0.8)) * np.clip(0.5 + 0.5 * smooth_random(r, L, 40.0), 0, None)
    hum = np.sin(TWO_PI * 60.0 * t) + 0.5 * np.sin(TWO_PI * 120.0 * t)  # 120 / 240 cycles per loop
    y = unitpeak(y) * trem + 0.08 * fizz + 0.06 * hum
    y = saturate(0.9 * y, 1.6)
    return y + 0.15 * convolve_circular(y, rink_ir()[:N(0.6)])


def sfx_pass(i):
    r = rng_for("pass%d" % i)
    n = N(0.55)
    y = np.zeros(n)
    pre = 0.04
    mix_into(y, 0.4 * whoosh(r, pre + 0.015, 900, 3000, q=1.4, peak_at=0.85), 0)
    L = n - N(pre)
    tap = stick_tap(r, L, hard=(1.0, 0.85, 1.1)[i])
    slide = unit(fft_filter(r.standard_normal(L), lambda f: m_bp(f, 2800, 0.7), pad=0.0))
    slide *= env_pts(L, [(0, 0), (0.01, 0.5), (0.1, 0.3), (0.45, 0)]) * np.clip(0.8 + 0.3 * smooth_random(r, L, 90.0), 0, None)
    body = thump(L, 300, 140, 0.006, 0.02)
    mix_into(y, 1.0 * tap + 0.18 * slide + 0.4 * body, N(pre))
    y = saturate(unitpeak(y), 1.5)
    return add_reverb(y, rink_ir(), wet=0.1)[:n]


def sfx_puck_post(i, f0=None, decay=1.0):
    r = rng_for("post%d" % i)
    n = N(2.2)
    f0 = f0 or (395.0, 372.0)[i]
    ring = metal_tube(r, n, f0, decay=decay, bright=1.0)
    hit = puck_thock(r, n, 1.0, 1.05)
    clank = unitpeak(burst(r, 2.2, 0.0012, lambda f: m_hp(f, 2500, 2)))
    frame = thump(n, 240, 140, 0.008, 0.05) + 0.4 * modal(n, [(152, 1.0, 0.2), (231, 0.6, 0.15)])
    y = 0.95 * unitpeak(ring) + 0.4 * hit + 0.5 * clank + 0.35 * frame
    y = saturate(0.9 * y, 1.3)
    y = add_reverb(y, rink_ir(), wet=0.12)
    return add_reverb(y, arena_ir_mono(), wet=0.14)[:n]


def sfx_puck_crossbar():
    return sfx_puck_post(2, f0=520.0, decay=0.85)


def sfx_puck_boards(i):
    r = rng_for("boards%d" % i)
    n = N(0.8)
    sc = (1.0, 0.9, 1.1, 0.95)[i]
    th = thump(n, 220 * sc, 85 * sc, 0.01, 0.06)
    panel = unitpeak(modal(n, board_modes(r, sc)))
    slap = unitpeak(burst(r, 0.8, 0.004, lambda f: m_bp(f, 1400, 0.6)))
    hit = puck_thock(r, n, 0.9, 0.95)
    rat = unitpeak(rattle(r, n, 0.02, 0.35, rate=24, tau=0.08))
    y = 1.0 * th + 0.7 * panel + 0.4 * slap + 0.45 * hit + 0.1 * rat
    y = saturate(0.9 * unitpeak(y), 1.6)
    return add_reverb(y, rink_ir(), wet=0.16)[:n]


def sfx_puck_glass(i):
    r = rng_for("glass%d" % i)
    n = N(1.2)
    t = T(n)
    panel = unitpeak(modal(n, glass_panel_modes(r, (1.3, 1.45)[i], decay=0.45)))
    panel *= 1.0 + 0.25 * np.sin(TWO_PI * r.uniform(5, 8) * t) * np.exp(-t / 0.25)
    thunk = thump(n, 210, 110, 0.008, 0.04) + 0.5 * unitpeak(burst(r, 1.2, 0.012, lambda f: m_bp(f, 800, 0.8)))
    hit = puck_thock(r, n, 0.8, 0.9)
    ring = modal(n, [(r.uniform(2100, 2600), 0.6, 0.06), (r.uniform(3300, 3900), 0.4, 0.04)])
    rat = unitpeak(rattle(r, n, 0.03, 0.7, rate=30, tau=0.18, pitch=0.9))
    y = 0.6 * panel + 1.0 * thunk + 0.55 * hit + 0.15 * ring + 0.25 * rat
    y = saturate(0.9 * unitpeak(y), 1.4)
    return add_reverb(y, rink_ir(), wet=0.18)[:n]


def puck_ice_hit(r, n, a=1.0):
    slap = unitpeak(burst(r, n / SR, 0.004, lambda f: m_bp(f, 2500, 0.6) * m_hp(f, 600, 1)))
    thd = thump(n, 240, 110, 0.006, 0.02)
    tick = puck_thock(r, n, 0.7, 1.1)
    return a * (0.8 * slap + 0.6 * thd + 0.4 * tick)


def sfx_puck_ice(i):
    r = rng_for("puckice%d" % i)
    n = N(0.55)
    y = np.zeros(n)
    bounces = [[(0.0, 1.0)], [(0.0, 1.0), (0.075, 0.45)], [(0.0, 0.9), (0.055, 0.4), (0.1, 0.2)]][i]
    for t0, a in bounces:
        mix_into(y, puck_ice_hit(r, N(0.2), a), N(t0))
    slide = unit(fft_filter(r.standard_normal(n), lambda f: m_bp(f, 3000, 0.7), pad=0.0))
    y += 0.12 * slide * env_pts(n, [(0, 0), (0.02, 1), (0.15, 0.5), (0.5, 0)])
    y = saturate(unitpeak(y), 1.4)
    return add_reverb(y, rink_ir(), wet=0.12)[:n]


def sfx_net_ripple():
    r = rng_for("net")
    n = N(1.0)
    t = T(n)
    whump = unitpeak(burst(r, 1.0, 0.05, lambda f: m_bp(f, 300, 0.8), attack=0.004))
    th = thump(n, 160, 70, 0.02, 0.06)
    mesh = unit(fft_filter(r.standard_normal(n), lambda f: m_bp(f, 4500, 0.9), pad=0.0))
    am = np.zeros(n)
    tg = 0.004
    while tg < 0.55:
        mix_into(am, env_exp(N(0.02), r.uniform(0.002, 0.006)) * r.uniform(0.3, 1.0) * (1 - tg / 0.6) ** 1.5, N(tg))
        tg += r.uniform(0.006, 0.022)
    swish = sweep_noise(r, n, [(0, 2500), (0.08, 5000), (0.3, 3000)], 0.8, env=[(0, 0), (0.015, 1), (0.1, 0.4), (0.35, 0)])
    frame = modal(n, [(610, 1.0, 0.12), (1650, 0.6, 0.09), (3200, 0.3, 0.05)]) * 0.15
    drop = np.zeros(n)
    mix_into(drop, puck_ice_hit(r, N(0.2), 0.35), N(0.32))
    y = 0.8 * whump + 0.6 * th + 0.5 * mesh * am + 0.4 * swish + frame + drop
    return add_reverb(y, rink_ir(), wet=0.12)[:n]


# =============================================================================================
# Bodies
# =============================================================================================


def sfx_check(i):
    r = rng_for("check%d" % i)
    n = N(0.8)
    sc = (1.0, 0.92, 1.08, 0.97)[i]
    y = body_thump(r, n, 140 * sc, 50 * sc, 0.085, crunch=(0.6, 0.8, 0.5, 0.7)[i])
    y += 0.3 * unitpeak(burst(r, 0.8, 0.003, lambda f: m_hp(f, 1500, 1)))
    sk = np.zeros(n)
    mix_into(sk, 0.3 * ice_carve(r, 0.25, 2500, 5000, grit=1.3, attack=0.01), N(0.03))
    y = saturate(1.0 * unitpeak(y), 2.4) + sk
    return add_reverb(y, rink_ir(), wet=0.14)[:n]


def glass_shake(r, n, t0=0.0, decay=1.0, amount=1.0):
    t = T(n)
    panel = unitpeak(modal(n, glass_panel_modes(r, 0.9, decay=1.6 * decay)))
    panel *= 1.0 + 0.5 * np.sin(TWO_PI * r.uniform(4.0, 6.0) * t)
    rat = unitpeak(rattle(r, n, 0.02, 1.2 * decay, rate=34, tau=0.35 * decay, pitch=0.85))
    y = 0.7 * panel + 0.45 * rat
    out = np.zeros(n)
    mix_into(out, amount * y, N(t0))
    return out


def sfx_check_power():
    r = rng_for("checkpower")
    n = N(2.6)
    y = np.zeros(n)
    hit = body_thump(r, n, 120, 38, 0.16, crunch=1.0)
    boom = thump(n, 85, 26, 0.05, 0.35)
    crunch = unitpeak(grains(r, n, 0.0, 0.18, lambda tt: 900, fc=(600, 3000), tau=(0.002, 0.006)))
    boards = thump(n, 170, 60, 0.012, 0.12) + 0.6 * unitpeak(modal(n, board_modes(r, 0.8)))
    crack = unitpeak(burst(r, 2.6, 0.005, lambda f: m_hp(f, 400, 1)))
    y = 1.0 * hit + 0.9 * boom + 0.35 * crunch + 0.6 * boards + 0.4 * crack
    y = saturate(1.3 * unitpeak(y), 2.8)
    y += 0.55 * glass_shake(r, n, 0.015, decay=1.4)
    y = compressor(y, -16, 3.0, 0.001, 0.1)
    y = add_reverb(y, rink_ir(), wet=0.12)
    return add_reverb(y, arena_ir_mono(), wet=0.22)[:n]


def sfx_boards_slam(i):
    r = rng_for("slam%d" % i)
    n = N(1.9)
    sc = (1.0, 0.9)[i]
    y = body_thump(r, n, 120 * sc, 45, 0.1, crunch=0.6)
    y += 0.9 * thump(n, 180 * sc, 55, 0.012, 0.14) + 0.7 * unitpeak(modal(n, board_modes(r, 0.85 * sc)))
    y = saturate(1.1 * unitpeak(y), 2.2)
    y += 0.6 * glass_shake(r, n, 0.01, decay=1.1)
    return add_reverb(y, rink_ir(), wet=0.16)[:n]


def sfx_fall_ice(i):
    r = rng_for("fall%d" % i)
    dur = (1.2, 1.4, 1.0)[i]
    n = N(dur + 0.2)
    t = T(n)
    y = np.zeros(n)
    for t0, a in [(0.0, 1.0), (0.05, 0.7), (0.11, 0.45), (0.18 + 0.03 * i, 0.3)]:
        m = n - N(t0)
        hit = body_thump(r, m, 120 * r.uniform(0.9, 1.1), 55, 0.05, crunch=0.4)
        mix_into(y, a * hit, N(t0))
    helmet = modal(N(0.1), [(r.uniform(900, 1200), 1.0, 0.012), (r.uniform(2100, 2600), 0.6, 0.008)])
    mix_into(y, 0.25 * helmet, N(0.09))
    slide = unit(fft_filter(r.standard_normal(n), lambda f: m_bp(f, 1900, 0.6) + 0.5 * m_bp(f, 5000, 0.8), pad=0.0))
    slide *= np.clip(0.75 + 0.35 * smooth_random(r, n, 60.0), 0, None)
    slide *= np.interp(t, [0, 0.06, 0.2, dur * 0.8, dur], [0, 0.6, 0.55, 0.15, 0])
    y = saturate(0.9 * unitpeak(y), 1.8) + 0.3 * slide
    return add_reverb(y, rink_ir(), wet=0.14)[:n]


def sfx_stick_clack(i):
    r = rng_for("clack%d" % i)
    n = N(0.5)
    y = np.zeros(n)
    hits = [[(0.0, 1.0)], [(0.0, 0.85), (0.065, 1.0)], [(0.0, 0.5), (0.11, 1.0)]][i]
    for t0, a in hits:
        L = N(0.3)
        c = unitpeak(modal(L, stick_modes(r, r.uniform(620, 780), decay=0.6, bright=1.15)))
        c += 0.6 * unitpeak(modal(L, stick_modes(r, r.uniform(500, 600), decay=0.5, bright=1.1)))
        c += 0.7 * unitpeak(burst(r, 0.3, 0.0015, lambda f: m_hp(f, 1500, 2)))
        mix_into(y, a * c, N(t0))
    if i == 2:
        mix_into(y, 0.3 * sweep_noise(r, N(0.12), [(0, 2000), (0.12, 3500)], 1.0, env=[(0, 0), (0.05, 1), (0.12, 0)]), 0)
    y = saturate(0.9 * unitpeak(y), 1.5)
    return add_reverb(y, rink_ir(), wet=0.12)[:n]


# =============================================================================================
# Goalie
# =============================================================================================


def sfx_save_pad(i):
    r = rng_for("pad%d" % i)
    n = N(0.6)
    sc = (1.0, 0.9, 1.1)[i]
    th = thump(n, 190 * sc, 85, 0.012, 0.045)
    foam = unitpeak(burst(r, 0.6, 0.025, lambda f: m_bp(f, 750 * sc, 0.6), attack=0.0015))
    leather = unitpeak(burst(r, 0.6, 0.005, lambda f: m_bp(f, 2200, 0.8)))
    hit = iir(puck_thock(r, n, 0.8, 0.9), biquad("lp", 3500, 0.7))
    y = 1.0 * th + 0.8 * foam + 0.35 * leather + 0.35 * hit
    reb = np.zeros(n)
    mix_into(reb, puck_ice_hit(r, N(0.2), 0.25), N(0.2 + 0.04 * i))
    y = saturate(0.9 * unitpeak(y), 1.8) + reb
    return add_reverb(y, rink_ir(), wet=0.12)[:n]


def sfx_save_glove():
    r = rng_for("glove")
    n = N(0.6)
    pop = unitpeak(burst(r, 0.6, 0.007, lambda f: m_bp(f, 1500, 0.6) + 0.4 * m_bp(f, 3500, 1.0), attack=0.0004))
    th = thump(n, 210, 95, 0.01, 0.04)
    pocket = unitpeak(burst(r, 0.6, 0.03, lambda f: m_lp(f, 500, 2), attack=0.001))
    creak = np.zeros(n)
    cr = osc_saw(np.interp(T(N(0.12)), [0, 0.12], [140, 95]), N(0.12)) * env_pts(N(0.12), [(0, 0), (0.02, 1), (0.12, 0)])
    mix_into(creak, unitpeak(iir(cr, biquad("bp", 1200, 1.0))), N(0.07))
    y = 1.0 * pop + 0.9 * th + 0.5 * pocket + 0.12 * creak
    y = saturate(unitpeak(y), 1.8)
    return add_reverb(y, rink_ir(), wet=0.1)[:n]


def sfx_save_blocker():
    r = rng_for("blocker")
    n = N(0.7)
    tok = unitpeak(modal(n, [(420, 1.0, 0.02), (980, 0.8, 0.015), (1850, 0.5, 0.01), (3100, 0.3, 0.006)]))
    click = unitpeak(burst(r, 0.7, 0.0015, lambda f: m_hp(f, 1800, 2)))
    th = thump(n, 230, 110, 0.008, 0.03)
    foam = unitpeak(burst(r, 0.7, 0.015, lambda f: m_bp(f, 900, 0.7)))
    defl = np.zeros(n)
    mix_into(defl, whoosh(r, 0.25, 2800, 900, q=1.5, peak_at=0.15), N(0.02))
    y = 0.8 * tok + 0.5 * click + 0.7 * th + 0.4 * foam + 0.2 * defl
    y = saturate(unitpeak(y), 1.6)
    return add_reverb(y, rink_ir(), wet=0.12)[:n]


def fm_bell(midi, dur, index=2.5, ratio=3.5, tau=0.35):
    n = N(dur)
    t = T(n)
    f = float(midi_hz(midi))
    I = index * np.exp(-t / (tau * 0.5))
    return np.sin(TWO_PI * f * t + I * np.sin(TWO_PI * f * ratio * t)) * env_exp(n, tau, 0.001)


def sfx_save_power():
    """'Brick wall' power save: deep stone impact + gravel crunch, then a magic shimmer swell."""
    r = rng_for("powersave")
    n = N(2.6)
    t = T(n)
    stone = thump(n, 110, 30, 0.03, 0.3) + 0.7 * thump(n, 260, 120, 0.006, 0.05)
    knock = unitpeak(modal(n, [(180, 1.0, 0.08), (310, 0.8, 0.06), (520, 0.5, 0.04), (770, 0.3, 0.03)]))
    gravel = unitpeak(grains(r, n, 0.0, 0.45, lambda tt: 700 * math.exp(-tt / 0.12), fc=(500, 3000), tau=(0.001, 0.005)))
    crack = unitpeak(burst(r, 2.6, 0.006, lambda f: m_lp(f, 5000, 1) * m_hp(f, 200, 1)))
    hit = saturate(1.0 * stone + 0.6 * knock + 0.45 * gravel + 0.45 * crack, 2.0)
    shimmer = np.zeros(n)
    for k, m in enumerate([88, 92, 95, 100, 104, 107]):          # E6 G#6 B6 E7 G#7 B7
        mix_into(shimmer, (0.6 - 0.05 * k) * fm_bell(m, 1.6, index=1.5, ratio=2.0, tau=0.6), N(0.08 + 0.06 * k))
    sparkle = unitpeak(grains(r, n, 0.08, 1.6, lambda tt: 40, fc=(5000, 12000), tau=(0.003, 0.01)))
    swell = sweep_noise(r, n, [(0, 1500), (0.9, 9000)], 2.0, env=[(0, 0), (0.1, 0.0), (0.6, 0.6), (1.4, 0)])
    magic = unitpeak(shimmer) + 0.25 * sparkle + 0.15 * swell
    magic = echo(magic, 0.13, 0.35, 0.3, repeats=4, lp_hz=8000, hp_hz=800)[:n]
    y = 1.0 * unitpeak(hit) + 0.32 * magic
    return add_reverb(y, arena_ir_mono(), wet=0.22)[:n]


# =============================================================================================
# Officials, horns
# =============================================================================================


def whistle(r, hold, double=False):
    n = N(hold + 0.08)
    t = T(n)
    rate = 32.0 * (1.0 + 0.05 * smooth_random(r, n, 3.0))
    ph = phase_acc(rate, n)
    f0 = 3050.0 * (1.0 - 0.05 * np.exp(-t / 0.03)) * (1.0 + 0.045 * np.sin(TWO_PI * ph))
    tone = osc_sine(f0, n) + 0.14 * osc_sine(2 * f0, n) + 0.04 * osc_sine(3 * f0, n)
    am = 1.0 - 0.45 * (0.5 + 0.5 * np.sin(TWO_PI * ph + 0.8))
    breath = unit(fft_filter(r.standard_normal(n), lambda f: m_bp(f, 3100, 1.5), pad=0.0))
    env = env_pts(n, [(0, 0), (0.015, 0.9), (hold * 0.6, 1.0), (hold, 0.92), (hold + 0.04, 0)])
    return (tone * am + 0.13 * breath * (0.6 + 0.4 * am)) * env


def sfx_whistle_short():
    r = rng_for("whistle_s")
    y = whistle(r, 0.32)
    return add_reverb(y, arena_ir_mono(), wet=0.25)[:N(0.9)]


def sfx_whistle_long():
    r = rng_for("whistle_l")
    n = N(1.8)
    y = np.zeros(n)
    mix_into(y, 0.85 * whistle(r, 0.16), 0)
    mix_into(y, whistle(r, 0.95), N(0.24))
    return add_reverb(y, arena_ir_mono(), wet=0.25)[:n]


def horn_voice(r, f, n, hold, pw=0.38):
    """One air-horn 'trumpet': pressure-build pitch scoop + flutter, raspy pulse+saw source."""
    t = T(n)
    scoop = 1.0 - 0.07 * np.exp(-t / 0.07)
    flutter = 1.0 + 0.0025 * smooth_random(r, n, 7.0)
    ff = f * scoop * flutter
    y = 0.6 * osc_pulse(ff, n, pw, r.random()) + 0.5 * osc_saw(ff * 1.002, n, r.random())
    return y


def sfx_goal_horn():
    """Deep arena goal horn (stereo): a bank of detuned air horns on a low F# major chord, sub
    rumble, honk resonances, wall slap-back and a long arena tail."""
    r = rng_for("goalhorn")
    hold = 3.4
    n = N(hold + 0.5)
    t = T(n)
    out = np.zeros((n, 2))
    notes = [(92.5, 1.0), (116.54, 0.75), (138.59, 0.8), (185.0, 0.35)]      # F#2 A#2 C#3 F#3
    for f, lvl in notes:
        for k in range(3):
            v = horn_voice(r, f * 2.0 ** (r.uniform(-9, 9) / 1200.0), n, hold)
            out += pan(lvl * v, r.uniform(-0.7, 0.7))
    sub = osc_sine(46.25 * (1.0 - 0.07 * np.exp(-t / 0.07)), n) + 0.4 * osc_sine(92.5, n)
    out += pan(1.4 * sub, 0.0)
    out = np.stack([iir(out[:, c], biquad("hp", 35, 0.7), biquad("peak", 420, 1.1, 6.0), biquad("peak", 1150, 1.4, 7.0),
                        biquad("peak", 2400, 1.8, 3.0), biquad("lp", 4800, 0.7)) for c in range(2)], axis=1)
    out = saturate(0.7 * out / (np.max(np.abs(out)) + 1e-9), 2.2)
    out = np.stack([iir(out[:, c], biquad("lp", 5000, 0.7), biquad("lp", 7000, 0.6)) for c in range(2)], axis=1)
    env = env_pts(n, [(0, 0), (0.05, 0.6), (0.14, 1.0), (hold, 0.96), (hold + 0.25, 0.0), (hold + 0.5, 0.0)])
    air = np.stack([unit(fft_filter(r.standard_normal(n), lambda f: m_bp(f, 1800, 0.7), pad=0.0)) for _ in range(2)], axis=1)
    out = out * env[:, None] + 0.03 * air * env[:, None]
    slap = np.zeros_like(out)
    for d, g, sgn in ((0.11, 0.22, 1), (0.29, 0.15, -1), (0.47, 0.08, 1)):
        k = N(d)
        slap[k:] += g * out[:-k][:, ::sgn]
    out = out + iir(slap, biquad("lp", 2500, 0.7))
    y = add_reverb(out, arena_ir(), wet=0.32, dry=1.0)
    return y[:N(hold + 1.6)]


def sfx_period_buzzer():
    """End-of-period buzzer: harsh, wide electric horn with mains grind, ~2 s (stereo)."""
    r = rng_for("buzzer")
    hold = 1.9
    n = N(hold + 0.08)
    t = T(n)
    y = np.zeros(n)
    for f in (174.6, 220.0, 261.6):                                   # F3 A3 C4 (bright, hard)
        y += osc_pulse(f * (1.0 + 0.002 * smooth_random(r, n, 6.0)), n, 0.3, r.random())
    y *= 1.0 + 0.35 * np.sin(TWO_PI * 60.0 * t)
    y = iir(y, biquad("hp", 120, 0.7), biquad("peak", 900, 1.0, 8.0), biquad("peak", 2600, 1.6, 5.0), biquad("lp", 6000, 0.7))
    y = saturate(unitpeak(y), 3.2)
    y = iir(y, biquad("lp", 7000, 0.7), biquad("lp", 9000, 0.6))
    y *= env_pts(n, [(0, 0), (0.01, 1), (hold, 0.97), (hold + 0.06, 0)])
    st = np.stack([y, np.roll(y, N(0.0007))], axis=1)
    return add_reverb(st, arena_ir(), wet=0.3)[:N(hold + 1.2)]


def sfx_faceoff_drop():
    r = rng_for("faceoff")
    n = N(0.6)
    y = np.zeros(n)
    mix_into(y, 1.2 * puck_ice_hit(r, N(0.3), 1.0), 0)
    mix_into(y, 0.35 * puck_ice_hit(r, N(0.2), 1.0), N(0.06))
    clack = unitpeak(modal(N(0.2), stick_modes(r, 650, 0.4, 1.1))) * 0.25
    mix_into(y, clack, N(0.11))
    y = saturate(unitpeak(y), 1.6)
    return add_reverb(y, rink_ir(), wet=0.14)[:n]


# =============================================================================================
# Fights
# =============================================================================================


def punch(r, n, weight=1.0, swish_len=0.05):
    y = np.zeros(n)
    pre = swish_len
    mix_into(y, 0.3 * whoosh(r, pre + 0.01, 500, 1800 * (1.2 - 0.2 * weight), q=1.0, peak_at=0.9), 0)
    L = n - N(pre)
    th = thump(L, 130 / weight ** 0.3, 45, 0.02, 0.05 + 0.05 * weight)
    smack = unitpeak(burst(r, L / SR, 0.006, lambda f: m_bp(f, 1900, 0.7), attack=0.0003))
    flesh = unitpeak(burst(r, L / SR, 0.02 * weight, lambda f: m_lp(f, 900, 2), attack=0.001))
    crunch = unitpeak(grains(r, L, 0.0, 0.05 * weight, lambda tt: 600, fc=(800, 3000), tau=(0.001, 0.004)))
    hit = 1.0 * th + 0.6 * smack + 0.5 * flesh + 0.35 * weight * crunch
    mix_into(y, hit, N(pre))
    return y


def sfx_fight_jab(i):
    r = rng_for("jab%d" % i)
    n = N(0.45)
    y = punch(r, n, 0.7 + 0.08 * i, 0.04)
    y = saturate(unitpeak(y), 2.0)
    return add_reverb(y, rink_ir(), wet=0.1)[:n]


def sfx_fight_punch(i):
    r = rng_for("punch%d" % i)
    n = N(0.65)
    y = punch(r, n, 1.1 + 0.1 * i, 0.07)
    y = saturate(1.2 * unitpeak(y), 2.6)
    return add_reverb(y, rink_ir(), wet=0.12)[:n]


def sfx_fight_uppercut():
    r = rng_for("uppercut")
    n = N(1.3)
    y = np.zeros(n)
    pre = 0.16
    mix_into(y, 0.5 * whoosh(r, pre + 0.02, 300, 2600, q=0.9, peak_at=0.9), 0)
    L = n - N(pre)
    hit = punch(r, L, 1.6, 0.001)
    boom = thump(L, 90, 30, 0.04, 0.25)
    crack = unitpeak(burst(r, L / SR, 0.003, lambda f: m_hp(f, 1200, 2)))
    mix_into(y, 1.0 * hit + 0.7 * boom + 0.4 * crack, N(pre))
    y = saturate(1.3 * unitpeak(y), 2.8)
    y = add_reverb(y, rink_ir(), wet=0.12)
    return add_reverb(y, arena_ir_mono(), wet=0.15)[:n]


def sfx_fight_block():
    r = rng_for("fblock")
    n = N(0.45)
    th = thump(n, 160, 80, 0.01, 0.035)
    pad_ = unitpeak(burst(r, 0.45, 0.012, lambda f: m_bp(f, 700, 0.7)))
    cloth = unitpeak(burst(r, 0.45, 0.03, lambda f: m_bp(f, 3500, 0.8), attack=0.004))
    y = 1.0 * th + 0.6 * pad_ + 0.25 * cloth
    y = saturate(unitpeak(y), 1.8)
    return add_reverb(y, rink_ir(), wet=0.1)[:n]


def cloth_tug(r, dur, f0=2500, f1=4200):
    n = N(dur)
    t = T(n)
    fc = np.interp(t, [0, dur], [f0, f1])
    y = unit(svf(r.standard_normal(n), fc, 0.9, "bp"))
    flutter = np.clip(0.4 + 0.8 * np.abs(smooth_random(r, n, 120.0)), 0, None)
    return y * flutter * env_pts(n, [(0, 0), (0.02, 1.0), (dur * 0.6, 0.8), (dur, 0)])


def sfx_fight_grab():
    r = rng_for("grab")
    n = N(0.75)
    y = np.zeros(n)
    mix_into(y, 0.8 * cloth_tug(r, 0.22, 1800, 3800), 0)
    mix_into(y, 1.0 * cloth_tug(r, 0.3, 2200, 4600), N(0.25))
    mix_into(y, 0.5 * thump(N(0.1), 150, 90, 0.01, 0.03), 0)
    mix_into(y, 0.4 * thump(N(0.1), 140, 85, 0.01, 0.03), N(0.25))
    return add_reverb(y, rink_ir(), wet=0.08)[:n]


def sfx_gloves_drop():
    r = rng_for("gloves")
    n = N(1.5)
    y = np.zeros(n)
    for t0, a in ((0.0, 1.0), (0.17, 0.85)):
        L = N(0.25)
        g = thump(L, 150, 75, 0.012, 0.03) + 0.6 * unitpeak(burst(r, 0.25, 0.02, lambda f: m_lp(f, 900, 2), attack=0.002))
        g += 0.2 * unitpeak(burst(r, 0.25, 0.01, lambda f: m_bp(f, 2500, 0.8)))
        mix_into(y, a * g, N(t0))
    for t0, a in ((0.36, 1.0), (0.47, 0.5), (0.53, 0.3), (0.58, 0.18)):
        L = N(0.3)
        c = unitpeak(modal(L, stick_modes(r, r.uniform(480, 620), decay=0.7, bright=1.1)))
        c += 0.6 * unitpeak(burst(r, 0.3, 0.0015, lambda f: m_hp(f, 1500, 2)))
        mix_into(y, a * 0.8 * c, N(t0))
    slide = sweep_noise(r, N(0.6), [(0, 3000), (0.6, 2200)], 0.8, env=[(0, 0), (0.03, 1), (0.6, 0)])
    mix_into(y, 0.12 * slide, N(0.5))
    y = saturate(unitpeak(y), 1.4)
    return add_reverb(y, rink_ir(), wet=0.12)[:n]


# =============================================================================================
# Gags, fire, crowd props
# =============================================================================================


def sfx_ambulance():
    """Comedic two-tone siren racing past left -> right (doppler, distance, air absorption)."""
    r = rng_for("ambulance")
    dur = 3.3
    n = N(dur)
    t = T(n)
    c, v, d, tc = 343.0, 32.0, 9.0, 1.55
    # emission time for each reception time (solve retarded time iteratively)
    te = t.copy()
    for _ in range(6):
        x = v * (te - tc)
        te = t - np.sqrt(x * x + d * d) / c
    x = v * (te - tc)
    dist = np.sqrt(x * x + d * d)
    # two-tone hi-lo, 0.42 s per tone, quick glides between
    period = 0.84
    ph = (te % period) / period
    hi = 0.5 + 0.5 * np.tanh(40.0 * (np.minimum(ph, 1.0 - ph) - 0.0) * np.sign(0.5 - ph))
    tone_sel = np.where(ph < 0.5, 1.0, 0.0)
    tone_sel = fft_filter(tone_sel, lambda f: m_lp(f, 40.0, 2), pad=0.0)
    f_src = 770.0 + (960.0 - 770.0) * tone_sel
    f_src *= 1.0 + 0.008 * np.sin(TWO_PI * 7.0 * te)            # comedic wobble
    # received frequency follows d(te)/dt
    dte = np.gradient(te) * SR
    f_rx = f_src * dte
    sig = osc_pulse(f_rx, n, 0.42) + 0.5 * osc_saw(f_rx * 2.0, n)
    sig = iir(sig, biquad("hp", 400, 0.7), biquad("peak", 1300, 1.2, 6.0), biquad("peak", 2600, 2.0, 4.0), biquad("lp", 6000, 0.7))
    amp = (d / dist) ** 1.2
    far = np.clip((dist - d) / 40.0, 0.0, 1.0)
    dark = iir(sig, biquad("lp", 1500, 0.7))
    sig = (sig * (1.0 - far) + dark * far) * amp
    engine = unit(fft_filter(r.standard_normal(n), lambda f: m_bp(f, 180, 0.8), pad=0.0)) * 0.15 * amp
    whoosh_ = unit(fft_filter(r.standard_normal(n), lambda f: m_bp(f, 900, 0.5), pad=0.0)) * 0.12 * amp ** 3
    mono = sig + engine + whoosh_
    st = pan(mono, np.clip(x / np.sqrt(x * x + 4.0), -1, 1) * 0.95)
    st = fade(st, 0.25, 0.4)
    return add_reverb(st, arena_ir(), wet=0.12)[:n]


def sfx_flame_burst():
    r = rng_for("flameburst")
    dur = 2.2
    n = N(dur + 0.2)
    t = T(n)
    boom = thump(n, 100, 32, 0.06, 0.25)
    cut = np.interp(t, [0, 0.03, 0.25, 0.8, dur], [300, 1200, 6500, 2800, 1200])
    gas_env = np.interp(t, [0, 0.012, 0.12, 0.5, 1.2, dur, dur + 0.2], [0, 0.9, 1.0, 0.6, 0.35, 0.0, 0.0])
    gas = unit(svf(r.standard_normal(n), cut, 0.8, "lp")) * gas_env * (0.8 + 0.2 * smooth_random(r, n, 14.0))
    whoosh_ = sweep_noise(r, n, [(0, 400), (0.3, 3500), (dur, 1800)], 1.2, env=[(0, 0), (0.05, 0.4), (0.15, 1.0), (0.5, 0.3), (0.9, 0)])
    crk = unitpeak(crackles(r, n, lambda tt: 10.0 + 60.0 * min(tt / 0.15, 1.0) * math.exp(-max(tt - 0.3, 0.0) / 0.8), big_prob=0.18))
    sizzle = unit(fft_filter(r.standard_normal(n), lambda f: m_hp(f, 6000, 2), pad=0.0)) * gas_env
    roar = unit(fft_filter(r.standard_normal(n), lambda f: m_tilt(f, -4.0, 200) * m_lp(f, 600, 2) * m_hp(f, 40, 2), pad=0.0)) * gas_env
    y = 0.9 * boom + 0.35 * gas + 0.18 * whoosh_ + 0.45 * crk + 0.03 * sizzle + 0.35 * roar
    y = saturate(0.9 * unitpeak(y), 1.6)
    return add_reverb(y, rink_ir(), wet=0.15)[:N(dur)]


def sfx_fire_loop():
    """Seamless 6 s crackling fire bed: every layer is periodic in the loop length."""
    r = rng_for("fireloop")
    L = N(6.0)
    roar = shaped_noise(r, L, lambda f: m_tilt(f, -4.0, 300.0) * m_hp(f, 60, 2) * m_lp(f, 900, 2))
    gust = 0.75 + 0.25 * smooth_random(r, L, 1.5)
    band = shaped_noise(r, L, lambda f: m_bp(f, 1600, 0.7))
    flick = np.clip(0.55 + 0.45 * smooth_random(r, L, 12.0), 0.05, None)
    hiss = shaped_noise(r, L, lambda f: m_hp(f, 5000, 2))
    crk = unitpeak(crackles(r, L, lambda tt: 26.0, circular=True))
    y = 0.6 * roar * gust + 0.28 * band * flick + 0.05 * hiss + 0.55 * crk
    return y + 0.12 * convolve_circular(y, rink_ir())


def sfx_hat_rain():
    """Hats raining onto the ice: dozens of soft whooshes and felt 'pff' landings across the stereo field."""
    r = rng_for("hats")
    dur = 4.8
    n = N(dur)
    out = np.zeros((n, 2))
    count = 56
    times = np.sort(r.gamma(3.0, 0.45, count))
    times = times[times < dur - 0.6]
    for t0 in times:
        p = r.uniform(-0.95, 0.95)
        fl = r.uniform(0.18, 0.45)
        sw = whoosh(r, fl, r.uniform(1800, 2600), r.uniform(500, 900), q=r.uniform(0.8, 1.6), peak_at=0.7)
        land_L = N(0.2)
        land = thump(land_L, r.uniform(160, 240), 90, 0.008, 0.02) * 0.5
        land += unitpeak(burst(r, 0.2, r.uniform(0.01, 0.025), lambda f: m_lp(f, r.uniform(1000, 2200), 2), attack=0.002))
        ev = np.zeros(N(fl) + land_L)
        mix_into(ev, r.uniform(0.15, 0.35) * sw, 0)
        mix_into(ev, r.uniform(0.35, 0.8) * land, N(fl * 0.85))
        mix_into(out, pan(ev, p), N(t0))
    out = add_reverb(out, arena_ir(), wet=0.25)[:n]
    return fade(out, 0.0, 0.5)


def sfx_glass_rattle():
    r = rng_for("glassrattle")
    n = N(1.6)
    y = glass_shake(r, n, 0.0, decay=1.2, amount=1.0)
    y += 0.5 * thump(n, 120, 60, 0.02, 0.06)
    return add_reverb(y, rink_ir(), wet=0.16)[:n]


# =============================================================================================
# UI
# =============================================================================================


def synth_note(midi, dur, kind="pulse", pw=0.5, tau=None, attack=0.002, vib=0.0, detune=0.0, release=0.02,
               bright=1.0):
    n = N(dur + release)
    t = T(n)
    f = float(midi_hz(midi)) * (1.0 + vib * np.sin(TWO_PI * 6.0 * t) * np.clip((t - 0.08) / 0.1, 0.0, 1.0))
    if kind == "pulse":
        y = osc_pulse(f, n, pw)
    elif kind == "saw":
        y = 0.5 * osc_saw(f * (1 + detune), n) + 0.5 * osc_saw(f * (1 - detune), n, 0.37)
    elif kind == "tri":
        y = osc_tri(f, n)
    else:
        y = osc_sine(f, n)
    if bright < 1.0:
        y = iir(y, biquad("lp", 2000 + 9000 * bright, 0.7))
    env = env_exp(n, tau, attack) if tau else env_pts(n, [(0, 0), (attack, 1), (dur, 0.85), (dur + release, 0)])
    return y * env


def ui_move():
    r = rng_for("ui_move")
    n = N(0.09)
    y = 0.6 * fm_bell(96, 0.09, index=1.2, ratio=3.0, tau=0.02) + 0.35 * osc_tri(1567.98, n) * env_exp(n, 0.015, 0.001)
    y += 0.25 * unitpeak(burst(r, 0.09, 0.0007, lambda f: m_hp(f, 4000, 2)))
    return iir(y, biquad("lp", 9000, 0.7))


def ui_select():
    n = N(0.4)
    y = np.zeros(n)
    for t0, m, d in [(0.0, 86, 0.06), (0.06, 93, 0.24)]:          # D6 -> A6
        v = pad_to(0.5 * synth_note(m, d, "pulse", pw=0.3, tau=d * 0.45), N(d + 0.1)) + 0.35 * fm_bell(m + 12, d + 0.1, 1.5, 3.0, d * 0.5)
        mix_into(y, v, N(t0))
    y = iir(y, biquad("lp", 9000, 0.7))
    return echo(y, 0.08, 0.3, 0.2, repeats=2)[:n]


def ui_back():
    n = N(0.2)
    y = np.zeros(n)
    for t0, m, d in [(0.0, 84, 0.05), (0.05, 77, 0.11)]:           # C6 -> F5
        v = 0.5 * synth_note(m, d, "tri", tau=d * 0.5) + 0.3 * synth_note(m, d, "pulse", pw=0.25, tau=d * 0.4)
        mix_into(y, v, N(t0))
    return iir(y, biquad("lp", 4500, 0.7))


def guitar_chord(r, roots, dur, mute=0.0, gain=1.0):
    """Distorted power chord from Karplus-Strong strings (mono)."""
    y = np.zeros(N(dur))
    for k, m in enumerate(roots):
        s = ks_pluck(r, float(midi_hz(m)) * 2.0 ** (r.uniform(-4, 4) / 1200.0), dur, damp=mute, bright=0.9, decay=0.9995 - 0.004 * mute)
        mix_into(y, s, N(0.004 * k))
    y = saturate(gain * 6.0 * y / (np.max(np.abs(y)) + 1e-9), 3.0)
    return iir(y, biquad("hp", 90, 0.7), biquad("peak", 2200, 1.0, 4.0), biquad("lp", 5200, 0.8))


def ui_start():
    """Big 'press start': riser, power-chord + brass stab, crash, icy bell, sub hit (stereo)."""
    r = rng_for("ui_start")
    n = N(2.2)
    out = np.zeros((n, 2))
    pre = 0.28
    riser = sweep_noise(r, N(pre), [(0, 600), (pre, 7000)], 1.5, env=[(0, 0), (pre * 0.8, 0.8), (pre, 1.0)])
    mix_into(out, pan(0.18 * riser, 0.0), 0)
    hit_t = N(pre)
    L = n - hit_t
    gtr_l = fade(guitar_chord(r, [40, 47, 52], 1.6), 0.0, 0.9)
    gtr_r = fade(guitar_chord(r, [40, 47, 52], 1.6), 0.0, 0.9)
    mix_into(out, np.stack([gtr_l, 0.3 * gtr_r], axis=1) * 0.35, hit_t)
    mix_into(out, np.stack([0.3 * gtr_l, gtr_r], axis=1) * 0.35, hit_t + N(0.012))
    for m, g in [(64, 0.3), (68, 0.25), (71, 0.25), (76, 0.25)]:      # E major brass
        v = synth_note(m, 0.9, "saw", detune=0.006, attack=0.006, vib=0.004, release=0.3, bright=0.6)
        mix_into(out, pan(g * v, r.uniform(-0.5, 0.5)), hit_t)
    mix_into(out, pan(0.35 * fm_bell(100, 1.4, 2.0, 3.5, 0.5), 0.2), hit_t)
    boom = thump(L, 120, 35, 0.03, 0.3)
    mix_into(out, pan(0.9 * boom, 0.0), hit_t)
    crash = crash_cym(r, 1.8)
    mix_into(out, 0.35 * crash, hit_t)
    out = add_reverb(out, arena_ir(), wet=0.2)[:n]
    return saturate(0.9 * out / np.max(np.abs(out)), 1.4)


def crash_cym(r, dur=2.0):
    n = N(dur)
    t = T(n)
    out = np.zeros((n, 2))
    for ch in range(2):
        partials = modal(n, [(r.uniform(3000, 11000), r.uniform(0.3, 1.0), r.uniform(0.4, 1.2), r.uniform(0, TWO_PI))
                             for _ in range(40)])
        hiss = unit(fft_filter(r.standard_normal(n), lambda f: m_hp(f, 3500, 2) * m_lp(f, 14000, 2), pad=0.0))
        y = 0.6 * unit(partials) * np.exp(-t / 0.7) + hiss * (0.7 * np.exp(-t / 0.65) + 0.6 * np.exp(-t / 0.06))
        out[:, ch] = y * np.clip(t / 0.001, 0.0, 1.0)
    return fade(out, 0.0, 0.3)


def ui_join():
    """Player joined: quick rising arpeggio + stick clack + sparkle."""
    r = rng_for("ui_join")
    n = N(0.7)
    y = np.zeros(n)
    for k, m in enumerate([79, 83, 86, 91]):                         # G5 B5 D6 G6
        v = pad_to(0.5 * synth_note(m, 0.12, "pulse", pw=0.3, tau=0.08), N(0.25)) + 0.35 * fm_bell(m + 12, 0.25, 1.5, 3.0, 0.1)
        mix_into(y, v * (0.7 + 0.1 * k), N(0.05 * k))
    clack = unitpeak(modal(N(0.15), stick_modes(r, 700, 0.5, 1.1)))
    mix_into(y, 0.35 * clack, 0)
    sp = unitpeak(grains(r, n, 0.15, 0.5, lambda tt: 50, fc=(6000, 12000), tau=(0.004, 0.012)))
    y = y + 0.12 * sp
    return echo(iir(y, biquad("lp", 10000, 0.7)), 0.09, 0.3, 0.2, repeats=2)[:n]


def ui_error():
    n = N(0.32)
    y = np.zeros(n)
    for t0 in (0.0, 0.14):
        L = N(0.11)
        v = osc_pulse(146.8, L, 0.4) + 0.7 * osc_saw(155.6, L)
        v *= env_pts(L, [(0, 0), (0.004, 1), (0.09, 0.9), (0.11, 0)])
        mix_into(y, v, N(t0))
    y = iir(y, biquad("hp", 100, 0.7), biquad("lp", 2500, 0.7))
    return saturate(unitpeak(y), 1.8)


def ui_tick():
    r = rng_for("ui_tick")
    n = N(0.12)
    wood = modal(n, [(1250, 1.0, 0.018), (2650, 0.5, 0.01), (4100, 0.25, 0.006)])
    beep = osc_sine(1760.0, n) * env_exp(n, 0.035, 0.001)
    click = unitpeak(burst(r, 0.12, 0.0008, lambda f: m_bp(f, 3500, 1.0)))
    return iir(unitpeak(wood) + 0.55 * beep + 0.3 * click, biquad("lp", 10000, 0.7))


def ui_whoosh():
    r = rng_for("ui_whoosh")
    dur = 0.55
    n = N(dur)
    y = sweep_noise(r, n, [(0, 500), (0.22, 3200), (dur, 900)], 1.1, env=[(0, 0), (0.2, 1.0), (dur, 0)])
    air = unit(fft_filter(r.standard_normal(n), lambda f: m_hp(f, 5000, 2), pad=0.0)) * env_pts(n, [(0, 0), (0.22, 0.3), (dur, 0)])
    tone = osc_sine(np.interp(T(n), [0, dur], [300, 900]), n) * env_pts(n, [(0, 0), (0.2, 0.15), (dur, 0)])
    return y + 0.4 * air + tone


def ui_impact():
    """Logo slam: sub boom + metal/ice crunch + crash + shards (stereo)."""
    r = rng_for("ui_impact")
    n = N(2.4)
    out = np.zeros((n, 2))
    boom = thump(n, 110, 28, 0.05, 0.5) + 0.6 * thump(n, 300, 90, 0.006, 0.06)
    crunch = unitpeak(burst(r, 2.4, 0.03, lambda f: m_bp(f, 900, 0.5), attack=0.0005))
    metal = unitpeak(modal(n, [(r.uniform(180, 2400), r.uniform(0.3, 1.0), r.uniform(0.2, 0.8), r.uniform(0, TWO_PI)) for _ in range(18)]))
    shards = unitpeak(grains(r, n, 0.0, 0.8, lambda tt: 300 * math.exp(-tt / 0.25), fc=(3000, 11000), tau=(0.003, 0.02)))
    mono = saturate(1.0 * unitpeak(boom) + 0.5 * crunch + 0.25 * metal, 2.2) + 0.25 * shards
    out += pan(mono, 0.0)
    out += 0.35 * crash_cym(r, 2.4)
    return add_reverb(out, arena_ir(), wet=0.25)[:n]
