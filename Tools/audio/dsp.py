"""
ICE RIOT -- numpy DSP core: oscillators (PolyBLEP), envelopes, FFT / biquad / state-variable filters,
modal synthesis, noise shaping, reverb, dynamics, loudness (ITU-R BS.1770) and WAV I/O.

Everything here is deterministic; randomness always comes from rng_for(<name>).
"""

import math
import wave
import zlib

import numpy as np

SR = 48000
NYQ = SR / 2.0
TWO_PI = 2.0 * np.pi


# =============================================================================================
# Basics
# =============================================================================================


def N(seconds):
    """Seconds -> sample count."""
    return max(1, int(round(seconds * SR)))


def T(n):
    """Time axis (seconds) for n samples."""
    return np.arange(n, dtype=np.float64) / SR


def rng_for(name):
    return np.random.default_rng(zlib.crc32(("iceriot:" + name).encode("utf-8")))


def dbamp(d):
    return 10.0 ** (np.asarray(d, dtype=np.float64) / 20.0)


def amp2db(a):
    return 20.0 * math.log10(max(float(a), 1e-12))


def peak(x):
    return float(np.max(np.abs(x))) if x.size else 0.0


def rms(x):
    return float(np.sqrt(np.mean(np.square(x)))) if x.size else 0.0


def midi_hz(m):
    return 440.0 * 2.0 ** ((np.asarray(m, dtype=np.float64) - 69.0) / 12.0)


def as2d(x):
    return x if x.ndim == 2 else x[:, None]


def pad_to(x, n):
    """Zero-pad or truncate along axis 0 to exactly n samples."""
    if x.shape[0] >= n:
        return x[:n].copy()
    pad = [(0, n - x.shape[0])] + [(0, 0)] * (x.ndim - 1)
    return np.pad(x, pad)


def to_stereo(x):
    return x if x.ndim == 2 else np.stack([x, x], axis=1) * 0.7071


def mix_into(buf, sig, start, gain=1.0):
    """Add sig into buf at sample offset start (clipped to the buffer)."""
    if sig.ndim == 1 and buf.ndim == 2:
        sig = np.repeat(sig[:, None], buf.shape[1], axis=1) * 0.7071
    if start >= buf.shape[0]:
        return
    if start < 0:
        sig = sig[-start:]
        start = 0
    n = min(sig.shape[0], buf.shape[0] - start)
    if n > 0:
        buf[start:start + n] += gain * sig[:n]


def mix_circular(buf, sig, start, gain=1.0):
    """Add sig into a looping buffer, wrapping whatever runs past the end back to the start."""
    if sig.ndim == 1 and buf.ndim == 2:
        sig = np.repeat(sig[:, None], buf.shape[1], axis=1) * 0.7071
    L = buf.shape[0]
    start %= L
    pos = 0
    while pos < sig.shape[0]:
        s = (start + pos) % L
        n = min(sig.shape[0] - pos, L - s)
        buf[s:s + n] += gain * sig[pos:pos + n]
        pos += n


def pan(x, pos):
    """Constant-power pan of a mono signal; pos (scalar or per-sample) in [-1, +1]. Returns (n, 2)."""
    th = (np.clip(pos, -1.0, 1.0) + 1.0) * np.pi / 4.0
    return np.stack([x * np.cos(th), x * np.sin(th)], axis=1)


def resample(x, ratio):
    """Pitch/speed change by linear interpolation (ratio > 1 -> higher and shorter)."""
    n_out = max(1, int(x.shape[0] / ratio))
    idx = np.arange(n_out) * ratio
    if x.ndim == 2:
        return np.stack([np.interp(idx, np.arange(x.shape[0]), x[:, c]) for c in range(x.shape[1])], axis=1)
    return np.interp(idx, np.arange(x.shape[0]), x)


def unit(x):
    """Scale to unit RMS."""
    return x / (rms(x) + 1e-12)


def unitpeak(x):
    """Scale to unit peak."""
    return x / (peak(x) + 1e-12)


def set_rms(x, db):
    return x * (float(dbamp(db)) / (rms(x) + 1e-12))


