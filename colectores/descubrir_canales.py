#!/usr/bin/env python3
"""Descubre canales RSS/Atom de un sitio: lee su portada buscando el aviso estándar <link rel="alternate" type="application/rss+xml"> y, si no
está, prueba las rutas habituales. Cada candidato se valida bajándolo y leyéndolo como XML: sólo cuenta si trae ítems.

Es la herramienta con la que se actualizan los canales que dejan de responder: PROPONE el canal que anda, no lo cambia solo (la dirección o la
curaduría lo confirma). Sin ningún modelo.

Uso: descubrir_canales.py URL_PORTADA [URL_PORTADA ...]"""
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

UA = "Mozilla/5.0 (compatible; YsyryEscaner/1.0; +https://github.com/fundacion-sherman-kent/ysyry)"
RUTAS = ["/feed", "/feed/", "/rss", "/rss/", "/rss.xml", "/feed.xml", "/atom.xml", "/index.xml", "/arc/outboundfeeds/rss/?outputType=xml", "/feeds/posts/default", "/?feed=rss2"]


def bajar(url, t=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xml,*/*"})
    with urllib.request.urlopen(req, timeout=t) as r:
        return r.read(3_000_000), r.geturl()


def items(datos):
    """Cantidad de ítems si es un canal válido; 0 si no. Tolera XML con basura al final (caso de algunos medios)."""
    try:
        raiz = ET.fromstring(datos)
    except ET.ParseError:
        try:
            texto = datos.decode("utf-8", "replace")
            texto = texto[: texto.rfind("</item>") + 7] + "</channel></rss>" if "</item>" in texto else texto
            raiz = ET.fromstring(texto.encode("utf-8"))
        except Exception:
            return 0
    return sum(1 for e in raiz.iter() if e.tag.split("}")[-1] in ("item", "entry"))


def descubrir(portada):
    candidatos = []
    base = portada if portada.startswith("http") else "https://" + portada
    try:
        html, final = bajar(base)
        txt = html.decode("utf-8", "replace")
        for m in re.finditer(r"<link[^>]+>", txt, re.I):
            tag = m.group(0)
            if re.search(r'type=["\']application/(rss|atom)\+xml', tag, re.I):
                h = re.search(r'href=["\']([^"\']+)', tag, re.I)
                if h:
                    candidatos.append(urllib.parse.urljoin(final, h.group(1).replace("&amp;", "&")))
        raiz = "%s://%s" % urllib.parse.urlparse(final)[:2]
    except Exception as e:
        print("  portada no responde (%s)" % str(e)[:60])
        raiz = base.rstrip("/")
    candidatos += [raiz + r for r in RUTAS]
    vistos, ok = set(), []
    for u in candidatos:
        if u in vistos:
            continue
        vistos.add(u)
        try:
            datos, _ = bajar(u)
            n = items(datos)
            if n:
                ok.append((u, n))
        except Exception:
            continue
        if len(ok) >= 4:
            break
    return ok


if __name__ == "__main__":
    for p in sys.argv[1:]:
        r = descubrir(p)
        print("%s -> %s" % (p, ("; ".join("%s (%d ítems)" % x for x in r)) if r else "ningún canal que responda"))
