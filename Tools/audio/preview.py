"""
ICE RIOT -- verification: level/loop analysis and PNG previews (waveforms, log spectrograms,
loop seams) rendered with numpy only (no matplotlib).
"""

import math
import struct
import zlib

import numpy as np

from .dsp import SR, N, peak, rms, amp2db, as2d, _detector, loudness_lufs, true_peak_db

FONT = {  # 5x7 bitmap glyphs, one int per row (bit 4 = leftmost pixel)
    "A": (14, 17, 17, 17, 31, 17, 17), "B": (30, 17, 17, 30, 17, 17, 30), "C": (14, 17, 16, 16, 16, 17, 14),
    "D": (28, 18, 17, 17, 17, 18, 28), "E": (31, 16, 16, 30, 16, 16, 31), "F": (31, 16, 16, 30, 16, 16, 16),
    "G": (14, 17, 16, 23, 17, 17, 15), "H": (17, 17, 17, 31, 17, 17, 17), "I": (14, 4, 4, 4, 4, 4, 14),
    "J": (7, 2, 2, 2, 2, 18, 12), "K": (17, 18, 20, 24, 20, 18, 17), "L": (16, 16, 16, 16, 16, 16, 31),
    "M": (17, 27, 21, 21, 17, 17, 17), "N": (17, 17, 25, 21, 19, 17, 17), "O": (14, 17, 17, 17, 17, 17, 14),
    "P": (30, 17, 17, 30, 16, 16, 16), "Q": (14, 17, 17, 17, 21, 18, 13), "R": (30, 17, 17, 30, 20, 18, 17),
    "S": (15, 16, 16, 14, 1, 1, 30), "T": (31, 4, 4, 4, 4, 4, 4), "U": (17, 17, 17, 17, 17, 17, 14),
    "V": (17, 17, 17, 17, 17, 10, 4), "W": (17, 17, 17, 21, 21, 21, 10), "X": (17, 17, 10, 4, 10, 17, 17),
    "Y": (17, 17, 17, 10, 4, 4, 4), "Z": (31, 1, 2, 4, 8, 16, 31),
    "0": (14, 17, 19, 21, 25, 17, 14), "1": (4, 12, 4, 4, 4, 4, 14), "2": (14, 17, 1, 2, 4, 8, 31),
    "3": (31, 2, 4, 2, 1, 17, 14), "4": (2, 6, 10, 18, 31, 2, 2), "5": (31, 16, 30, 1, 1, 17, 14),
    "6": (6, 8, 16, 30, 17, 17, 14), "7": (31, 1, 2, 4, 8, 8, 8), "8": (14, 17, 17, 14, 17, 17, 14),
    "9": (14, 17, 17, 15, 1, 2, 12), "_": (0, 0, 0, 0, 0, 0, 31), "-": (0, 0, 0, 31, 0, 0, 0),
    ".": (0, 0, 0, 0, 0, 12, 12), ":": (0, 12, 12, 0, 12, 12, 0), "(": (2, 4, 8, 8, 8, 4, 2),
    ")": (8, 4, 2, 2, 2, 4, 8), "/": (0, 1, 2, 4, 8, 16, 0), "%": (24, 25, 2, 4, 8, 19, 3),
    "=": (0, 0, 31, 0, 31, 0, 0), "+": (0, 4, 4, 31, 4, 4, 0), ",": (0, 0, 0, 0, 12, 4, 8),
    "'": (12, 4, 8, 0, 0, 0, 0), "!": (4, 4, 4, 4, 4, 0, 4), "?": (14, 17, 1, 2, 4, 0, 4),
    "#": (10, 10, 31, 10, 31, 10, 10), "|": (4, 4, 4, 4, 4, 4, 4),
}
INFERNO = np.array([[0, 0, 4], [40, 11, 84], [101, 21, 110], [159, 42, 99], [212, 72, 66], [245, 125, 21],
                    [250, 193, 39], [252, 255, 164]], dtype=np.float64)
