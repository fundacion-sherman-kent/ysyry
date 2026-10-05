#!/usr/bin/env python3
"""Escáner propio de Ysyry: detecta hechos sobre el corredor en titulares de prensa y de organismos, SIN ningún modelo (cero tokens).

Cómo funciona, de principio a fin y todo con reglas que se pueden leer y corregir:
  1. Baja los canales RSS/Atom públicos de medios regionales y de organismos (SENAD y Policía Nacional de Paraguay, entre otros).
  2. Descarta lo que no habla del corredor: el titular (o su bajada) tiene que nombrar un lugar del corredor (puertos, pasos y ciudades
     del río) o palabras del río (hidrovía, río Paraná, barcaza, convoy…).
  3. Clasifica el hecho por palabras clave: decomiso, detención u operativo, piratería o robo, siniestro náutico, navegabilidad,
     regulatorio o gremial, operativo del Estado. Un titular puede ser de más de un tipo.
  4. Extrae lo que se puede extraer con expresiones regulares: lugar, zona del pulso y cantidad (kilos, toneladas, litros, armas…).
  5. Junta los titulares casi iguales en un solo hecho (medios distintos que lo cubren) y comprueba que el enlace responda.
  6. Puntúa y guarda 14 días. Nada se publica como «hecho»: son CANDIDATOS detectados por reglas.

Lo que NO hace, y por eso nunca pasa de «candidato»: no entiende el texto, no verifica que el hecho sea cierto, y no puede probar que dos
medios sean independientes (muchos copian a una agencia o a un comunicado oficial). Por eso el nivel de evidencia automático no pasa de
«corroborado». Escribe DATOS_DIR/escaner.json."""
import hashlib
import html as _html
import json
import os
import re
import sys
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "sitio"))
import pulso as _pulso  # noqa: E402  (zona del pulso a partir de latitud y longitud)

UA = "Mozilla/5.0 (compatible; YsyryEscaner/1.0; +https://github.com/fundacion-sherman-kent/ysyry)"
DIAS = 14
# (dominio, canal, clase, idioma). «oficial» = organismo del Estado; «prensa» = medio.
FUENTES = [
    ("abc.com.py", "https://www.abc.com.py/arc/outboundfeeds/rss/?outputType=xml", "prensa", "es"),
    ("abc.com.py", "https://www.abc.com.py/arc/outboundfeeds/rss/category/policiales/?outputType=xml", "prensa", "es"),
    ("lanacion.com.py", "https://www.lanacion.com.py/arc/outboundfeeds/rss/?outputType=xml", "prensa", "es"),
    ("lacapital.com.ar", "https://www.lacapital.com.ar/rss/ultimo-momento.xml", "prensa", "es"),
    ("clarin.com", "https://www.clarin.com/rss/lo-ultimo/", "prensa", "es"),
    ("infobae.com", "https://www.infobae.com/arc/outboundfeeds/rss/", "prensa", "es"),
    ("perfil.com", "https://www.perfil.com/feed", "prensa", "es"),
    ("lanacion.com.ar", "https://www.lanacion.com.ar/arcio/rss/", "prensa", "es"),
    ("g1.globo.com", "https://g1.globo.com/rss/g1/mato-grosso-do-sul/", "prensa", "pt"),
    ("senad.gov.py", "https://www.senad.gov.py/feed/", "oficial", "es"),
    ("policianacional.gov.py", "https://www.policianacional.gov.py/feed/", "oficial", "es"),
]

