"""Založí nové město: najde hranici obce, rozdělí ji na čtverce 2,3 km a zapíše mesto.json.

python novy_mesto.py "Chrastava"                 # hranice obce z OpenStreetMap (Nominatim)
python novy_mesto.py "Chrastava" --max 4         # jen 4 čtverce nejblíž středu (rychlý první pokus)
python novy_mesto.py "Praha 6" --dotaz "Praha 6, Česko"

Čtverec patří do mapy, když v něm leží aspoň 5 % jeho plochy z území obce. Mřížka se posune tak,
aby čtverců bylo co nejméně. Nulová výška terénu a spodek řezu se změří z výškového modelu Terrarium.
Texty v mesto.json (titulek, popis) si potom uprav ručně, hlavně rod: Izometrický / Izometrická / Izometrické.
"""
import io, json, math, re, sys, urllib.parse, urllib.request
import numpy as np, shapely
from PIL import Image

args = sys.argv[1:]
if not args or args[0].startswith('-'): sys.exit(__doc__)
NAZEV = args[0]
opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
DOTAZ = opt('--dotaz', f'{NAZEV}, Česko')
MAX = int(opt('--max', 0))
HALF = 1150.0
UA = {'User-Agent': 'izomapa/1.0 (https://github.com/adamklatovsky/izomapa)'}


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()


# 1) hranice obce
q = urllib.parse.urlencode({'q': DOTAZ, 'format': 'json', 'polygon_geojson': 1, 'limit': 8, 'countrycodes': 'cz'})
res = json.loads(get('https://nominatim.openstreetmap.org/search?' + q))
res = [r for r in res if r.get('geojson', {}).get('type') in ('Polygon', 'MultiPolygon')]
if not res: sys.exit(f'Hranici „{DOTAZ}“ jsem nenašel. Zkus --dotaz s přesnějším názvem obce.')
res.sort(key=lambda r: (r.get('class') != 'boundary', -float(r.get('importance') or 0)))
hit = res[0]
area_ll = shapely.geometry.shape(hit['geojson'])
print('obec:', hit['display_name'])

# 2) lokální metry kolem těžiště
c = area_ll.centroid
KX, KY = math.cos(math.radians(c.y)) * 111320.0, 110574.0
loc = shapely.transform(area_ll, lambda p: np.column_stack(((p[:, 0] - c.x) * KX, (p[:, 1] - c.y) * KY)))
print(f'rozloha {loc.area / 1e6:.1f} km²')


def grid(ox, oy):
    """čtverce (i, j) s posunem mřížky (ox, oy), které pokrývají obec aspoň z 5 % své plochy"""
    x0, y0, x1, y1 = loc.bounds; S = 2 * HALF; out = []
    for i in range(math.floor((x0 - ox + HALF) / S), math.floor((x1 - ox + HALF) / S) + 1):
        for j in range(math.floor((y0 - oy + HALF) / S), math.floor((y1 - oy + HALF) / S) + 1):
            sq = shapely.box(ox + i * S - HALF, oy + j * S - HALF, ox + i * S + HALF, oy + j * S + HALF)
            if loc.intersection(sq).area >= 0.05 * S * S: out.append((i, j))
    return out


best = None
for ox in np.linspace(-HALF, HALF, 9)[:-1]:
    for oy in np.linspace(-HALF, HALF, 9)[:-1]:
        g = grid(ox, oy)
        if g and (best is None or len(g) < len(best[2])): best = (ox, oy, g)
ox, oy, cells = best
# čtverec (0, 0) = ten se středem obce (bod obce z OpenStreetMap, obvykle náměstí), jinak ten s největším územím
S = 2 * HALF
cover = lambda ij: loc.intersection(shapely.box(ox + ij[0] * S - HALF, oy + ij[1] * S - HALF, ox + ij[0] * S + HALF, oy + ij[1] * S + HALF)).area
px_, py_ = (float(hit['lon']) - c.x) * KX, (float(hit['lat']) - c.y) * KY
home = (math.floor((px_ - ox + HALF) / S), math.floor((py_ - oy + HALF) / S))
i0, j0 = home if home in cells else max(cells, key=cover)
cells = [(i - i0, j - j0) for i, j in cells]
cx, cy = ox + i0 * S, oy + j0 * S
if MAX: cells = sorted(cells, key=lambda ij: (ij[0] ** 2 + ij[1] ** 2, ij))[:MAX]
lon0, lat0 = c.x + cx / KX, c.y + cy / KY
print('čtverců', len(cells), cells)

# 3) výšky terénu (Terrarium z12) v obdélníku mapy
I = [a for a, _ in cells]; J = [b for _, b in cells]
x0, x1 = cx + min(I) * S - HALF, cx + max(I) * S + HALF
y0, y1 = cy + min(J) * S - HALF, cy + max(J) * S + HALF
lo0, lo1, la0, la1 = c.x + x0 / KX, c.x + x1 / KX, c.y + y0 / KY, c.y + y1 / KY


def tile(lon, lat, z):
    n = 2 ** z
    return int((lon + 180) / 360 * n), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)


z = 12; hs = []
tx0, ty0 = tile(lo0, la1, z); tx1, ty1 = tile(lo1, la0, z)
for tx in range(tx0, tx1 + 1):
    for ty in range(ty0, ty1 + 1):
        a = np.asarray(Image.open(io.BytesIO(get(f'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{tx}/{ty}.png'))).convert('RGB')).astype(float)
        n = 2 ** z; u = (tx + (np.arange(256) + 0.5) / 256) / n; v = (ty + (np.arange(256) + 0.5) / 256) / n
        lon = u * 360 - 180; lat = np.degrees(np.arctan(np.sinh(math.pi * (1 - 2 * v))))
        m = ((lat >= la0) & (lat <= la1))[:, None] & ((lon >= lo0) & (lon <= lo1))[None, :]     # jen obdélník mapy
        hs.append((a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768)[m])
h = np.concatenate(hs)
href = float(np.percentile(h, 25)); dno = math.floor(float(h.min()) - href - 30)
print(f'terén {h.min():.0f}–{h.max():.0f} m n. m., nula {href:.0f} m, spodek řezu {dno} m')

rod = 'á' if NAZEV.endswith('a') else 'é' if NAZEV[-1] in 'oeěí' else 'ý'
adj = f'Izometrick{rod}'
mesto = {
    'nazev': NAZEV,
    'titulek': f'{adj} {NAZEV}',
    'h1': [adj, NAZEV],
    'podtitul': f'{NAZEV} z otevřených dat, ve stylu SimCity 2000.',
    'popis': f'Izometrická pixel-art mapa: {NAZEV} ve stylu SimCity 2000. Roční období, den a noc, počasí a příběhy míst.',
    'url': '',
    'stred': [round(lon0, 6), round(lat0, 6)],
    'polovina': HALF,
    'ctverce': [list(ij) for ij in sorted(cells, key=lambda ij: (-ij[1], ij[0]))],
    'href': round(href, 1),
    'dno': dno,
    'mhd': {'gtfs': None, 'zdroj': None, 'zdroj_url': None},
    'vanocni_strom': None,
}
txt = json.dumps(mesto, ensure_ascii=False, indent=1)
txt = re.sub(r'\[\s*(-?[\d.]+),\s*(-?[\d.]+)\s*\]', r'[\1, \2]', txt)          # dvojice čísel na jeden řádek
open('mesto.json', 'w', encoding='utf-8').write(txt + '\n')
print('zapsáno mesto.json – zkontroluj texty (rod, název) a případně doplň MHD')
