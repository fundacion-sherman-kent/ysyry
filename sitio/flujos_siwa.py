"""Flujos ilícitos que usan el corredor, tomados de SIWA (Fundación Sherman Kent, CC BY 4.0: «SIWA, Fundación Sherman Kent»).

De SIWA se toman tres cosas, sin volver a medirlas:
  · las rutas registradas por tercero de cada familia de flujo (cocaína, marihuana, armas, contrabando, trata, minerales…), cada una con
    sus puntos de paso, su fuente, su confianza y el año desde el que está registrada;
  · el termómetro de frescura de los flujos (`frescura-flujos.json`) y la cola de refresco (`propuestas-flujos.json`), que dicen qué tan
    atrasada está cada familia;
  · el Vigía de fuentes (`vigia-fuentes.json`), que avisa cuando cambió la página de una fuente de edición anual.
De todo eso Ysyry se queda con las rutas que pasan cerca del corredor y las cruza con la frescura y con el Vigía.

Una ruta es un registro de terceros, no un flujo medido; el trazo une puntos de paso y no es el recorrido real. «Activa» sólo quiere
decir registrada en los últimos 24 meses (la misma regla de SIWA para «reciente»), no que hoy esté pasando algo."""
import html
import json
import re
import statistics
import urllib.request
from pathlib import Path

import indicios as _ind
import pulso as _pulso

SITIO = "https://siwa.fundacionkent.org/sitio/"
DATOS = "https://siwa.fundacionkent.org/datos/publico/"
FAMILIAS_ARCHIVO = ["cocaina", "marihuana", "sinteticos", "opioides", "precursores", "armas", "contrabando", "especies", "minerales", "migracion", "trata"]
FAMILIA_SIWA = {"cocaina": "narcotrafico", "marihuana": "narcotrafico", "sinteticos": "narcotrafico", "opioides": "narcotrafico", "precursores": "narcotrafico",
                "armas": "armas", "contrabando": "contrabando", "especies": "especies", "minerales": "minerales", "migracion": "migracion", "trata": "trata"}
ROTULO = {"narcotrafico": "Narcotráfico", "armas": "Armas", "contrabando": "Contrabando", "especies": "Especies", "minerales": "Oro y minerales",
          "migracion": "Migración", "trata": "Trata"}
# asociación inferida por Ysyry entre una familia de flujo y la fuente de edición anual que vigila el Vigía de SIWA
VIGIA_DE_FAMILIA = {"narcotrafico": ["unodc_portal"], "trata": ["unodc_portal"], "armas": ["sipri_milex"], "minerales": ["usgs_mcs"]}
CAJA = (-36.5, -71.5, -15.0, -51.8)
CERCA_KM = 40.0
KM_UNIDAD = 2.57
PALABRAS_RIO = re.compile(r"hidrov|r[ií]o paran[aá]|r[ií]o paraguay|lanchas|puerto de rosario|san lorenzo", re.I)
UA = {"User-Agent": "Ysyry-FUSK/1.0 (+https://github.com/fundacion-sherman-kent/ysyry)"}


def _bajar(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))


def cargar(copia):
    """Baja las rutas, la frescura, la cola y el Vigía de SIWA; si algo falla usa la copia fechada de sitio/datos/siwa/flujos_corredor.json."""
    p = Path(copia)
    try:
        rutas = {f: _bajar(SITIO + "flujos-rutas-%s.json" % f)["rutas"] for f in FAMILIAS_ARCHIVO}
        res = {"rutas": rutas, "frescura": _bajar(DATOS + "frescura-flujos.json"), "propuestas": _bajar(DATOS + "propuestas-flujos.json"),
               "vigia": _bajar(DATOS + "vigia-fuentes.json"), "en_vivo": True}
        return res
    except Exception as e:
        print("SIWA (flujos) no respondió (%s): se usa la copia fechada" % str(e)[:60])
        return json.load(open(p, encoding="utf-8")) | {"en_vivo": False} if p.exists() else None


def _km(x, y, segs):
    mejor = 1e9
    for (ax, ay), (bx, by) in segs:
        if x < min(ax, bx) - 18 or x > max(ax, bx) + 18 or y < min(ay, by) - 18 or y > max(ay, by) + 18:
            continue
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy
        t = 0 if L == 0 else max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / L))
        mejor = min(mejor, ((x - ax - t * dx) ** 2 + (y - ay - t * dy) ** 2) ** 0.5)
    return mejor * KM_UNIDAD


