#!/usr/bin/env python3
"""Nivel del río, Dirección de Meteorología e Hidrología de Paraguay.

Lee la tabla pública de `meteorologia.gov.py/nivel-rio/` (actualizada a
diario por el organismo, no en vivo). No hay robots.txt que lo restrinja
(responde 404) y la consulta es una por día, vía el robot.

Escribe en DATOS_DIR/nivel-rio-py.json (dato PÚBLICO, va al repositorio
público de Ysyry — no es identidad de nadie, es una lectura institucional
de río, como las que ya usa SIWA).

Fuente: Dirección de Meteorología e Hidrología, República del Paraguay.
"""
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

URL = "https://www.meteorologia.gov.py/nivel-rio/indexconvencional.php"
USER_AGENT = "Ysyry/0.1 (Fundacion Sherman Kent; +https://github.com/fundacion-sherman-kent/ysyry)"


def main():
    carpeta = Path(os.environ.get("DATOS_DIR", "datos/publico"))
    carpeta.mkdir(parents=True, exist_ok=True)

    req = urllib.request.Request(URL, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            html = r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        print("ERROR HTTP %s" % e.code)
        return 1
    except Exception as e:
        print("ERROR:", str(e)[:200])
        return 1

    filas = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S)
    estaciones = []
    for f in filas:
        celdas = re.findall(r"<td[^>]*>(.*?)</td>", f, re.S)
        celdas = [re.sub(r"<[^>]+>", "", c).strip() for c in celdas]
        if len(celdas) < 6:
            continue
        estaciones.append({
            "estacion": celdas[0],
            "fecha_lectura": celdas[1],
            "nivel": celdas[2],
            "variacion_24h": celdas[3],
            "minimo_historico": celdas[4],
            "maximo_historico": celdas[5],
        })

    if not estaciones:
        print("ERROR: la tabla no trajo ninguna fila — posible cambio de formato del sitio")
        return 1

    salida = {
        "obtenido": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fuente": {
            "nombre": "Dirección de Meteorología e Hidrología, Paraguay",
            "url": URL,
            "nota": "Actualizado a diario por el organismo, no en vivo",
        },
        "estaciones": estaciones,
    }
    with open(carpeta / "nivel-rio-py.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(salida, fh, ensure_ascii=False, indent=1, sort_keys=True)

    # historial: una línea por estación y día de lectura; sin duplicar si el organismo no actualizó
    hist = carpeta / "nivel-rio-py-historial.jsonl"
    vistos = set()
    if hist.exists():
        for linea in open(hist, encoding="utf-8"):
            if linea.strip():
                j = json.loads(linea)
                vistos.add((j["estacion"], j["lectura"]))
    nuevos = 0
    with open(hist, "a", encoding="utf-8", newline="\n") as fh:
        for e in estaciones:
            m = re.match(r"\s*(-?\d+(?:[.,]\d+)?)", e["nivel"] or "")
            lectura = e["fecha_lectura"]
            if not m or (e["estacion"], lectura) in vistos:
                continue
            fh.write(json.dumps({"estacion": e["estacion"], "lectura": lectura, "nivel_m": float(m.group(1).replace(",", ".")),
                                 "obtenido": salida["obtenido"]}, ensure_ascii=False) + "\n")
            nuevos += 1
    print("Historial: %d lecturas nuevas" % nuevos)
    print("Estaciones leídas: %d" % len(estaciones))
    for e in estaciones[:3]:
        print("  %s: %s (%s)" % (e["estacion"], e["nivel"], e["fecha_lectura"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
