#!/usr/bin/env python3
"""Focos de calor a lo largo del corredor, a nivel de tramo: NASA FIRMS (VIIRS de Suomi NPP y de NOAA-20).

Usa los archivos regionales de acceso libre de FIRMS (no hace falta clave), los recorta al corredor y se queda sólo con los
detectados a menos de RADIO_KM de la línea del río, para contar «focos cerca del río» por tramo en vez de por provincia entera.
Acumula tres días. Un foco es una anomalía térmica detectada por satélite: no es un incendio confirmado ni dice su causa (quema
agrícola, incendio forestal, antorcha industrial). Datos de NASA, dominio público.

Escribe DATOS_DIR/focos_corredor.json."""
import csv
import io
import json
import math
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
BASE = "https://firms.modaps.eosdis.nasa.gov/data/active_fire/"
ARCHIVOS = [("suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_South_America_24h.csv", "VIIRS Suomi NPP"),
            ("noaa-20-viirs-c2/csv/J1_VIIRS_C2_South_America_24h.csv", "VIIRS NOAA-20")]
CAJA = (-36.5, -71.5, -15.0, -51.8)          # lat_min, lon_min, lat_max, lon_max del corredor
RADIO_KM = 25.0
KM_POR_UNIDAD = 2.57                         # kilómetros por unidad del mapa
AX, BX, AY, BY = 38.9572, 2781.788, -43.2531, -653.764
DIAS = 3


def segmentos():
    d = json.load(open(RAIZ / "sitio" / "datos" / "mapa_v10.json", encoding="utf-8"))
    out = []
    for clave in ("rio_parana", "rio_paraguay"):
        cur, buf = [], []
        for c, n in re.findall(r"([MLZ])|(-?\d+\.?\d*)", d[clave]):
            if c:
                if c == "M" and cur:
                    out += list(zip(cur, cur[1:]))
                    cur = []
                buf = []
            else:
                buf.append(float(n))
                if len(buf) == 2:
                    cur.append(tuple(buf))
                    buf = []
        if cur:
            out += list(zip(cur, cur[1:]))
    return out


def distancia_km(x, y, segs):
    mejor = 1e9
    for (ax, ay), (bx, by) in segs:
        if x < min(ax, bx) - 12 or x > max(ax, bx) + 12 or y < min(ay, by) - 12 or y > max(ay, by) + 12:
            continue                      # lejos: ni se calcula
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy
        t = 0 if L == 0 else max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / L))
        d = math.hypot(x - ax - t * dx, y - ay - t * dy)
        if d < mejor:
            mejor = d
    return mejor * KM_POR_UNIDAD


def bajar(ruta):
    req = urllib.request.Request(BASE + ruta, headers={"User-Agent": "Ysyry-FUSK/1.0 (+https://github.com/fundacion-sherman-kent/ysyry)"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read().decode("utf-8", "replace")


def main():
    carpeta = Path(os.environ.get("DATOS_DIR", "datos/publico"))
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / "focos_corredor.json"
    previo = json.load(open(destino, encoding="utf-8")) if destino.exists() else {"puntos": []}
    segs = segmentos()
    nuevos, fallas = {}, []
    for ruta, nombre in ARCHIVOS:
        try:
            filas = list(csv.DictReader(io.StringIO(bajar(ruta))))
        except Exception as e:
            print("%s no respondió: %s" % (nombre, str(e)[:80]))
            fallas.append(nombre)
            continue
        tot = cerca = 0
        for f in filas:
            try:
                lat, lon = float(f["latitude"]), float(f["longitude"])
            except Exception:
                continue
            if not (CAJA[0] <= lat <= CAJA[2] and CAJA[1] <= lon <= CAJA[3]):
                continue
            tot += 1
            x, y = AX * lon + BX, AY * lat + BY
            km = distancia_km(x, y, segs)
            if km > RADIO_KM:
                continue
            cerca += 1
            p = [round(lat, 4), round(lon, 4), f["acq_date"], f["acq_time"], float(f.get("frp") or 0), (f.get("confidence") or "")[:1].lower(),
                 f.get("daynight", ""), nombre, round(km, 1)]
            nuevos[(p[0], p[1], p[2], p[3], nombre)] = p
        print("%s: %d filas, %d en el corredor, %d a menos de %d km del río" % (nombre, len(filas), tot, cerca, RADIO_KM))
    if len(fallas) == len(ARCHIVOS):
        print("FIRMS no respondió: no se toca el archivo anterior")
        return 1
    corte = (datetime.now(timezone.utc) - timedelta(days=DIAS)).strftime("%Y-%m-%d")
    acumulado = {(p[0], p[1], p[2], p[3], p[7]): p for p in previo.get("puntos", []) if p[2] >= corte}
    acumulado.update(nuevos)
    puntos = sorted(acumulado.values(), key=lambda p: (p[2], p[3]))
    salida = {"obtenido": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "fuente": {"nombre": "NASA FIRMS (VIIRS Suomi NPP y NOAA-20), archivos regionales de acceso libre", "url": "https://firms.modaps.eosdis.nasa.gov/active_fire/",
                         "nota": "Anomalías térmicas, no incendios confirmados. Sólo las detectadas a menos de %d km del río. Dominio público de NASA." % RADIO_KM},
              "radio_km": RADIO_KM, "dias": DIAS, "fallas": fallas,
              "columnas": ["lat", "lon", "fecha", "hora_utc", "frp_mw", "confianza_l_n_h", "dia_noche", "sensor", "km_al_rio"], "puntos": puntos}
    json.dump(salida, open(destino, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, separators=(",", ":"))
    print("Puntos acumulados (%d días): %d" % (DIAS, len(puntos)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