def seleccionar(datos, segs, anio):
    """Rutas con algún punto de paso a menos de CERCA_KM del río, o que nombran la hidrovía o el río; con su trazo recortado al corredor."""
    out = []
    for archivo, lista in datos["rutas"].items():
        for r in lista:
            wps = r.get("waypoints") or []
            pts = []
            cerca = False
            zonas = set()
            for lon, lat, nombre, rol in [(w[0], w[1], w[2], w[3] if len(w) > 3 else "") for w in wps]:
                if not (CAJA[0] <= lat <= CAJA[2] and CAJA[1] <= lon <= CAJA[3]):
                    continue
                x, y = _pulso.AX * lon + _pulso.BX, _pulso.AY * lat + _pulso.BY
                km = _km(x, y, segs)
                pts.append((x, y, nombre, rol, km))
                if km <= CERCA_KM:
                    cerca = True
                    zonas.add(_pulso.zona_de(x, y))
            nombra = bool(PALABRAS_RIO.search(r.get("nombre", "")))
            if not (cerca or nombra) or not pts:
                continue
            if nombra and not zonas:
                zonas = {_pulso.zona_de(x, y) for x, y, *_ in pts}
            desde = r.get("desde")
            out.append({"id": r["id"], "archivo": archivo, "familia": FAMILIA_SIWA[archivo], "nombre": r["nombre"], "subtipo": r.get("subtipo") or "",
                        "confianza": r.get("confianza", ""), "modo": r.get("modo", ""), "fuente": r.get("fuente", ""), "url": r.get("url", ""), "nota": r.get("nota", ""),
                        "desde": desde, "antiguedad": (anio - desde) if isinstance(desde, int) else None,
                        "activa": isinstance(desde, int) and anio - desde <= 2, "pts": pts, "zonas": sorted(zonas), "nombra_rio": nombra})
    return out


def trazo_svg(i, r):
    d = "M" + "L".join("%.1f,%.1f" % (x, y) for x, y, *_ in r["pts"]) if len(r["pts"]) > 1 else ""
    if not d:
        x, y = r["pts"][0][0], r["pts"][0][1]
        return ('<g class="flujo-g solo-fam clicable" data-i="fl%d" data-familia="flujos" transform="translate(%.1f,%.1f)">'
                '<circle class="hit" r="12"/><circle class="flujo-pt%s" r="3.4"/></g>' % (i, x, y, " flujo-act" if r["activa"] else ""))
    return ('<g class="flujo-g solo-fam clicable" data-i="fl%d" data-familia="flujos"><path class="flujo-hit" d="%s"/><path class="flujo%s" d="%s"/></g>'
            % (i, d, " flujo-act" if r["activa"] else "", d))


def info_ruta(i, r, hoy_txt):
    est = "es reciente: registrada en los últimos 24 meses (activa en el sentido de SIWA)" if r["activa"] else (
        "hace %d años, no es reciente" % r["antiguedad"] if r["antiguedad"] is not None else "sin dato de antigüedad")
    tipo = [r["subtipo"] or ROTULO.get(r["familia"], r["familia"]),
            "Confianza según SIWA: %s" % (r["confianza"] or "sin dato"),
            "Registrada desde %s (%s)" % (r["desde"] if r["desde"] else "año sin dato", est)]
    if r["modo"]:
        tipo.append("Modo: " + r["modo"])
    puntos = [("%s (%s)" % (n, rol) if rol else n) for _, _, n, rol, _ in r["pts"]][:8]
    ctx = ["Puntos de paso dentro del corredor: " + "; ".join(puntos),
           "Fuentes que cita SIWA: " + (r["fuente"] or "sin dato"),
           ("Nota de SIWA: " + r["nota"][:420]) if r["nota"] else "",
           "Lo que no dice: es una ruta registrada por terceros, no un flujo medido; el trazo une puntos de paso y no es el recorrido real; no dice que hoy esté pasando algo ni involucra a quienes viven o trabajan en esos lugares."]
    ctx = [c for c in ctx if c]
    if r["url"].startswith(("http://", "https://")):
        ctx.append("Fuente principal: " + r["url"])
    return {"id": "fl%d" % i, "categoria": "Flujo ilícito registrado por SIWA · " + ROTULO.get(r["familia"], r["familia"]), "titulo": r["id"] + " · " + r["nombre"][:110],
            "tipo": " · ".join(t.replace(" · ", ", ") for t in tipo), "fuente": "SIWA, Fundación Sherman Kent (CC BY 4.0), con los datos de base de las fuentes citadas · consultado el " + hoy_txt,
            "clase": "flujo", "coord": None, "foto": None, "ctx": ctx, "ctx_t": "Qué dice SIWA de esta ruta",
            "ctx_f": "Rutas registradas por agencias e investigaciones de terceros; cada una lleva su fuente y su confianza. Ysyry no las volvió a medir."}


def indicios_por_zona(rutas):
    por = {}
    for r in rutas:
        for z in r["zonas"]:
            por.setdefault(z, []).append(r)
    out = {}
    fuente = {"nombre": "SIWA, rutas registradas por tercero", "familia": "base secundaria", "calificacion": "B2"}
    for z, lst in por.items():
        fams = {}
        for r in lst:
            fams[ROTULO.get(r["familia"], r["familia"])] = fams.get(ROTULO.get(r["familia"], r["familia"]), 0) + 1
        act = [r for r in lst if r["activa"]]
        conf = {k: len([r for r in lst if r["confianza"] == k]) for k in ("alta", "media", "baja")}
        out[z] = {"id": "FLU", "tipo": "Flujos ilícitos", "titulo": "Rutas de flujos ilícitos registradas por SIWA que pasan por este tramo",
                  "texto": "%d %s (%d %s en los últimos 24 meses): %s. Confianza según SIWA: %d alta, %d media, %d baja." % (
                      len(lst), "ruta" if len(lst) == 1 else "rutas", len(act), "registrada" if len(act) == 1 else "registradas", ", ".join("%s %d" % (k, v) for k, v in sorted(fams.items(), key=lambda kv: -kv[1])), conf["alta"], conf["media"], conf["baja"]),
                  "fuentes": [fuente], "nivel": "Calificado por SIWA",
                  "no_dice": "Son rutas registradas por terceros, no flujos medidos; que una ruta toque un tramo no dice que hoy pase algo allí. «Activa» sólo significa registrada en los últimos 24 meses.",
                  "dato": {"n": len(lst), "activas": len(act)}}
    return out


