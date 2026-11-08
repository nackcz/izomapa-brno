# komíny, chladicí věže, vysílače, nádrže a nadzemní potrubí z OpenStreetMap (Overpass, ODbL, bez registrace)
# assets/kominy.json: [{"lat", "lon", "h", "k": "komin" | "vez" | "stozar" | "nadrz" | "rozhledna", "r": poloměr paty nebo null}]
# assets/potrubi.json: [[[lat, lon], ...]]; spouštět z kořene repa: python nastroje/kominy.py
import json, math, subprocess, sys; sys.path.insert(0, '.')
import geo

SHODA_M = 15          # stejný komín bývá v OSM jako bod i jako plocha
VYCHOZI_H = {'komin': 25.0, 'vez': 40.0, 'stozar': 30.0, 'nadrz': 10.0, 'rozhledna': 13.0}


def vyska(t):
    try: return float(str(t.get('height', '')).replace('m', '').replace(',', '.').strip())
    except ValueError: return None


def vyber(prvky):
    """Sloučí blízký bod a plochu stejného druhu; samostatné body a plochy zachová."""
    out = []
    for e in prvky:
        t = e.get('tags', {}); b = e.get('bounds')
        c = {'lat': (b['minlat'] + b['maxlat']) / 2, 'lon': (b['minlon'] + b['maxlon']) / 2} if b else e.get('center') or e   # Overpass u "center bb" vrací jen bounds
        tt = t.get('tower:type')
        if tt == 'observation' and 'building' in t: continue         # zděné rozhledny jsou v datech jako budovy
        k = 'rozhledna' if tt == 'observation' else 'vez' if tt == 'cooling' else 'nadrz' if t.get('man_made') == 'storage_tank' else 'stozar' if tt == 'communication' else 'komin'
        r = None
        if b:
            sirka = (b['maxlon'] - b['minlon']) * 111320 * math.cos(math.radians(c['lat'])); delka = (b['maxlat'] - b['minlat']) * 111320
            r = round(min(sirka, delka) / 2, 1)
        out.append({'lat': c['lat'], 'lon': c['lon'], 'h': vyska(t), 'k': k, 'r': r, 'plocha': 'center' in e or 'bounds' in e})
    out.sort(key=lambda q: (not q['plocha'], -(q['h'] or 0)))
    jeden = []
    for q in out:
        y = (q['lat'] * 111320, q['lon'] * 111320 * math.cos(math.radians(q['lat'])))
        for p in jeden:
            if q['k'] == p['k'] and q['plocha'] != p['plocha'] and not p.get('_sparovano') and math.dist(y, (p['lat'] * 111320, p['lon'] * 111320 * math.cos(math.radians(p['lat'])))) < SHODA_M:
                p['h'] = p['h'] or q['h']; p['_sparovano'] = True; break
        else: jeden.append(q)
    for p in jeden: p['h'] = p['h'] or VYCHOZI_H[p['k']]; del p['plocha']; p.pop('_sparovano', None)
    return jeden


def potrubi(prvky):
    """Vynechá potrubí výslovně pod zemí, pod vodou nebo v tunelu."""
    def viditelne(e):
        t = e.get('tags', {})
        if t.get('location', '').lower() in ('underground', 'underwater'):
            return False
        if t.get('tunnel', '').lower() not in ('', 'no', 'false', '0'):
            return False
        try:
            if float(t.get('layer', 0)) < 0: return False
        except (ValueError, TypeError):
            pass  # nečitelná vrstva sama o sobě nedokládá podzemní potrubí
        return True
    return [[[round(p['lat'], 6), round(p['lon'], 6)] for p in e['geometry']] for e in prvky
            if e.get('geometry') and viditelne(e)]


OVERPASS = ['https://overpass-api.de/api/interpreter', 'https://overpass.openstreetmap.fr/api/interpreter', 'https://maps.mail.ru/osm/tools/overpass/api/interpreter',
            'https://overpass.kumi.systems/api/interpreter']


if __name__ == '__main__':
    x0, y0, x1, y1 = geo.extent(geo.MARGIN + 20)
    lo0, la0 = geo.to_lonlat(x0, y0); lo1, la1 = geo.to_lonlat(x1, y1); b = f'{la0},{lo0},{la1},{lo1}'
    def dotaz(q):
        for url in OVERPASS:   # hlavní server, při chybě zrcadla
            r = subprocess.run(['curl', '-s', '-f', '-m', '120', '-A', 'izomapa-tools/1.0', '--data-urlencode', f'data={q}', url],
                               capture_output=True, text=True)
            if r.returncode == 0: return json.loads(r.stdout)['elements']
            print('Overpass nedostupný:', url, 'kód', r.returncode)
        raise SystemExit('Žádný Overpass server neodpověděl')
    v = vyber(dotaz(f'[out:json][timeout:60];(nwr["man_made"="chimney"]({b});nwr["tower:type"~"^(stack|cooling|communication|observation)$"]({b});nwr["man_made"="storage_tank"]({b}););out tags center bb;'))
    json.dump(v, open('assets/kominy.json', 'w'), indent=0)
    tr = potrubi(dotaz(f'[out:json][timeout:60];way["man_made"="pipeline"]({b});out tags geom;'))
    json.dump(tr, open('assets/potrubi.json', 'w'))
    print({k: sum(p['k'] == k for p in v) for k in VYCHOZI_H}, 'potrubí', len(tr))
