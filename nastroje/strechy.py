# barvy střech z ortofota ČÚZK (CC BY 4.0): stáhne snímky po 0,4 m/px a pro každou budovu spočítá barvu střechy
# -> build/orto04/ (dlaždice), assets/strechy_orto.json (id budovy -> [r, g, b]); prep.py ji použije místo náhodné barvy
# spouštět z kořene repa: python nastroje/strechy.py   (stahuje se jednou, po přerušení pokračuje)
import glob, json, os, subprocess, sys; sys.path.insert(0, '.')
import numpy as np, geo, pyarrow.parquet as pq, shapely
from PIL import Image, ImageDraw
Image.MAX_IMAGE_PIXELS = None
D = 'build/orto04/'; os.makedirs(D, exist_ok=True)
M, T = 0.4, 1500
X0, Y0, X1, Y1 = geo.extent(geo.MARGIN + 20)
W, H = int((X1 - X0) / M), int((Y1 - Y0) / M)


def tile(tx, ty):
    f = f'{D}{tx}_{ty}.jpg'
    for _ in range(3):
        try:
            return np.asarray(Image.open(f).convert('RGB'))
        except OSError:
            w, h = min(T, W - tx), min(T, H - ty)
            lo0, la1 = geo.to_lonlat(X0 + tx * M, Y1 - ty * M); lo1, la0 = geo.to_lonlat(X0 + (tx + w) * M, Y1 - (ty + h) * M)
            subprocess.run(['curl', '-s', '-m', '120', '-o', f, 'https://ags.cuzk.gov.cz/arcgis1/services/ORTOFOTO/MapServer/WMSServer?SERVICE=WMS&VERSION=1.3.0'
                            f'&REQUEST=GetMap&LAYERS=0&STYLES=&CRS=EPSG:4326&BBOX={la0},{lo0},{la1},{lo1}&WIDTH={w}&HEIGHT={h}&FORMAT=image/jpeg'])
    return None


cache = {}
def tile_c(k):
    if k not in cache:
        if len(cache) > 12: cache.pop(next(iter(cache)))
        cache[k] = tile(*k)
    return cache[k]


def crop(x0, y0, x1, y1):
    out = np.zeros((y1 - y0, x1 - x0, 3), np.uint8)
    for ty in range(y0 // T * T, y1, T):
        for tx in range(x0 // T * T, x1, T):
            a = tile_c((tx, ty))
            if a is None: continue
            sx, sy = max(x0, tx), max(y0, ty); ex, ey = min(x1, tx + a.shape[1]), min(y1, ty + a.shape[0])
            if ex > sx and ey > sy: out[sy - y0:ey - y0, sx - x0:ex - x0] = a[sy - ty:ey - ty, sx - tx:ex - tx]
    return out


def roof_color(px):
    """barva střechy z pixelů uvnitř půdorysu: bez zeleně (koruny stromů) a stínů, medián horní části jasu"""
    r, g, b = px[:, 0].astype(int), px[:, 1].astype(int), px[:, 2].astype(int)
    keep = ~((g > r + 5) & (g > b + 5))
    if keep.mean() < 0.45: return None
    q = px[keep]; L = q.mean(1); lo, hi = np.percentile(L, 35), np.percentile(L, 85)
    q = q[(L >= lo) & (L <= hi)]
    if len(q) < 10 or q.mean() < 28: return None
    return [int(v) for v in np.median(q, axis=0)]


def in_shade(c):
    """střecha celá ve stínu je tmavá a do modra (stín svítí obloha): skutečnou barvu nevidíme"""
    return c.mean() < 50 or (c.mean() < 90 and c[2] - c[0] > 25)


def tone(res):
    """snímek má barevný nádech: vyvážit podle téměř neutrálních střech, pak přidat sytost, aby barvy seděly k vzhledu mapy"""
    a = np.array(list(res.values()), float)
    neutral = a[(a.max(1) - a.min(1)) / a.max(1) < 0.18]
    gain = neutral.mean() / np.median(neutral, axis=0) if len(neutral) >= 20 else np.ones(3)
    out = {}
    for k, v in res.items():
        c = np.array(v, float) * gain
        c = np.clip((c - HAZE) * 255 / (255 - HAZE), 0, 255); g = c.mean()   # odečíst opar: ortofoto ČÚZK je světlé a zamlžené
        c = np.clip((g + (c - g) * SAT) * VAL, 0, 255)
        if not in_shade(c): out[k] = [int(round(x)) for x in c]
    return out


SAT, VAL, HAZE = 2.3, 0.86, 32        # vyzkoušeno v Liberci proti Mapy.cz: s 1,45 / 0,92 bez odečtení oparu vycházely červené střechy lososové
if __name__ == '__main__':
    for ty in range(0, H, T):
        for tx in range(0, W, T):
            if tile(tx, ty) is None: print('chybí dlaždice', tx, ty)
        print('ortofoto', ty, H, flush=True)
    res, seen = {}, set()
    for f in sorted(glob.glob('data*/building.parquet')):
        if 'data_all' in f: continue
        for r in pq.read_table(f, columns=['id', 'geometry']).to_pylist():
            if r['id'] in seen: continue
            seen.add(r['id'])
            g = shapely.from_wkb(r['geometry'])
            xy = [geo.to_local(lo, la) for lo, la in (g.exterior.coords if g.geom_type == 'Polygon' else max(g.geoms, key=lambda q: q.area).exterior.coords)]
            p = shapely.Polygon(xy).buffer(-0.8)
            if p.is_empty or p.area < 8: continue
            if p.geom_type != 'Polygon': p = max(p.geoms, key=lambda q: q.area)
            c = [((x - X0) / M, (Y1 - y) / M) for x, y in p.exterior.coords]
            xs, ys = zip(*c); x0, y0, x1, y1 = int(min(xs)), int(min(ys)), int(max(xs)) + 1, int(max(ys)) + 1
            if x0 < 0 or y0 < 0 or x1 > W or y1 > H: continue
            m = Image.new('L', (x1 - x0, y1 - y0)); ImageDraw.Draw(m).polygon([(a - x0, b - y0) for a, b in c], fill=255)
            px = crop(x0, y0, x1, y1)[np.asarray(m) > 0]
            if len(px) < 30: continue
            col = roof_color(px)
            if col: res[r['id']] = col
    json.dump(tone(res), open('assets/strechy_orto.json', 'w'), separators=(',', ':'))
    print('budov', len(seen), 'barva střechy', len(res))
