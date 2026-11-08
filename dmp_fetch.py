# stáhne listy DMP 1G (ČÚZK, CC BY 4.0, laserové skenování povrchu) pokrývající budovy mapy do build/dmp/
# python dmp_fetch.py   (seznam listů z ATOM feedu ČÚZK se stáhne do build/dmp/atom.xml, ~24 MB)
import sys, re, glob, os, subprocess
import pyarrow.parquet as pq, shapely
os.makedirs('build/dmp', exist_ok=True)
A = 'build/dmp/atom.xml'
if not os.path.exists(A): subprocess.run(['curl', '-sL', '-m', '300', '-o', A, 'https://atom.cuzk.gov.cz/DMP1G-SJTSK/DMP1G-SJTSK.xml'], check=True)
s = open(A, encoding='utf8').read()
sheets = []
for e in s.split('<entry>')[1:]:
    p = re.search(r'<georss:polygon>(.*?)<', e); k = re.search(r'DMP1G-SJTSK_([A-Z0-9]+)\.xml', e)
    if p and k:
        v = list(map(float, p.group(1).split())); sheets.append((k.group(1), min(v[1::2]), min(v[0::2]), max(v[1::2]), max(v[0::2])))
b = {}
for f in glob.glob('data*/building.parquet'):
    t = pq.read_table(f, columns=['id', 'bbox']).to_pylist()
    for r in t: b[r['id']] = r['bbox']
xs = shapely.box([r['xmin'] for r in b.values()], [r['ymin'] for r in b.values()], [r['xmax'] for r in b.values()], [r['ymax'] for r in b.values()])
tree = shapely.STRtree(xs); use = [n for n, *q in sheets if len(tree.query(shapely.box(*q)))]
print(len(b), 'budov', len(use), 'listů')
for n in use:
    z = f'build/dmp/{n}.laz'
    if os.path.exists(z): continue
    subprocess.run(['curl', '-sL', '-m', '180', '-o', f'build/dmp/{n}.zip', f'https://openzu.cuzk.cz/opendata/DMP1G/epsg-5514/{n}.zip'], check=True)
    subprocess.run(['unzip', '-oq', f'build/dmp/{n}.zip', '-d', 'build/dmp'], check=True); os.remove(f'build/dmp/{n}.zip')
print('hotovo', len(glob.glob('build/dmp/*.laz')))
