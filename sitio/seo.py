#!/usr/bin/env python3
"""Lo que necesitan los buscadores para encontrar Ysyry: robots.txt, mapa del sitio (sitemap.xml) y datos estructurados (JSON-LD:
organización, sitio web y conjunto de datos abiertos, que alimenta a Google Dataset Search).
Uso: seo.py CARPETA   (escribe CARPETA/robots.txt y CARPETA/sitemap.xml)"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import direccion

NOMBRE = "Ysyry"
DESCRIPCION = ("Plataforma pública y gratuita sobre el corredor de la Hidrovía Paraguay-Paraná: nivel del río, buques por AIS, avisos oficiales, "
               "indicios con su fuente y su nivel de evidencia, y preguntas con probabilidad que se resuelven solas. Dos fuentes independientes como mínimo.")


def jsonld():
    org = {"@type": "Organization", "@id": "https://fundacionkent.org/#fundacion", "name": "Fundación Sherman Kent", "url": "https://fundacionkent.org/"}
    return json.dumps({"@context": "https://schema.org", "@graph": [
        org,
        {"@type": "WebSite", "@id": direccion.APP + "#sitio", "name": NOMBRE, "url": direccion.APP, "description": DESCRIPCION, "inLanguage": "es",
         "isAccessibleForFree": True, "publisher": {"@id": org["@id"]}},
        {"@type": "Dataset", "@id": direccion.APP + "#datos", "name": "Ysyry: libro de indicios y hechos detectados del corredor Hidrovía Paraguay-Paraná",
         "description": "Indicios por zona del corredor (nivel del río, presencia del Estado por AIS, avisos oficiales, focos de calor, prensa), cada uno con sus fuentes, su fecha y su nivel de evidencia, más los hechos que detecta el escáner de prensa y organismos. Se actualiza cada hora.",
         "url": direccion.APP, "inLanguage": "es", "isAccessibleForFree": True, "license": "https://creativecommons.org/licenses/by/4.0/",
         "creator": {"@id": org["@id"]}, "publisher": {"@id": org["@id"]}, "temporalCoverage": "2026-10-01/..", "spatialCoverage": "Hidrovía Paraguay-Paraná (Argentina, Bolivia, Brasil, Paraguay y Uruguay)",
         "keywords": ["Hidrovía Paraguay-Paraná", "nivel del río", "navegación fluvial", "AIS", "alertas", "datos abiertos", "Paraná", "Paraguay"],
         "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": direccion.APP + "datos/indicios.json"},
                          {"@type": "DataDownload", "encodingFormat": "application/atom+xml", "contentUrl": direccion.APP + "feed.xml"}]}]},
        ensure_ascii=False, separators=(",", ":"))


def main(carpeta):
    c = Path(carpeta)
    c.mkdir(parents=True, exist_ok=True)
    (c / "robots.txt").write_text("User-agent: *\nAllow: /\n\nSitemap: %ssitemap.xml\n" % direccion.BASE, encoding="utf-8", newline="\n")
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    (c / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                   '  <url><loc>%s</loc><lastmod>%s</lastmod><changefreq>hourly</changefreq><priority>1.0</priority></url>\n</urlset>\n' % (direccion.APP, hoy),
                                   encoding="utf-8", newline="\n")
    print("robots.txt y sitemap.xml escritos en", c)


if __name__ == "__main__":
    main(sys.argv[1])
