# typy budov z RÚIAN (ČÚZK, CC BY 4.0): způsob využití a počet podlaží z veřejné služby, bez registrace, jen pro Česko
# -> assets/ruian_budovy.json (id budovy -> [třída nebo null, podlaží nebo null]); prep.py je použije tam, kde data typ nemají
# spouštět z kořene repa: python nastroje/ruian.py   (stahuje se po čtvercích do build/ruian/, po přerušení pokračuje)
import glob, json, os, subprocess, sys, urllib.parse; sys.path.insert(0, '.')
import geo, numpy as np, pyarrow.parquet as pq, shapely

URL = 'https://ags.cuzk.gov.cz/arcgis/rest/services/RUIAN/Prohlizeci_sluzba_nad_daty_RUIAN/MapServer/3/query?'
D = 'build/ruian/'
KROK = 2000
# kód způsobu využití -> třída budovy; „jiná“ (19) a „víceúčelová“ (20) stavba o typu nic neříkají
TRIDY = {1: 'industrial', 2: 'farm', 3: 'residential', 4: 'farm_auxiliary', 5: 'civic', 6: 'apartments', 7: 'house', 8: 'cabin', 9: 'civic',
         10: 'retail', 11: 'hotel', 12: 'industrial', 13: 'farm_auxiliary', 14: 'office', 15: 'civic', 16: 'service', 17: 'transportation',
         18: 'garage', 21: 'greenhouse'}
MIN_PREKRYTI = 0.5


def stahni(x0, y0, x1, y1):
    f = f'{D}{round(x0)}_{round(y0)}.json'
    if not os.path.exists(f):
        lo0, la0 = geo.to_lonlat(x0, y0); lo1, la1 = geo.to_lonlat(x1, y1)
        q = urllib.parse.urlencode({'geometry': f'{lo0},{la0},{lo1},{la1}', 'geometryType': 'esriGeometryEnvelope', 'inSR': 4326, 'outSR': 4326,
                                    'spatialRel': 'esriSpatialRelIntersects', 'outFields': 'kod,zpusobvyuzitikod,pocetpodlazi', 'f': 'json'})
        subprocess.run(['curl', '-s', '-f', '-m', '180', '-o', f + '.tmp', URL + q], check=True)
        if 'features' not in json.load(open(f + '.tmp')): raise SystemExit(f'RÚIAN nevrátil data pro {f}')
        os.replace(f + '.tmp', f)
    return json.load(open(f))['features']


def trida(kod):
    return TRIDY.get(kod)


def prirad(budovy, objekty):
    """budovy: {id: polygon}, objekty: [(polygon, kód využití, podlaží)]; každé budově nejvíc překrytý objekt, aspoň z poloviny její plochy."""
    strom = shapely.STRtree([o[0] for o in objekty]); out = {}
    for i, p in budovy.items():
        best, kolik = None, 0.0
        for j in strom.query(p):
            a = shapely.area(shapely.intersection(p, objekty[j][0]))
            if a > kolik: best, kolik = j, a
        if best is None or kolik < MIN_PREKRYTI * p.area: continue
        t, f = trida(objekty[best][1]), objekty[best][2] or None
        if t or f: out[i] = [t, f]
    return out


if __name__ == '__main__':
    os.makedirs(D, exist_ok=True)
    X0, Y0, X1, Y1 = geo.extent(geo.MARGIN + 20)
    seen = {}; x = X0
    while x < X1:
        y = Y0
        while y < Y1:
            for o in stahni(x, y, min(x + KROK, X1), min(y + KROK, Y1)):
                a = o['attributes']; g = o.get('geometry')
                if g and g.get('rings') and a['kod'] not in seen:
                    r = [[geo.to_local(lo, la) for lo, la in q] for q in g['rings']]
                    p = shapely.make_valid(shapely.Polygon(r[0], r[1:]))
                    seen[a['kod']] = (p, a['zpusobvyuzitikod'], a['pocetpodlazi'])
            y += KROK
        x += KROK
    budovy = {}
    for f in sorted(glob.glob('data*/building.parquet')):
        if 'data_all' in f: continue
        for r in pq.read_table(f, columns=['id', 'geometry']).to_pylist():
            if r['id'] in budovy: continue
            g = shapely.from_wkb(r['geometry']); g = g if g.geom_type == 'Polygon' else max(g.geoms, key=lambda q: q.area)
            budovy[r['id']] = shapely.transform(g, lambda c: np.array([geo.to_local(*q) for q in c]))
    out = prirad(budovy, list(seen.values()))
    json.dump(out, open('assets/ruian_budovy.json', 'w'))
    print('objektů', len(seen), 'budov', len(budovy), 'přiřazeno', len(out))
