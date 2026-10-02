"""Junta los cuadros de OSM (cauces anchos del Paraná, el Delta y el Uruguay) en un solo trazado SVG en
unidades del mapa. Salida: agua_osm.json con {"d": trazado, "fecha": ..., "poligonos": n, "puntos": n}."""
import glob
import json
import math
import sys

AX, BX, AY, BY = 38.9572, 2781.788, -43.2531, -653.764
TOL = float(sys.argv[1]) if len(sys.argv) > 1 else 0.12   # unidades del mapa (~2,57 km cada una)


def proy(lon, lat):
    return AX * lon + BX, AY * lat + BY


def dp(pts, tol):
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    pila = [(0, len(pts) - 1)]
    while pila:
        i, j = pila.pop()
        ax, ay = pts[i]
        bx, by = pts[j]
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy) or 1e-9
        mejor, k = 0, -1
        for m in range(i + 1, j):
            d = abs((pts[m][0] - ax) * dy - (pts[m][1] - ay) * dx) / L
            if d > mejor:
                mejor, k = d, m
        if mejor > tol:
            keep[k] = True
            pila += [(i, k), (k, j)]
    return [p for p, c in zip(pts, keep) if c]


def unir(segmentos):
    """Une vías abiertas en anillos cerrados por extremos coincidentes."""
    anillos, abiertos = [], [list(s) for s in segmentos if len(s) > 1]
    cerrados = [s for s in abiertos if s[0] == s[-1]]
    abiertos = [s for s in abiertos if s[0] != s[-1]]
    anillos += cerrados
    while abiertos:
        a = abiertos.pop()
        crecio = True
        while crecio and a[0] != a[-1]:
            crecio = False
            for i, b in enumerate(abiertos):
                if b[0] == a[-1]:
                    a += b[1:]
                elif b[-1] == a[-1]:
                    a += b[::-1][1:]
                elif b[-1] == a[0]:
                    a = b[:-1] + a
                elif b[0] == a[0]:
                    a = b[::-1][:-1] + a
                else:
                    continue
                abiertos.pop(i)
                crecio = True
                break
        # una cadena que queda abierta fue cortada por el borde del cuadro: se la cierra (SVG rellena con Z)
        if len(a) > 3:
            anillos.append(a)
    return anillos


vistos, anillos = set(), []
for f in sorted(glob.glob("t_*.json") + glob.glob("m_*.json")):
    for e in json.load(open(f, encoding="utf-8")).get("elements", []):
        clave = (e["type"], e["id"])
        if clave in vistos:
            continue
        vistos.add(clave)
        if e["type"] == "way" and e.get("geometry"):
            anillos.append([(g["lon"], g["lat"]) for g in e["geometry"]])
        elif e["type"] == "relation":
            segs = [[(g["lon"], g["lat"]) for g in m["geometry"]] for m in e.get("members", [])
                    if m.get("role") == "outer" and m.get("geometry")]
            anillos += unir(segs)

trazos, npts = [], 0
for a in anillos:
    p = [proy(lon, lat) for lon, lat in a]
    if len(p) < 4:
        continue
    xs, ys = [q[0] for q in p], [q[1] for q in p]
    if (max(xs) - min(xs)) * (max(ys) - min(ys)) < 0.02:     # islotes y charcos: ruido para este mapa
        continue
    if p[0] == p[-1]:     # anillo cerrado: Douglas-Peucker necesita dos extremos distintos
        m = len(p) // 2
        p = dp(p[:m + 1], TOL)[:-1] + dp(p[m:], TOL)
    else:
        p = dp(p, TOL)
    if len(p) < 4:
        continue
    npts += len(p)
    trazos.append("M" + "L".join("%.1f,%.1f" % q for q in p) + "Z")
print("polígonos:", len(trazos), "puntos:", npts, "bytes:", sum(len(t) for t in trazos))
json.dump({"d": "".join(trazos), "poligonos": len(trazos), "puntos": npts}, open("agua_osm.json", "w"), separators=(",", ":"))