def normalize(x, peak_db=-1.0):
    p = peak(x)
    return x * (float(dbamp(peak_db)) / p) if p > 0 else x


# =============================================================================================
# Envelopes
# =============================================================================================


def env_exp(n, tau, attack=0.0):
    """Exponential decay with time constant tau (s); optional smooth attack (s)."""
    t = T(n)
    e = np.exp(-t / max(tau, 1e-6))
    if attack > 0:
        e *= np.sin(0.5 * np.pi * np.clip(t / attack, 0.0, 1.0)) ** 2
    return e


def env_pts(n, pts):
    """Piecewise-linear envelope through (time_s, value) points."""
    ts, vs = zip(*pts)
    return np.interp(T(n), ts, vs)


def env_adsr(n, a, d, s, gate, r):
    """ADSR: attack a, decay d (to level s), note-off at gate (s), release r."""
    t = T(n)
    e = np.where(t < a, t / max(a, 1e-6), s + (1.0 - s) * np.exp(-(t - a) / max(d, 1e-6)))
    level_at_gate = (gate / max(a, 1e-6)) if gate < a else s + (1.0 - s) * math.exp(-(gate - a) / max(d, 1e-6))
    rel = level_at_gate * np.exp(-(t - gate) / max(r, 1e-6))
    return np.where(t < gate, e, rel)


def fade(x, fin=0.0, fout=0.0):
    x = x.copy()
    if fin > 0:
        k = min(N(fin), x.shape[0])
        w = np.sin(0.5 * np.pi * np.linspace(0.0, 1.0, k)) ** 2
        x[:k] *= w if x.ndim == 1 else w[:, None]
    if fout > 0:
        k = min(N(fout), x.shape[0])
        w = np.cos(0.5 * np.pi * np.linspace(0.0, 1.0, k)) ** 2
        x[-k:] *= w if x.ndim == 1 else w[:, None]
    return x


def smooth_random(r, n, rate_hz):
    """Band-limited random curve (unit RMS) whose fluctuations sit below ~rate_hz. Periodic in n."""
    f = np.fft.rfftfreq(n, 1.0 / SR)
    X = np.fft.rfft(r.standard_normal(n)) * np.exp(-(f / max(rate_hz, 1e-3)) ** 2)
    X[0] = 0.0
    y = np.fft.irfft(X, n)
    return y / (rms(y) + 1e-12)


# =============================================================================================
# Filters
# =============================================================================================


def m_lp(f, fc, order=2):
    return 1.0 / np.sqrt(1.0 + (np.asarray(f) / fc) ** (2 * order))


def m_hp(f, fc, order=2):
    ff = np.maximum(np.asarray(f, dtype=np.float64), 1e-6)
    return 1.0 / np.sqrt(1.0 + (fc / ff) ** (2 * order))


def m_bp(f, fc, q):
    ff = np.maximum(np.asarray(f, dtype=np.float64), 1e-6)
    return 1.0 / np.sqrt(1.0 + q * q * (ff / fc - fc / ff) ** 2)


def m_peak(f, fc, q, gain_db):
    return 1.0 + (dbamp(gain_db) - 1.0) * m_bp(f, fc, q) ** 2


def m_tilt(f, db_per_oct, f_ref=1000.0):
    ff = np.maximum(np.asarray(f, dtype=np.float64), 20.0)
    return (ff / f_ref) ** (db_per_oct / 6.0206)


def fft_filter(x, mag_fn, circular=False, pad=0.25):
    """Zero-phase filtering with an arbitrary magnitude response mag_fn(freqs_hz).
    circular=True keeps a loop exactly periodic. Works on mono or (n, ch) arrays."""
    n = x.shape[0]
    nfft = n if circular else n + N(pad)
    X = np.fft.rfft(x, nfft, axis=0)
    H = mag_fn(np.fft.rfftfreq(nfft, 1.0 / SR))
    X *= H if x.ndim == 1 else H[:, None]
    return np.fft.irfft(X, nfft, axis=0)[:n]


