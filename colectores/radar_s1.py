#!/usr/bin/env python3
"""Pasadas de radar Sentinel-1 sobre el río: busca las nuevas y detecta objetos en el agua.

Sentinel-1 es dato abierto de Copernicus (ESA). Se lee de la copia pública de Microsoft
Planetary Computer (colección sentinel-1-rtc: 10 m, ya georreferenciada, sin cuenta),
que publica las pasadas con la misma demora que el catálogo oficial. Se leen por rangos
de bytes sólo los recuadros del río, no las escenas completas (1-2 GB cada una).

Salida: DATOS_DIR/radar/pasadas.jsonl (una línea por pasada procesada, con sus
detecciones). Es idempotente: no repite pasadas ya procesadas.

Atribución obligatoria: «Contiene datos modificados de Copernicus Sentinel».

Variables de entorno:
  DATOS_DIR   carpeta de salida (por defecto "datos")
  DESDE       fecha AAAA-MM-DD desde la cual buscar (por defecto, hace 10 días)
  MAX_PASADAS tope de pasadas nuevas por corrida (por defecto 6)
"""
import datetime
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import radar_deteccion as rd  # noqa: E402

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLECCION = "sentinel-1-rtc"
AOI = (-61.5, -34.95, -57.4, -27.3)  # tramos 4 y 5 del colector de AIS
PASO = 0.25
SIN_DATO = -32768.0


def celdas():
    c = json.loads((Path(__file__).resolve().parent / "radar_celdas.json").read_text(encoding="utf-8"))
    return [tuple(x) for x in c["celdas"]]


def buscar_pasadas(desde):
    """Agrupa los cuadros (de 25 s) en pasadas: misma plataforma y órbita, con menos de 2 min entre sí."""
    import planetary_computer as pc
    from pystac_client import Client
    cat = Client.open(STAC, modifier=pc.sign_inplace)
    items = list(cat.search(collections=[COLECCION], bbox=AOI, datetime="%s/.." % desde, max_items=2000).items())
    items.sort(key=lambda i: (i.properties.get("platform"), i.properties.get("sat:relative_orbit"), i.datetime))
    pasadas, actual = [], None
    for it in items:
        clave = (it.properties.get("platform"), it.properties.get("sat:relative_orbit"))
        if actual and actual["clave"] == clave and (it.datetime - actual["items"][-1].datetime).total_seconds() < 120:
            actual["items"].append(it)
        else:
            actual = {"clave": clave, "items": [it]}
            pasadas.append(actual)
    for p in pasadas:
        ts = [i.datetime for i in p["items"]]
        p["inicio"] = min(ts)
        p["id"] = "%s-orb%s-%s" % (p["clave"][0], p["clave"][1], p["inicio"].strftime("%Y%m%dT%H%M"))
    return sorted(pasadas, key=lambda p: p["inicio"])


def leer_recuadro(items, bbox):
    """Mosaico VV (potencia) del recuadro con todos los cuadros de la pasada que lo tocan.
    Devuelve (matriz, transform, crs) o None si casi no hay datos."""
    import rasterio
    from rasterio.warp import transform_bounds
    from rasterio.windows import from_bounds
    mosaico = tr = crs = None
    for it in items:
        # descarta rápido los cuadros que no tocan el recuadro
        b = it.bbox
        if b[2] < bbox[0] or b[0] > bbox[2] or b[3] < bbox[1] or b[1] > bbox[3]:
            continue
        try:
            with rasterio.open(it.assets["vv"].href) as ds:
                nb = transform_bounds("EPSG:4326", ds.crs, *bbox)
                win = from_bounds(*nb, transform=ds.transform)
                a = ds.read(1, window=win, boundless=True, fill_value=SIN_DATO).astype("float32")
                if mosaico is None:
                    mosaico, tr, crs = a, ds.window_transform(win), ds.crs
                elif a.shape == mosaico.shape and ds.crs == crs:
                    m = (mosaico <= -1000) & (a > -1000)
                    mosaico[m] = a[m]
        except Exception as e:  # un cuadro que falla no tira la pasada entera
            print("    aviso: cuadro %s no se pudo leer (%s)" % (it.id[-12:], str(e)[:60]), flush=True)
    if mosaico is None or (mosaico > -1000).mean() < 0.15:
        return None
    return mosaico, tr, crs


