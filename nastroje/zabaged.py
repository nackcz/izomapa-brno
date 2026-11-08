# plochy ZABAGED (ČÚZK, CC BY 4.0) pro celou mapu: orná půda, trvalý travní porost, sad/zahrada -> assets/zabaged.json
# spouštět z kořene repa: python nastroje/zabaged.py   (polygony jako [[lat, lon], ...], první kruh vnější, další díry)
import sys, os, json, re, urllib.parse, subprocess; sys.path.insert(0, '.')
import geo
import shapely
from pyproj import Transformer
LAYERS = {'orna': 'Orná_půda_a_ostatní_dále_nespecifikované_plochy', 'ttp': 'Trvalý_travní_porost', 'sad': 'Ovocný_sad__zahrada'}
URL = 'https://ags.cuzk.gov.cz/arcgis/services/ZABAGED_POLOHOPIS/MapServer/WFSServer?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature'
T = Transformer.from_crs(4326, 5514, always_xy=True); B = Transformer.from_crs(5514, 4326, always_xy=True)
_a, _b, _c, _d = geo.bbox_lonlat(100); xs, ys = T.transform([_a, _b, _a, _b], [_c, _c, _d, _d])
X0, Y0, X1, Y1 = min(xs), min(ys), max(xs), max(ys)
D = 'build/zabaged/'; os.makedirs(D, exist_ok=True); os.makedirs('assets', exist_ok=True)
out = {}
for key, name in LAYERS.items():
    seen, polys = set(), []
    for tx in range(int(X0), int(X1), 2500):
        for ty in range(int(Y0), int(Y1), 2500):
            start = 0
            while True:
                f = f'{D}{key}_{tx}_{ty}_{start}.xml'
                if not os.path.exists(f):
                    q = f'&TYPENAMES={urllib.parse.quote("ZABAGED_POLOHOPIS:" + name)}&BBOX={tx},{ty},{tx + 2500},{ty + 2500},urn:ogc:def:crs:EPSG::5514&COUNT=500&STARTINDEX={start}'
                    subprocess.run(['curl', '-s', '-m', '180', '-o', f, URL + q], check=True)
                s = open(f, encoding='utf-8').read()
                members = s.split('<wfs:member>')[1:]
                for m in members:
                    fid = re.search(r'<ZABAGED_POLOHOPIS:FID_ZBG>(\d+)<', m)
                    typ = re.search(r'<ZABAGED_POLOHOPIS:TYP_PUDY_K>(\w+)<', m)
                    if not fid or fid.group(1) in seen: continue
                    if key == 'orna' and typ and typ.group(1) != 'OR': continue        # jen orná půda, ne „ostatní plochy“
                    seen.add(fid.group(1))
                    for poly in re.findall(r'<gml:Polygon.*?</gml:Polygon>', m, re.S):
                        rings = []
                        for r in re.findall(r'<gml:posList[^>]*>([^<]*)<', poly):
                            v = list(map(float, r.split())); xs_, ys_ = v[0::2], v[1::2]
                            lo, la = B.transform(xs_, ys_)
                            rings.append([[round(a, 6), round(b, 6)] for a, b in zip(la, lo)])
                        if rings and shapely.Polygon([(b, a) for a, b in rings[0]]).area > 2e-8: polys.append(rings)
                if len(members) < 500: break
                start += 500
    out[key] = polys; print(key, len(polys))
json.dump(out, open('assets/zabaged.json', 'w'), separators=(',', ':'))
