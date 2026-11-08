"""Trasa autobusu mezi zastávkami po silnicích z dat mapy (pro GTFS bez shapes.txt, např. IDS JMK).

Graf = vrcholy segmentů Overture (subtype road, jen sjízdné třídy), zhuštěné po 20 m; uzly se slévají podle souřadnic
zaokrouhlených na 0,5 m. Zastávka se přichytí k nejbližšímu uzlu do 80 m. Zastávka mimo mapu: po silnici k uzlu nejblíž k ní (okraj mapy),
dál rovně (to už prohlížeč nekreslí). Bez cesty vede úsek rovně.
"""
import heapq
import numpy as np
import pyarrow.parquet as pq
import shapely
from shapely.ops import transform
from geo import to_local

COST = {'motorway': 1.0, 'trunk': 1.0, 'primary': 1.0, 'secondary': 1.0, 'tertiary': 1.0,
        'unclassified': 1.2, 'residential': 1.2, 'living_street': 1.5, 'service': 2.0, 'unknown': 1.5}
SNAP = 80.0


class Graph:
    def __init__(self, parquet):
        t = pq.read_table(parquet, columns=['subtype', 'class', 'geometry']).to_pylist()
        self.xy, self.idx, self.adj = [], {}, []
        for r in t:
            c = COST.get(r['class'])
            if r['subtype'] != 'road' or c is None: continue
            g = transform(lambda x, y, z=None: to_local(x, y), shapely.from_wkb(r['geometry'])).segmentize(20.0)
            for ls in getattr(g, 'geoms', [g]):
                ids = [self.node(p) for p in ls.coords]
                for a, b in zip(ids, ids[1:]):
                    if a == b: continue
                    w = c * float(np.hypot(*np.subtract(self.xy[a], self.xy[b])))
                    self.adj[a].append((b, w)); self.adj[b].append((a, w))
        self.arr = np.array(self.xy) if self.xy else np.zeros((0, 2))
        self.cache, self.fails = {}, 0

    def node(self, p):
        k = (round(p[0] * 2), round(p[1] * 2))
        if k not in self.idx:
            self.idx[k] = len(self.xy); self.xy.append((float(p[0]), float(p[1]))); self.adj.append([])
        return self.idx[k]

    def snap(self, p, far=False):
        """nejbližší uzel do SNAP m; far=True: i dál (zastávka mimo mapu -> silnice na okraji mapy směrem k ní)"""
        if not len(self.arr): return None
        d = np.hypot(self.arr[:, 0] - p[0], self.arr[:, 1] - p[1]); i = int(d.argmin())
        return i if far or d[i] <= SNAP else None

    def leg(self, a, b):
        """body cesty z a do b (bez a), nebo None"""
        if (a, b) in self.cache: return self.cache[(a, b)]
        dist, prev, q = {a: 0.0}, {}, [(0.0, a)]
        lim = 4 * float(np.hypot(*np.subtract(self.xy[a], self.xy[b]))) + 500   # objížďka nejvýš ~4×
        while q:
            d, u = heapq.heappop(q)
            if u == b: break
            if d > dist.get(u, 1e18) or d > lim: continue
            for v, w in self.adj[u]:
                if d + w < dist.get(v, 1e18): dist[v] = d + w; prev[v] = u; heapq.heappush(q, (d + w, v))
        res = None
        if b in prev or a == b:
            res, u = [], b
            while u != a: res.append(self.xy[u]); u = prev[u]
            res.reverse()
        self.cache[(a, b)] = res
        return res

    def path(self, stops):
        """lomená čára přes zastávky [(x, y)] a vzdálenost každé zastávky po ní"""
        near = [self.snap(p) for p in stops]
        nodes = [n if n is not None or not any(q is not None for q in near[max(i - 1, 0):i + 2]) else self.snap(stops[i], True)
                 for i, n in enumerate(near)]
        line, dists, L = [tuple(stops[0])], [0.0], 0.0
        def add(p):
            nonlocal L
            L += float(np.hypot(p[0] - line[-1][0], p[1] - line[-1][1])); line.append(tuple(p))
        for i in range(1, len(stops)):
            a, b = nodes[i - 1], nodes[i]
            pts = self.leg(a, b) if a is not None and b is not None else None
            if pts is None:
                if near[i - 1] is not None and near[i] is not None: self.fails += 1
                add(stops[i])
            else:
                if len(line) == 1 or line[-1] != self.xy[a]: add(self.xy[a])
                for p in pts: add(p)
                if near[i] is None: add(stops[i])                # dál mimo mapu rovně
            dists.append(L)
        if len(line) < 2: line.append((line[0][0] + 0.1, line[0][1]))
        return line, dists