def a_lonlat(filas, cols, tr, crs):
    from pyproj import Transformer
    xs, ys = tr * (np.asarray(cols) + 0.5, np.asarray(filas) + 0.5)
    lon, lat = Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform(xs, ys)
    return lon, lat


def procesar_pasada(p):
    detecciones = []
    leidos = 0
    for lon0, lat0 in celdas():
        bbox = (lon0 - 0.01, lat0 - 0.01, lon0 + PASO + 0.01, lat0 + PASO + 0.01)
        r = leer_recuadro(p["items"], bbox)
        if r is None:
            continue
        leidos += 1
        mosaico, tr, crs = r
        valido = mosaico > -1000
        objs, _ = rd.detectar(np.where(valido, mosaico, 0).astype("float32"), valido)
        if not objs:
            continue
        lon, lat = a_lonlat([o["fila"] for o in objs], [o["col"] for o in objs], tr, crs)
        for o, x, y in zip(objs, lon, lat):
            # cada celda se lee con 0.01° de margen; se queda con lo que cae dentro de la celda
            if not (lon0 <= x < lon0 + PASO and lat0 <= y < lat0 + PASO):
                continue
            detecciones.append({"lon": round(float(x), 5), "lat": round(float(y), 5),
                                "largo_m": int(round(o["largo_px"] * 10)), "pico_db": round(o["pico_db"], 1),
                                "area_px": o["area_px"], "fraccion_agua": o["fraccion_agua"], "clase": o["clase"]})
    return detecciones, leidos


def main():
    carpeta = Path(os.environ.get("DATOS_DIR", "datos")) / "radar"
    carpeta.mkdir(parents=True, exist_ok=True)
    archivo = carpeta / "pasadas.jsonl"
    hechas = set()
    if archivo.exists():
        hechas = {json.loads(l)["id"] for l in archivo.read_text(encoding="utf-8").splitlines() if l.strip()}
    desde = os.environ.get("DESDE") or (datetime.date.today() - datetime.timedelta(days=10)).isoformat()
    tope = int(os.environ.get("MAX_PASADAS", "6"))
    pasadas = [p for p in buscar_pasadas(desde) if p["id"] not in hechas]
    print("Pasadas desde %s: %d nuevas (ya procesadas: %d)" % (desde, len(pasadas), len(hechas)), flush=True)
    nuevas = 0
    for p in pasadas[:tope]:
        t0 = time.time()
        det, leidos = procesar_pasada(p)
        agua = [d for d in det if d["clase"] == "agua"]
        print("  %s: %d recuadros con datos, %d objetos en el agua, %d junto a la orilla [%.0fs]" %
              (p["id"], leidos, len(agua), len(det) - len(agua), time.time() - t0), flush=True)
        if leidos == 0:
            continue
        # Sólo se guardan los objetos en el agua (lo que el método afirma). Los de orilla son miles,
        # sobre todo edificios y vegetación, y no se afirman como nada: se guarda sólo su cuenta.
        reg = {"id": p["id"], "plataforma": p["clave"][0], "orbita": p["clave"][1],
               "tiempo": p["inicio"].strftime("%Y-%m-%dT%H:%M:%SZ"), "cuadros": len(p["items"]),
               "recuadros_con_datos": leidos, "objetos_orilla_no_afirmados": len(det) - len(agua),
               "detecciones": agua,
               "fuente": "Copernicus Sentinel-1 (ESA), copia de Microsoft Planetary Computer"}
        with open(archivo, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(reg, ensure_ascii=False, sort_keys=True) + chr(10))
        nuevas += 1
    print("Pasadas guardadas en esta corrida: %d. Contiene datos modificados de Copernicus Sentinel." % nuevas)
    return 0


if __name__ == "__main__":
    sys.exit(main())
