# výřez z dlaždic renderu kolem bodu: python nastroje/vyrez.py TILEDIR lat lon w h out.png [výška terénu]   (out = - vypíše potřebné dlaždice)
import sys, json, os; sys.path.insert(0, '.')
from PIL import Image
import geo
d, lat, lon, w, h, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), sys.argv[6]
info = json.load(open(os.path.join(d, 'info.json'))); I = geo.Image2D(info); T = info['tile']
x, y = geo.to_local(lon, lat)
px, py, _ = I.px(x, y, float(sys.argv[7]) if len(sys.argv) > 7 else 25)
x0, y0 = int(px - w / 2), int(py - h / 2)
i0, j0, i1, j1 = x0 // T, y0 // T, (x0 + w) // T, (y0 + h) // T
if out == '-': print(';'.join(f'{i}_{j}' for i in range(i0, i1 + 1) for j in range(j0, j1 + 1))); sys.exit()
big = Image.new('RGBA', ((i1 - i0 + 1) * T, (j1 - j0 + 1) * T), (0, 0, 0, 0))
for i in range(i0, i1 + 1):
    for j in range(j0, j1 + 1):
        f = os.path.join(d, f'{i}_{j}.png')
        if os.path.exists(f): big.alpha_composite(Image.open(f).convert('RGBA'), ((i - i0) * T, (j - j0) * T))
big.crop((x0 - i0 * T, y0 - j0 * T, x0 - i0 * T + w, y0 - j0 * T + h)).save(out)
