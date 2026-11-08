# les podle ortofota ČÚZK: stáhne letecké snímky celé mapy po 2 m/px a z nich masku korun stromů
# -> build/orto/ (dlaždice), build/orto_cele.jpg, build/les_maska.png + .json (prep.py: kde není koruna, je louka a žádné stromy)
# spouštět z kořene repa: python nastroje/les.py   (stahuje se jednou, ~1 min na čtverec)
import sys, os, json, subprocess; sys.path.insert(0, '.')
import numpy as np, geo
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
D = 'build/orto/'; os.makedirs(D, exist_ok=True)
M = 2.0
X0, Y0, X1, Y1 = geo.extent(geo.MARGIN + 20)
W, H = int((X1 - X0) / M), int((Y1 - Y0) / M); T = 1500
big = Image.new('RGB', (W, H))
for ty in range(0, H, T):
    for tx in range(0, W, T):
        w, h = min(T, W - tx), min(T, H - ty)
        lo0, la1 = geo.to_lonlat(X0 + tx * M, Y1 - ty * M); lo1, la0 = geo.to_lonlat(X0 + (tx + w) * M, Y1 - (ty + h) * M)
        f = f'{D}{tx}_{ty}.jpg'
        if not os.path.exists(f):
            subprocess.run(['curl', '-s', '-m', '120', '-o', f, 'https://ags.cuzk.gov.cz/arcgis1/services/ORTOFOTO/MapServer/WMSServer?SERVICE=WMS&VERSION=1.3.0'
                            f'&REQUEST=GetMap&LAYERS=0&STYLES=&CRS=EPSG:4326&BBOX={la0},{lo0},{la1},{lo1}&WIDTH={w}&HEIGHT={h}&FORMAT=image/jpeg'], check=True)
        big.paste(Image.open(f).convert('RGB'), (tx, ty))
        print('ortofoto', tx, ty, flush=True)
big.save('build/orto_cele.jpg', quality=85)
a = np.asarray(big).astype(np.int16); r, g, b = a[..., 0], a[..., 1], a[..., 2]; L = a.mean(2)
canopy = (g >= r - 4) & (g >= b - 8) & (L < 82)                 # koruny: tmavě zelené; louky a pole jsou světlejší


def box(x, k):
    p = np.pad(x.astype(np.float32), k + 1, mode='edge'); c = p.cumsum(0).cumsum(1); n = 2 * k + 1
    return (c[n:, n:] - c[:-n, n:] - c[n:, :-n] + c[:-n, :-n])[:x.shape[0], :x.shape[1]] / n / n


mask = box(canopy, 2) > 0.3                                      # vyhladit šum (stíny, tmavé střechy)
mask |= box(L > 250, 3) > 0.5                                    # bílá = mimo Česko (ortofoto chybí): stromy nechat podle dat
Image.fromarray((mask * 255).astype(np.uint8)).save('build/les_maska.png')
json.dump({'x0y1m': [X0, Y1, M]}, open('build/les_maska.json', 'w'))
print('maska lesa', W, H, f'koruny {mask.mean() * 100:.0f} %')
