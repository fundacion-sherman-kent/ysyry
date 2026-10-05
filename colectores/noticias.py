#!/usr/bin/env python3
"""Segunda familia de fuentes: titulares de prensa sobre el corredor, de la API abierta de GDELT (gdeltproject.org) y, cuando GDELT
limita las consultas (lo hace seguido), de los canales RSS públicos de seis medios regionales.

Se guardan sólo el titular, el enlace, el medio y la fecha (nunca el texto de la nota), por tema y por zona, para que Ysyry cuente
cuántos MEDIOS DISTINTOS cubren un tema. Es una detección automática por palabras clave: no la verificó una persona, así que
nada de lo que sale de acá es un hecho, es un indicio de que hay cobertura. Se filtran titulares que no hablan del río (p. ej.
«piratas del asfalto»). GDELT pide una consulta cada 5 segundos: se espera más que eso y se reintenta.

Escribe DATOS_DIR/noticias.json (dato público: titulares y enlaces ya públicos)."""
import json
import html as _html
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
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
# Respaldo: canales RSS públicos de medios regionales (hecho para que lo lean programas; se guarda sólo titular, enlace, medio y fecha).
FEEDS = [("abc.com.py", "https://www.abc.com.py/arc/outboundfeeds/rss/?outputType=xml"),
         ("lanacion.com.py", "https://www.lanacion.com.py/arc/outboundfeeds/rss/?outputType=xml"),
         ("lacapital.com.ar", "https://www.lacapital.com.ar/rss/ultimo-momento.xml"),
         ("clarin.com", "https://www.clarin.com/rss/lo-ultimo/"),
         ("infobae.com", "https://www.infobae.com/arc/outboundfeeds/rss/"),
         ("perfil.com", "https://www.perfil.com/feed")]
# cada tema del respaldo exige que el titular (o su bajada) cumpla TODAS estas expresiones
RSS_REGLAS = {
    "pirateria": [r"(pirater|piratas|robo de carga|asalto|asaltan|ataque a (buque|barcaza)|abordaje)", RIO],
    "crimen_organizado": [r"(\bpcc\b|primer comando|comando vermelho)", r"(paraguay|canindeyu|alto parana|triple frontera|pedro juan|hidrovia)"],
    "narcotrafico": [r"(narco|cocaina|cargamento|droga|estupefaciente)", r"(barcaza|hidrovia|rio parana|rio paraguay|puerto de rosario|convoy)"],
    "navegabilidad": [r"(bajante|calado|nivel del rio|altura del rio)", r"(parana|paraguay|hidrovia|rosario|asuncion)"],
    "regulatorio": [r"(hidrovia|via navegable)", r"(licitacion|dragado|peaje|concesion|jan de nul|deme\b)"],
    "gremial": [r"(practicos|\bparo\b|huelga|conflicto gremial)", r"(hidrovia|portuari|puerto de|navegacion|barcazas|buques)"],
    "operativos": [r"(prefectura|armada paraguaya|gendarmeria)", r"(operativo|secuestro|incautacion|detenid)", r"(rio parana|rio paraguay|hidrovia|barcaza|puerto)"],
}


def bajar_feeds():
    """[(dominio, titulo, bajada_normalizada, url, fecha)] de los canales RSS que responden."""
    out = []
    for dominio, url in FEEDS:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; " + UA + ")"}), timeout=40) as r:
                raiz = ET.fromstring(r.read())
        except Exception as e:
            print("  RSS %s no respondió: %s" % (dominio, str(e)[:60]))
            continue
        n = 0
        for it in raiz.iter("item"):
            tit = _html.unescape((it.findtext("title") or "").strip())
            desc = re.sub(r"<[^>]+>", " ", _html.unescape(it.findtext("description") or ""))
            link = (it.findtext("link") or "").strip()
            if tit and link.startswith(("http://", "https://")):
                f = (it.findtext("pubDate") or "")[5:16]
                out.append((dominio, tit, norm(tit + " " + desc[:300]), link, f))
                n += 1
        print("  RSS %s: %d items" % (dominio, n))
    return out


def desde_feeds(tema_id, feeds):
    reglas = RSS_REGLAS.get(tema_id)
    if not reglas:
        return []
    lista, vistos = [], set()
    for dominio, tit, texto, link, f in feeds:
        nt = norm(tit)
        if nt in vistos or not all(re.search(rx, texto) for rx in reglas):
            continue
        vistos.add(nt)
        lista.append({"titulo": tit[:220], "url": link, "dominio": dominio, "fecha": f, "pais": "", "zona": zona(tit)})
    return lista


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
    fallas, frescos, bloqueos = [], [], 0
    for t in TEMAS:
        print("Tema:", t["id"])
        # disyuntor: si GDELT ya falló del todo en dos temas seguidos, bloquea esta dirección y no se pierde más tiempo
        arts = None if bloqueos >= 2 else consultar(t["q"], t["idioma"])
        bloqueos = bloqueos + 1 if arts is None else 0
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
        acum = salida["temas"].get(base)
        if acum and not acum.get("error"):
            acum["articulos"] += lista
        else:
            salida["temas"][base] = {"rotulo": t["rotulo"], "articulos": lista}
        print("  %d titulares útiles de %d" % (len(lista), len(arts)))
    if fallas:
        print("GDELT falló en %d temas: se completan con los canales RSS de seis medios" % len(fallas))
        feeds = bajar_feeds()
        if feeds:
            for tid in {f.replace("_pt", "") for f in fallas}:
                arts = desde_feeds(tid, feeds)
                hoy = salida["obtenido"][:10]
                for x in arts:
                    x["visto"] = hoy
                # los canales sólo muestran lo más reciente: se acumula lo ya visto durante 7 días
                corte = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
                ya = {x["url"] for x in arts}
                arts += [x for x in ((previo.get("temas") or {}).get(tid, {}).get("articulos") or []) if x.get("visto", "") >= corte and x.get("url") not in ya]
                rot = next((t["rotulo"] for t in TEMAS if t["id"].replace("_pt", "") == tid), tid)
                salida["temas"][tid] = {"rotulo": rot, "articulos": arts, "origen": "rss de 6 medios (GDELT limitó las consultas)"}
                if "%s" % tid not in frescos:
                    frescos.append(tid)
            fallas = [f for f in fallas if f.replace("_pt", "") not in frescos]
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
