#!/usr/bin/env python3
"""Mareógrafos del Servicio de Hidrografía Naval (SHN, Armada Argentina) sobre el tramo final del corredor: Martín García, San Fernando y Buenos Aires.
Dato abierto oficial «Datos Horarios de Marea» (hidro.gob.ar/DA/DatosAbiertos.asp): alturas horarias de los últimos 10 días, en metros sobre el Plano
de Reducción de Sondajes del Río de la Plata. Es un organismo distinto de la Prefectura (PNA) y de la CARU, y mide el mismo tramo.

El nivel del Plata sube y baja con la marea y el viento, por eso la variación se calcula entre medias de días completos (24 horas). La SHN no publica
umbrales de aguas bajas para estas escalas: sólo sirve para corroborar la tendencia.
Escribe DATOS_DIR/nivel-rio-shn.json."""
import csv
import io
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

URL = "https://www.hidro.gob.ar/oceanografia/AlturasHorarias.asp?export=csv"
UA = {"User-Agent": "Mozilla/5.0 (compatible; YsyryFUSK/1.0; +https://github.com/fundacion-sherman-kent/ysyry)"}
# ubicación aproximada de cada mareógrafo (la SHN no publica coordenadas en el CSV)
ESTACIONES = {"Martín García": (-34.183, -58.250), "San Fernando": (-34.443, -58.530), "Buenos Aires": (-34.571, -58.366)}


def main():
    carpeta = Path(os.environ.get("DATOS_DIR", "datos/publico"))
    carpeta.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(urllib.request.Request(URL, headers=UA), timeout=60) as r:
            texto = r.read().decode("latin-1")
    except Exception as e:
        print("SHN no respondió: %s" % str(e)[:100])
        return 1
    filas = list(csv.reader(io.StringIO(texto), delimiter=";"))
    cab = filas[0]
    cols = {}
    for nombre in ESTACIONES:
        clave = nombre.replace("í", "").lower()          # «Martín García» llega con la í rota según la codificación
        for i, c in enumerate(cab):
            if c.replace("�", "").replace("í", "").replace("Ã", "").replace("­", "").lower().startswith(clave[:6]) and clave.split()[-1][:4] in c.lower().replace("�", ""):
                cols[nombre] = i
    est = []
    for nombre, (lat, lon) in ESTACIONES.items():
        i = cols.get(nombre)
        if i is None:
            print("  %s: columna no encontrada" % nombre)
            continue
        datos = []
        for f in filas[1:]:
            if len(f) > i and f[i].strip():
                try:
                    datos.append((datetime.strptime(f[0].strip(), "%d/%m/%Y %H:%M"), float(f[i])))
                except ValueError:
                    pass
        datos.sort()
        if not datos:
            continue
        por_dia = {}
        for t, v in datos:
            por_dia.setdefault(t.date(), []).append(v)
        completos = [(d, sum(vs) / len(vs)) for d, vs in sorted(por_dia.items()) if len(vs) >= 23]
        var = round((completos[-1][1] - completos[-2][1]) * 100) if len(completos) >= 2 else None
        t_ult, v_ult = datos[-1]
        est.append({"nombre": nombre, "lat": lat, "lon": lon, "hora_local": t_ult.strftime("%Y-%m-%d %H:%M"), "nivel_m": v_ult,
                    "media_dia_m": round(completos[-1][1], 3) if completos else None, "dia_media": str(completos[-1][0]) if completos else None, "var_cm": var})
        print("  %s: %.2f m (%s), media del día %s, variación entre días completos %s cm" % (nombre, v_ult, est[-1]["hora_local"], est[-1]["media_dia_m"], var))
    if not est:
        print("SHN no devolvió lecturas: no se toca el archivo anterior")
        return 1
    salida = {"obtenido": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "fuente": {"nombre": "Servicio de Hidrografía Naval (Argentina), Datos Horarios de Marea", "url": "https://www.hidro.gob.ar/oceanografia/alturashorarias.asp",
                         "nota": "Alturas horarias sobre el Plano de Reducción de Sondajes del Río de la Plata (hora de Argentina). Mueven la marea y el viento; sin umbrales de aguas bajas."},
              "estaciones": est}
    with open(carpeta / "nivel-rio-shn.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(salida, fh, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
