#!/usr/bin/env python3
"""Viento en el Río de la Plata y el Delta, del estado del tiempo presente del Servicio Meteorológico Nacional de Argentina (SMN).
Dato abierto (licencia CC BY 4.0), sin clave: ssl.smn.gob.ar/dpd/zipopendata.php?dato=tiepre. Se conservan las estaciones de la ribera del Plata y el
bajo Delta. Sirve de CONTEXTO del nivel: un viento sostenido del Este o el Sudeste empuja agua hacia el interior del Plata y sube el nivel aunque el río
venga bajando (la «sudestada»). No mide el nivel ni predice nada.
Escribe DATOS_DIR/viento-smn.json."""
import io
import json
import os
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

URL = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=tiepre"
UA = {"User-Agent": "Mozilla/5.0 (compatible; YsyryFUSK/1.0; +https://github.com/fundacion-sherman-kent/ysyry)"}
ESTACIONES = ("Aeroparque Buenos Aires", "San Fernando", "Punta Indio B.A.", "La Plata", "Buenos Aires")


def main():
    carpeta = Path(os.environ.get("DATOS_DIR", "datos/publico"))
    carpeta.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(urllib.request.Request(URL, headers=UA), timeout=60) as r:
            z = zipfile.ZipFile(io.BytesIO(r.read()))
        texto = z.read(z.namelist()[0]).decode("latin-1")
    except Exception as e:
        print("SMN no respondió: %s" % str(e)[:100])
        return 1
    est = []
    for linea in texto.splitlines():
        c = [x.strip() for x in linea.split(";")]
        if len(c) < 10 or c[0] not in ESTACIONES:
            continue
        viento = c[8]
        partes = viento.split()
        if viento.lower().startswith("calma"):
            direccion, kmh = "Calma", 0
        elif len(partes) >= 2 and partes[-1].isdigit():
            direccion, kmh = " ".join(partes[:-1]), int(partes[-1])
        else:
            continue
        est.append({"nombre": c[0], "fecha": c[1], "hora": c[2], "direccion": direccion, "kmh": kmh, "estado": c[3]})
        print("  %-24s %s %s: %s %d km/h" % (c[0], c[1], c[2], direccion, kmh))
    if not est:
        print("Ninguna estación del Plata en el archivo: no se toca el anterior")
        return 1
    salida = {"obtenido": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "fuente": {"nombre": "Servicio Meteorológico Nacional (Argentina), estado del tiempo presente", "url": "https://www.smn.gob.ar/",
                         "nota": "Última observación de cada estación (km/h). Licencia CC BY 4.0."}, "estaciones": est}
    with open(carpeta / "viento-smn.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(salida, fh, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
