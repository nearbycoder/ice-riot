"""Stack animation frame strips vertically: blender -b -P Blender/strip_sheet.py -- out.png a.png b.png ..."""
import sys
import bpy
import numpy as np
argv = sys.argv[sys.argv.index("--") + 1:]
out, files = argv[0], argv[1:]
imgs = []
for f in files:
    im = bpy.data.images.load(f)
    w, h = im.size
    a = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(a)
    imgs.append(a.reshape(h, w, 4))
W = max(i.shape[1] for i in imgs)
rows = []
for a in imgs:
    if a.shape[1] < W:
        pad = np.zeros((a.shape[0], W - a.shape[1], 4), np.float32)
        pad[..., 3] = 1
        a = np.concatenate([a, pad], 1)
    rows.append(a)
sheet = np.concatenate(rows[::-1], axis=0)
o = bpy.data.images.new("s", sheet.shape[1], sheet.shape[0], alpha=True)
o.pixels.foreach_set(sheet.ravel())
o.filepath_raw = out
o.file_format = "PNG"
o.save()
print("SHEET", out)
