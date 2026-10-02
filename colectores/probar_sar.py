#!/usr/bin/env python3
"""Sonda: ¿hay detecciones de buques por radar (Sentinel-1) sobre el río, y cuántas
no coinciden con ningún AIS?

Consulta el conjunto public-global-sar-presence:latest de Global Fishing Watch (4Wings)
sobre dos áreas del corredor y compara detecciones con coincidencia AIS (matched=true)
y sin ella (matched=false). Sólo imprime conteos agregados y la forma de la respuesta:
ninguna identidad. Sirve para decidir si vale construir el colector definitivo, porque
GFW detecta sobre todo en mar y costa, y el Paraná es un río interior.

Variables de entorno:
  GFW_TOKEN   token de la API de Global Fishing Watch (secreto del repositorio)
  DIAS        ventana en días hacia atrás desde hoy menos la demora (por defecto 30)
"""
import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://gateway.api.globalfishingwatch.org/v3/4wings/report"
DATASET = "public-global-sar-presence:latest"
USER_AGENT = "Ysyry/0.1 (Fundacion Sherman Kent; +https://github.com/fundacion-sherman-kent/ysyry)"

AREAS = {
    "Delta y Rosario (río inferior)": (-61.0, -34.9, -57.6, -32.5),
    "Corredor completo": (-62.0, -35.5, -56.0, -15.0),
    "Río de la Plata (estuario)": (-58.5, -35.6, -55.0, -34.0),
    "CONTROL mar: Atlántico frente a Uruguay y Buenos Aires": (-56.0, -39.0, -51.0, -35.0),
}


def poligono(b):
    lo_lon, lo_lat, hi_lon, hi_lat = b
    return {"type": "Polygon", "coordinates": [[[lo_lon, lo_lat], [hi_lon, lo_lat], [hi_lon, hi_lat],
                                                [lo_lon, hi_lat], [lo_lon, lo_lat]]]}


def consultar(token, bbox, desde, hasta, matched, resolucion="HIGH", temporal="ENTIRE"):
    q = [("spatial-resolution", resolucion), ("temporal-resolution", temporal), ("format", "JSON"),
         ("datasets[0]", DATASET), ("date-range", "%s,%s" % (desde, hasta)),
         ("filters[0]", "matched='%s'" % matched)]
    url = BASE + "?" + urllib.parse.urlencode(q)
    cuerpo = json.dumps({"geojson": poligono(bbox)}).encode()
    req = urllib.request.Request(url, data=cuerpo, method="POST", headers={
        "Authorization": "Bearer " + token, "Content-Type": "application/json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]
    except Exception as e:
        return 0, str(e)[:200]


def aplanar(resp):
    """La respuesta de 4Wings agrupa por dataset: {entries: [{dataset: [ {celdas...} ]}]}."""
    filas = []
    for entrada in (resp.get("entries") or []):
        for _, celdas in entrada.items():
            if isinstance(celdas, list):
                filas.extend(celdas)
    return filas


def sondear_fechas(token):
    """¿Hasta cuándo tiene datos el conjunto? Ventanas de 30 días, mar y Delta."""
    hoy = datetime.date.today()
    ventanas = [(hoy - datetime.timedelta(days=d + 30), hoy - datetime.timedelta(days=d))
                for d in (3, 60, 120, 240, 365, 540, 730)]
    for nombre in ("CONTROL mar: Atlántico frente a Uruguay y Buenos Aires", "Delta y Rosario (río inferior)"):
        print("== %s ==" % nombre, flush=True)
        for desde, hasta in ventanas:
            estado, resp = consultar(token, AREAS[nombre], desde, hasta, "false")
            if estado != 200 or not isinstance(resp, dict):
                print("  %s a %s -> HTTP %s: %s" % (desde, hasta, estado, str(resp)[:160]), flush=True)
                continue
            filas = aplanar(resp)
            total = sum(float(f.get("detections", f.get("value", 0)) or 0) for f in filas)
            print("  %s a %s -> %d celdas, %.0f detecciones sin AIS" % (desde, hasta, len(filas), total), flush=True)
    return 0


def main():
    token = os.environ.get("GFW_TOKEN", "")
    if not token:
        print("Falta GFW_TOKEN")
        return 2
    if os.environ.get("FECHAS") == "1":
        return sondear_fechas(token)
    dias = int(os.environ.get("DIAS", "30"))
    hasta = datetime.date.today() - datetime.timedelta(days=3)  # los últimos días suelen estar incompletos
    desde = hasta - datetime.timedelta(days=dias)
    print("Ventana: %s a %s (%d días)" % (desde, hasta, dias), flush=True)
    for nombre, bbox in AREAS.items():
        print("\n== %s ==" % nombre, flush=True)
        for matched in ("true", "false"):
            estado, resp = consultar(token, bbox, desde, hasta, matched)
            if estado != 200 or not isinstance(resp, dict):
                print("  matched=%s -> HTTP %s: %s" % (matched, estado, str(resp)[:250]), flush=True)
                continue
            filas = aplanar(resp)
            if not filas:
                print("    forma de la respuesta: %s" % json.dumps(resp)[:300], flush=True)
            claves = sorted({k for f in filas for k in f}) if filas else []
            total = sum(float(f.get("detections", f.get("value", 0)) or 0) for f in filas)
            print("  matched=%s -> %d celdas, %.0f detecciones. Campos: %s" % (matched, len(filas), total, claves), flush=True)
            if filas and matched == "false":
                lats = [f["lat"] for f in filas if "lat" in f]
                lons = [f["lon"] for f in filas if "lon" in f]
                if lats and lons:
                    print("    extensión de celdas sin AIS: lat %.2f..%.2f, lon %.2f..%.2f" %
                          (min(lats), max(lats), min(lons), max(lons)), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