# lugares del corredor: nombre normalizado -> (etiqueta, lat, lon). Ubicación aproximada del lugar mencionado, no del hecho.
LUGARES = {
    "rosario": ("Rosario", -32.95, -60.65), "san lorenzo": ("San Lorenzo", -32.75, -60.73), "timbues": ("Timbúes", -32.67, -60.77),
    "puerto general san martin": ("Puerto General San Martín", -32.72, -60.73), "san nicolas": ("San Nicolás", -33.33, -60.21),
    "villa constitucion": ("Villa Constitución", -33.23, -60.33), "zarate": ("Zárate", -34.10, -59.03), "campana": ("Campana", -34.17, -58.96),
    "nueva palmira": ("Nueva Palmira", -33.88, -58.42), "colonia del sacramento": ("Colonia", -34.47, -57.84),
    "puerto de buenos aires": ("Puerto de Buenos Aires", -34.60, -58.37), "dock sud": ("Dock Sud", -34.65, -58.35), "delta del parana": ("Delta del Paraná", -34.10, -58.60),
    "villeta": ("Villeta", -25.51, -57.56), "asuncion": ("Asunción", -25.28, -57.63), "concepcion": ("Concepción", -23.40, -57.43),
    "pilar": ("Pilar", -26.86, -58.30), "alberdi": ("Alberdi", -26.20, -58.14), "clorinda": ("Clorinda", -25.29, -57.72), "formosa": ("Formosa", -26.18, -58.18),
    "corrientes": ("Corrientes", -27.47, -58.83), "barranqueras": ("Barranqueras", -27.48, -58.93), "goya": ("Goya", -29.14, -59.26), "reconquista": ("Reconquista", -29.15, -59.65),
    "santa fe": ("Santa Fe", -31.63, -60.70), "paso de patria": ("Paso de Patria", -27.31, -58.57), "ayolas": ("Ayolas", -27.39, -56.84),
    "encarnacion": ("Encarnación", -27.33, -55.87), "posadas": ("Posadas", -27.37, -55.90), "ciudad del este": ("Ciudad del Este", -25.51, -54.61),
    "foz do iguacu": ("Foz do Iguaçu", -25.53, -54.58), "puerto iguazu": ("Puerto Iguazú", -25.60, -54.57), "salto del guaira": ("Salto del Guairá", -24.06, -54.34),
    "pedro juan caballero": ("Pedro Juan Caballero", -22.55, -55.73), "ponta pora": ("Ponta Porã", -22.54, -55.73), "canindeyu": ("Canindeyú", -24.20, -55.30),
    "alto parana": ("Alto Paraná", -25.30, -54.80), "triple frontera": ("Triple Frontera", -25.55, -54.58), "itaipu": ("Itaipú", -25.41, -54.59), "yacyreta": ("Yacyretá", -27.40, -56.72),
    "corumba": ("Corumbá", -19.01, -57.65), "ladario": ("Ladário", -19.00, -57.60), "porto murtinho": ("Porto Murtinho", -21.70, -57.88), "caceres": ("Cáceres", -16.07, -57.68),
    "bahia negra": ("Bahía Negra", -20.23, -58.17), "fuerte olimpo": ("Fuerte Olimpo", -21.04, -57.87), "puerto quijarro": ("Puerto Quijarro", -17.78, -57.77),
}
RIO = re.compile(r"\b(hidrovia|rio parana|rio paraguay|rio uruguay|rio de la plata|rio paraguai|barcazas?|convoyes? fluviales?|empujador|puerto fluvial|via navegable|puerto de rosario)\b")
TIPOS = [
    ("decomiso", "Decomiso o incautación", 3, [r"(decomis|incaut|secuestr\w* .{0,25}(kilos|kg|toneladas|cargamento)|cargamento de|kilos de|toneladas de|apreensao|apreendid)",
                                                r"(cocain|marihuan|cannabis|droga|estupefac|cigarrill|armas|municion|combustible|oro\b|madera|contraband|maconha|mercaderia)"]),
    ("detencion", "Detención u operativo contra el crimen organizado", 2, [r"(operativo|allanamiento|detien\w+|deten\w+|detuv\w+|aprehend|capturad|desbarat|desarticul|prision|presos?|expuls\w+)",
                                                                           r"(narco|trafico|contraband|banda|organizacion criminal|pcc|comando vermelho|crimen organizado|lavado)"]),
    ("pirateria", "Piratería o robo de carga", 3, [r"(pirater|piratas|robo de carga|asalt\w+ (a|al|una) (barcaza|buque|embarcacion|convoy)|abordaje|roubo de carga)"]),
    ("siniestro", "Siniestro náutico", 2, [r"(colision|choque|varadur|encall|hundimient|naufrag|derrame|incendio)", r"(barcaza|buque|convoy|embarcacion|remolcador|balsa|navio|barco)"]),
    ("navegabilidad", "Bajante, calado y navegabilidad", 1, [r"(bajante|calado|altura del rio|nivel del rio|dragado|dragagem|vazante)"]),
    ("regulatorio", "Licitación, peaje o conflicto gremial", 1, [r"(licitacion|peaje|concesion|paro\b|huelga|practicos|conflicto gremial|greve)", r"(hidrovia|puerto|portuari|navegacion|via navegable|porto)"]),
    ("estado", "Operativo de una fuerza del Estado", 1, [r"(prefectura|armada|gendarmeria|policia nacional|senad|fuerza naval|marinha)", r"(operativo|patrull|control|secuestro|incaut|detenc|apreens)"]),
]
CANTIDAD = re.compile(r"(\d{1,3}(?:[\.,]\d{3})+(?:[\.,]\d+)?|\d+(?:[\.,]\d+)?)\s*(kilos?|kilogramos?|kg|toneladas?|tn|litros?|cajetillas|armas|fusiles|cartuchos|municiones)\b")


