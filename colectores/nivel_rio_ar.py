#!/usr/bin/env python3
"""Nivel del río en Argentina: escalas de la Prefectura Naval Argentina (PNA) publicadas por el Instituto Nacional del Agua (INA) en su
Sistema de Alerta Hidrológico (alerta.ina.gob.ar, API pública). Es una SEGUNDA fuente de nivel, de otro organismo y de otro país que la de
Meteorología de Paraguay, y trae los umbrales oficiales de cada escala (aguas bajas, alerta, evacuación).

Se baja la altura de las últimas lecturas de las escalas de la Hidrovía (Posadas hasta el Río de la Plata, Formosa sobre el Paraguay y
Concordia sobre el Uruguay) y se suma al historial. Escribe DATOS_DIR/nivel-rio-ar.json y nivel-rio-ar-historial.jsonl.

Atribución: Prefectura Naval Argentina, vía INA (Sistema de Alerta Hidrológico)."""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "https://alerta.ina.gob.ar/a5/obs/puntual/"
UA = {"User-Agent": "Ysyry-FUSK/1.0 (+https://github.com/fundacion-sherman-kent/ysyry)"}
# estaciones del INA (id) sobre el corredor
ESTACIONES = [14, 15, 18, 19, 20, 21, 22, 23, 24, 25, 26, 28, 29, 30, 31, 32, 33, 34, 35, 36, 38, 39, 40, 41, 43, 45, 57, 79, 85,
               1699]   # 1699: Nueva Palmira, de la Comisión Administradora del Río Uruguay (CARU), otro organismo; lecturas cada 30 minutos
DIAS = 12


def bajar(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    carpeta = Path(os.environ.get("DATOS_DIR", "datos/publico"))
    carpeta.mkdir(parents=True, exist_ok=True)
    try:
        series = bajar(API + "series?tipo=puntual&var_id=2&proc_id=1&estacion_id=" + ",".join(str(i) for i in ESTACIONES))["rows"]
    except Exception as e:
        print("INA no respondió (series): %s" % str(e)[:100])
        return 1
    hoy = datetime.now(timezone.utc)
    ini, fin = (hoy - timedelta(days=DIAS)).strftime("%Y-%m-%d"), (hoy + timedelta(days=1)).strftime("%Y-%m-%d")
    est = []
    for s in series:
        e = s["estacion"]
        try:
            obs = bajar(API + "observaciones?series_id=%d&timestart=%s&timeend=%s" % (s["id"], ini, fin))
        except Exception as ex:
            print("  %s sin observaciones: %s" % (e["nombre"], str(ex)[:60]))
            continue
        crudo = [(o["timestart"][:10], o["valor"]) for o in obs if o.get("valor") is not None]
        por_dia = {}
        for f, v in crudo:
            por_dia.setdefault(f, []).append(v)
        hoy_iso = hoy.strftime("%Y-%m-%d")
        # escalas con varias lecturas por día: media diaria, sin el día en curso (incompleto) para que la variación compare días enteros
        lect = sorted((f, round(sum(vs) / len(vs), 3)) for f, vs in por_dia.items() if len(vs) == 1 or f != hoy_iso)
        if not lect:
            continue
        ult, prev = lect[-1], (lect[-2] if len(lect) > 1 else None)
        est.append({"id": e["id"], "nombre": e["nombre"], "rio": e.get("rio") or "", "provincia": e.get("provincia") or "", "lat": e["geom"]["coordinates"][1],
                    "lon": e["geom"]["coordinates"][0], "propietario": e.get("propietario") or "", "nivel_alerta": e.get("nivel_alerta"), "nivel_evacuacion": e.get("nivel_evacuacion"),
                    "nivel_aguas_bajas": e.get("nivel_aguas_bajas"), "fecha": ult[0], "nivel_m": ult[1],
                    "var_cm": round((ult[1] - prev[1]) * 100) if prev else None, "serie": [[f, v] for f, v in lect]})
    if not est:
        print("Ninguna escala devolvió lecturas: no se toca el archivo anterior")
        return 1
    salida = {"obtenido": hoy.strftime("%Y-%m-%dT%H:%M:%SZ"),
              "fuente": {"nombre": "Prefectura Naval Argentina (escalas), publicadas por el INA en el Sistema de Alerta Hidrológico", "url": "https://alerta.ina.gob.ar/",
                         "nota": "Altura hidrométrica diaria de las escalas de la Hidrovía, con los umbrales oficiales de cada escala; no es el calado de la vía."},
              "estaciones": est}
    with open(carpeta / "nivel-rio-ar.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(salida, fh, ensure_ascii=False, separators=(",", ":"))
    hist = carpeta / "nivel-rio-ar-historial.jsonl"
    vistos = set()
    if hist.exists():
        for l in open(hist, encoding="utf-8"):
            if l.strip():
                j = json.loads(l)
                vistos.add((j["id"], j["fecha"]))
    nuevos = 0
    with open(hist, "a", encoding="utf-8", newline="\n") as fh:
        for x in est:
            for f, v in x["serie"]:
                if (x["id"], f) not in vistos:
                    fh.write(json.dumps({"id": x["id"], "estacion": x["nombre"], "fecha": f, "nivel_m": v}, ensure_ascii=False) + "\n")
                    nuevos += 1
    print("Escalas con lectura: %d de %d; lecturas nuevas en el historial: %d" % (len(est), len(ESTACIONES), nuevos))
    return 0


if __name__ == "__main__":
    sys.exit(main())
