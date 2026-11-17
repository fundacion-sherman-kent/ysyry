#!/usr/bin/env python3
"""Genera sitio/datos/pistas.json: pistas de aterrizaje HABILITADAS (registradas) cercanas al corredor, de OurAirports (dominio público, ourairports.com).
Se queda con las que están a menos de KM_RIO del cauce dibujado del Paraná o del Paraguay, o a menos de KM_FRONTERA de un paso de frontera seca.
Sólo pistas registradas: las clandestinas no figuran en ninguna base abierta y por definición no se pueden mapear con datos abiertos.
Uso: pistas.py AIRPORTS.csv [SALIDA.json]   (bajar el CSV de https://davidmegginson.github.io/ourairports-data/airports.csv)"""
import csv
import json
import math
import sys
from datetime import date
from pathlib import Path

AQUI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AQUI))
import indicios as _ind
import pulso as _p

KM_RIO, KM_FRONTERA = 45, 60
TIPOS = {"small_airport": "pista pequeña", "medium_airport": "aeródromo mediano", "large_airport": "aeropuerto grande", "heliport": "helipuerto", "closed": "cerrada"}
KM_POR_UNIDAD = 111.0 / _p.AX * math.cos(math.radians(24))


def main():
    d = json.load(open(AQUI / "datos" / "mapa_v10.json", encoding="utf-8"))
    segs = _ind._segmentos(d["rio_parana"]) + _ind._segmentos(d["rio_paraguay"])
    fr = json.load(open(AQUI / "datos" / "fronteras.json", encoding="utf-8"))["pasos"]
    out = []
    for r in csv.DictReader(open(sys.argv[1], encoding="utf-8")):
        if r["iso_country"] not in ("PY", "AR", "BR", "BO", "UY") or r["type"] not in TIPOS or r["type"] == "heliport":
            continue
        la, lo = float(r["latitude_deg"]), float(r["longitude_deg"])
        x, y = _p.AX * lo + _p.BX, _p.AY * la + _p.BY
        if not (0 < x < 760 and 0 < y < 920):
            continue
        _, dr = _ind._al_rio(x, y, segs)
        dr *= KM_POR_UNIDAD
        df = min(math.hypot(la - f["lat"], (lo - f["lon"]) * math.cos(math.radians(24))) * 111 for f in fr)
        if dr > KM_RIO and df > KM_FRONTERA:
            continue
        out.append({"id": r["ident"], "n": r["name"], "t": r["type"], "p": r["iso_country"], "la": round(la, 4), "lo": round(lo, 4), "m": r["municipality"] or None,
                    "ft": int(float(r["elevation_ft"])) if r["elevation_ft"] else None, "km_rio": round(dr), "km_fr": round(df)})
    out.sort(key=lambda a: (a["p"], a["id"]))
    res = {"obtenido": date.today().isoformat(), "fuente": "OurAirports (ourairports.com), dominio público", "criterio": "a menos de %d km del río o de %d km de un paso de frontera seca; sin helipuertos" % (KM_RIO, KM_FRONTERA), "pistas": out}
    Path(sys.argv[2] if len(sys.argv) > 2 else AQUI / "datos" / "pistas.json").write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    from collections import Counter
    print(len(out), Counter(a["t"] for a in out), Counter(a["p"] for a in out))


main()
