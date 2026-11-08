"""Doplnění chybějících časů mezizastávek GTFS mezi známými časy."""

def dopln_mezicasy(rows):
    """Seřazené (pořadí, příjezd, odjezd, vzdálenost, stop_id); bez extrapolace konců."""
    rows = sorted(rows)
    znamy = [i for i, r in enumerate(rows) if r[1] is not None]
    if len(znamy) < 2:
        return [r for r in rows if r[1] is not None]
    out = list(rows)
    for a, b in zip(znamy, znamy[1:]):
        start, end = rows[a][2], rows[b][1]
        for i in range(a + 1, b):
            q, _, _, dist, stop = rows[i]
            f = (i - a) / (b - a)
            t = round(start + (end - start) * f)
            d0, d1 = rows[a][3], rows[b][3]
            if d1 > d0 and not d0 < dist < d1: dist = d0 + (d1 - d0) * f
            out[i] = (q, t, t, dist, stop)
    return [r for r in out if r[1] is not None]