def shaped_noise(r, n, mag_fn=None):
    """Unit-RMS stationary noise with the given magnitude response; periodic in n (loop-safe)."""
    X = np.fft.rfft(r.standard_normal(n))
    if mag_fn is not None:
        X *= mag_fn(np.fft.rfftfreq(n, 1.0 / SR))
    X[0] = 0.0
    y = np.fft.irfft(X, n)
    return y / (rms(y) + 1e-12)


def biquad(kind, fc, q=0.7071, gain_db=0.0):
    """RBJ cookbook biquad coefficients -> (b0, b1, b2, a1, a2)."""
    fc = min(max(fc, 5.0), NYQ * 0.98)
    w0 = TWO_PI * fc / SR
    c, s = math.cos(w0), math.sin(w0)
    alpha = s / (2.0 * q)
    A = 10.0 ** (gain_db / 40.0)
    if kind == "lp":
        b, a = [(1 - c) / 2, 1 - c, (1 - c) / 2], [1 + alpha, -2 * c, 1 - alpha]
    elif kind == "hp":
        b, a = [(1 + c) / 2, -(1 + c), (1 + c) / 2], [1 + alpha, -2 * c, 1 - alpha]
    elif kind == "bp":
        b, a = [alpha, 0.0, -alpha], [1 + alpha, -2 * c, 1 - alpha]
    elif kind == "peak":
        b, a = [1 + alpha * A, -2 * c, 1 - alpha * A], [1 + alpha / A, -2 * c, 1 - alpha / A]
    elif kind == "lowshelf":
        sq = 2 * math.sqrt(A) * alpha
        b = [A * ((A + 1) - (A - 1) * c + sq), 2 * A * ((A - 1) - (A + 1) * c), A * ((A + 1) - (A - 1) * c - sq)]
        a = [(A + 1) + (A - 1) * c + sq, -2 * ((A - 1) + (A + 1) * c), (A + 1) + (A - 1) * c - sq]
    elif kind == "highshelf":
        sq = 2 * math.sqrt(A) * alpha
        b = [A * ((A + 1) + (A - 1) * c + sq), -2 * A * ((A - 1) + (A + 1) * c), A * ((A + 1) + (A - 1) * c - sq)]
        a = [(A + 1) - (A - 1) * c + sq, 2 * ((A - 1) + (A + 1) * c), (A + 1) - (A - 1) * c - sq]
    else:
        raise ValueError(kind)
    return (b[0] / a[0], b[1] / a[0], b[2] / a[0], a[1] / a[0], a[2] / a[0])


def _biquad_loop(xs, co):
    b0, b1, b2, a1, a2 = co
    z1 = z2 = 0.0
    out = []
    app = out.append
    for xi in xs:
        yi = b0 * xi + z1
        z1 = b1 * xi - a1 * yi + z2
        z2 = b2 * xi - a2 * yi
        app(yi)
    return out


_IIR_IR = {}


def _cascade_ir(coeffs):
    key = tuple(coeffs)
    if key not in _IIR_IR:
        h = np.zeros(SR)
        h[0] = 1.0
        for co in coeffs:
            h = np.asarray(_biquad_loop(h.tolist(), co))
        keep = np.nonzero(np.abs(h) > 1e-8 * np.max(np.abs(h)))[0]
        _IIR_IR[key] = h[: keep[-1] + 1] if keep.size else h[:1]
    return _IIR_IR[key]


def iir(x, *coeffs):
    """Causal (minimum-phase) cascade of biquads, rendered as an FFT convolution with the cascade's
    (cached, 1 s-truncated) impulse response."""
    h = _cascade_ir(coeffs)
    y = convolve(x, h if x.ndim == 1 else h[:, None] * np.ones((1, x.shape[1])))
    return y[: x.shape[0]]


def iir_circular(x, *coeffs):
    """Same as iir() but for loops: wraps the filter tail around (exactly periodic result)."""
    h = _cascade_ir(coeffs)
    L = x.shape[0]
    if h.shape[0] > L:
        h = h[:L]
    return convolve_circular(x, h if x.ndim == 1 else h[:, None] * np.ones((1, x.shape[1])))


