#!/usr/bin/env python3
"""Cruza las detecciones de radar con el AIS recibido y con las demás pasadas.

Responde dos preguntas, y mide cuánto vale cada respuesta:

  1. ¿Qué detecciones NO tienen un AIS recibido cerca? Se compara contra las posiciones
     de AIS del registro, llevadas al instante exacto de la pasada por extrapolación
     (posición + rumbo + velocidad): un buque a 10 nudos recorre ~5 km en media hora.
  2. ¿Qué detecciones NO se mueven entre pasadas? Un objeto que aparece en el mismo lugar
     en varias pasadas es fijo (pila de puente, boya, pontón, barcaza amarrada): no es una
     candidata.

Y, como control del propio método, calcula para cada pasada con AIS cercano en el tiempo
el RECALL: de los buques con AIS que estaban en el agua, qué fracción tiene una detección
de radar a su lado. Si esa fracción es baja, el detector se pierde buques; si es alta, las
detecciones sin AIS son más confiables. Sin este número, cualquier lista de «candidatas» no
vale nada.

Lo que sale de acá son CANDIDATAS, nunca una confirmación. «Sin AIS» quiere decir «ningún
AIS recibido por nuestra red en ese lugar y momento»: puede ser un buque con el AIS apagado,
pero también uno que transmite y no llegó a ningún receptor (el río alto casi no tiene), una
barcaza empujada (el AIS informa al remolcador, no a cada barcaza) o una falsa alarma.

Entradas (DATOS_DIR, por defecto "datos"): radar/pasadas.jsonl y vivo/*.jsonl.
Salida: radar/cruce.json.
"""
import datetime
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

VENTANA_AIS_MIN = 75          # sólo se usan fixes de AIS a ±75 min de la pasada
EXTRAPOLAR_HASTA_MIN = 60     # no se extrapola un fix más viejo que esto
RADIO_MOVIL_M = 700.0         # error de la extrapolación + tamaño del buque
RADIO_QUIETO_M = 350.0
RADIO_FIJO_M = 40.0           # mismo objeto en otra pasada
PASADAS_PARA_FIJO = 2         # visto en al menos 2 OTRAS pasadas
M_POR_GRADO = 111_320.0


def a_metros(lon, lat, lat0):
    return np.column_stack([np.asarray(lon) * M_POR_GRADO * math.cos(math.radians(lat0)),
                            np.asarray(lat) * M_POR_GRADO])


def parsear(t):
    return datetime.datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)


def ais_en(carpeta, t):
    """Una posición por MMSI, llevada al instante t. Devuelve lista de (lon, lat, movil)."""
    mejor = {}
    for archivo in sorted((carpeta / "vivo").glob("*.jsonl")):
        with open(archivo, encoding="utf-8") as fh:
            for linea in fh:
                r = json.loads(linea)
                e = r.get("evento")
                if not e:
                    continue
                p = e.get("properties") or {}
                if not p.get("seen"):
                    continue
                try:
                    dt = (t - parsear(p["seen"])).total_seconds()
                except ValueError:
                    continue
                if abs(dt) > VENTANA_AIS_MIN * 60:
                    continue
                mmsi = str(e.get("id") or p.get("mmsi"))
                if mmsi not in mejor or abs(dt) < abs(mejor[mmsi][0]):
                    mejor[mmsi] = (dt, e["geometry"]["coordinates"], p)
    salida = []
    for dt, (lon, lat), p in mejor.values():
        sog, cog = p.get("sog"), p.get("cog")
        movil = bool(sog is not None and sog >= 1.0)
        if movil and cog is not None and abs(dt) <= EXTRAPOLAR_HASTA_MIN * 60:
            d = sog * 0.514444 * dt  # metros; dt>0: la pasada es posterior al fix
            rumbo = math.radians(cog)
            lat += math.degrees(d * math.cos(rumbo) / 6_371_000)
            lon += math.degrees(d * math.sin(rumbo) / (6_371_000 * math.cos(math.radians(lat))))
        salida.append((lon, lat, movil))
    return salida


