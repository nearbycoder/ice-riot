"""Compose several PNGs into one grid image (used to review preview renders).

blender -b --factory-startup -P Blender/contact_sheet.py -- out.png COLS CELL_W CELL_H img1.png img2.png ...
"""
import sys
import bpy
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
out, cols, cw, ch = argv[0], int(argv[1]), int(argv[2]), int(argv[3])
files = argv[4:]
rows = (len(files) + cols - 1) // cols
sheet = np.zeros((rows * ch, cols * cw, 4), dtype=np.float32)
sheet[..., 3] = 1.0
for i, f in enumerate(files):
    img = bpy.data.images.load(f)
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)
    # nearest-neighbour resample to the cell, preserving aspect
    s = min(cw / w, ch / h)
    nw, nh = max(1, int(w * s)), max(1, int(h * s))
    ys = (np.arange(nh) / s).astype(int).clip(0, h - 1)
    xs = (np.arange(nw) / s).astype(int).clip(0, w - 1)
    cell = px[ys][:, xs]
    r, c = divmod(i, cols)
    # image rows are bottom-up in Blender; place cells so the first image is top-left
    y0 = (rows - 1 - r) * ch + (ch - nh) // 2
    x0 = c * cw + (cw - nw) // 2
    sheet[y0:y0 + nh, x0:x0 + nw] = cell
    bpy.data.images.remove(img)
out_img = bpy.data.images.new("sheet", cols * cw, rows * ch, alpha=True)
out_img.pixels.foreach_set(sheet.ravel())
out_img.filepath_raw = out
out_img.file_format = "PNG"
out_img.save()
print("SHEET", out)
