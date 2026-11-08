"""Přepne stav všech čtverců (hotovo / rozpracováno) v site/tiles.json a site/overlay.json bez přerenderování.
python set_status.py hotovo"""
import json, sys
st = sys.argv[1] if len(sys.argv) > 1 else 'hotovo'
t = json.load(open('site/tiles.json'))
t.setdefault('base', {})['status'] = st
import time; t['ver'] = time.strftime('%Y%m%d%H%M')      # verze dlaždic pro cache (mění se při každém nasazení)
for c in t.get('chunks', {}).values(): c['status'] = st
json.dump(t, open('site/tiles.json', 'w'))
o = json.load(open('site/overlay.json'))
o['chunks'] = {k: st for k in o.get('chunks', {})}
json.dump(o, open('site/overlay.json', 'w'), separators=(',', ':'), ensure_ascii=False)
print('stav', st, 'čtverců', len(t.get('chunks', {})) + 1)