def tabla_html(rutas, datos, fecha):
    e = html.escape
    fr = {f["familia"]: f for f in (datos.get("frescura") or {}).get("por_familia", [])}
    cola = {p["familia"]: p for p in (datos.get("propuestas") or {}).get("propuestas", [])}
    vig = {f["clave"]: f for f in (datos.get("vigia") or {}).get("fuentes", [])}
    filas = []
    for fam in ["narcotrafico", "contrabando", "armas", "trata", "minerales", "especies", "migracion"]:
        lst = [r for r in rutas if r["familia"] == fam]
        if not lst:
            continue
        act = [r for r in lst if r["activa"]]
        f = fr.get(fam, {})
        c = cola.get(fam, {})
        marcadas = [vig[k] for k in VIGIA_DE_FAMILIA.get(fam, []) if k in vig]
        cambiaron = [v["que_es"].split(" — ")[0] for v in marcadas if v.get("cambio_desde_la_ultima")]
        if not marcadas:
            vtxt = "Sin fuente de edición anual vigilada asociada"
        elif cambiaron:
            vtxt = "Cambió esta vuelta: %s. Puede haber una edición nueva por incorporar." % ", ".join(cambiaron)
        else:
            vtxt = "Vigiladas sin cambios: " + ", ".join(v["que_es"].split(" — ")[0] for v in marcadas)
        filas.append("<tr><th scope=\"row\">%s</th><td>%d en el corredor · %d activas</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            e(ROTULO.get(fam, fam)), len(lst), len(act),
            e(("Antigüedad mediana %s años; %s %% de sus rutas son recientes" % (f.get("antiguedad_mediana_anios"), f.get("pct_recientes"))) if f else "Sin dato de frescura"),
            e(("Prioridad de refresco: %s (%d rutas en cola)" % (c.get("prioridad"), len(c.get("corredores_a_refrescar", [])))) if c else "Sin cola"), e(vtxt)))
    if not filas:
        return ""
    return ('<div class="pulso" id="flujos-siwa"><h2>Flujos ilícitos que usan el corredor, y qué tan frescos están</h2>'
            '<p class="sub">Rutas registradas por terceros que SIWA publica y que pasan a menos de %d km del río. Se ven en el mapa con la pestaña «Flujos ilícitos (SIWA)»: en naranja las registradas en los últimos 24 meses, en claro las más antiguas. '
            '<b>Son registros, no flujos medidos</b>, y el trazo une puntos de paso: no es el recorrido real. La frescura y la cola de refresco son las que calcula SIWA para cada familia; la columna del Vigía cruza esas familias con las fuentes de edición anual que SIWA vigila (la asociación entre familia y fuente la infiere Ysyry).</p>'
            '<div class="tabla-pulso"><table><thead><tr><th>Familia</th><th>Rutas</th><th>Frescura (SIWA)</th><th>Cola de refresco (SIWA)</th><th>Vigía de fuentes (SIWA)</th></tr></thead><tbody>%s</tbody></table></div>'
            '<p class="sub">%s Fuente: SIWA, Fundación Sherman Kent (CC BY 4.0). Consultado el %s (UTC)%s.</p></div>'
            % (int(CERCA_KM), "".join(filas), "%d rutas de %d archivos de SIWA tocan el corredor." % (len(rutas), len(FAMILIAS_ARCHIVO)), e(fecha),
               "" if datos.get("en_vivo") else "; copia fechada porque SIWA no respondió"))


def instantanea(datos, rutas):
    """Copia mínima para trabajar sin red: sólo lo que Ysyry usa."""
    ids = {r["id"] for r in rutas}
    return {"rutas": {a: [r for r in l if r["id"] in ids] for a, l in datos["rutas"].items()}, "frescura": {"por_familia": datos["frescura"]["por_familia"], "corrida": datos["frescura"].get("corrida")},
            "propuestas": {"propuestas": [{"familia": p["familia"], "prioridad": p["prioridad"], "corredores_a_refrescar": p["corredores_a_refrescar"][:8]} for p in datos["propuestas"]["propuestas"]]},
            "vigia": {"fuentes": [{k: f.get(k) for k in ("clave", "que_es", "cambio_desde_la_ultima")} for f in datos["vigia"]["fuentes"]], "corrida": datos["vigia"].get("corrida")}}