BG, PANEL, GRID = (18, 19, 24), (28, 30, 38), (55, 58, 70)


def draw_text(img, x, y, text, color=(225, 225, 230), scale=1):
    for chh in text.upper():
        glyph = FONT.get(chh)
        if glyph:
            for row, bits in enumerate(glyph):
                for col in range(5):
                    if bits & (1 << (4 - col)):
                        img[y + row * scale:y + (row + 1) * scale, x + col * scale:x + (col + 1) * scale] = color
        x += 6 * scale


def write_png(path, img):
    img = np.ascontiguousarray(img, dtype=np.uint8)
    h, w, _ = img.shape
    raw = b"".join(b"\x00" + img[y].tobytes() for y in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                 + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def _mono(sig):
    return sig.mean(axis=1) if sig.ndim == 2 else sig


def draw_wave(img, x0, y0, w, h, sig, color=(90, 200, 255), zoom=False):
    img[y0:y0 + h, x0:x0 + w] = PANEL
    s = _mono(sig)
    cols = w
    mid = y0 + h // 2
    img[mid, x0:x0 + w] = GRID
    for lvl in (0.5,):
        img[mid - int(lvl * (h // 2 - 1)), x0:x0 + w] = (36, 38, 48)
        img[mid + int(lvl * (h // 2 - 1)), x0:x0 + w] = (36, 38, 48)
    scale = (1.0 / (peak(s) + 1e-12)) if zoom else 1.0
    edges = np.linspace(0, s.shape[0], cols + 1).astype(int)
    for c in range(cols):
        seg = s[edges[c]:max(edges[c + 1], edges[c] + 1)] * scale
        mn, mx = float(seg.min()), float(seg.max())
        r_ = math.sqrt(float(np.mean(seg ** 2)))
        a = int(np.clip(mid - mx * (h // 2 - 1), y0, y0 + h - 1))
        b = int(np.clip(mid - mn * (h // 2 - 1), y0, y0 + h - 1))
        img[a:b + 1, x0 + c] = tuple(int(v * 0.55) for v in color)
        a2 = int(np.clip(mid - r_ * (h // 2 - 1), y0, y0 + h - 1))
        b2 = int(np.clip(mid + r_ * (h // 2 - 1), y0, y0 + h - 1))
        img[a2:b2 + 1, x0 + c] = color


def draw_spec(img, x0, y0, w, h, sig, fmin=40.0, fmax=20000.0, dyn=80.0):
    """Log-frequency spectrogram (inferno colours), 0 dB = loudest bin of the clip."""
    img[y0:y0 + h, x0:x0 + w] = (0, 0, 4)
    s = _mono(sig)
    cols = w
    nfft = 2048
    xp = np.pad(s, (nfft // 2, nfft))
    centers = np.linspace(0, s.shape[0] - 1, cols).astype(int)
    idx = centers[:, None] + np.arange(nfft)[None, :]
    S = np.abs(np.fft.rfft(xp[idx] * np.hanning(nfft), axis=1))
    D = 20.0 * np.log10(S + 1e-9)
    D = np.clip((D - (D.max() - dyn)) / dyn, 0.0, 1.0)
    freqs = fmin * (fmax / fmin) ** (np.arange(h)[::-1] / (h - 1))
    bins = np.clip(np.round(freqs / (SR / nfft)).astype(int), 1, nfft // 2)
    V = D[:, bins].T
    pos = V * (INFERNO.shape[0] - 1)
    lo = np.floor(pos).astype(int)
    hi = np.minimum(lo + 1, INFERNO.shape[0] - 1)
    fr = (pos - lo)[..., None]
    img[y0:y0 + h, x0:x0 + cols] = (INFERNO[lo] * (1 - fr) + INFERNO[hi] * fr).astype(np.uint8)
    for f in (100, 1000, 10000):
        yy = y0 + int(round((h - 1) * (1 - math.log(f / fmin) / math.log(fmax / fmin))))
        img[yy, x0:x0 + w:4] = (120, 120, 140)


def preview_pairs(path, title, items, cw=520, chh=70):
    """One row per item: waveform (left) and spectrogram (right)."""
    pad, lab = 10, 26
    H = 34 + len(items) * (chh + lab + pad) + pad
    img = np.zeros((H, pad * 3 + 2 * cw, 3), dtype=np.uint8)
    img[:] = BG
    draw_text(img, pad, 10, title, (255, 170, 60), 2)
    for k, (label, sig, sub) in enumerate(items):
        y = 34 + k * (chh + lab + pad)
        draw_text(img, pad, y + 2, label, (235, 235, 240))
        draw_text(img, pad, y + 13, sub, (140, 145, 160))
        draw_wave(img, pad, y + lab, cw, chh, sig)
        draw_spec(img, 2 * pad + cw, y + lab, cw, chh, sig)
    write_png(path, img)


def preview_seams(path, loops):
    """+-20 ms around each loop's wrap point (end -> start), auto-zoomed; red line = seam."""
    pad, cw, chh = 10, 560, 90
    H = 34 + len(loops) * (chh + 36) + pad
    img = np.zeros((H, pad * 2 + cw, 3), dtype=np.uint8)
    img[:] = BG
    draw_text(img, pad, 10, "LOOP SEAMS (+-20 MS, AUTO-ZOOM)", (255, 170, 60), 2)
    for k, (name, sig, sub) in enumerate(loops):
        y = 34 + k * (chh + 36)
        w = N(0.02)
        seg = np.concatenate([sig[-w:], sig[:w]], axis=0)
        draw_text(img, pad, y + 2, name, (235, 235, 240))
        draw_text(img, pad, y + 13, sub, (140, 145, 160))
        draw_wave(img, pad, y + 26, cw, chh, seg, zoom=True)
        img[y + 26:y + 26 + chh, pad + cw // 2] = (230, 60, 60)
    write_png(path, img)


def preview_music(path, tracks):
    pad, cw = 10, 1180
    H = 34 + len(tracks) * (26 + 80 + 6 + 180 + 20) + pad
    img = np.zeros((H, pad * 2 + cw, 3), dtype=np.uint8)
    img[:] = BG
    draw_text(img, pad, 10, "MUSIC", (255, 170, 60), 2)
    y = 34
    for name, sig, sub, bars in tracks:
        draw_text(img, pad, y + 2, name, (235, 235, 240))
        draw_text(img, pad, y + 13, sub, (140, 145, 160))
        draw_wave(img, pad, y + 26, cw, 80, sig)
        for b in range(1, bars):
            img[y + 26:y + 106, pad + int(cw * b / bars)] = (70, 72, 90) if b % 4 else (120, 90, 60)
        draw_spec(img, pad, y + 112, cw, 180, sig)
        y += 26 + 80 + 6 + 180 + 20
    write_png(path, img)


def analyze(x, loop):
    a = as2d(x)
    info = {"peak_dbfs": round(amp2db(peak(a)), 2), "rms_dbfs": round(amp2db(rms(a)), 2),
            "lufs": round(loudness_lufs(a), 2),
            "clipped_samples": int(np.sum(np.abs(a) >= 32767.0 / 32768.0)),
            "dc_offset": round(float(np.max(np.abs(np.mean(a, axis=0)))), 5)}
    if loop:
        d = np.abs(np.diff(a, axis=0))
        typical = np.percentile(d, 99.9, axis=0) + 1e-9
        info["seam_jump_ratio"] = round(float(np.max(np.abs(a[0] - a[-1]) / typical)), 3)
        w = N(0.1)
        info["seam_rms_db_delta"] = round(abs(amp2db(rms(a[-w:])) - amp2db(rms(a[:w]))), 2)
    else:
        mag = _detector(a)
        info["onset_ms"] = round(1000.0 * int(np.argmax(mag > peak(a) * 0.0032)) / SR, 2)
    return info
