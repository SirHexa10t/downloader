#!/usr/bin/env python3

# from PIL import Image
# import os, sys, math

# folder = sys.argv[1]
# script_dir = os.path.dirname(os.path.abspath(__file__))
# icon_dir = os.path.join(script_dir, "icons")

# files = sorted(f for f in os.listdir(folder) if f.lower().endswith('.png'))
# images = [Image.open(os.path.join(folder, f)).convert('RGBA') for f in files]

# tile = images[0].size[0]
# icon_size = tile // 3

# icons = {}
# if os.path.isdir(icon_dir):
#     for ic in os.listdir(icon_dir):
#         if ic.lower().endswith('.png'):
#             name = os.path.splitext(ic)[0]
#             icons[name] = Image.open(os.path.join(icon_dir, ic)).convert('RGBA').resize((icon_size, icon_size))

# cols = math.ceil(math.sqrt(len(images)))
# rows = math.ceil(len(images) / cols)

# grid = Image.new('RGBA', (cols * tile, rows * tile), (0, 0, 0, 0))
# for i, img in enumerate(images):
#     r, c = divmod(i, cols)
#     x, y = c * tile, r * tile
#     grid.paste(img, (x, y))
#     for name, icon in icons.items():
#         if name in files[i]:
#             grid.paste(icon, (x + tile - icon_size, y), icon)
#             break

# name = os.path.basename(os.path.normpath(folder))
# out = os.path.join(os.getcwd(), f"{name}_grid.png")
# grid.save(out)
# print(f"{len(images)} images → {cols}x{rows} grid ({cols*tile}x{rows*tile}px) → {out}")




from PIL import Image
import os, sys, math

folder = sys.argv[1]
script_dir = os.path.dirname(os.path.abspath(__file__))
icon_dir = os.path.join(script_dir, "icons")

files = sorted(f for f in os.listdir(folder) if f.lower().endswith('.png'))
images = {f: Image.open(os.path.join(folder, f)).convert('RGBA') for f in files}

tile = list(images.values())[0].size[0]
icon_size = tile // 3

icons = {}
if os.path.isdir(icon_dir):
    for ic in sorted(os.listdir(icon_dir)):
        if ic.lower().endswith('.png'):
            name = os.path.splitext(ic)[0]
            icons[name] = Image.open(os.path.join(icon_dir, ic)).convert('RGBA').resize((icon_size, icon_size))

# Order files: by icon match first, then remaining
ordered = []
used = set()
for name in icons:
    for f in files:
        if name in f and f not in used:
            ordered.append((f, name))
            used.add(f)
for f in files:
    if f not in used:
        ordered.append((f, None))

cols = math.ceil(math.sqrt(len(ordered)))
rows = math.ceil(len(ordered) / cols)

grid = Image.new('RGBA', (cols * tile, rows * tile), (0, 0, 0, 0))
for i, (f, icon_name) in enumerate(ordered):
    r, c = divmod(i, cols)
    x, y = c * tile, r * tile
    grid.paste(images[f], (x, y))
    if icon_name:
        grid.paste(icons[icon_name], (x + tile - icon_size, y), icons[icon_name])

name = os.path.basename(os.path.normpath(folder))
out = os.path.join(os.getcwd(), f"{name}_grid.png")
grid.save(out)
print(f"{len(ordered)} images → {cols}x{rows} grid ({cols*tile}x{rows*tile}px) → {out}")



