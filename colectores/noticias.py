#!/usr/bin/env python3
"""Segunda familia de fuentes: titulares de prensa sobre el corredor, de la API abierta de GDELT (gdeltproject.org).

Se guardan sólo el titular, el enlace, el medio y la fecha (nunca el texto de la nota), por tema y por zona, para que Ysyry cuente
cuántos MEDIOS DISTINTOS cubren un tema. Es una detección automática por palabras clave: no la verificó una persona, así que
nada de lo que sale de acá es un hecho, es un indicio de que hay cobertura. Se filtran titulares que no hablan del río (p. ej.
«piratas del asfalto»). GDELT pide una consulta cada 5 segundos: se espera más que eso y se reintenta.

Escribe DATOS_DIR/noticias.json (dato público: titulares y enlaces ya públicos)."""
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.gdeltproject.org/api/v2/doc/doc"
UA = "Ysyry-FUSK/1.0 (+https://github.com/fundacion-sherman-kent/ysyry)"
PAUSA = 9           # segundos entre consultas
RIO = r"(barcaza|buque|fluvial|\brio\b|puerto|hidrovia|parana|paraguay|pesquero|remolcador|convoy|embarcacion|prefectura|armada)"
TEMAS = [
    {"id": "pirateria", "rotulo": "Piratería y robo de carga fluvial", "idioma": "spanish",
     "q": '(pirateria OR "robo de carga" OR "asalto a barcaza" OR "ataque a buque" OR "piratas fluviales") (Parana OR hidrovia OR "rio Paraguay" OR barcaza)',
     "exige": RIO, "excluye": r"(asfalto|informatic|software|netflix|pelicula|serie|streaming|descarga)"},
    {"id": "crimen_organizado", "rotulo": "Crimen organizado transnacional en la Triple Frontera y el Alto Paraná", "idioma": "spanish",
     "q": '(PCC OR "Primer Comando de la Capital" OR "Comando Vermelho") (Paraguay OR Canindeyu OR "Alto Parana" OR "Triple Frontera" OR "Pedro Juan Caballero")',
     "exige": r"(pcc|primer comando|comando vermelho|paraguay|canindeyu|alto parana|triple frontera)", "excluye": r"(costa rica|curridabat|futbol|campeonato)"},
    {"id": "crimen_organizado_pt", "rotulo": "Crimen organizado transnacional en la Triple Frontera y el Alto Paraná", "idioma": "portuguese",
     "q": '(PCC OR "Primeiro Comando da Capital" OR "Comando Vermelho") (Paraguai OR "Foz do Iguaçu" OR "Ponta Porã" OR "Pedro Juan Caballero" OR "Tríplice Fronteira")',
     "exige": r"(pcc|primeiro comando|comando vermelho|paraguai|foz do iguacu|ponta pora|pedro juan|triplice fronteira)", "excluye": r"(futebol|campeonato|costa rica)"},
    {"id": "narcotrafico", "rotulo": "Narcotráfico por la vía fluvial", "idioma": "spanish",
     "q": '(narcotrafico OR cocaina OR cargamento OR "droga") (hidrovia OR "rio Parana" OR "rio Paraguay" OR barcaza OR "puerto de Rosario")',
     "exige": RIO, "excluye": r"(fentanilo|pacifico|caribe|ecuador|mexico)"},
    {"id": "navegabilidad", "rotulo": "Bajante, calado y navegabilidad", "idioma": "spanish",
     "q": '(bajante OR "bajante del Parana" OR "bajante del rio Paraguay" OR calado OR "nivel del rio") (Parana OR Paraguay OR hidrovia OR Rosario OR Asuncion)',
     "exige": r"(bajante|calado|nivel del rio|navegab|hidrovia|parana|paraguay)", "excluye": r"(tarifa|lluvia en la ciudad)"},
    {"id": "regulatorio", "rotulo": "Licitación, dragado y peaje de la Hidrovía", "idioma": "spanish",
     "q": '(hidrovia OR "via navegable troncal") (licitacion OR dragado OR peaje OR concesion OR "Jan De Nul" OR DEME)',
     "exige": r"(hidrovia|via navegable|dragado|peaje|concesion|jan de nul|deme)", "excluye": r"(autopista|ruta nacional)"},
    {"id": "gremial", "rotulo": "Conflictos gremiales en puertos y navegación", "idioma": "spanish",
     "q": '(practicos OR "paro" OR "conflicto gremial" OR huelga) (hidrovia OR "puerto de Rosario" OR "Puerto Zarate" OR "puertos del Parana" OR "San Lorenzo")',
     "exige": r"(practicos|puerto|hidrovia|portuari|navegacion|buques|barcazas)", "excluye": r"(futbol|docentes|colectivos|subte)"},
    {"id": "operativos", "rotulo": "Operativos de fuerzas de seguridad en el corredor", "idioma": "spanish",
     "q": '(Prefectura OR "Prefectura Naval" OR "Armada Paraguaya" OR "Gendarmeria") (operativo OR secuestro OR incautacion OR detenidos) (Parana OR "rio Paraguay" OR hidrovia OR barcaza)',
     "exige": RIO, "excluye": r"(pesca deportiva|regata)"},
]
# palabras que ubican el titular en una zona del pulso; lo que no coincide queda «general»
ZONAS = [("z4", r"(triple frontera|ciudad del este|foz do iguacu|puerto iguazu|alto parana|canindeyu|pedro juan|ponta pora|posadas|encarnacion|itaipu|yacyreta)"),
         ("z5", r"(rio paraguay|asuncion|concepcion|corumba|pilar|alberdi|villeta|ladario|porto murtinho|formosa|bahia negra)"),
         ("z3", r"(corrientes|santa fe|parana \(|entre rios|reconquista|goya|la paz)"),
         ("z2", r"(rosario|san lorenzo|san nicolas|puerto general san martin|timbues|villa constitucion|arroyo seco|san pedro)"),
         ("z1", r"(zarate|campana|delta|tigre|buenos aires|nueva palmira|montevideo|rio de la plata|dock sud|la plata)")]


