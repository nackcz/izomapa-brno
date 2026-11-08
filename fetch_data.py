"""Stáhne data pro výřez: Overture Maps (S3, anonymně) + terén Terrarium (AWS Open Data).

python fetch_data.py --vse         # všechny čtverce z mesto.json + místa + městské části (první spuštění)
python fetch_data.py --chunk -1,0  # čtverec mapy s rezervou 300 m -> data_c-1_0/ (čtverec 0,0 -> data/)
python fetch_data.py --places      # názvy a firmy (Overture places) pro karty budov -> data/places.parquet
python fetch_data.py --deleni      # městské části a osady (Overture divisions) -> data_all/division_area.parquet
"""
import math, os, subprocess, sys, time, urllib.request
import pyarrow.dataset as ds, pyarrow.fs as fs, pyarrow.parquet as pq
import geo

REL = '2026-10-21.0'
LAYERS = [('buildings', 'building'), ('transportation', 'segment'), ('base', 'land_use'), ('base', 'water'),
          ('base', 'land_cover'), ('base', 'infrastructure'), ('base', 'land'), ('addresses', 'address')]


def tile(lon, lat, z):
    n = 2 ** z
    return int((lon + 180) / 360 * n), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)


def dem(D, X0, X1, Y0, Y1, z=14):
    """terén Terrarium (AWS Open Data) pro výřez"""
    os.makedirs(f'{D}/dem', exist_ok=True)
    tx0, ty0 = tile(X0, Y1, z); tx1, ty1 = tile(X1, Y0, z)
    for x in range(tx0, tx1 + 1):
        for y in range(ty0, ty1 + 1):
            if not os.path.exists(f'{D}/dem/{z}_{x}_{y}.png'):
                urllib.request.urlretrieve(f'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png', f'{D}/dem/{z}_{x}_{y}.png')


if sys.argv[1:2] == ['--vse']:
    # Overture se prohledává po celém světě (pomalé), proto každou vrstvu jednou pro celou mapu a čtverce se z ní vyříznou lokálně
    proxy = os.environ.get('HTTPS_PROXY')
    s3 = fs.S3FileSystem(anonymous=True, region='us-west-2', **({'proxy_options': proxy} if proxy else {}))
    os.makedirs('data_all', exist_ok=True)
    X0, X1, Y0, Y1 = geo.bbox_lonlat(400)
    for theme, typ in LAYERS:
        out = f'data_all/{typ}.parquet'
        if os.path.exists(out): continue
        t = time.time()
        d = ds.dataset(f'overturemaps-us-west-2/release/{REL}/theme={theme}/type={typ}/', filesystem=s3, format='parquet')
        f = ((ds.field('bbox', 'xmin') < X1) & (ds.field('bbox', 'xmax') > X0) & (ds.field('bbox', 'ymin') < Y1) & (ds.field('bbox', 'ymax') > Y0))
        tb = d.to_table(filter=f); pq.write_table(tb, out)
        print(typ, tb.num_rows, f'{time.time() - t:.0f}s', flush=True)
    for c in sorted(geo.CHUNKS):
        D = 'data' if c == (0, 0) else f'data_c{c[0]}_{c[1]}'
        os.makedirs(f'{D}/dem', exist_ok=True)
        cx, cy = geo.chunk_center(c); r = geo.HALF + 300
        (x0, x1), (y0, y1) = geo.to_lonlat([cx - r, cx + r], [cy - r, cy + r])
        x0, x1, y0, y1 = float(x0), float(x1), float(y0), float(y1)
        for theme, typ in LAYERS:
            tb = pq.read_table(f'data_all/{typ}.parquet')
            b = tb.column('bbox').combine_chunks()
            import pyarrow.compute as pc
            m = pc.and_(pc.and_(pc.less(b.field('xmin'), x1), pc.greater(b.field('xmax'), x0)),
                        pc.and_(pc.less(b.field('ymin'), y1), pc.greater(b.field('ymax'), y0)))
            pq.write_table(tb.filter(m), f'{D}/{typ}.parquet')
        dem(D, x0, x1, y0, y1)
        print('čtverec', c, '->', D, flush=True)
    if not os.path.exists('data/places.parquet'): subprocess.run([sys.executable, __file__, '--places'], check=True)
    if not os.path.exists('data_all/division_area.parquet'): subprocess.run([sys.executable, __file__, '--deleni'], check=True)
    sys.exit()
