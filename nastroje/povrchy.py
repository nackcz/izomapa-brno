# zeleň podle ortofota ČÚZK: data označí celé školní nebo firemní pozemky jako zpevněné, i když je na nich tráva
# -> build/zelen_maska.png + .json (po 2 m; prep.py podle ní mění zpevněné plochy na trávu); spouštět po nastroje/strechy.py z kořene repa
import json, sys; sys.path.insert(0, '.'); sys.path.insert(0, 'nastroje')
import numpy as np, strechy as s
from PIL import Image, ImageFilter
Image.MAX_IMAGE_PIXELS = None
K = 5                                       # 5 pixelů po 0,4 m = buňka 2 m


def green(a):
    """zelené pixely; tmavé (stíny) o povrchu nic neřeknou, proto se nepočítají ani jako zpevněné"""
    r, g, b = a[..., 0].astype(int), a[..., 1].astype(int), a[..., 2].astype(int)
    lit = (r + g + b) / 3 > 45
    return (g > r + 3) & (g > b + 3) & lit, lit


if __name__ == '__main__':
    W, H = s.W // K, s.H // K
    out = np.zeros((H, W), np.uint8)
    for ty in range(0, s.H, s.T):
        for tx in range(0, s.W, s.T):
            a = s.tile(tx, ty)
            if a is None: continue
            g, l = green(a); h, w = a.shape[0] // K, a.shape[1] // K
            cut = lambda m: m[:h * K, :w * K].reshape(h, K, w, K).sum((1, 3))
            gs, ls = cut(g), cut(l)
            f = np.where(ls >= 5, gs / np.maximum(ls, 1), 0)
            out[ty // K:ty // K + h, tx // K:tx // K + w] = (f * 255).astype(np.uint8)
    im = Image.fromarray(out).filter(ImageFilter.GaussianBlur(1.5)).point(lambda v: 255 if v > 150 else 0)
    im = im.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))    # bez ojedinělých buněk
    im.save('build/zelen_maska.png'); json.dump({'x0y1m': [s.X0, s.Y1, s.M * K]}, open('build/zelen_maska.json', 'w'))
    print('maska zeleně', im.size, f'{np.asarray(im).mean() / 2.55:.0f} %')
