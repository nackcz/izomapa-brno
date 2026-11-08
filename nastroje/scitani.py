"""Výsledky Celostátního sčítání dopravy ŘSD -> build/scitani.json (počet vozidel za 24 h na úseku silnice).

python nastroje/scitani.py [xlsx nebo URL]
Výsledky: https://www.rsd.cz/silnice-a-dalnice/scitani-dopravy (sloupec SV = všechna vozidla za 24 h, nak = nákladní)
"""
import json, os, re, sys, urllib.request, zipfile
from xml.etree import ElementTree as ET

URL = 'https://www.rsd.cz/documents/38144/3734982/V2_CSD_2025_20260826.xlsx/5a2163ce-1bcc-6264-8251-98e4dd34a9ec?t=1788264442427'
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def rows(path):
    z = zipfile.ZipFile(path)
    strings = [''.join(t.text or '' for t in si.iter('{%s}t' % NS['m'])) for si in ET.fromstring(z.read('xl/sharedStrings.xml'))]
    for row in ET.fromstring(z.read('xl/worksheets/sheet1.xml')).iter('{%s}row' % NS['m']):
        out = {}
        for c in row.findall('m:c', NS):
            v = c.find('m:v', NS)
            if v is not None: out[re.match('[A-Z]+', c.get('r')).group()] = strings[int(v.text)] if c.get('t') == 's' else v.text
        yield out


def sections(path):
    it = rows(path); head = None
    for r in it:
        if 'SV' in r.values(): head = {v: k for k, v in r.items()}; break
    if not head: raise SystemExit('v tabulce chybí sloupec SV')
    res = []
    for r in it:
        try: sv = int(float(r.get(head['SV'], '')))
        except ValueError: continue
        def num(k):
            try: return float(r.get(head[k], 0))
            except ValueError: return 0.0
        res.append({'kraj': r.get(head['NÁZEV_KRAJE']), 'sil': str(r.get(head['SIL'], '')).strip(), 'usek': r.get(head['ÚSEK']), 'sv': sv,
                    'nak': round(num('TV') - num('A') - num('Z'))})          # TV bez sloupců A a Z = LN + SN + SNP + TN + TNP + NSN (nákladní)
    return res


if __name__ == '__main__':
    src = sys.argv[1] if len(sys.argv) > 1 else URL
    if re.match('https?://', src):
        os.makedirs('build', exist_ok=True)
        req = urllib.request.Request(src, headers={'User-Agent': 'izomapa'})
        open('build/scitani.xlsx', 'wb').write(urllib.request.urlopen(req, timeout=120).read()); src = 'build/scitani.xlsx'
    data = sections(src)
    json.dump(data, open('build/scitani.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print('úseků sčítání', len(data))
