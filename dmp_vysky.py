# změří budovy z mračna bodů DMP 1G (body tříd 2 terén, 6 budova): python dmp_vysky.py  (po dmp_fetch.py)
# build/dmp_vysky.json: id -> [plocha, bodů, medián nad terénem, p90 nad terénem, patra OSM, výška v datech, typ, lat, lon]
# assets/dmp_vysky.json: id -> [medián, p90] jen u spolehlivých měření (ty použije prep.py), build/dmp_kontrola.csv: zbytek
import glob, json, math, sys
from multiprocessing import Pool
import numpy as np, laspy, shapely, pyarrow.parquet as pq
from shapely import wkb
from pyproj import Transformer
T = Transformer.from_crs(4326, 5514, always_xy=True)
def krovak(g):
    return shapely.transform(g, lambda c: np.column_stack(T.transform(c[:, 0], c[:, 1])))
B = {}
for f in sorted(glob.glob('data*/building.parquet')):
    for r in pq.read_table(f, columns=['id', 'geometry', 'height', 'num_floors', 'class']).to_pylist():
        if r['id'] in B: continue
        B[r['id']] = r
ids = list(B); P = krovak(shapely.from_wkb([B[i]['geometry'] for i in ids])); P = shapely.make_valid(P)
RING = shapely.difference(shapely.buffer(P, 14), shapely.buffer(P, 1))
def sheet(f):
    l = laspy.read(f); X, Y, Z, C = np.array(l.x), np.array(l.y), np.array(l.z), np.array(l.classification); out = {}
    for cls, polys, key in ((6, P, 0), (2, RING, 1)):
        m = C == cls
        if not m.any(): continue
        tree = shapely.STRtree(shapely.points(X[m], Y[m])); zz = Z[m]
        pi, ti = tree.query(polys, predicate='contains')
        order = np.argsort(pi); pi, ti = pi[order], ti[order]
        for k, g in zip(*np.unique(pi, return_index=True)):
            pass
        u, st = np.unique(pi, return_index=True); st = list(st) + [len(pi)]
        for j, k in enumerate(u): out.setdefault(int(k), [[], []])[key] = zz[ti[st[j]:st[j + 1]]].tolist()
    return out
if __name__ == '__main__':
    fs = sorted(glob.glob('build/dmp/*.laz')) if '--znovu' not in sys.argv else []; acc = {}   # --znovu: jen znovu vyhodnotit build/dmp_vysky.json
    with Pool(8) as p:
        for i, o in enumerate(p.imap_unordered(sheet, fs)):
            for k, (a, b) in o.items():
                q = acc.setdefault(k, [[], []]); q[0] += a; q[1] += b
            print(i + 1, len(fs), flush=True)
    res = {}
    for k, (a, b) in acc.items():
        r = B[ids[k]]; c = shapely.from_wkb(r['geometry']).centroid
        if len(a) >= 1 and len(b) >= 2:
            g0 = float(np.median(b)); res[ids[k]] = [round(float(P[k].area)), len(a), round(float(np.median(a)) - g0, 1), round(float(np.percentile(a, 90)) - g0, 1), r['num_floors'], round(r['height'], 1) if r['height'] else None, r['class'], round(c.y, 6), round(c.x, 6)]
    if '--znovu' in sys.argv: res = json.load(open('build/dmp_vysky.json'))
    json.dump(res, open('build/dmp_vysky.json', 'w')); print(len(B), 'budov', len(res), 'změřeno')
    import csv, os
    ok, bad = {}, []
    for k, (ar, n, med, p90, fl, hd, cl, la, lo) in res.items():
        why = ''
        if ar >= 80 and n < max(3, ar * .04): why = 'málo bodů'
        if med < 1.5 or med > 75: why = 'nesmyslná výška'
        # hustý laser má přednost před patry v OSM (ta bývají chybná, ověřeno na ortofotu); řídký je na kontrolu
        if fl and fl >= 3 and abs(med - fl * 2.9) > 6.5 and (med < 3 or n < ar * .4): why = why or 'nesedí na patra OSM'
        if p90 - med > 8 and ar > 300: why = why or 'více výšek pod jedním půdorysem'
        if why: bad.append([why, cl or '', ar, n, med, p90, fl or '', la, lo, k])
        else: ok[k] = [med, p90]
    os.makedirs('assets', exist_ok=True)
    json.dump(ok, open('assets/dmp_vysky.json', 'w'), separators=(',', ':'))
    with open('build/dmp_kontrola.csv', 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f, delimiter=';'); w.writerow(['důvod', 'typ', 'plocha m2', 'bodů', 'medián', 'p90', 'patra OSM', 'lat', 'lon', 'id']); w.writerows(bad)
    print('použito', len(ok), 'ke kontrole', len(bad), '(build/dmp_kontrola.csv)')