def svf(x, fc, q=0.7071, mode="lp"):
    """Time-varying state-variable filter (Simper/Cytomic TPT). fc and q may be per-sample arrays.
    mode: lp | bp (unity peak gain) | hp | notch."""
    n = x.shape[0]
    fcv = np.clip(np.broadcast_to(np.asarray(fc, dtype=np.float64), (n,)), 10.0, NYQ * 0.95)
    k = 1.0 / np.broadcast_to(np.asarray(q, dtype=np.float64), (n,))
    g = np.tan(np.pi * fcv / SR)
    a1 = 1.0 / (1.0 + g * (g + k))
    a2 = g * a1
    a3 = g * a2
    ic1 = ic2 = 0.0
    lp, bp = [], []
    lpa, bpa = lp.append, bp.append
    for xi, c1, c2, c3 in zip(x.tolist(), a1.tolist(), a2.tolist(), a3.tolist()):
        v3 = xi - ic2
        v1 = c1 * ic1 + c2 * v3
        v2 = ic2 + c2 * ic1 + c3 * v3
        ic1 = 2.0 * v1 - ic1
        ic2 = 2.0 * v2 - ic2
        lpa(v2)
        bpa(v1)
    lp = np.asarray(lp)
    bp = np.asarray(bp)
    if mode == "lp":
        return lp
    if mode == "bp":
        return bp * k
    if mode == "hp":
        return x - k * bp - lp
    if mode == "notch":
        return x - k * bp
    raise ValueError(mode)


def dc_block(x, fc=15.0):
    return iir(x, biquad("hp", fc, 0.7071))


# =============================================================================================
# Oscillators
# =============================================================================================


def phase_acc(freq, n, ph0=0.0):
    """Running phase in cycles for a (possibly per-sample) frequency."""
    f = np.broadcast_to(np.asarray(freq, dtype=np.float64), (n,))
    ph = np.empty(n)
    ph[0] = 0.0
    if n > 1:
        np.cumsum(f[:-1] / SR, out=ph[1:])
    return ph + ph0


def _blep(p, dt):
    y = np.zeros_like(p)
    m = p < dt
    t = p[m] / dt[m]
    y[m] = t + t - t * t - 1.0
    m = p > 1.0 - dt
    t = (p[m] - 1.0) / dt[m]
    y[m] = t * t + t + t + 1.0
    return y


def osc_sine(freq, n, ph0=0.0):
    return np.sin(TWO_PI * phase_acc(freq, n, ph0))


def osc_saw(freq, n, ph0=0.0):
    """Band-limited (PolyBLEP) sawtooth, -1..1."""
    f = np.broadcast_to(np.asarray(freq, dtype=np.float64), (n,))
    p = phase_acc(f, n, ph0) % 1.0
    dt = np.clip(np.abs(f) / SR, 1e-9, 0.5)
    return 2.0 * p - 1.0 - _blep(p, dt)


def osc_pulse(freq, n, pw=0.5, ph0=0.0):
    """Band-limited pulse with duty cycle pw (difference of two PolyBLEP saws), zero mean."""
    f = np.broadcast_to(np.asarray(freq, dtype=np.float64), (n,))
    ph = phase_acc(f, n, ph0)
    dt = np.clip(np.abs(f) / SR, 1e-9, 0.5)
    p1 = ph % 1.0
    p2 = (ph + pw) % 1.0
    return (2.0 * p1 - 1.0 - _blep(p1, dt)) - (2.0 * p2 - 1.0 - _blep(p2, dt))


def osc_tri(freq, n, ph0=0.0):
    p = phase_acc(freq, n, ph0) % 1.0
    return 1.0 - 4.0 * np.abs(p - 0.5)


def supersaw(freq, n, r, voices=7, spread_cents=18.0):
    """Detuned saw stack (unit-ish level)."""
    y = np.zeros(n)
    for k in range(voices):
        d = (k - (voices - 1) / 2.0) / max(1.0, (voices - 1) / 2.0) * spread_cents
        y += osc_saw(np.asarray(freq) * 2.0 ** (d / 1200.0), n, r.random())
    return y / math.sqrt(voices)


