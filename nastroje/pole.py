# pole podle ortofota: travní porost ze ZABAGED, který je na ortofotu žlutohnědý (obilí, posečené seno), je ve skutečnosti pole
# -> assets/zabaged.json klíč 'pole' (indexy do 'ttp'); spouštět po nastroje/zabaged.py a nastroje/les.py (build/orto_cele.jpg)
import sys, json; sys.path.insert(0, '.')
import numpy as np, geo
from PIL import Image, ImageDraw
Image.MAX_IMAGE_PIXELS = None
A = np.asarray(Image.open('build/orto_cele.jpg').convert('RGB')).astype(np.int16)
Z = json.load(open('assets/zabaged.json')); X0, Y1, M = json.load(open('build/les_maska.json'))['x0y1m']
pole = []
for i, p in enumerate(Z['ttp']):
    x, y = geo.to_local(np.array([q[1] for q in p[0]]), np.array([q[0] for q in p[0]]))
    u, v = (x - X0) / M, (Y1 - y) / M
    if u.min() < 0 or v.min() < 0 or u.max() >= A.shape[1] or v.max() >= A.shape[0]: continue
    x0, y0, x1, y1 = int(u.min()), int(v.min()), int(u.max()) + 1, int(v.max()) + 1
    mk = Image.new('L', (x1 - x0, y1 - y0)); ImageDraw.Draw(mk).polygon(list(zip(u - x0, v - y0)), fill=1)
    c = A[y0:y1, x0:x1][np.asarray(mk) > 0]
    if len(c) < 500: continue                                     # aspoň 0,2 ha
    r, g, b = np.median(c, 0)
    if r >= g - 10 and (r + g + b) / 3 > 105: pole.append(i)
Z['pole'] = pole
json.dump(Z, open('assets/zabaged.json', 'w'), separators=(',', ':'))
print('polí z ortofota', len(pole), 'z', len(Z['ttp']))
