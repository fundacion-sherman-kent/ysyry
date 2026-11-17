#!/usr/bin/env python3
"""Base de siniestros náuticos, derrames y cargas peligrosas en el corredor: acumula DIAS_BASE días los hechos de tipo «siniestro» que detecta el escáner propio (escaner.py, canales RSS de medios
y organismos) y les agrega la clasificación de la CARGA por palabras clave sobre el titular (combustibles e hidrocarburos, gas, químicos y fertilizantes, agroquímicos, otra carga, sin dato).
No hay base abierta que un robot pueda leer: el IBAMA de Brasil (comunicados de accidentes ambientales) bloquea el acceso automático y la Prefectura, la Marinha y la Armada Paraguaya no publican
siniestros como datos abiertos. Por eso son titulares sin verificar. Lee DATOS_DIR/escaner.json y escribe DATOS_DIR/siniestros-corredor.json."""
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

DIAS_BASE = 365
CARGAS = [
    ("combustible", "Combustibles e hidrocarburos", r"(combustible|nafta|gasoil|diesel|petroleo|hidrocarburo|fuel|derrame de|oleo|gasolina|etanol)"),
    ("gas", "Gas y amoníaco", r"(\bgas\b|\bglp\b|amoniaco|amonia|gnl)"),
    ("quimicos", "Químicos y fertilizantes", r"(quimic|fertilizante|acido|soda caustica|urea|toxic|peligros)"),
    ("agro", "Agroquímicos", r"(agroquimico|agrotoxic|plaguicida|herbicida)"),
    ("granos", "Granos y carga general", r"(soja|granos|cereal|maiz|trigo|contenedor|carga)"),
]
TIPOS_SIN = [("derrame", r"derram|vazamento|mancha|contaminacion del rio|oleo"), ("incendio", r"incendio|explosion|incendi"), ("hundimiento", r"hundimient|naufrag|afund"),
             ("varadura", r"varadur|encall"), ("colision", r"colision|choque|abalro")]


def norm(s):
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()


def carga_de(t):
    t = norm(t)
    for cid, _r, rx in CARGAS:
        if re.search(rx, t):
            return cid
    return "sin_dato"


def tipo_de(t):
    t = norm(t)
    for tid, rx in TIPOS_SIN:
        if re.search(rx, t):
            return tid
    return "otro"


def main():
    carpeta = Path(os.environ.get("DATOS_DIR", "datos/publico"))
    fuente = carpeta / "escaner.json"
    if not fuente.exists():
        print("No existe escaner.json")
        return 1
    esc = json.load(open(fuente, encoding="utf-8"))
    ruta = carpeta / "siniestros-corredor.json"
    previo = {}
    if ruta.exists():
        try:
            previo = json.load(open(ruta, encoding="utf-8"))
        except Exception:
            previo = {}
    base = {h["id"]: h for h in previo.get("hechos", [])}
    ahora = datetime.now(timezone.utc)
    nuevos = 0
    for e in esc.get("eventos", []):
        if not any(t[0] == "siniestro" for t in e.get("tipos", [])) or not e.get("fecha") or not e.get("id"):
            continue
        medios = [{"dominio": m["dominio"], "clase": m.get("clase", "prensa"), "url": m["url"]} for m in e.get("medios", []) if m.get("dominio") and m.get("url")]
        h = base.get(e["id"])
        if h:
            vistos = {m["url"] for m in h["medios"]}
            h["medios"] += [m for m in medios if m["url"] not in vistos]
            continue
        base[e["id"]] = {"id": e["id"], "fecha": e["fecha"], "titulo": e["titulo"][:220], "url": e["url"], "dominio": e["dominio"], "siniestro": tipo_de(e["titulo"]), "carga": carga_de(e["titulo"]),
                         "lugares": e.get("lugares", []), "ubicacion": e.get("ubicacion"), "zona": e.get("zona", "general"),
                         "medios": medios or [{"dominio": e["dominio"], "clase": e.get("clase", "prensa"), "url": e["url"]}]}
        nuevos += 1
    corte = (ahora - timedelta(days=DIAS_BASE)).strftime("%Y-%m-%d")
    hechos = sorted((h for h in base.values() if h["fecha"] >= corte), key=lambda h: h["fecha"], reverse=True)
    salida = {"obtenido": ahora.strftime("%Y-%m-%dT%H:%M:%SZ"), "desde_base": previo.get("desde_base") or ahora.strftime("%Y-%m-%d"),
              "fuente": {"nombre": "Escáner propio de Ysyry: canales RSS públicos de medios regionales y organismos", "url": "https://github.com/fundacion-sherman-kent/ysyry",
                         "nota": "No son datos oficiales. Detección y clasificación por palabras clave sobre titulares; ningún dato lo verificó una persona."},
              "hechos": hechos}
    with open(ruta, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(salida, fh, ensure_ascii=False, separators=(",", ":"))
    print("Siniestros: %d hechos en la base (%d nuevos)" % (len(hechos), nuevos))
    return 0


if __name__ == "__main__":
    sys.exit(main())