def modal(n, modes, attack=0.0003):
    """Sum of exponentially damped sinusoids; modes = [(freq, amp, tau[, phase]), ...]."""
    t = T(n)
    y = np.zeros(n)
    for m in modes:
        f, a, tau = m[0], m[1], m[2]
        ph = m[3] if len(m) > 3 else 0.0
        if f >= NYQ * 0.92 or a == 0.0:
            continue
        y += a * np.sin(TWO_PI * f * t + ph) * np.exp(-t / tau)
    if attack > 0:
        y *= np.clip(t / attack, 0.0, 1.0)
    return y


def burst(r, dur, tau, mag_fn=None, attack=0.0):
    """Filtered noise burst (noise filtered first, envelope after: the attack stays sharp)."""
    n = N(dur)
    x = r.standard_normal(n)
    if mag_fn is not None:
        x = fft_filter(x, mag_fn, pad=0.0)
        x /= rms(x) + 1e-12
    return x * env_exp(n, tau, attack)


def thump(n, f_start, f_end, tau_pitch, tau_amp, attack=0.0004):
    """Pitch-dropping sine thud (body / boards / boom)."""
    t = T(n)
    f = f_end + (f_start - f_end) * np.exp(-t / tau_pitch)
    return osc_sine(f, n) * env_exp(n, tau_amp) * np.clip(t / attack, 0.0, 1.0)


def ks_pluck(r, freq, dur, damp=0.5, bright=0.7, decay=0.996, pick_pos=0.18):
    """Karplus-Strong plucked string, vectorized one period at a time.

    Rendered at an internal rate SR' = P * freq (P = integer period) so the pitch is exact,
    then resampled to SR. damp: 0..1 extra per-period lowpass (palm mute ~0.9). decay: per-period gain."""
    P = max(8, int(math.ceil(SR / freq)))
    sr_int = P * freq
    n_int = int(dur * sr_int) + P
    periods = n_int // P + 1
    exc = r.uniform(-1.0, 1.0, P)
    # pick brightness: smooth the excitation
    sm = max(1, int(round((1.0 - bright) * 6)))
    if sm > 1:
        exc = np.convolve(np.concatenate([exc, exc[:sm]]), np.ones(sm) / sm, "valid")[:P]
    # pick position comb
    d = max(1, int(pick_pos * P))
    exc = exc - np.roll(exc, d)
    exc -= exc.mean()
    out = np.empty(periods * P)
    cur = exc
    a = 0.5 + 0.5 * (1.0 - damp)            # lowpass coefficient: 1 = no damping, 0.5 = classic KS
    for k in range(periods):
        out[k * P:(k + 1) * P] = cur
        prev = np.concatenate([[cur[-1]], cur[:-1]])
        cur = decay * (a * cur + (1.0 - a) * prev)
    # resample internal rate -> SR
    n_out = N(dur)
    idx = np.arange(n_out) * (sr_int / SR)
    return np.interp(idx, np.arange(out.shape[0]), out)


# =============================================================================================
# Convolution, reverb, delay
# =============================================================================================


def _fft_size(n):
    return 1 << int(math.ceil(math.log2(max(n, 2))))


def convolve(x, h):
    """Linear convolution along axis 0 (mono/stereo broadcast). Output length len(x)+len(h)-1."""
    x2, h2 = as2d(x), as2d(h)
    n = x2.shape[0] + h2.shape[0] - 1
    nfft = _fft_size(n)
    y = np.fft.irfft(np.fft.rfft(x2, nfft, axis=0) * np.fft.rfft(h2, nfft, axis=0), nfft, axis=0)[:n]
    return y[:, 0] if (x.ndim == 1 and h.ndim == 1) else y


def convolve_circular(x, h):
    """Circular convolution with period len(x) (h must be shorter): reverb for seamless loops."""
    L = x.shape[0]
    x2, h2 = as2d(x), as2d(h)
    if h2.shape[0] > L:
        raise ValueError("IR longer than loop")
    y = np.fft.irfft(np.fft.rfft(x2, L, axis=0) * np.fft.rfft(h2, L, axis=0), L, axis=0)
    return y[:, 0] if (x.ndim == 1 and h.ndim == 1) else y