def norm(s):
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()).split())


def num(s):
    s = s.strip()
    if re.fullmatch(r"\d{1,3}(?:[\.,]\d{3})+", s):
        return float(re.sub(r"[\.,]", "", s))
    return float(s.replace(",", "."))


def bajar(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read()


def items(raiz):
    for it in raiz.iter():
        t = it.tag.split("}")[-1]
        if t not in ("item", "entry"):
            continue
        g = lambda n: next((c for c in it if c.tag.split("}")[-1] == n), None)
        titulo = _html.unescape((g("title").text or "").strip()) if g("title") is not None else ""
        desc = ""
        for n in ("description", "summary", "content"):
            if g(n) is not None and g(n).text:
                desc = re.sub(r"<[^>]+>", " ", _html.unescape(g(n).text))[:500]
                break
        link = ""
        l = g("link")
        if l is not None:
            link = (l.get("href") or l.text or "").strip()
        fecha = ""
        for n in ("pubDate", "published", "updated"):
            if g(n) is not None and g(n).text:
                fecha = g(n).text.strip()
                break
        if titulo and link.startswith(("http://", "https://")):
            yield titulo, desc, link, fecha


def fecha_iso(s):
    from email.utils import parsedate_to_datetime
    try:
        return parsedate_to_datetime(s).astimezone(timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        m = re.match(r"(\d{4}-\d{2}-\d{2})", s or "")
        return m.group(1) if m else ""


def lugares_en(texto):
    return [(k, v) for k, v in LUGARES.items() if re.search(r"\b" + re.escape(k) + r"\b", texto)]


def clasificar(texto):
    tipos = []
    for tid, rotulo, peso, reglas in TIPOS:
        if all(re.search(r, texto) for r in reglas):
            tipos.append((tid, rotulo, peso))
    return tipos


def analizar(titulo, desc, dominio, clase):
    t = norm(titulo + " " + desc)
    lugs = lugares_en(t)
    rio = bool(RIO.search(t))
    if not lugs and not rio:
        return None
    tipos = clasificar(t)
    if not tipos:
        return None
    # los lugares genéricos solos (una provincia, una ciudad grande) no alcanzan para un tipo débil
    tipo_fuerte = any(p >= 2 for _, _, p in tipos)
    if not (tipo_fuerte or rio or len(lugs) >= 1 and any(k in ("hidrovia",) for k in [])):
        if not rio:
            return None
    q = CANTIDAD.search((titulo + " " + desc).lower())      # sobre el texto original: la normalización borra los puntos de los miles
    cantidad = {"valor": num(q.group(1)), "unidad": q.group(2)} if q else None
    zona = "general"
    if lugs:
        _, (_, lat, lon) = lugs[0]
        zona = _pulso.zona_de(_pulso.AX * lon + _pulso.BX, _pulso.AY * lat + _pulso.BY)
    puntaje = sum(p for _, _, p in tipos) + (2 if rio else 0) + (2 if lugs else 0) + (1 if cantidad else 0) + (1 if clase == "oficial" else 0)
    return {"tipos": [(a, b) for a, b, _ in tipos], "lugares": [v[0] for _, v in lugs][:4], "ubicacion": ([lugs[0][1][1], lugs[0][1][2]] if lugs else None),
            "zona": zona, "cantidad": cantidad, "puntaje": puntaje, "rio": rio}


def similares(a, b):
    ta, tb = set(norm(a).split()), set(norm(b).split())
    return bool(ta and tb) and len(ta & tb) / float(len(ta | tb)) >= 0.7


def verificar(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Range": "bytes=0-2048"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status < 400
    except Exception:
        return False


def main():
    carpeta = Path(os.environ.get("DATOS_DIR", "datos/publico"))
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / "escaner.json"
    previo = json.load(open(destino, encoding="utf-8")) if destino.exists() else {"eventos": []}
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    corte = (datetime.now(timezone.utc) - timedelta(days=DIAS)).strftime("%Y-%m-%d")
    consultadas, nuevos = [], []
    for dominio, url, clase, idioma in FUENTES:
        try:
            raiz = ET.fromstring(bajar(url))
        except Exception as e:
            print("  %-24s no respondió: %s" % (dominio, str(e)[:60]))
            consultadas.append({"dominio": dominio, "ok": False, "items": 0, "candidatos": 0})
            continue
        n = c = 0
        for titulo, desc, link, fecha in items(raiz):
            n += 1
            a = analizar(titulo, desc, dominio, clase)
            if a:
                c += 1
                nuevos.append({"titulo": titulo[:220], "url": link, "dominio": dominio, "clase": clase, "fecha": fecha_iso(fecha) or hoy, **a})
        print("  %-24s %3d items, %d candidatos" % (dominio, n, c))
        consultadas.append({"dominio": dominio, "ok": True, "items": n, "candidatos": c})
    if not any(x["ok"] for x in consultadas):
        print("Ninguna fuente respondió: no se toca el archivo anterior")
        return 1
    # juntar con lo previo y agrupar los titulares casi iguales en un solo hecho
    todos = [dict(e, _vieja=True) for e in previo.get("eventos", [])] + nuevos
    hechos = []
    for e in sorted(todos, key=lambda x: -x["puntaje"]):
        for h in hechos:
            if h["url"] == e["url"] or (set(t for t, _ in h["tipos"]) & set(t for t, _ in e["tipos"]) and similares(h["titulo"], e["titulo"])):
                med = {m["dominio"]: m for m in h["medios"]}
                for m in (e.get("medios") or [{"dominio": e["dominio"], "clase": e["clase"], "url": e["url"]}]):
                    med.setdefault(m["dominio"], m)
                h["medios"] = list(med.values())
                break
        else:
            hechos.append(dict(e, medios=e.get("medios") or [{"dominio": e["dominio"], "clase": e["clase"], "url": e["url"]}]))
    out = []
    ya_verificados = {e["url"]: e.get("verificado") for e in previo.get("eventos", [])}
    for h in hechos:
        if h["fecha"] < corte:
            continue
        h.pop("_vieja", None)
        h["id"] = hashlib.sha1(norm(h["titulo"]).encode()).hexdigest()[:10]
        h["verificado"] = ya_verificados.get(h["url"]) if h["url"] in ya_verificados else None
        out.append(h)
    out.sort(key=lambda x: (-x["puntaje"] - len(x["medios"]), x["fecha"]), reverse=False)
    out.sort(key=lambda x: (x["fecha"], x["puntaje"]), reverse=True)
    for h in out[:40]:                                  # sólo se comprueba el enlace de los 40 mejores y recientes
        if h["verificado"] is None:
            h["verificado"] = verificar(h["url"])
    salida = {"obtenido": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "dias": DIAS, "fuentes": consultadas,
              "aviso": "Candidatos detectados por reglas (palabras clave, lugares y cantidades) sobre titulares: no los verificó una persona y no son hechos confirmados.",
              "eventos": out[:200]}
    json.dump(salida, open(destino, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
    print("Candidatos guardados: %d (%d con 2 o más medios)" % (len(out), len([h for h in out if len(h["medios"]) >= 2])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
