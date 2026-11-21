"""ICE RIOT 2D drawing kit: numpy signed-distance shapes + Blender-rendered text masks.

Used for every flat texture (team crests, banners, board ads, ice markings, digits, face paint).

* Canvas pixels are float32 display (sRGB-encoded) values, rows bottom-up (Blender pixel order).
* Shapes are signed distance fields in canvas units (negative inside), turned into anti-aliased
  coverage with `cov()`.  Text is rendered by Eevee (orthographic, emission) into a coverage mask.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

import ir_env as eh  # noqa: E402

FONT_IMPACT = "/System/Library/Fonts/Supplemental/Impact.ttf"
FONT_DIN = "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf"
FONT_DIN_ALT = "/System/Library/Fonts/Supplemental/DIN Alternate Bold.ttf"
FONT_BLACK = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
FONT_ROUNDED = "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf"
FONT_ROCKWELL = "/System/Library/Fonts/Supplemental/Rockwell.ttc"
FONT_FUTURA = "/System/Library/Fonts/Supplemental/Futura.ttc"
FONT_COPPER = "/System/Library/Fonts/Supplemental/Copperplate.ttc"
FONT_TREBUCHET = "/System/Library/Fonts/Supplemental/Trebuchet MS Bold.ttf"
FONT_NARROW = "/System/Library/Fonts/Supplemental/Arial Narrow Bold.ttf"


def col(c, a=1.0):
    """'#hex' or tuple -> display RGB tuple."""
    if isinstance(c, str):
        return eh.srgb(c)
    return tuple(c[:3])


def shade(c, f):
    """Multiply a display color (lighten with f>1 toward white)."""
    c = col(c)
    if f >= 1.0:
        t = f - 1.0
        return tuple(x + (1 - x) * t for x in c)
    return tuple(x * f for x in c)


def mixc(a, b, t):
    a, b = col(a), col(b)
    return tuple(x + (y - x) * t for x, y in zip(a, b))


# ---------------------------------------------------------------------------
# Path helpers (lists of (x, y))
# ---------------------------------------------------------------------------
def bez(p0, c0, c1, p1, n=16):
    out = []
    for i in range(n):
        t = i / n
        u = 1 - t
        out.append((u ** 3 * p0[0] + 3 * u * u * t * c0[0] + 3 * u * t * t * c1[0] + t ** 3 * p1[0],
                    u ** 3 * p0[1] + 3 * u * u * t * c0[1] + 3 * u * t * t * c1[1] + t ** 3 * p1[1]))
    return out


def path(*segs, n=16):
    """path((p0,c0,c1,p1), (c0,c1,p1), ...) -> polyline; later segments start at the previous end."""
    pts = []
    cur = None
    for s in segs:
        if len(s) == 4:
            p0, c0, c1, p1 = s
        elif len(s) == 3:
            p0 = cur
            c0, c1, p1 = s
        elif len(s) == 1:          # straight line to point
            p0 = cur
            p1 = s[0]
            c0, c1 = p0, p1
            pts.append(p0)
            cur = p1
            continue
        pts.extend(bez(p0, c0, c1, p1, n))
        cur = p1
    return pts


def arc(cx, cy, r, a0, a1, n=48, rx=None, ry=None):
    rx = r if rx is None else rx
    ry = r if ry is None else ry
    return [(cx + rx * math.cos(a0 + (a1 - a0) * i / n), cy + ry * math.sin(a0 + (a1 - a0) * i / n))
            for i in range(n + 1)]


def mirror_x(pts, cx=0.0):
    """Close a left half outline (top -> bottom on the left side) into a symmetric polygon."""
    right = [(2 * cx - x, y) for x, y in reversed(pts)]
    return list(pts) + right


def xf(pts, s=1.0, dx=0.0, dy=0.0, rot=0.0, sx=None, sy=None):
    c, sn = math.cos(rot), math.sin(rot)
    sx = s if sx is None else sx
    sy = s if sy is None else sy
    out = []
    for x, y in pts:
        x, y = x * sx, y * sy
        out.append((x * c - y * sn + dx, x * sn + y * c + dy))
    return out


# ---------------------------------------------------------------------------
# Canvas
# ---------------------------------------------------------------------------
class Canvas:
    def __init__(self, W, H, rect=None, bg=None):
        self.W, self.H = int(W), int(H)
        if rect is None:
            asp = H / W
            rect = (-1.0, -asp, 1.0, asp)
        self.rect = rect
        x0, y0, x1, y1 = rect
        self.px = (x1 - x0) / W
        xs = x0 + (np.arange(W, dtype=np.float32) + 0.5) * self.px
        ys = y0 + (np.arange(H, dtype=np.float32) + 0.5) * ((y1 - y0) / H)
        self.X, self.Y = np.meshgrid(xs, ys)
        self.rgb = np.zeros((H, W, 3), np.float32)
        self.a = np.zeros((H, W), np.float32)
        if bg is not None:
            self.rgb[:] = col(bg)
            self.a[:] = 1.0

    # -- coverage ----------------------------------------------------------
    def cov(self, sd, soft=1.0):
        return np.clip(0.5 - sd / (self.px * soft), 0.0, 1.0).astype(np.float32)

    def put(self, cov, color, alpha=1.0):
        """Composite a coverage mask with a flat color or a per-pixel (H,W,3) color array."""
        a = (cov * alpha).astype(np.float32)
        if isinstance(color, np.ndarray) and color.ndim == 3:
            c = color
        else:
            c = np.array(col(color), np.float32)[None, None, :]
        out_a = a + self.a * (1 - a)
        num = c * a[..., None] + self.rgb * (self.a * (1 - a))[..., None]
        self.rgb = np.where(out_a[..., None] > 1e-6, num / np.maximum(out_a[..., None], 1e-6), self.rgb)
        self.a = out_a

    def fill(self, sd, color, alpha=1.0, grow=0.0, soft=1.0):
        self.put(self.cov(sd - grow, soft), color, alpha)

    def layer(self, sd, color, outlines=(), alpha=1.0):
        """outlines: [(width, color), ...] painted outermost first, then the fill."""
        for w, c in sorted(outlines, key=lambda t: -t[0]):
            self.fill(sd, c, alpha, grow=w)
        self.fill(sd, color, alpha)

    def multiply(self, cov, color, strength=1.0):
        c = np.array(col(color), np.float32)[None, None, :]
        k = (cov * strength)[..., None]
        self.rgb = self.rgb * (1 - k) + self.rgb * c * k

    def screen(self, cov, color, strength=1.0):
        c = np.array(col(color), np.float32)[None, None, :]
        k = (cov * strength)[..., None]
        scr = 1 - (1 - self.rgb) * (1 - c)
        self.rgb = self.rgb * (1 - k) + scr * k

    def lgrad(self, p0, p1, c0, c1):
        """Per-pixel linear gradient color array from p0 (c0) to p1 (c1)."""
        d = np.array(p1, np.float32) - np.array(p0, np.float32)
        t = ((self.X - p0[0]) * d[0] + (self.Y - p0[1]) * d[1]) / float(d.dot(d))
        t = np.clip(t, 0, 1)[..., None]
        a = np.array(col(c0), np.float32)
        b = np.array(col(c1), np.float32)
        return (a + (b - a) * t).astype(np.float32)

    def rgrad(self, c, r, c0, c1):
        t = np.clip(np.hypot(self.X - c[0], self.Y - c[1]) / r, 0, 1)[..., None]
        a = np.array(col(c0), np.float32)
        b = np.array(col(c1), np.float32)
        return (a + (b - a) * t).astype(np.float32)

    def rgba(self):
        out = np.zeros((self.H, self.W, 4), np.float32)
        out[..., :3] = self.rgb
        out[..., 3] = self.a
        return out

    def save(self, path, opaque=False):
        arr = self.rgba()
        if opaque:
            arr[..., 3] = 1.0
        return eh.save_png(arr, path)

    # -- shapes (signed distance, canvas units) ---------------------------
    def circle(self, cx, cy, r):
        return np.hypot(self.X - cx, self.Y - cy) - r

    def ellipse(self, cx, cy, rx, ry, rot=0.0):
        X, Y = self._local(cx, cy, rot)
        k = np.hypot(X / rx, Y / ry)
        return (k - 1.0) * min(rx, ry)

    def ring(self, cx, cy, r, w):
        return np.abs(np.hypot(self.X - cx, self.Y - cy) - r) - w * 0.5

    def box(self, cx, cy, hw, hh, r=0.0, rot=0.0):
        X, Y = self._local(cx, cy, rot)
        qx = np.abs(X) - hw + r
        qy = np.abs(Y) - hh + r
        return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r

    def seg(self, a, b, r):
        ax, ay = a
        bx, by = b
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy + 1e-12
        t = np.clip(((self.X - ax) * dx + (self.Y - ay) * dy) / L2, 0, 1)
        return np.hypot(self.X - (ax + t * dx), self.Y - (ay + t * dy)) - r

    def polyline(self, pts, r, closed=False):
        d = None
        n = len(pts)
        for i in range(n if closed else n - 1):
            s = self.seg(pts[i], pts[(i + 1) % n], r)
            d = s if d is None else np.minimum(d, s)
        return d

    def poly(self, pts):
        """Exact signed distance to a simple polygon."""
        P = np.asarray(pts, np.float64)
        if np.allclose(P[0], P[-1]):
            P = P[:-1]
        n = len(P)
        X = self.X.astype(np.float64)
        Y = self.Y.astype(np.float64)
        d = np.full(X.shape, 1e20)
        s = np.ones(X.shape)
        for i in range(n):
            vi = P[i]
            vj = P[i - 1]
            ex, ey = vj[0] - vi[0], vj[1] - vi[1]
            wx, wy = X - vi[0], Y - vi[1]
            L2 = ex * ex + ey * ey + 1e-18
            t = np.clip((wx * ex + wy * ey) / L2, 0, 1)
            bx, by = wx - ex * t, wy - ey * t
            d = np.minimum(d, bx * bx + by * by)
            c1 = Y >= vi[1]
            c2 = Y < vj[1]
            c3 = ex * wy > ey * wx
            flip = (c1 & c2 & c3) | (~c1 & ~c2 & ~c3)
            s = np.where(flip, -s, s)
        return (s * np.sqrt(d)).astype(np.float32)

    def _local(self, cx, cy, rot):
        X = self.X - cx
        Y = self.Y - cy
        if rot:
            c, s = math.cos(-rot), math.sin(-rot)
            X, Y = X * c - Y * s, X * s + Y * c
        return X, Y

    # -- text --------------------------------------------------------------
    def text(self, body, font=FONT_IMPACT, center=(0, 0), height=None, width=None, shear=0.0, spacing=1.0,
             rot=0.0, arc_r=None, arc_bottom=False, extrude_grow=0.0):
        """Coverage mask of a text string fitted to height (cap) and/or width, centered at `center`.
        arc_r: bend along a circle of that radius whose center is below (top arc) / above (bottom arc)."""
        return render_text_mask(self, body, font, center, height, width, shear, spacing, rot, arc_r, arc_bottom)

    def grow(self, cov, w):
        """Coverage mask dilated by w canvas units (for outlines around text masks)."""
        r = int(round(w / self.px))
        if r <= 0:
            return cov
        m = eh.dilate(cov, r)
        return np.clip(eh.box_blur(m, 1), 0, 1)

    def cov_sd(self, cov):
        """Turn a coverage mask into a crude sdf usable with fill()."""
        return (0.5 - cov) * self.px

    def stamp(self, img, center, width, rot=0.0, alpha=1.0):
        """Composite an RGBA image (bottom-up rows, straight alpha) scaled to `width` canvas units."""
        h, w = img.shape[:2]
        scale = width / w
        X, Y = self._local(center[0], center[1], rot)
        u = X / scale + w * 0.5
        v = Y / scale + h * 0.5
        inside = (u >= 0) & (u < w - 1) & (v >= 0) & (v < h - 1)
        u0 = np.clip(np.floor(u).astype(np.int64), 0, w - 2)
        v0 = np.clip(np.floor(v).astype(np.int64), 0, h - 2)
        fu = np.clip(u - u0, 0, 1)[..., None]
        fv = np.clip(v - v0, 0, 1)[..., None]
        pm = img.copy()
        pm[..., :3] *= pm[..., 3:4]
        s = (pm[v0, u0] * (1 - fu) * (1 - fv) + pm[v0, u0 + 1] * fu * (1 - fv) +
             pm[v0 + 1, u0] * (1 - fu) * fv + pm[v0 + 1, u0 + 1] * fu * fv)
        a = np.where(inside, s[..., 3], 0.0)
        c = s[..., :3] / np.maximum(s[..., 3:4], 1e-6)
        self.put(a.astype(np.float32), c.astype(np.float32), alpha)


_TEXT_N = [0]


def render_text_mask(cv, body, font, center, height, width, shear, spacing, rot, arc_r, arc_bottom):
    """Eevee flat render of a text mesh into the canvas' pixel grid -> coverage (H, W)."""
    scene_objs = list(bpy.context.scene.objects)
    hidden = []
    for o in scene_objs:
        if not o.hide_render:
            o.hide_render = True
            hidden.append(o)
    _TEXT_N[0] += 1
    mat = eh.flat_mat("__txt_white", (1, 1, 1))
    o = eh.text_obj("__txt%d" % _TEXT_N[0], body, 1.0, font=font, mat=mat, shear=shear, spacing=spacing,
                    resolution=24)
    eh.bake_obj(o)
    lo, hi = eh.mesh_bounds(o)
    w0, h0 = hi.x - lo.x, hi.y - lo.y
    s = None
    if width is not None and height is not None:
        s = min(width / w0, height / h0)
    elif width is not None:
        s = width / w0
    else:
        s = height / h0
    cx0, cy0 = (lo.x + hi.x) * 0.5, (lo.y + hi.y) * 0.5
    me = o.data
    cr, sr = math.cos(rot), math.sin(rot)
    if arc_r:
        # subdivide long edges so the bend stays smooth
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(me)
        for _ in range(3):
            long_edges = [e for e in bm.edges if e.calc_length() * s > arc_r * 0.03]
            if not long_edges:
                break
            bmesh.ops.subdivide_edges(bm, edges=long_edges, cuts=2, use_grid_fill=False)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        bm.to_mesh(me)
        bm.free()
    for v in me.vertices:
        x = (v.co.x - cx0) * s
        y = (v.co.y - cy0) * s
        if arc_r:
            if not arc_bottom:
                th = math.pi / 2 - x / arc_r
                rr = arc_r + y
                x, y = rr * math.cos(th), rr * math.sin(th) - arc_r
            else:
                th = -math.pi / 2 + x / arc_r
                rr = arc_r - y
                x, y = rr * math.cos(th), rr * math.sin(th) + arc_r
        else:
            x, y = x * cr - y * sr, x * sr + y * cr
        v.co = Vector((x + center[0], y + center[1], 0.0))
    me.update()
    x0, y0, x1, y1 = cv.rect
    eh.flat_scene(cv.W, cv.H, samples=8, transparent=True, filter_size=1.0)
    eh.ortho_camera((x0 + x1) * 0.5, (y0 + y1) * 0.5, x1 - x0)
    if cv.H > cv.W:
        bpy.context.scene.camera.data.sensor_fit = "VERTICAL"
        bpy.context.scene.camera.data.ortho_scale = y1 - y0
    img = eh.render_rgba("txt")
    bpy.data.objects.remove(o)
    for h in hidden:
        h.hide_render = False
    return img[..., 3].astype(np.float32)
