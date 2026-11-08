# směr hřebene šikmých střech z laseru DMP 1G: v trojúhelníkové střeše výška závisí na vzdálenosti od hřebene, ne na poloze podél něj
# -> assets/hrebeny.json (id budovy -> 'L' hřeben podél delší strany, 'S' podél kratší); spouštět po dmp_fetch.py z kořene repa
import glob, json, sys
from multiprocessing import Pool
import numpy as np, laspy, shapely, pyarrow.parquet as pq
from pyproj import Transformer
T = Transformer.from_crs(4326, 5514, always_xy=True)
B = {}
for f in sorted(glob.glob('data*/building.parquet')):
    for r in pq.read_table(f, columns=['id', 'geometry']).to_pylist():
        B.setdefault(r['id'], r['geometry'])
ids = list(B)
P = shapely.make_valid(shapely.transform(shapely.from_wkb([B[i] for i in ids]), lambda c: np.column_stack(T.transform(c[:, 0], c[:, 1]))))


def r2(x, z):
    """kolik rozptylu výšky vysvětlí přímka podle x"""
    if x.std() < 1e-6 or z.std() < 1e-6: return 0.0
    return float(np.corrcoef(x, z)[0, 1] ** 2)


def ridge(poly, xyz):
    """'L' / 'S' / None podle toho, jestli výška klesá od osy napříč delší, nebo kratší strany"""
    o = poly.minimum_rotated_rectangle
    if o.geom_type != 'Polygon': return None, 0, 0
    c = np.array(o.exterior.coords)[:3]; e1, e2 = c[1] - c[0], c[2] - c[1]
    if np.linalg.norm(e1) < np.linalg.norm(e2): e1, e2 = e2, e1
    u, v = e1 / np.linalg.norm(e1), e2 / np.linalg.norm(e2); m = np.array(o.centroid.coords[0])
    d = xyz[:, :2] - m; a, b, z = np.abs(d @ u), np.abs(d @ v), xyz[:, 2]
    return ('L', 'S')[r2(a, z) > r2(b, z)], r2(b, z), r2(a, z)


def sheet(f):
    l = laspy.read(f); C = np.array(l.classification); m = C == 6
    if not m.any(): return {}
    X, Y, Z = np.array(l.x)[m], np.array(l.y)[m], np.array(l.z)[m]
    pi, ti = shapely.STRtree(shapely.points(X, Y)).query(P, predicate='contains')
    out = {}
    o = np.argsort(pi); pi, ti = pi[o], ti[o]
    u, st = np.unique(pi, return_index=True); st = list(st) + [len(pi)]
    for j, k in enumerate(u):
        t = ti[st[j]:st[j + 1]]
        out[int(k)] = np.column_stack([X[t], Y[t], Z[t]]).tolist()
    return out


if __name__ == '__main__':
    acc = {}
    with Pool(4) as p:
        for o in p.imap_unordered(sheet, sorted(glob.glob('build/dmp/*.laz'))):
            for k, v in o.items(): acc.setdefault(k, []).extend(v)
    res = {}; stat = {'L': 0, 'S': 0, 'nejisté': 0}
    for k, v in acc.items():
        a = np.array(v)
        if len(a) < 20 or P[k].area < 40: continue
        if np.percentile(a[:, 2], 90) - np.percentile(a[:, 2], 10) < 1.0: continue          # plochá
        w, rl, rs = ridge(P[k], a)
        if w is None: continue
        best, other = (rl, rs) if w == 'L' else (rs, rl)
        if best < 0.45 or best - other < 0.2: stat['nejisté'] += 1; continue
        res[ids[k]] = w; stat[w] += 1
    json.dump(res, open('assets/hrebeny.json', 'w'), separators=(',', ':'))
    print(stat)
