#!/usr/bin/env python3
"""Posiciones de embarcaciones en vivo, vía la API de Open Waters AIS.

Open Waters (openwaters.io/ais) agrega dos redes comunitarias — AISHub y
aisstream.io — en un solo endpoint HTTP, sin necesidad de clave para leer.
Escrito contra su protocolo público y documentado, sin copiar código de
ningún repositorio de terceros.

Guarda sólo en el repositorio PRIVADO de registro. No imprime identidades;
sólo conteos. Si el servidor responde con un error, se informa como tal,
nunca se confunde con "no hay buques".

Fuente: Open Waters AIS <https://openwaters.io/ais/>, que a su vez atribuye
a AISHub <https://www.aishub.net> y a aisstream.io. Términos de reutilización
institucional no verificados aparte de su documentación pública.

Variables de entorno:
  DATOS_DIR   carpeta de salida (por defecto "datos")
  AIS_API     base de la API (por defecto la de Open Waters)
"""
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = os.environ.get("AIS_API", "https://ais.openwaters.io/v1/vessels")
USER_AGENT = "Ysyry/0.1 (Fundacion Sherman Kent; +https://github.com/fundacion-sherman-kent/ysyry)"

TRAMOS = {
    "1 Alto Paraguay (Cáceres-Corumbá)": (-19.3, -58.4, -15.8, -56.8),
    "2 Medio Paraguay (Corumbá-Asunción)": (-25.5, -58.3, -19.0, -57.0),
    "3 Paraguay-Paraná (Asunción-Corrientes)": (-27.7, -59.0, -25.2, -57.4),
    "4 Paraná medio (Corrientes-Rosario)": (-33.2, -61.0, -27.3, -58.3),
    "5 Paraná inferior y Delta (Rosario-Río de la Plata)": (-34.95, -60.9, -32.9, -57.6),
}


def pedir(bbox):
    """(estado, dict|texto). Nunca confunde un error de red con 'sin buques'."""
    url = BASE + "?bbox=%s,%s,%s,%s" % bbox
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]
    except Exception as e:
        return 0, str(e)[:200]


def main():
    carpeta = Path(os.environ.get("DATOS_DIR", "datos"))
    (carpeta / "vivo").mkdir(parents=True, exist_ok=True)

    obtenido = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    mes = obtenido[:7]
    eventos = []
    conteo = {}
    embarcaciones = set()
    errores = 0

    for nombre, (lo_lat, lo_lon, hi_lat, hi_lon) in TRAMOS.items():
        t0 = time.time()
        estado, resp = pedir((lo_lat, lo_lon, hi_lat, hi_lon))
        if estado != 200 or not isinstance(resp, dict):
            errores += 1
            print("%s -> ERROR HTTP %s: %s [%.1fs]" % (nombre, estado, str(resp)[:150], time.time() - t0), flush=True)
            conteo[nombre] = None
            continue
        feats = resp.get("features", [])
        conteo[nombre] = len(feats)
        for f in feats:
            mmsi = f.get("id") or (f.get("properties") or {}).get("mmsi")
            if mmsi:
                embarcaciones.add(mmsi)
            eventos.append({"obtenido": obtenido, "tramo": nombre, "evento": f,
                             "fuente": {"nombre": "Open Waters AIS", "atribucion": resp.get("attribution")}})
        print("%s -> %d buques [%.1fs]" % (nombre, len(feats), time.time() - t0), flush=True)

    if eventos:
        with open(carpeta / "vivo" / (mes + ".jsonl"), "a", encoding="utf-8", newline="\n") as fh:
            for e in eventos:
                fh.write(json.dumps(e, ensure_ascii=False, sort_keys=True) + "\n")

    print("\nResumen:")
    for t, n in conteo.items():
        print("  %s: %s" % (t, "sin dato (error)" if n is None else n))
    print("Embarcaciones distintas vistas:", len(embarcaciones))
    print("Fuente: Open Waters AIS (agrega AISHub + aisstream.io).")
    return 1 if errores == len(TRAMOS) else 0


if __name__ == "__main__":
    sys.exit(main())