def norm(s):
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()


def consultar(q, idioma):
    url = API + "?" + urllib.parse.urlencode({"query": "%s sourcelang:%s" % (q, idioma), "mode": "artlist", "maxrecords": 40,
                                              "format": "json", "timespan": "7d", "sort": "datedesc"})
    for intento, espera in enumerate((PAUSA, 30, 60, 120)):      # GDELT limita por dirección: se espera cada vez más
        time.sleep(espera)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
                texto = r.read().decode("utf-8", "replace")
            if texto.lstrip().startswith("{"):
                return json.loads(texto).get("articles", [])
            print("  GDELT pide esperar (intento %d)" % (intento + 1))
        except Exception as e:
            print("  fallo (intento %d): %s" % (intento + 1, str(e)[:80]))
    return None


def zona(titulo):
    t = norm(titulo)
    for z, rx in ZONAS:
        if re.search(rx, t):
            return z
    return "general"


def main():
    carpeta = Path(os.environ.get("DATOS_DIR", "datos/publico"))
    previo = {}
    if (carpeta / "noticias.json").exists():
        try:
            previo = json.load(open(carpeta / "noticias.json", encoding="utf-8"))
        except Exception:
            previo = {}
    salida = {"obtenido": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "fuente": {"nombre": "GDELT Project (API DOC 2.0)", "url": "https://www.gdeltproject.org/",
                         "nota": "Detección automática por palabras clave sobre titulares de los últimos 7 días. No verificada por una persona."},
              "temas": {}}
    fallas, frescos = [], []
    for t in TEMAS:
        print("Tema:", t["id"])
        arts = consultar(t["q"], t["idioma"])
        if arts is None:
            # se conserva lo último bueno de este tema, rotulado con su fecha, y se cuenta como falla
            viejo = (previo.get("temas") or {}).get(t["id"].replace("_pt", ""))
            if viejo and viejo.get("articulos") and not viejo.get("error"):
                viejo = dict(viejo, desactualizado_desde=viejo.get("desactualizado_desde") or previo.get("obtenido", ""))
                salida["temas"][t["id"].replace("_pt", "")] = viejo
            else:
                salida["temas"].setdefault(t["id"].replace("_pt", ""), {"rotulo": t["rotulo"], "error": "GDELT no respondió", "articulos": []})
            fallas.append(t["id"])
            continue
        frescos.append(t["id"])
        vistos, lista = set(), []
        for a in arts:
            tit = (a.get("title") or "").strip()
            n = norm(tit)
            if not tit or n in vistos or not re.search(t["exige"], n) or re.search(t["excluye"], n):
                continue
            vistos.add(n)
            lista.append({"titulo": tit[:220], "url": a.get("url", ""), "dominio": a.get("domain", ""), "fecha": (a.get("seendate") or "")[:8],
                          "pais": a.get("sourcecountry", ""), "zona": zona(tit)})
        base = t["id"].replace("_pt", "")
        previo = salida["temas"].get(base)
        if previo and not previo.get("error"):
            previo["articulos"] += lista
        else:
            salida["temas"][base] = {"rotulo": t["rotulo"], "articulos": lista}
        print("  %d titulares útiles de %d" % (len(lista), len(arts)))
    for v in salida["temas"].values():
        v["dominios_distintos"] = len({a["dominio"] for a in v["articulos"]})
    carpeta.mkdir(parents=True, exist_ok=True)
    if not frescos:
        print("GDELT no respondió en ningún tema (limita las consultas): no se toca el archivo anterior")
        return 1
    salida["frescos"], salida["fallas"] = frescos, fallas
    with open(carpeta / "noticias.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(salida, fh, ensure_ascii=False, indent=1)
    print("Temas: %d, titulares: %d" % (len(salida["temas"]), sum(len(v["articulos"]) for v in salida["temas"].values())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