def cruzar_pasada(pasada, ais):
    det = pasada["detecciones"]
    agua = [d for d in det if d["clase"] == "agua"]
    res = {"id": pasada["id"], "tiempo": pasada["tiempo"], "ais_cercanos": len(ais),
           "detecciones_agua": len(agua), "detecciones_orilla": pasada.get("objetos_orilla_no_afirmados", len(det) - len(agua))}
    if not det or not ais:
        res.update({"con_ais": None, "sin_ais": None, "recall": None})
        return res, [False] * len(det)
    lat0 = float(np.mean([d["lat"] for d in det]))
    pd_ = a_metros([d["lon"] for d in det], [d["lat"] for d in det], lat0)
    pa = a_metros([a[0] for a in ais], [a[1] for a in ais], lat0)
    arbol = cKDTree(pd_)
    # recall: de los buques con AIS (dentro del área cubierta por la pasada), cuántos tienen detección cerca
    cubiertos = [i for i, a in enumerate(ais) if arbol.query(pa[i], k=1)[0] < 30_000]  # hay detecciones en la zona
    hallados = 0
    for i in cubiertos:
        radio = RADIO_MOVIL_M if ais[i][2] else RADIO_QUIETO_M
        if arbol.query(pa[i], k=1)[0] <= radio:
            hallados += 1
    # detecciones con AIS cerca
    arbol_a = cKDTree(pa)
    con_ais = []
    for i, d in enumerate(det):
        dist, j = arbol_a.query(pd_[i], k=1)
        radio = RADIO_MOVIL_M if ais[j][2] else RADIO_QUIETO_M
        con_ais.append(bool(dist <= radio))
    n_agua_con = sum(1 for d, c in zip(det, con_ais) if d["clase"] == "agua" and c)
    res.update({"con_ais": n_agua_con, "sin_ais": len(agua) - n_agua_con,
                "recall": round(hallados / len(cubiertos), 2) if cubiertos else None,
                "ais_en_area": len(cubiertos), "ais_con_deteccion": hallados})
    return res, con_ais


def fijos(pasadas):
    """Para cada pasada, marca las detecciones vistas en el mismo lugar en otras pasadas."""
    todos = []
    for k, p in enumerate(pasadas):
        for d in p["detecciones"]:
            todos.append((d["lon"], d["lat"], k))
    if not todos:
        return {}
    lat0 = float(np.mean([t[1] for t in todos]))
    pts = a_metros([t[0] for t in todos], [t[1] for t in todos], lat0)
    arbol = cKDTree(pts)
    ks = np.array([t[2] for t in todos])
    marcas, base = {}, 0
    for k, p in enumerate(pasadas):
        m = []
        for i, d in enumerate(p["detecciones"]):
            vecinos = arbol.query_ball_point(pts[base + i], RADIO_FIJO_M)
            otras = {int(ks[v]) for v in vecinos if ks[v] != k}
            m.append(len(otras) >= PASADAS_PARA_FIJO)
        marcas[k] = m
        base += len(p["detecciones"])
    return marcas


def main():
    carpeta = Path(os.environ.get("DATOS_DIR", "datos"))
    arch = carpeta / "radar" / "pasadas.jsonl"
    if not arch.exists():
        print("No hay pasadas procesadas todavía.")
        return 0
    pasadas = [json.loads(l) for l in arch.read_text(encoding="utf-8").splitlines() if l.strip()]
    pasadas.sort(key=lambda p: p["tiempo"])
    marcas = fijos(pasadas)
    informe = []
    for k, p in enumerate(pasadas):
        ais = ais_en(carpeta, parsear(p["tiempo"]))
        res, con_ais = cruzar_pasada(p, ais)
        agua = [(i, d) for i, d in enumerate(p["detecciones"]) if d["clase"] == "agua"]
        res["fijas_entre_pasadas"] = sum(1 for i, _ in agua if marcas[k][i])
        res["candidatas"] = sum(1 for i, _ in agua if not marcas[k][i] and (not con_ais or not con_ais[i])) if ais else None
        informe.append(res)
        print("%s | agua %d, orilla %d | AIS cercano %d | con AIS %s, sin AIS %s | fijas %d | recall %s" % (
            res["id"], res["detecciones_agua"], res["detecciones_orilla"], res["ais_cercanos"],
            res["con_ais"], res["sin_ais"], res["fijas_entre_pasadas"], res["recall"]), flush=True)
    (carpeta / "radar" / "cruce.json").write_text(
        json.dumps({"generado": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "pasadas": informe}, ensure_ascii=False, indent=1) + chr(10), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