def reverb_ir(r, rt60=1.8, length=None, predelay=0.02, damping=(1.0, 0.8, 0.5, 0.28),
              early=10, stereo=True, er_gain=0.6):
    """Synthetic hall/arena impulse response (unit energy per channel), 4-band frequency-dependent
    decay (<400, 400-2k, 2k-6k, >6k Hz) plus a few sparse early reflections."""
    length = length or min(rt60 * 1.15 + predelay, 5.0)
    n = N(length)
    t = T(n)
    nch = 2 if stereo else 1
    f = np.fft.rfftfreq(n, 1.0 / SR)
    lf = np.log2(np.maximum(f, 1.0))
    steps = [0.5 * (1.0 + np.tanh(3.0 * (lf - math.log2(c)))) for c in (400.0, 2000.0, 6000.0)]
    masks = [1.0 - steps[0], steps[0] - steps[1], steps[1] - steps[2], steps[2]]
    build = np.clip((t - predelay) / 0.035, 0.0, 1.0) ** 1.5
    ir = np.zeros((n, nch))
    for ch in range(nch):
        W = np.fft.rfft(r.standard_normal(n))
        acc = np.zeros(n)
        for mask, dmp in zip(masks, damping):
            acc += np.fft.irfft(W * mask, n) * 10.0 ** (-3.0 * t / (rt60 * dmp))
        acc *= build
        acc /= np.sqrt(np.sum(acc ** 2)) + 1e-12
        er = np.zeros(n)
        for k in range(early):
            tk = predelay * 0.4 + r.uniform(0.004, 0.065)
            idx = N(tk)
            if idx < n:
                er[idx] += r.choice([-1.0, 1.0]) * er_gain * math.exp(-k * 0.22) * r.uniform(0.5, 1.0)
        er = fft_filter(er, lambda ff: m_lp(ff, 6500.0, 1), pad=0.0)
        acc = acc + er * 0.35
        ir[:, ch] = acc / (np.sqrt(np.sum(acc ** 2)) + 1e-12)
    ir = fade(ir, 0.0, min(0.15, length * 0.3))
    return ir if stereo else ir[:, 0]


def add_reverb(x, ir, wet, dry=1.0):
    """Dry + wet convolution reverb. Output grows by the IR length; stereo IR -> stereo output."""
    y = wet * convolve(x, ir)
    d = x if (x.ndim == 2 or y.ndim == 1) else pan(x, 0.0) * math.sqrt(2.0)
    out = np.zeros_like(y)
    out[: d.shape[0]] += dry * (d if out.ndim == d.ndim else as2d(d))
    return out + y


def echo(x, delay_s, feedback=0.35, wet=0.3, repeats=6, lp_hz=4500.0, hp_hz=250.0, circular=False,
         pingpong=False):
    """Feedback-style delay rendered as a sum of progressively darker taps."""
    d = N(delay_s)
    n = x.shape[0]
    out = x.copy() if circular else pad_to(x, n + d * repeats)
    tap = x.copy()
    shape = lambda f: m_lp(f, lp_hz, 1) * m_hp(f, hp_hz, 1)
    for k in range(1, repeats + 1):
        tap = fft_filter(tap, shape, circular=circular)
        g = wet * feedback ** (k - 1)
        src = tap
        if pingpong and tap.ndim == 2:
            src = tap[:, ::-1] if k % 2 else tap
        if circular:
            out += g * np.roll(src, k * d, axis=0)
        else:
            out[k * d:k * d + n] += g * src
    return out


# =============================================================================================
# Dynamics
# =============================================================================================


def saturate(x, drive=2.0, mix=1.0, asym=0.0):
    y = (np.tanh(drive * x + asym) - math.tanh(asym)) / math.tanh(drive)
    return mix * y + (1.0 - mix) * x


def _detector(x):
    return np.max(np.abs(x), axis=1) if x.ndim == 2 else np.abs(x)


