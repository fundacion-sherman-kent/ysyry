"""Fronteras secas del corredor en la página: un marcador por paso con su ficha, a partir de la capa curada sitio/datos/fronteras.json.
Es una capa curada a mano y por verificar: marca DÓNDE están los pasos que la literatura abierta asocia con tráfico de personas, animales, flora y contrabando,
pero no mide ese tráfico (no hay fuente abierta que lo haga). Cada ficha dice qué se sabe, de dónde sale y qué no se sabe."""
import json
from pathlib import Path

import pulso as _pulso

ROT = {"personas": "Tráfico de personas", "animales": "Tráfico de animales", "flora": "Tráfico de flora", "contrabando": "Contrabando en general"}


def cargar(ruta):
    if not ruta or not Path(ruta).exists():
        return None
    d = json.load(open(ruta, encoding="utf-8"))
    for p in d["pasos"]:
        p["x"], p["y"] = _pulso.AX * p["lon"] + _pulso.BX, _pulso.AY * p["lat"] + _pulso.BY
    return d


def marca(i, p):
    return ('<g class="frontera-g clicable" data-i="fr%d" data-familia="seguridad fronteras" transform="translate(%.1f,%.1f)">'
            '<circle class="hit" r="12"/><path class="frontera" d="M0,-6.5L6.5,0L0,6.5L-6.5,0Z"/><path class="frontera-raya" d="M-3,0L3,0"/></g>' % (i, p["x"], p["y"]))


def info(i, p, d):
    ctx = ["Evidencia: Fuente única, no verificado. La posición es aproximada (±5 km) y lo que se dice de los flujos sale de informes y prensa públicos de carácter general, no de una medición."]
    cargados = [(ROT[k], v) for k, v in p["flujos"].items() if v]
    sin = [ROT[k] for k, v in p["flujos"].items() if not v]
    for r, v in cargados:
        ctx.append("%s: %s." % (r, v))
    if sin:
        ctx.append("Sin información cargada: " + "; ".join(sin) + ". Que no figure no significa que no ocurra: significa que esta ficha todavía no tiene un informe público que lo sustente.")
    ctx.append("Qué es un paso de frontera seca: un límite entre países que no está marcado por un río, así que se cruza a pie o en vehículo sin puente ni embarcación. Son, sobre todo, ciudades gemelas con comercio, familias y trabajo legítimos: marcar el paso NO implica que lo que lo cruza sea ilícito.")
    ctx.append("Lo que no dice: no mide cuánto tráfico ilícito pasa, no es una acusación contra una ciudad ni contra quienes viven en ella, y no reemplaza los datos de las autoridades de migración, aduana y seguridad de cada país.")
    return {"id": "fr%d" % i, "categoria": "Frontera seca · %s" % " – ".join(p["paises"]), "titulo": p["nombre"], "tipo": p["tipo"] + " · " + p["descripcion"],
            "fuente": "%s · capa curada por la dirección el %s/%s/%s · por verificar" % (p["fuente"], d["ultima_revision"][8:10], d["ultima_revision"][5:7], d["ultima_revision"][:4]),
            "clase": "riesgo", "coord": "%.3f, %.3f (aprox.)" % (p["lat"], p["lon"]), "foto": None, "ctx": ctx, "ctx_t": "Indicio y su evidencia", "ctx_f": "Capa curada: no se actualiza sola."}
