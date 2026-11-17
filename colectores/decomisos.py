#!/usr/bin/env python3
"""Base estructurada de decomisos e incautaciones en el corredor, que ACUMULA durante DIAS_BASE días los hechos de tipo «decomiso» que detecta el escáner propio (escaner.py:
canales RSS públicos de medios regionales y de organismos como la SENAD, con detección por reglas; no usa GDELT, que bloquea las consultas desde GitHub).

El escáner sólo guarda 14 días; acá se conservan 12 meses, y a cada hecho se le agrega la clasificación de la MERCADERÍA (drogas, armas, cigarrillos, combustible, fauna y flora, agroquímicos y ganado,
oro, dinero, mercadería en general) por palabras clave sobre el titular, que puede equivocarse. Se guarda sólo titular, enlace, medio y fecha, lugar mencionado y cantidad citada en el titular.
No son bases oficiales: ni la Policía Federal y la Receita Federal de Brasil, ni la SENAD y la DNIT de Paraguay, ni la ARCA y las fuerzas federales de Argentina publican decomisos como datos abiertos
legibles por un robot. Un titular no es un hecho verificado, y que haya decomisos informados no mide cuánto contrabando pasa.

Lee DATOS_DIR/escaner.json y escribe DATOS_DIR/decomisos-corredor.json."""
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

DIAS_BASE = 365
CLASES = [
    ("erradicacion", "Erradicación de cultivos y destrucción de plantaciones", r"(erradic|ofensiva|plantacion|perdidas al narco|destruccion|destruyen|destruyo)"),
    ("drogas", "Drogas", r"(narcotraf|cocaina|marihuana|maconha|droga|estupefaciente|cannabis|crack|clorhidrato|pasta base|extasis|skunk|narcotic|dosis|laboratorio)"),
    ("armas", "Armas y municiones", r"(\barmas?\b|municion|fusil|pistola|armamento|explosiv|granada|cartucho)"),
    ("cigarrillos", "Cigarrillos y tabaco", r"(cigarrillo|cigarro|tabaco|cajetilla)"),
    ("combustible", "Combustible", r"(combustible|nafta|gasoil|diesel|gasolina|etanol)"),
    ("fauna_flora", "Fauna, flora y madera", r"(fauna|silvestre|madera|yacare|caiman|jacare|\btala\b|rollos|especies protegidas|tortuga|carbon vegetal|animales exotic)"),
    ("agro", "Agroquímicos, ganado y granos", r"(agroquimico|agrotoxic|plaguicida|fitosanitario|\bsemillas\b|ganado|\bcarne\b|\bsoja\b|granos|fertilizante)"),
    ("oro", "Oro y minería ilegal", r"(\boro\b|mineria ilegal|garimpo|garimpeir|mercurio)"),
    ("dinero", "Dinero y divisas", r"(divisas|dolares|efectivo|lavado|\breais\b|dinheiro|guaranies)"),
    ("mercaderia", "Mercadería y contrabando en general", r"(contraband|mercader|electronic|celulares|\bropa\b|perfume|descaminho|bebidas|whisky|neumaticos|aduana)"),
]


def norm(s):
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()


def clase_de(titulo):
    t = norm(titulo)
    for cid, _rot, rx in CLASES:
        if re.search(rx, t):
            return cid
    return "otra"


def main():
    carpeta = Path(os.environ.get("DATOS_DIR", "datos/publico"))
    fuente = carpeta / "escaner.json"
    if not fuente.exists():
        print("No existe escaner.json: nada que acumular")
        return 1
    esc = json.load(open(fuente, encoding="utf-8"))
    ruta = carpeta / "decomisos-corredor.json"
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
        if not any(t[0] == "decomiso" for t in e.get("tipos", [])) or not e.get("fecha") or not e.get("id"):
            continue
        medios = [{"dominio": m["dominio"], "clase": m.get("clase", "prensa"), "url": m["url"]} for m in e.get("medios", []) if m.get("dominio") and m.get("url")]
        h = base.get(e["id"])
        if h:
            vistos = {m["url"] for m in h["medios"]}
            h["medios"] += [m for m in medios if m["url"] not in vistos]
            continue
        base[e["id"]] = {"id": e["id"], "fecha": e["fecha"], "titulo": e["titulo"][:220], "url": e["url"], "dominio": e["dominio"], "clase_fuente": e.get("clase", "prensa"),
                         "mercaderia": clase_de(e["titulo"]), "lugares": e.get("lugares", []), "ubicacion": e.get("ubicacion"), "zona": e.get("zona", "general"),
                         "cantidad": e.get("cantidad"), "medios": medios or [{"dominio": e["dominio"], "clase": e.get("clase", "prensa"), "url": e["url"]}], "visto": ahora.strftime("%Y-%m-%d")}
        nuevos += 1
    corte = (ahora - timedelta(days=DIAS_BASE)).strftime("%Y-%m-%d")
    hechos = sorted((h for h in base.values() if h["fecha"] >= corte), key=lambda h: h["fecha"], reverse=True)
    salida = {"obtenido": ahora.strftime("%Y-%m-%dT%H:%M:%SZ"), "desde_base": previo.get("desde_base") or ahora.strftime("%Y-%m-%d"),
              "fuente": {"nombre": "Escáner propio de Ysyry: canales RSS públicos de medios regionales y de la SENAD", "url": "https://github.com/fundacion-sherman-kent/ysyry",
                         "nota": "No son datos oficiales ni estadísticas. Detección y clasificación por palabras clave sobre titulares; ningún dato lo verificó una persona."},
              "hechos": hechos}
    with open(ruta, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(salida, fh, ensure_ascii=False, separators=(",", ":"))
    print("Decomisos: %d hechos en la base (%d nuevos hoy)" % (len(hechos), nuevos))
    return 0


if __name__ == "__main__":
    sys.exit(main())