def compressor(x, thresh_db=-18.0, ratio=3.0, attack=0.005, release=0.1, knee_db=6.0, makeup_db=0.0,
               block=32):
    """Feed-forward peak compressor with soft knee (block-rate envelope, sample-rate gain)."""
    n = x.shape[0]
    a = _detector(x)
    nb = (n + block - 1) // block
    det = np.max(pad_to(a, nb * block).reshape(nb, block), axis=1)
    lvl = 20.0 * np.log10(det + 1e-9)
    over = lvl - thresh_db
    slope = 1.0 - 1.0 / ratio
    gr = np.where(over <= -knee_db / 2, 0.0,
                  np.where(over >= knee_db / 2, over * slope, slope * (over + knee_db / 2) ** 2 / (2 * knee_db)))
    ca = math.exp(-block / (attack * SR))
    cr = math.exp(-block / (release * SR))
    g = 0.0
    sm = []
    for v in gr.tolist():
        c = ca if v > g else cr
        g = c * g + (1.0 - c) * v
        sm.append(g)
    gain_db = makeup_db - np.asarray(sm)
    gs = dbamp(np.interp(np.arange(n), (np.arange(nb) + 0.5) * block, gain_db))
    return x * (gs[:, None] if x.ndim == 2 else gs)


def limiter(x, ceiling_db=-1.0, lookahead=0.002, release=0.08):
    """Look-ahead brick-wall limiter (no overs by construction, then a safety clip)."""
    n = x.shape[0]
    c = float(dbamp(ceiling_db))
    req = np.minimum(1.0, c / (_detector(x) + 1e-12))
    B = max(4, N(lookahead))
    nb = (n + B - 1) // B
    bm = np.min(np.concatenate([req, np.ones(nb * B - n)]).reshape(nb, B), axis=1)
    fwd = np.minimum(bm, np.concatenate([bm[1:], [1.0]]))
    rc = math.exp(-B / (release * SR))
    g = 1.0
    sm = []
    for v in fwd.tolist():
        g = min(v, 1.0 - (1.0 - g) * rc)
        sm.append(g)
    gs = np.repeat(np.asarray(sm), B)[:n]
    cs = np.cumsum(np.concatenate([np.full(B, gs[0]), gs]))
    gs = (cs[B:] - cs[:-B]) / B
    y = x * (gs[:, None] if x.ndim == 2 else gs)
    return np.clip(y, -c, c)


def process_circular(x, fn, reps=3):
    """Apply a stateful process to a loop as if it had been playing forever."""
    L = x.shape[0]
    y = fn(np.concatenate([x] * reps, axis=0))
    return y[(reps - 1) * L: reps * L]


# =============================================================================================
# Loudness (ITU-R BS.1770-4, K-weighted, gated)
# =============================================================================================


def _kweight_mag(f):
    """|H| of the BS.1770 K-weighting pre-filter (shelf + RLB high-pass) at 48 kHz."""
    z = np.exp(-1j * TWO_PI * np.asarray(f) / SR)
    b1 = [1.53512485958697, -2.69169618940638, 1.19839281085285]
    a1 = [1.0, -1.69065929318241, 0.73248077421585]
    b2 = [1.0, -2.0, 1.0]
    a2 = [1.0, -1.99004745483398, 0.99007225036621]
    h1 = (b1[0] + b1[1] * z + b1[2] * z * z) / (a1[0] + a1[1] * z + a1[2] * z * z)
    h2 = (b2[0] + b2[1] * z + b2[2] * z * z) / (a2[0] + a2[1] * z + a2[2] * z * z)
    return np.abs(h1 * h2)


def loudness_lufs(x):
    """Integrated loudness (LUFS) with absolute (-70) and relative (-10 LU) gating."""
    a = as2d(x)
    if a.shape[0] < N(0.4):
        a = pad_to(a, N(0.4))
    y = fft_filter(a, _kweight_mag, pad=0.0)
    B, H = N(0.4), N(0.1)
    nblk = 1 + (y.shape[0] - B) // H
    cs = np.concatenate([np.zeros((1, y.shape[1])), np.cumsum(y ** 2, axis=0)])
    starts = np.arange(nblk) * H
    ms = (cs[starts + B] - cs[starts]) / B            # per block, per channel
    z = np.sum(ms, axis=1)
    lk = -0.691 + 10.0 * np.log10(z + 1e-20)
    g = z[lk > -70.0]
    if g.size == 0:
        return -100.0
    rel = -0.691 + 10.0 * math.log10(float(np.mean(g))) - 10.0
    g2 = z[(lk > -70.0) & (lk > rel)]
    return -0.691 + 10.0 * math.log10(float(np.mean(g2)) + 1e-20)