if sys.argv[1:2] == ['--deleni']:
    proxy = os.environ.get('HTTPS_PROXY')
    s3 = fs.S3FileSystem(anonymous=True, region='us-west-2', **({'proxy_options': proxy} if proxy else {}))
    d = ds.dataset(f'overturemaps-us-west-2/release/2026-10-21.0/theme=divisions/type=division_area/', filesystem=s3, format='parquet')
    X0, X1, Y0, Y1 = geo.bbox_lonlat(0)
    f = ((ds.field('bbox', 'xmin') < X1) & (ds.field('bbox', 'xmax') > X0)
         & (ds.field('bbox', 'ymin') < Y1) & (ds.field('bbox', 'ymax') > Y0))
    os.makedirs('data_all', exist_ok=True)
    tb = d.to_table(filter=f)
    pq.write_table(tb, 'data_all/division_area.parquet')
    print('částí obcí', tb.num_rows)
    sys.exit()
if sys.argv[1:2] == ['--places']:
    proxy = os.environ.get('HTTPS_PROXY')
    s3 = fs.S3FileSystem(anonymous=True, region='us-west-2', **({'proxy_options': proxy} if proxy else {}))
    d = ds.dataset('overturemaps-us-west-2/release/2026-10-21.0/theme=places/type=place/', filesystem=s3, format='parquet')
    X0, X1, Y0, Y1 = geo.bbox_lonlat(0)             # celá mapa
    f = ((ds.field('bbox', 'xmin') < X1) & (ds.field('bbox', 'xmax') > X0)
         & (ds.field('bbox', 'ymin') < Y1) & (ds.field('bbox', 'ymax') > Y0))
    os.makedirs('data', exist_ok=True)
    tb = d.to_table(filter=f)
    pq.write_table(tb, 'data/places.parquet')
    print('míst', tb.num_rows)
    sys.exit()
OUT = sys.argv[1] if len(sys.argv) > 1 else 'data'
if OUT != '--chunk':
    X0, X1, Y0, Y1 = tuple(map(float, sys.argv[2].split(",")))   # vlastní výřez lon0,lon1,lat0,lat1
else:
    c = tuple(int(v) for v in sys.argv[2].split(','))
    OUT = 'data' if c == (0, 0) else f'data_c{c[0]}_{c[1]}'
    cx, cy = geo.chunk_center(c); r = geo.HALF + 300
    (X0, X1), (Y0, Y1) = geo.to_lonlat([cx - r, cx + r], [cy - r, cy + r])
os.makedirs(f'{OUT}/dem', exist_ok=True)
proxy = os.environ.get('HTTPS_PROXY')
s3 = fs.S3FileSystem(anonymous=True, region='us-west-2', **({'proxy_options': proxy} if proxy else {}))
for theme, typ in LAYERS:
    t = time.time()
    d = ds.dataset(f'overturemaps-us-west-2/release/{REL}/theme={theme}/type={typ}/', filesystem=s3, format='parquet')
    f = ((ds.field('bbox', 'xmin') < X1) & (ds.field('bbox', 'xmax') > X0)
         & (ds.field('bbox', 'ymin') < Y1) & (ds.field('bbox', 'ymax') > Y0))
    tb = d.to_table(filter=f)
    pq.write_table(tb, f'{OUT}/{typ}.parquet')
    print(typ, tb.num_rows, f'{time.time() - t:.0f}s')


dem(OUT, X0, X1, Y0, Y1)
print('terén hotov')