def true_peak_db(x, os=4):
    """Approximate true peak (dBTP) by FFT oversampling."""
    a = as2d(x)
    n = a.shape[0]
    X = np.fft.rfft(a, axis=0)
    y = np.fft.irfft(X, n * os, axis=0) * os
    return amp2db(np.max(np.abs(y)))


# =============================================================================================
# Finishing helpers
# =============================================================================================


def trim_lead(x, thresh_rel_db=-50.0, preroll=0.0):
    a = _detector(x)
    thr = a.max() * float(dbamp(thresh_rel_db))
    idx = int(np.argmax(a > thr))
    if preroll > 0:
        idx = max(0, idx - N(preroll))
    return x[idx:]


def trim_tail(x, thresh_rel_db=-66.0):
    a = _detector(x)
    above = np.nonzero(a > a.max() * float(dbamp(thresh_rel_db)))[0]
    return x[: above[-1] + 1] if above.size else x


def finalize_oneshot(x, peak_db=-1.0, max_len=None, fade_out=0.03, lead_db=-50.0, preroll=0.0,
                     fade_in=0.0003, limit_db=None):
    """One-shot mastering: DC block, trim leading silence, trim/cap the tail, fade out, optional
    peak limiting (raises perceived loudness of very transient material), normalize."""
    x = dc_block(x, 12.0)
    x = trim_lead(x, lead_db, preroll)
    x = trim_tail(x, -66.0)
    if max_len is not None and x.shape[0] > N(max_len):
        x = x[: N(max_len)]
    x = fade(x, fade_in, min(fade_out, x.shape[0] / SR * 0.5))
    if limit_db is not None:
        x = limiter(normalize(x, peak_db + limit_db), peak_db, 0.0015, 0.06)
    return normalize(x, peak_db)


def seamless_xfade(y, L, X):
    """Signal of length >= L+X -> exactly loopable length L by equal-power cross-fading its
    overhang [L, L+X) into its start [0, X)."""
    out = y[:L].copy()
    th = np.linspace(0.0, 0.5 * np.pi, X, endpoint=False)
    w_in, w_out = np.sin(th), np.cos(th)
    if y.ndim == 2:
        w_in, w_out = w_in[:, None], w_out[:, None]
    out[:X] = y[:X] * w_in + y[L:L + X] * w_out
    return out


def write_wav(path, x, seed=0):
    x = np.asarray(x, dtype=np.float64)
    if not np.all(np.isfinite(x)):
        raise ValueError("non-finite samples in " + path)
    ch = 1 if x.ndim == 1 else x.shape[1]
    r = np.random.default_rng(seed)
    dither = (r.random(x.shape) - r.random(x.shape)) * (x != 0.0)  # TPDF +-1 LSB, none on digital silence
    q = np.clip(np.round(x * 32767.0 + dither), -32768, 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(q.tobytes())


def read_wav(path):
    with wave.open(path, "rb") as w:
        sr, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
        x = np.frombuffer(w.readframes(n), dtype="<i2").astype(np.float64) / 32768.0
    return (x.reshape(-1, ch) if ch > 1 else x), sr


# =============================================================================================
# Rooms
# =============================================================================================

_IR_CACHE = {}


def ir_cached(key, **kw):
    if key not in _IR_CACHE:
        _IR_CACHE[key] = reverb_ir(rng_for("ir_" + key), **kw)
    return _IR_CACHE[key]


def rink_ir():
    """Short mono rink-level room (ice + boards + glass): seats close-up SFX in the space."""
    return ir_cached("rink", rt60=1.1, length=0.8, predelay=0.012, stereo=False,
                     damping=(1.0, 0.9, 0.65, 0.4))


def arena_ir_mono():
    return ir_cached("arena_m", rt60=2.0, length=1.8, predelay=0.03, stereo=False)


def arena_ir():
    """Big stereo hockey-arena hall (hard surfaces: ice, glass, concrete, a full bowl)."""
    return ir_cached("arena", rt60=2.6, length=3.0, predelay=0.035, stereo=True)
