"""Libro de indicios: cada observación del corredor con sus fuentes, su familia de fuente, su nivel de evidencia y
lo que NO dice. Es la capa entre las huellas (AIS, nivel del río, ACLED, focos, hechos citados) y las alertas.

Nivel de evidencia (regla de la casa: dos fuentes independientes o se rotula fuente única):
  «Fuente única»  una sola fuente.
  «Corroborado»   dos o más fuentes independientes de la misma familia (p. ej. varios medios).
  «Fuerte»        dos o más fuentes independientes de al menos dos familias (p. ej. prensa y una fuente oficial).
Las familias son: oficial, sensor, prensa, base secundaria y propia. Varias estaciones de un mismo organismo, o las dos
redes de AIS, cuentan como UNA fuente: miden con el mismo método y se equivocan juntas.

Nada de esto es una alerta ni una predicción. Una alerta es un juicio con probabilidad y plazo que escribe una persona,
lo impugna el décimo hombre y publica la dirección; acá sólo se acumulan los indicios que podrían sostener una."""
import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pulso as _pulso

NIVELES = ("Fuente única", "Corroborado", "Fuerte")
_PARAMS = json.load(open(Path(__file__).resolve().parent / "datos" / "parametros_reglas.json", encoding="utf-8"))


def _par(nombre):
    return _PARAMS[nombre]["valor"]


# parámetros iniciales: se cambian en sitio/datos/parametros_reglas.json, sin tocar código (ver ese archivo)
PCT_BAJO = float(_par("pct_bajo"))
VAR_BAJA_CM = _par("var_baja_cm")
DIAS_VENCIDA = _par("dias_vencida")
MIN_BUQUES_BRECHA = _par("min_buques_brecha")
CAPS_BRECHA = _par("caps_brecha")
AJUSTE_MAX_UNIDADES = float(_par("ajuste_max_unidades"))
INTERRUPCION_CAPS = _par("interrupcion_caps")
COBERTURA_CONTINUA = float(_par("cobertura_continua"))
MIN_MEDIOS = _par("min_medios_prensa")
MARGEN_CERCA_CM = _par("margen_cerca_cm")
REGULADAS_AR = {14, 15, 79}      # escalas dentro de embalses (Yacyretá, Salto Grande): su nivel lo fija la operación de la represa

FUENTE_NIVEL_AR = {"nombre": "Prefectura Naval Argentina (escalas), vía INA", "familia": "oficial", "calificacion": "A2",
                  "url": "https://alerta.ina.gob.ar/"}
FUENTE_NIVEL_CARU = {"nombre": "CARU (Comisión Administradora del Río Uruguay), escala de Nueva Palmira, vía INA", "familia": "oficial", "calificacion": "A2",
                    "url": "https://alerta.ina.gob.ar/"}
FUENTE_NIVEL_SHN = {"nombre": "Servicio de Hidrografía Naval (Argentina), mareógrafos", "familia": "oficial", "calificacion": "A2", "url": "https://www.hidro.gob.ar/oceanografia/alturashorarias.asp"}
FUENTE_NIVEL_BR = {"nombre": "ANA (Brasil), telemetría de escalas del SGB-CPRM", "familia": "oficial", "calificacion": "A2", "url": "https://telemetriaws1.ana.gov.br/"}
FUENTE_NIVEL = {"nombre": "Dirección de Meteorología e Hidrología, Paraguay", "familia": "oficial", "calificacion": "A2",
                "url": "https://www.meteorologia.gov.py/nivel-rio/indexconvencional.php"}
FUENTE_AIS = {"nombre": "AIS vía Open Waters (AISHub y aisstream.io)", "familia": "sensor", "calificacion": "B3"}
FUENTE_ACLED = {"nombre": "ACLED vía SIWA", "familia": "base secundaria", "calificacion": "B2"}
FUENTE_FIRMS = {"nombre": "NASA FIRMS (VIIRS Suomi NPP y NOAA-20)", "familia": "sensor", "calificacion": "A2"}


def nivel_evidencia(fuentes):
    """fuentes: lista de {'nombre','familia'} que sostienen la MISMA afirmación; se cuentan por nombre distinto."""
    distintas = {f["nombre"] for f in fuentes}
    familias = {f["familia"] for f in fuentes}
    if len(distintas) >= 2 and len(familias) >= 2:
        return "Fuerte"
    if len(distintas) >= 2:
        return "Corroborado"
    return "Fuente única"


# ---------------------------------------------------------------- estaciones de nivel de río
def _num(s):
    m = re.match(r"\s*(-?\d+(?:[.,]\d+)?)", s or "")
    return float(m.group(1).replace(",", ".")) if m else None


def _min_max(s):
    """'-0.68m --> 16-10-2024' -> (-0.68, '16-10-2024')"""
    v = _num(s)
    f = re.search(r"(\d{2}-\d{2}-\d{4})", s or "")
    return v, (f.group(1) if f else "")


def _fecha(s):
    try:
        return datetime.strptime(s, "%d-%m-%Y").date()
    except Exception:
        return None


def _segmentos(path_d):
    out, cur, buf = [], [], []
    for c, n in re.findall(r"([MLZ])|(-?\d+\.?\d*)", path_d):
        if c:
            if c == "M" and cur:
                out.append(cur)
                cur = []
            buf = []
        else:
            buf.append(float(n))
            if len(buf) == 2:
                cur.append(tuple(buf))
                buf = []
    if cur:
        out.append(cur)
    return [(a, b) for l in out for a, b in zip(l, l[1:])]


def _al_rio(x, y, segs):
    """Punto del cauce dibujado más cercano; si está a menos de AJUSTE_MAX_UNIDADES se usa, si no se deja donde está."""
    mejor, punto = 1e9, (x, y)
    for (ax, ay), (bx, by) in segs:
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy
        t = 0 if L == 0 else max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / L))
        px, py = ax + t * dx, ay + t * dy
        d = math.hypot(x - px, y - py)
        if d < mejor:
            mejor, punto = d, (px, py)
    return (punto if mejor <= AJUSTE_MAX_UNIDADES else (x, y)), mejor


def estaciones(ruta_nivel, geo, segs_rio, hoy):
    """Lista de estaciones con su posición en el mapa, su posición en el rango histórico y su estado."""
    d = json.load(open(ruta_nivel, encoding="utf-8"))
    out = []
    for e in d["estaciones"]:
        nivel = _num(e["nivel"])
        mn, f_mn = _min_max(e["minimo_historico"])
        mx, f_mx = _min_max(e["maximo_historico"])
        var = _num(e["variacion_24h"])
        lect = _fecha(e["fecha_lectura"])
        if nivel is None or mn is None or mx is None or mx <= mn:
            continue
        pct = max(0.0, min(100.0, 100.0 * (nivel - mn) / (mx - mn)))
        edad = (hoy - lect).days if lect else 999
        if edad > DIAS_VENCIDA:
            estado = "vencida"
        elif pct <= PCT_BAJO:
            estado = "bajo"
        elif pct >= 100 - PCT_BAJO:
            estado = "alto"
        else:
            estado = "medio"
        g = (geo or {}).get(e["estacion"])
        pos = None
        regulada = False
        if g:
            x, y = _pulso.AX * g["lon"] + _pulso.BX, _pulso.AY * g["lat"] + _pulso.BY
            (x2, y2), dist = _al_rio(x, y, segs_rio)
            pos = {"x": x2, "y": y2, "zona": _pulso.zona_de(x2, y2), "ajustada": dist <= AJUSTE_MAX_UNIDADES and dist > 0.05}
            regulada = pos["zona"] == "z4"          # tramo del Paraná entre las represas de Itaipú y Yacyretá
            if regulada and estado != "vencida":
                estado = "regulada"
        out.append({"nombre": e["estacion"], "nivel": nivel, "var_cm": var, "min": mn, "f_min": f_mn, "max": mx, "f_max": f_mx,
                    "pct": pct, "lectura": e["fecha_lectura"], "edad": edad, "estado": estado,
                    "sobre_min_cm": round((nivel - mn) * 100), "pos": pos, "regulada": regulada})
    return out, d.get("obtenido", "")


def estaciones_ar(ruta, segs_rio, hoy):
    """Escalas de la Prefectura Naval Argentina publicadas por el INA, con los umbrales oficiales de cada escala."""
    if not ruta or not Path(ruta).exists():
        return [], ""
    d = json.load(open(ruta, encoding="utf-8"))
    out = []
    for e in d["estaciones"]:
        lect = _fecha_iso(e["fecha"])
        edad = (hoy - lect).days if lect else 999
        umbral, alerta = e.get("nivel_aguas_bajas"), e.get("nivel_alerta")
        margen = round((e["nivel_m"] - umbral) * 100) if umbral is not None else None
        x, y = _pulso.AX * e["lon"] + _pulso.BX, _pulso.AY * e["lat"] + _pulso.BY
        (x2, y2), dist = _al_rio(x, y, segs_rio)
        regulada = e["id"] in REGULADAS_AR
        if edad > DIAS_VENCIDA:
            estado = "vencida"
        elif regulada:
            estado = "regulada"
        elif margen is not None and margen <= 0:
            estado = "bajo"
        elif margen is not None and margen <= MARGEN_CERCA_CM:
            estado = "cerca"
        elif alerta is not None and e["nivel_m"] >= alerta:
            estado = "alto"
        else:
            estado = "medio"
        out.append({"red": "ar", "org": "caru" if (e.get("propietario") or "").upper() == "CARU" else "pna", "id_ina": e["id"], "nombre": e["nombre"], "rio": e["rio"], "nivel": e["nivel_m"], "var_cm": e.get("var_cm"), "umbral": umbral, "alerta": alerta,
                    "evacuacion": e.get("nivel_evacuacion"), "margen_cm": margen, "lectura": e["fecha"], "edad": edad, "estado": estado, "regulada": regulada,
                    "pct": None, "min": None, "max": None, "pos": {"x": x2, "y": y2, "zona": _pulso.zona_de(x2, y2), "ajustada": 0.05 < dist <= AJUSTE_MAX_UNIDADES}})
    return out, d.get("obtenido", "")


def estaciones_br(ruta, segs_rio, hoy):
    """Escalas de la ANA de Brasil (telemetría cada 15 minutos). Son la fuente primaria de las mismas escalas que Paraguay republica."""
    if not ruta or not Path(ruta).exists():
        return [], ""
    d = json.load(open(ruta, encoding="utf-8"))
    out = []
    for e in d["estaciones"]:
        lect = _fecha_iso(e["hora_local"][:10])
        edad = (hoy - lect).days if lect else 999
        x, y = _pulso.AX * e["lon"] + _pulso.BX, _pulso.AY * e["lat"] + _pulso.BY
        (x2, y2), dist = _al_rio(x, y, segs_rio)
        out.append({"red": "br", "nombre": e["nombre"], "nivel": e["nivel_m"], "caudal": e.get("caudal_m3s"), "var_cm": e.get("var_cm"), "lectura": e["hora_local"],
                    "edad": edad, "estado": "vencida" if edad > DIAS_VENCIDA else "medio", "regulada": False, "pct": None, "min": None, "max": None,
                    "pos": {"x": x2, "y": y2, "zona": _pulso.zona_de(x2, y2), "ajustada": 0.05 < dist <= AJUSTE_MAX_UNIDADES}})
    return out, d.get("obtenido", "")


def estaciones_shn(ruta, segs_rio, hoy):
    """Mareógrafos del Servicio de Hidrografía Naval: alturas horarias; la variación es entre medias de días completos."""
    if not ruta or not Path(ruta).exists():
        return [], ""
    d = json.load(open(ruta, encoding="utf-8"))
    out = []
    for e in d["estaciones"]:
        lect = _fecha_iso(e["hora_local"][:10])
        edad = (hoy - lect).days if lect else 999
        x, y = _pulso.AX * e["lon"] + _pulso.BX, _pulso.AY * e["lat"] + _pulso.BY
        (x2, y2), dist = _al_rio(x, y, segs_rio)
        out.append({"red": "shn", "nombre": e["nombre"], "nivel": e["nivel_m"], "media_dia": e.get("media_dia_m"), "var_cm": e.get("var_cm"), "lectura": e["hora_local"], "edad": edad,
                    "estado": "vencida" if edad > DIAS_VENCIDA else "medio", "regulada": False, "pct": None, "min": None, "max": None,
                    "pos": {"x": x2, "y": y2, "zona": _pulso.zona_de(x2, y2), "ajustada": 0.05 < dist <= AJUSTE_MAX_UNIDADES}})
    return out, d.get("obtenido", "")


def info_estacion_shn(i, est):
    tipo = [("Altura %.2f m sobre el Plano de Reducción de Sondajes (lectura del %s, hora de Argentina)" % (est["nivel"], est["lectura"])).replace(".", ",")]
    if est.get("media_dia") is not None:
        tipo.append(("Media del último día completo %.2f m, %s respecto del día anterior" % (est["media_dia"], ("%+d cm" % est["var_cm"]) if est["var_cm"] is not None else "variación sin dato")).replace(".", ","))
    tipo.append("Sin umbrales oficiales: no se puede decir si el nivel es bajo ni alto")
    ctx = ["Evidencia: Fuente única (Servicio de Hidrografía Naval, Armada Argentina; dato abierto «Datos Horarios de Marea»). Es un organismo distinto de la Prefectura y de la CARU: sí cuenta como otra fuente de la tendencia del nivel en el Río de la Plata y el Delta.",
           "Lo que no dice: es un mareógrafo, la altura sube y baja con la marea y se mueve con el viento (una sudestada la sube aunque el río venga bajando); por eso se compara entre medias de días completos. No es el calado ni el límite de navegación. La ubicación del mareógrafo es aproximada."]
    return {"id": "es%d" % i, "categoria": "Nivel del río · mareógrafo del Servicio de Hidrografía Naval", "titulo": est["nombre"], "tipo": " · ".join(tipo),
            "fuente": "Servicio de Hidrografía Naval (Argentina), Datos Horarios de Marea · ubicación aproximada", "clase": "estacion", "coord": None, "foto": None,
            "ctx": ctx, "ctx_t": "Indicio y su evidencia", "ctx_f": "Se publican las lecturas tal como las informa el organismo."}


def info_estacion_br(i, est):
    tipo = [("Nivel %.2f m (lectura del %s hora de Brasil), %s en 24 h" % (est["nivel"], est["lectura"], ("%+d cm" % est["var_cm"]) if est["var_cm"] is not None else "variación sin dato")).replace(".", ",")]
    if est.get("caudal"):
        tipo.append(("Caudal %.0f m³/s" % est["caudal"]).replace(".", ","))
    tipo.append("Sin umbrales oficiales en esta interfaz: no se puede decir si el nivel es bajo ni alto")
    ctx = ["Evidencia: Fuente única (ANA, Brasil: telemetría de escalas del Serviço Geológico do Brasil). Es la fuente primaria de la misma escala que Meteorología de Paraguay republica: NO son dos fuentes distintas para esta escala.",
           "Lo que no dice: es la altura de la escala, no el calado ni el límite de navegación; sin historial propio todavía no hay comparación con su rango."]
    return {"id": "es%d" % i, "categoria": "Nivel del río · telemetría de la ANA (Brasil)", "titulo": est["nombre"], "tipo": " · ".join(tipo),
            "fuente": "ANA (Brasil), telemetría cada 15 minutos; escalas del SGB-CPRM · ubicación según la ANA", "clase": "estacion", "coord": None, "foto": None,
            "ctx": ctx, "ctx_t": "Indicio y su evidencia", "ctx_f": "Se publican las lecturas tal como las informa el organismo."}


def _fecha_iso(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def gauge_ar(est, ancho=260, alto=50):
    """De 0 a la cota de alerta: el umbral de aguas bajas, la alerta y el nivel de la última lectura."""
    tope = max(est["alerta"] or 0, est["nivel"], est["umbral"] or 0) * 1.05 or 1
    px = lambda v: 8 + (ancho - 16) * max(0.0, v) / tope
    partes = ['<line x1="8" y1="24" x2="%d" y2="24" stroke="var(--gris-acero)" stroke-width="3" stroke-linecap="round"/>' % (ancho - 8)]
    if est["umbral"] is not None:
        partes.append('<line x1="%.1f" y1="16" x2="%.1f" y2="32" stroke="#FB6500" stroke-width="2"/><text x="%.1f" y="46" font-size="9" fill="var(--gris-acero)" text-anchor="middle">aguas bajas %.2f</text>' % (px(est["umbral"]), px(est["umbral"]), px(est["umbral"]), est["umbral"]))
    if est["alerta"] is not None:
        partes.append('<line x1="%.1f" y1="16" x2="%.1f" y2="32" stroke="#667B89" stroke-width="2"/><text x="%.1f" y="46" font-size="9" fill="var(--gris-acero)" text-anchor="end">alerta %.2f</text>' % (px(est["alerta"]), px(est["alerta"]), px(est["alerta"]), est["alerta"]))
    partes.append('<circle cx="%.1f" cy="24" r="6" fill="%s" stroke="#00121E" stroke-width="1.2"/>' % (px(est["nivel"]), "#FB6500" if est["estado"] in ("bajo", "cerca") else "#8fd9c4"))
    return ('<svg class="gauge" viewBox="0 0 %d %d" role="img" aria-label="Nivel actual frente a los umbrales oficiales de la escala">%s</svg>' % (ancho, alto, "".join(partes))).replace(".", ",")


def info_estacion_ar(i, est):
    f = est["lectura"]
    tipo = [("Nivel %.2f m (lectura del %s), %s en 24 h" % (est["nivel"], f, ("%+d cm" % est["var_cm"]) if est["var_cm"] is not None else "variación sin dato")).replace(".", ",")]
    if est["umbral"] is not None:
        tipo.append(("Umbral oficial de aguas bajas %.2f m: está %d cm %s" % (est["umbral"], abs(est["margen_cm"]), "por encima" if est["margen_cm"] > 0 else "por debajo")).replace(".", ","))
    if est["alerta"] is not None:
        tipo.append(("Cota de alerta %.2f m%s" % (est["alerta"], (", de evacuación %.2f m" % est["evacuacion"]) if est["evacuacion"] else "")).replace(".", ","))
    if est["estado"] == "regulada":
        tipo.append("Escala dentro de un embalse: su nivel lo fija la operación de la represa, no mide sequía")
    if est["estado"] == "vencida":
        tipo.append("Lectura vencida: tiene %d días y no describe el río de hoy" % est["edad"])
    if est.get("org") == "caru":
        ctx = ["Evidencia: Fuente única (CARU, organismo binacional Argentina-Uruguay; publicada por el INA). Es un organismo distinto de la Prefectura: sí cuenta como segunda fuente de la tendencia del nivel en el Río de la Plata y el Delta.",
               "Lo que no dice: no publica umbrales, así que no puede decir si el nivel es bajo; la escala está sobre el río Uruguay, cerca de su boca, las mareas y el viento del Plata la mueven. Se compara la media diaria."]
        return {"id": "es%d" % i, "categoria": "Nivel del río · escala de la CARU (vía INA)", "titulo": est["nombre"] + " · " + est["rio"].title(), "tipo": " · ".join(tipo),
                "fuente": "Comisión Administradora del Río Uruguay (CARU), publicada por el INA · ubicación según el INA%s" % (", ajustada al cauce dibujado" if est["pos"]["ajustada"] else ""),
                "clase": "estacion", "coord": None, "foto": None, "ctx": ctx, "ctx_t": "Indicio y su evidencia",
                "ctx_f": "Se publican las lecturas tal como las informa el organismo."}
    ctx = ["Evidencia: Fuente única (Prefectura Naval Argentina, escalas oficiales, publicadas por el INA). Otras escalas del mismo organismo cuentan como la misma fuente; sí corrobora una estación de otro organismo sobre el mismo tramo.",
           "Lo que no dice: es la altura de la escala, no el calado ni el límite de navegación de la vía; los umbrales son los de esa escala. La lectura es diaria."]
    return {"id": "es%d" % i, "categoria": "Nivel del río · escala de la Prefectura (vía INA)", "titulo": est["nombre"] + " · " + est["rio"].title(), "tipo": " · ".join(tipo),
            "fuente": "Prefectura Naval Argentina (escalas), publicadas por el INA (Sistema de Alerta Hidrológico) · ubicación según el INA%s" % (", ajustada al cauce dibujado" if est["pos"]["ajustada"] else ""),
            "clase": "estacion", "coord": None, "foto": None, "ctx": ctx, "ctx_t": "Indicio y su evidencia",
            "ctx_f": "Se publican las lecturas tal como las informa el organismo. Estar cerca del umbral de aguas bajas es un indicio, no una alerta.",
            "spark_svg": gauge_ar(est), "spark_pie": "Posición del nivel entre los umbrales oficiales de la escala (el naranja marca las aguas bajas)."}


def gauge_svg(est, ancho=260, alto=46):
    """Rango histórico de la estación con el nivel de hoy marcado."""
    x = 8 + (ancho - 16) * est["pct"] / 100.0
    return ('<svg class="gauge" viewBox="0 0 %d %d" role="img" aria-label="Nivel actual dentro de su rango histórico">'
            '<line x1="8" y1="22" x2="%d" y2="22" stroke="var(--gris-acero)" stroke-width="3" stroke-linecap="round"/>'
            '<rect x="8" y="19" width="%.1f" height="6" rx="3" fill="#8fd9c4" opacity=".55"/>'
            '<circle cx="%.1f" cy="22" r="6" fill="%s" stroke="#00121E" stroke-width="1.2"/>'
            '<text x="8" y="40" font-size="9" fill="var(--gris-acero)">mín %.2f m</text>'
            '<text x="%d" y="40" font-size="9" fill="var(--gris-acero)" text-anchor="end">máx %.2f m</text></svg>'
            % (ancho, alto, ancho - 8, x - 8, x, "#FB6500" if est["estado"] == "bajo" else "#8fd9c4", est["min"], ancho - 8, est["max"])).replace("mín -", "mín −").replace(".", ",")


def info_estacion(i, est, fecha_obtenido):
    if est.get("red") == "br":
        return info_estacion_br(i, est)
    if est.get("red") == "shn":
        return info_estacion_shn(i, est)
    if est.get("red") == "ar":
        return info_estacion_ar(i, est)
    pos = est["pos"]
    tipo = [("Nivel %.2f m, %s en 24 h" % (est["nivel"], ("%+d cm" % est["var_cm"]) if est["var_cm"] is not None else "variación sin dato")).replace(".", ","),
            ("%d cm sobre su mínimo histórico (%.2f m, %s)" % (est["sobre_min_cm"], est["min"], est["f_min"])).replace(".", ","),
            ("Posición en su rango histórico: %d %% (mínimo %.2f m, máximo %.2f m)" % (round(est["pct"]), est["min"], est["max"])).replace(".", ","),
            "Lectura del %s" % est["lectura"]]
    if est["estado"] == "regulada":
        tipo.append("Tramo regulado por represas (Itaipú y Yacyretá): su nivel responde a la operación de las represas, así que su posición en el rango no mide sequía")
    if est["estado"] == "vencida":
        tipo.append("Lectura vencida: tiene %d días y no describe el río de hoy" % est["edad"])
    ctx = ["Evidencia: Fuente única (Dirección de Meteorología e Hidrología de Paraguay, oficial). Otras estaciones del mismo organismo cuentan como la misma fuente.",
           "Lo que no dice: no es el calado ni el límite de navegación de la vía; los máximos y mínimos son de cada estación y de su propia historia, y el organismo actualiza a diario, no en vivo."]
    return {"id": "es%d" % i, "categoria": "Nivel del río · estación hidrométrica", "titulo": est["nombre"], "tipo": " · ".join(tipo),
            "fuente": "Dirección de Meteorología e Hidrología, Paraguay (oficial) · ubicación geocodificada con OpenStreetMap, aproximada%s"
                      % (" y ajustada al cauce dibujado" if pos and pos["ajustada"] else ""),
            "clase": "estacion", "coord": None, "foto": None, "ctx": ctx, "ctx_t": "Indicio y su evidencia",
            "ctx_f": "Se publican las lecturas tal como las informa el organismo. Una estación en el cuarto inferior de su rango es un indicio, no una alerta.",
            "spark_svg": gauge_svg(est), "spark_pie": "Rango histórico de la estación: la marca es el nivel de la última lectura."}


def marca_estacion(i, est):
    p = est["pos"]
    return ('<g class="est-g clicable est-%s" data-i="es%d" data-familia="indicios navegacion" transform="translate(%.1f,%.1f)">'
            '<circle class="hit" r="12"/><path class="gota" d="M0,-5.5C3,-1.3 4.6,1 4.6,2.9A4.6,4.6 0 1 1 -4.6,2.9C-4.6,1 -3,-1.3 0,-5.5Z"/></g>'
            % (est["estado"], i, p["x"], p["y"]))


# ---------------------------------------------------------------- indicios por zona
def _nivel_por_zona(ests):
    por = {}
    for e in ests:
        if e["pos"]:
            por.setdefault(e["pos"]["zona"], []).append(e)
    return por


def indicios(calc, marcos_ventana, es_estado, ests, fuentes_siwa, unidades_por_zona, hechos_fuentes, siwa_mod, prensa=None, focos_z=None, extra=None):
    """{zona: [indicio]}; cada indicio: id, titulo, texto, fuentes, nivel, no_dice, tipo."""
    por_nivel = _nivel_por_zona(ests)
    res = {z[0]: [] for z in _pulso.ZONAS}
    res["gen"] = []
    for z, lista in por_nivel.items():
        vivas = [e for e in lista if e["estado"] not in ("vencida", "regulada")]
        if not vivas:
            continue
        bajas = [e for e in vivas if e["estado"] == "bajo"]
        cerca = [e for e in vivas if e["estado"] == "cerca"]
        bajando = [e for e in vivas if e["var_cm"] is not None and e["var_cm"] <= VAR_BAJA_CM]
        en_obs = bajas + cerca
        ambas = [e for e in en_obs if e in bajando]
        py = [e for e in vivas if e.get("red") not in ("ar", "br", "shn")]
        ar = [e for e in vivas if e.get("red") == "ar" and e.get("org") != "caru"]
        caru = [e for e in vivas if e.get("org") == "caru"]
        br = [e for e in vivas if e.get("red") == "br"]
        shn = [e for e in vivas if e.get("red") == "shn"]
        orgs = {"py": FUENTE_NIVEL, "ar": FUENTE_NIVEL_AR, "br": FUENTE_NIVEL_BR, "caru": FUENTE_NIVEL_CARU, "shn": FUENTE_NIVEL_SHN}
        grupos = (("py", py), ("ar", ar), ("br", br), ("caru", caru), ("shn", shn))
        con_lectura = [orgs[k] for k, g in grupos if g]
        con_aviso = [orgs[k] for k, g in grupos if k not in ("caru", "shn") and any(e in en_obs for e in g)]
        # La CARU y la SHN no publican umbrales: no pueden decir «aguas bajas». Sólo corroboran la tendencia (baja de nivel) cuando otro organismo ya marca el aviso.
        if con_aviso:
            con_aviso = con_aviso + [orgs[k] for k, g in (("caru", caru), ("shn", shn)) if any(e in bajando for e in g)]
        fuentes = con_aviso or con_lectura
        partes = []
        if py:
            partes.append("%d de Meteorología de Paraguay" % len(py))
        if ar:
            partes.append("%d de la Prefectura Naval Argentina, vía INA" % len(ar))
        if br:
            partes.append("%d de la ANA de Brasil" % len(br))
        if caru:
            partes.append("%d de la CARU (sin umbrales: sólo confirma la tendencia)" % len(caru))
        if shn:
            partes.append("%d mareógrafos del Servicio de Hidrografía Naval (sin umbrales: sólo confirman la tendencia)" % len(shn))
        txt = "%d estaciones con lectura al día (%s): %d en el cuarto inferior de su rango histórico o por debajo del umbral oficial de aguas bajas; %d a menos de %d cm de ese umbral; %d bajan %d cm o más en 24 h." % (
            len(vivas), "; ".join(partes), len(bajas), len(cerca), MARGEN_CERCA_CM, len(bajando), abs(VAR_BAJA_CM))
        res[z].append({"id": "NAV", "tipo": "Navegabilidad", "titulo": "Nivel del río frente a su historia y a sus umbrales", "texto": txt, "fuentes": fuentes,
                       "nivel": nivel_evidencia(fuentes),
                       "no_dice": "No es el calado ni una restricción de navegación; mide el nivel de cada escala contra su propia historia (Paraguay) o contra sus umbrales oficiales (Argentina). La CARU y los mareógrafos de la SHN sólo corroboran la baja de nivel, no el umbral (no publican umbrales); la marea y el viento mueven el nivel del Plata, y la escala de la CARU está sobre el río Uruguay, cerca de su boca en el Río de la Plata. Varias estaciones de un mismo organismo son una sola fuente: sólo corrobora un organismo distinto sobre el mismo tramo.",
                       "dato": {"vivas": len(vivas), "bajas": len(bajas), "cerca": len(cerca), "bajando": len(bajando), "ambas": len(ambas)}})
    # presencia del Estado en el AIS
    for z, *_ in _pulso.ZONAS:
        m = calc.get(z)
        if not m or not m["distintos"]:
            continue
        seguidas = 0
        for v in reversed(m["estado_serie"]):
            if v:
                break
            seguidas += 1
        txt = ("%d %s del Estado visibles por AIS en %d de %d capturas; %s buques por captura (mediana)."
               % (m["estado_distintos"], "unidad" if m["estado_distintos"] == 1 else "unidades", m["estado_capturas"], m["capturas"], ("%g" % m["mediana"]).replace(".", ",")))
        if m["mediana"] >= MIN_BUQUES_BRECHA and seguidas >= CAPS_BRECHA:
            txt = "Sin ninguna unidad del Estado visible por AIS en las últimas %d capturas, con %s buques por captura." % (seguidas, ("%g" % m["mediana"]).replace(".", ","))
        res[z].append({"id": "PRES", "tipo": "Presencia del Estado", "titulo": "Presencia del Estado visible por AIS", "texto": txt, "fuentes": [FUENTE_AIS],
                       "nivel": nivel_evidencia([FUENTE_AIS]),
                       "no_dice": "No es «el Estado no está»: las unidades que apagan el AIS o no lo tienen no figuran, y la fuente no cubre todo el río.",
                       "dato": {"sin_estado_seguidas": seguidas, "mediana": m["mediana"], "estado_capturas": m["estado_capturas"], "capturas": m["capturas"]}})
    # interrupciones de señal de AIS (buques que dejan de verse y reaparecen)
    inter = _interrupciones(marcos_ventana)
    for z, n in inter.items():
        if n["continua"] or n["hueco"]:
            res[z].append({"id": "INT", "tipo": "Calidad de la señal", "titulo": "Buques con interrupciones de señal",
                           "texto": "%d %s dejaron de verse durante %d o más capturas seguidas y reaparecieron: %d en celdas de cobertura continua (más llamativo) y %d en probables huecos de cobertura."
                                    % (n["continua"] + n["hueco"], "buques" if n["continua"] + n["hueco"] != 1 else "buque", INTERRUPCION_CAPS - 1, n["continua"], n["hueco"]),
                           "fuentes": [FUENTE_AIS], "nivel": nivel_evidencia([FUENTE_AIS]),
                           "no_dice": "Una interrupción no es un apagado deliberado: hay buques que entran a puerto, tramos con pocos receptores y fallas de la propia fuente. Que ocurra donde otros buques se ven siempre sólo lo hace más llamativo.", "dato": dict(n)})
    # violencia política (ACLED) y focos de calor, por las unidades que toca la zona
    for z, uni in unidades_por_zona.items():
        sa = siwa_mod.serie_acled(fuentes_siwa, uni) if fuentes_siwa else None
        if sa and len(sa["anios"]) >= 2:
            a1, a0 = sa["anios"][-1], sa["anios"][-2]
            v1, v0 = sa["eventos"][a1], sa["eventos"][a0]
            res[z].append({"id": "VIO", "tipo": "Violencia política", "titulo": "Eventos de violencia política, interanual",
                           "texto": "%d eventos en %d frente a %d en %d, en las provincias o departamentos que toca la zona." % (v1, a1, v0, a0),
                           "fuentes": [FUENTE_ACLED], "nivel": nivel_evidencia([FUENTE_ACLED]),
                           "no_dice": "ACLED codifica prensa y fuentes locales (base secundaria, no oficial); cuenta eventos de toda la unidad, no del tramo, y no los atribuye a ningún grupo.",
                           "dato": {"v1": v1, "v0": v0}})
    # hechos citados en el mapa, con las fuentes que los sostienen
    for z, lst in hechos_fuentes.items():
        for h in lst:
            res[z].append({"id": h["id"], "tipo": h["tipo"], "titulo": h["titulo"], "texto": h["texto"], "fuentes": h["fuentes"],
                           "nivel": nivel_evidencia(h["fuentes"]), "no_dice": h["no_dice"], "dato": {}})
    for z, ind_f in (focos_z or {}).items():
        res.setdefault(z, []).append(ind_f)
    for z, lista_x in (extra or {}).items():
        res.setdefault(z, []).extend(lista_x)
    for z, lst in (prensa or {}).items():
        res.setdefault(z, []).extend(lst)
    return res


def _celda(x, y):
    lat, lon = _pulso.latlon(x, y)
    return (math.floor(lat / 0.25), math.floor(lon / 0.25))


def _interrupciones(marcos):
    """Por zona: buques que dejaron de verse INTERRUPCION_CAPS capturas o más y reaparecieron, separando los que se perdieron en una celda de
    cobertura continua (otros buques se ven ahí casi siempre: más llamativo) de los que se perdieron en un probable hueco de cobertura."""
    vacio = {z[0]: {"continua": 0, "hueco": 0} for z in _pulso.ZONAS}
    if len(marcos) < INTERRUPCION_CAPS + 1:
        return vacio
    celdas_por_captura = [{_celda(p["x"], p["y"]) for p in m["puntos"]} for m in marcos]
    n = len(marcos)
    cobertura = {}
    for cs in celdas_por_captura:
        for c in cs:
            cobertura[c] = cobertura.get(c, 0) + 1
    vistos = {}
    for i, m in enumerate(marcos):
        for p in m["puntos"]:
            vistos.setdefault(_pulso._clave(p), []).append((i, p))
    out = vacio
    for k, lst in vistos.items():
        for (i0, p0), (i1, p1) in zip(lst, lst[1:]):
            if i1 - i0 >= INTERRUPCION_CAPS:
                z = _pulso.zona_de(p1["x"], p1["y"])
                otras = cobertura.get(_celda(p0["x"], p0["y"]), 0) / float(n)
                out[z]["continua" if otras >= COBERTURA_CONTINUA else "hueco"] += 1
                break
    return out


# ---------------------------------------------------------------- escáner propio: hechos detectados por reglas en titulares
ROTULO_TIPO = {"decomiso": "Decomiso o incautación", "detencion": "Detención u operativo contra el crimen organizado", "pirateria": "Piratería o robo de carga",
               "siniestro": "Siniestro náutico", "navegabilidad": "Bajante, calado y navegabilidad", "regulatorio": "Licitación, peaje o conflicto gremial",
               "estado": "Operativo de una fuerza del Estado"}


def escaner(ruta, hoy):
    """(eventos de los últimos 7 días con ubicación, indicios por zona). Detección automática: nunca más que «corroborado»."""
    if not ruta or not Path(ruta).exists():
        return [], [], {}
    d = json.load(open(ruta, encoding="utf-8"))
    evs = d.get("eventos", [])
    por_zona = {}
    for e in evs:
        por_zona.setdefault(e.get("zona") or "general", []).append(e)
    ind = {}
    for z, lst in por_zona.items():
        medios = {m["dominio"]: m for e in lst for m in e["medios"]}
        fuentes = [{"nombre": dom, "familia": "oficial" if m.get("clase") == "oficial" else "prensa", "calificacion": "C3"} for dom, m in medios.items()]
        tipos = {}
        for e in lst:
            for t, r in e["tipos"]:
                tipos[r] = tipos.get(r, 0) + 1
        nivel = nivel_evidencia(fuentes) if len(medios) >= MIN_MEDIOS else "Fuente única"
        if nivel == "Fuerte":
            nivel = "Corroborado"            # un escáner automático no puede probar independencia: tope «corroborado»
        mejor = sorted(lst, key=lambda e: (e["fecha"], e["puntaje"]), reverse=True)[:2]
        ind["gen" if z == "general" else z] = {
            "id": "ESC", "tipo": "Hechos detectados", "titulo": "Hechos detectados por el escáner en titulares, últimos 14 días",
            "texto": "%d %s (%s). Más recientes: %s" % (len(lst), "hecho detectado" if len(lst) == 1 else "hechos detectados",
                                                         ", ".join("%s %d" % (k, v) for k, v in sorted(tipos.items(), key=lambda kv: -kv[1])),
                                                         "; ".join("«%s» (%s, %s)" % (e["titulo"][:100], e["medios"][0]["dominio"], e["fecha"]) for e in mejor)),
            "fuentes": fuentes, "nivel": nivel + " (detección automática)" if nivel != "Fuente única" else nivel,
            "no_dice": "Detección automática por palabras clave, lugares y cantidades: no la verificó una persona y un titular no es un hecho confirmado. No puede probar que dos medios sean independientes (muchos copian a una agencia o a un comunicado oficial), así que nunca pasa de «corroborado».",
            "dato": {"n": len(lst)}, "enlaces": [e["medios"][0]["url"] for e in mejor]}
    recientes = [e for e in evs if e.get("ubicacion") and e["fecha"] >= (datetime.strptime(hoy, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")]
    return recientes, evs, ind


def marcas_escaner(recientes):
    """Un rombo por lugar con los hechos de los últimos 7 días; devuelve (svg, info del panel) por lugar."""
    por = {}
    for e in recientes:
        lat, lon = e["ubicacion"]
        por.setdefault((lat, lon), []).append(e)
    svgs, infos = [], []
    for k, ((lat, lon), lst) in enumerate(sorted(por.items())):
        x, y = _pulso.AX * lon + _pulso.BX, _pulso.AY * lat + _pulso.BY
        lugar = lst[0]["lugares"][0] if lst[0]["lugares"] else "Corredor"
        svgs.append('<g class="esc-g clicable" data-i="ev%d" data-familia="indicios" transform="translate(%.1f,%.1f)"><circle class="hit" r="12"/><path class="esc" d="M0,-5.5L5.5,0L0,5.5L-5.5,0Z"/></g>' % (k, x, y))
        ctx = []
        for e in sorted(lst, key=lambda e: (e["fecha"], e["puntaje"]), reverse=True)[:6]:
            q = (" · %s %s" % (("%g" % e["cantidad"]["valor"]).replace(".", ","), e["cantidad"]["unidad"])) if e.get("cantidad") else ""
            ctx.append("%s · %s%s: «%s» — %s%s %s" % (e["fecha"], "; ".join(r for _, r in e["tipos"]), q, e["titulo"][:150],
                                                   ", ".join(m["dominio"] for m in e["medios"]), " (enlace verificado)" if e.get("verificado") else " (enlace sin verificar)", e["medios"][0]["url"]))
        infos.append({"id": "ev%d" % k, "categoria": "Hechos detectados por el escáner · últimos 7 días", "titulo": "%s: %d %s" % (lugar, len(lst), "hecho" if len(lst) == 1 else "hechos"),
                      "tipo": "Candidatos detectados por reglas en titulares de prensa y de organismos · la ubicación es la del lugar mencionado, no la del hecho",
                      "fuente": "Escáner propio de Ysyry sobre canales RSS públicos de medios regionales y de organismos (sin modelo)", "clase": "escaner", "coord": None, "foto": None,
                      "ctx": ctx, "ctx_t": "Titulares detectados (candidatos, no verificados)",
                      "ctx_f": "No los verificó una persona y un titular no es un hecho confirmado. Lee la nota completa en el medio antes de sacar conclusiones."})
    return svgs, infos


def tabla_escaner(evs, hoy):
    import html
    e = html.escape
    filas = []
    for h in sorted(evs, key=lambda x: (x["fecha"], x["puntaje"]), reverse=True)[:25]:
        q = ("%s %s" % (("%g" % h["cantidad"]["valor"]).replace(".", ","), h["cantidad"]["unidad"])) if h.get("cantidad") else "—"
        med = "; ".join('<a href="%s" target="_blank" rel="noopener nofollow">%s</a>%s' % (e(m["url"]), e(m["dominio"]), " (oficial)" if m.get("clase") == "oficial" else "")
                        for m in h["medios"] if m["url"].startswith(("http://", "https://")))
        filas.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                     % (e(h["fecha"]), e("; ".join(r for _, r in h["tipos"])), e(", ".join(h.get("lugares") or ["—"])), e(h["titulo"][:170]), med, e(q),
                        "sí" if h.get("verificado") else ("no" if h.get("verificado") is False else "—")))
    cuerpo = ('<div class="tabla-pulso"><table><thead><tr><th>Fecha</th><th>Tipo</th><th>Lugar</th><th>Titular</th><th>Medios</th><th>Cantidad</th><th>Enlace responde</th></tr></thead><tbody>%s</tbody></table></div>' % "".join(filas)) \
        if filas else '<p class="sub">En los canales que lee el escáner no apareció, en los últimos 14 días, ningún titular que nombre un lugar o el río del corredor y un tipo de hecho de la lista. Eso no significa que no haya pasado nada: sólo lee titulares recientes de pocos medios.</p>'
    return ('<div class="pulso" id="escaner"><h2>Hechos detectados por el escáner propio · últimos 14 días</h2>'
            '<p class="sub">Un programa sin ningún modelo lee los canales RSS públicos de medios regionales y de organismos (SENAD y Policía Nacional de Paraguay, entre otros) y detecta, con reglas escritas, titulares que nombran un lugar o el río del corredor y un tipo de hecho: decomiso, detención, piratería, siniestro, bajante, conflicto gremial u operativo del Estado. '
            '<b>Son candidatos, no hechos confirmados:</b> no entiende el texto, no verifica que sea cierto y no puede probar que dos medios sean independientes. Los rombos del mapa marcan el lugar mencionado, no el del hecho.</p>%s'
            '<p class="sub">Consultado el %s (UTC).</p></div>' % (cuerpo, e(hoy)))


# ---------------------------------------------------------------- avisos oficiales (INMET, Meteorología de Paraguay, GDACS)
ZONA_LUGAR = {"Corumbá": "z5", "Ladário": "z5", "Porto Murtinho": "z5", "Cáceres": "z5", "Paraguay": "z5", "Foz do Iguaçu": "z4", "Ponta Porã": "z4", "Guaíra": "z4"}


def avisos(ruta):
    """{zona: [indicio]}: avisos oficiales vigentes que nombran lugares de cada tramo, más el estado de cobertura de las fuentes en «gen»."""
    if not ruta or not Path(ruta).exists():
        return {}
    d = json.load(open(ruta, encoding="utf-8"))
    por = {}
    for a in d.get("avisos", []):
        if a.get("lat") is not None:
            zs = {_pulso.zona_de(_pulso.AX * a["lon"] + _pulso.BX, _pulso.AY * a["lat"] + _pulso.BY)}
        else:
            zs = {ZONA_LUGAR[l] for l in a.get("lugares", []) if l in ZONA_LUGAR} or {"gen"}
        for z in zs:
            por.setdefault(z, []).append(a)
    out = {}
    for z, lst in por.items():
        # un indicio por fuente: dos avisos de servicios distintos casi nunca hablan del mismo hecho, así que no se corroboran entre sí
        for fuente in sorted({a["fuente"] for a in lst}):
            propios = [a for a in lst if a["fuente"] == fuente]
            grupos = {}
            for a in propios:
                g = grupos.setdefault((a["fenomeno"][:70], a.get("severidad", "")), {"fin": "", "n": 0})
                g["n"] += 1
                g["fin"] = max(g["fin"], a.get("fin") or "")
            partes = ["%s%s%s" % (k[0], (" (" + k[1] + ")") if k[1] else "", (", hasta " + g["fin"]) if g["fin"] else ", vigente") for k, g in list(grupos.items())[:5]]
            fuentes = [{"nombre": fuente, "familia": "oficial", "calificacion": "A2"}]
            out.setdefault(z, []).append({"id": "AVI", "tipo": "Avisos oficiales", "titulo": "Avisos vigentes de %s que nombran este tramo" % fuente.split(" (")[0],
                                          "texto": "%d %s: %s." % (len(propios), "aviso" if len(propios) == 1 else "avisos", "; ".join(partes)), "fuentes": fuentes, "nivel": nivel_evidencia(fuentes),
                                          "no_dice": "Es un aviso general del servicio oficial para esos municipios o esa zona, no dice cómo afecta la navegación. Sólo cubre las fuentes consultadas: no se consulta el INUMET de Uruguay.",
                                          "dato": {"n": len(propios)}})
    fs = d.get("fuentes", [])
    out.setdefault("gen", []).append({"id": "AVC", "tipo": "Avisos oficiales", "titulo": "Fuentes de avisos oficiales consultadas",
                                       "texto": "Consultadas hoy: %s. %d avisos vigentes sobre el corredor. No consultadas: %s." % (
                                           ", ".join("%s%s" % (f["nombre"], "" if f.get("ok") else " (no respondió)") for f in fs), len(d.get("avisos", [])), "; ".join(d.get("no_consultadas", []))),
                                       "fuentes": [{"nombre": "Servicios meteorológicos y GDACS", "familia": "oficial", "calificacion": "A2"}], "nivel": "Estado de cobertura",
                                       "no_dice": "«Sin avisos» sólo vale para las fuentes consultadas.", "dato": {}})
    return out


# ---------------------------------------------------------------- focos de calor cerca del río (NASA FIRMS)
def focos(ruta):
    """(puntos con x, y, zona; indicios por zona). Cuenta los focos de los últimos 3 días a menos de 25 km del río."""
    if not ruta or not Path(ruta).exists():
        return [], {}
    d = json.load(open(ruta, encoding="utf-8"))
    pts, por = [], {}
    for lat, lon, fecha, hora, frp, conf, dn, sensor, km in d.get("puntos", []):
        x, y = _pulso.AX * lon + _pulso.BX, _pulso.AY * lat + _pulso.BY
        z = _pulso.zona_de(x, y)
        pts.append({"x": x, "y": y, "z": z, "frp": frp, "conf": conf, "dn": dn, "fecha": fecha})
        c = por.setdefault(z, {"n": 0, "alta": 0, "noche": 0})
        c["n"] += 1
        c["alta"] += 1 if conf == "h" else 0
        c["noche"] += 1 if dn == "N" else 0
    out = {}
    for z, c in por.items():
        out[z] = {"id": "FOC", "tipo": "Focos de calor", "titulo": "Focos de calor cerca del río, últimos 3 días",
                  "texto": "%d detecciones a menos de %d km del río (%d de confianza alta, %d nocturnas), de dos satélites VIIRS." % (c["n"], int(d.get("radio_km", 25)), c["alta"], c["noche"]),
                  "fuentes": [FUENTE_FIRMS], "nivel": nivel_evidencia([FUENTE_FIRMS]),
                  "no_dice": "Una anomalía térmica no es un incendio confirmado ni dice su causa (quema agrícola, incendio forestal, antorcha industrial). Dos satélites pueden ver el mismo foco, y una semana nublada lo esconde.",
                  "dato": c}
    return pts, out


def marca_foco(p):
    return '<g class="foco-g" data-familia="indicios" transform="translate(%.1f,%.1f)"><circle class="foco%s" r="%s"/></g>' % (p["x"], p["y"], " foco-alto" if p["conf"] == "h" else "", "2.6" if p["conf"] == "h" else "2")


# ---------------------------------------------------------------- prensa (segunda familia de fuentes)
TEMAS_PRENSA = {"pirateria": "Piratería y robo de carga fluvial", "crimen_organizado": "Crimen organizado transnacional",
                "narcotrafico": "Narcotráfico por la vía fluvial", "navegabilidad": "Bajante, calado y navegabilidad",
                "regulatorio": "Licitación, dragado y peaje", "gremial": "Conflictos gremiales en puertos", "operativos": "Operativos de fuerzas de seguridad"}


def indicios_prensa(ruta):
    """{zona|'gen': [indicio]} a partir de noticias.json: medios DISTINTOS por tema y zona en los últimos 7 días. Detección automática."""
    if not ruta or not Path(ruta).exists():
        return {}
    d = json.load(open(ruta, encoding="utf-8"))
    out = {}
    for tid, t in d.get("temas", {}).items():
        if t.get("desactualizado_desde"):      # un tema que ya no se pudo actualizar no cuenta como cobertura de esta semana
            continue
        por = {}
        for a in t.get("articulos", []):
            if a.get("dominio") and a.get("url", "").startswith(("http://", "https://")):
                por.setdefault(a.get("zona") or "general", []).append(a)
        for z, arts in por.items():
            medios = {}
            for a in arts:
                medios.setdefault(a["dominio"], a)
            fuentes = [{"nombre": dom, "familia": "prensa", "calificacion": "C3"} for dom in medios]
            muestra = list(medios.values())[:2]
            out.setdefault("gen" if z == "general" else z, []).append({
                "id": "PRE-" + tid, "tipo": "Prensa", "titulo": "Cobertura de prensa: " + TEMAS_PRENSA.get(tid, t.get("rotulo", tid)),
                "texto": "%s en los últimos 7 días (%d %s). Ejemplos: %s" % (
                    ("1 medio" if len(medios) == 1 else "%d medios distintos" % len(medios)), len(arts), "titular" if len(arts) == 1 else "titulares", "; ".join("«%s» (%s)" % (a["titulo"][:110], a["dominio"]) for a in muestra)),
                "fuentes": fuentes, "nivel": nivel_evidencia(fuentes) if len(medios) >= MIN_MEDIOS else "Fuente única",
                "no_dice": "Detección automática por palabras clave sobre titulares, no verificada por una persona: un titular no es un hecho confirmado, y varios medios pueden repetir la misma agencia. Leé las notas antes de sacar conclusiones.",
                "dato": {"medios": len(medios), "tema": tid}, "enlaces": [a["url"] for a in muestra]})
    return out


# ---------------------------------------------------------------- tabla de la página
def tabla_html(ind, fecha):
    import html
    e = html.escape
    filas = []
    for z, nombre, _ in _pulso.ZONAS + [("gen", "Corredor en general", "")]:
        lst = ind.get(z, [])
        if not lst and z == "gen":
            continue
        if not lst:
            filas.append('<tr><th scope="row">%s</th><td colspan="4" class="sd">Sin indicios con datos en esta zona hoy. No significa que no pase nada: significa que no lo vemos.</td></tr>' % e(nombre))
            continue
        for k, i in enumerate(lst):
            f = "; ".join("%s (%s)" % (x["nombre"], x["familia"]) for x in i["fuentes"][:6]) + (" y %d más" % (len(i["fuentes"]) - 6) if len(i["fuentes"]) > 6 else "")
            enl = "".join('<br><a href="%s" target="_blank" rel="noopener nofollow">nota ↗</a>' % e(u_) for u_ in i.get("enlaces", []) if u_.startswith(("http://", "https://")))
            filas.append('<tr>%s<td><b>%s</b><br>%s</td><td><span class="ev ev-%s">%s</span></td><td>%s</td><td>%s</td></tr>'
                         % ('<th scope="row" rowspan="%d">%s</th>' % (len(lst), e(nombre)) if k == 0 else "",
                            e(i["titulo"]), e(i["texto"]), e(i["nivel"].split()[0].lower()), e(i["nivel"]) + ("<br><small>no verificado: falta una segunda fuente</small>" if i["nivel"].startswith("Fuente única") else ""), e(f) + enl, e(i["no_dice"])))
    return ('<div class="pulso" id="indicios-zonas"><h2>Libro de indicios por zona</h2>'
            '<p class="sub">Cada observación con sus fuentes, su familia de fuente y su nivel de evidencia. <b>Fuente única</b>: una sola. <b>Corroborado</b>: dos o más fuentes independientes de la misma familia. '
            '<b>Fuerte</b>: dos o más independientes de al menos dos familias. Varias estaciones de un mismo organismo, o las dos redes de AIS, cuentan como una fuente. '
            '<b>Regla de verificación de la casa: dos fuentes independientes como mínimo.</b> Con una sola, el indicio se rotula «fuente única, no verificado» y no se presenta como un hecho; con dos o más, «corroborado» o «fuerte». ' + '<b>Un indicio no es una alerta:</b> las alertas las escribe una persona, las impugna el décimo hombre y las publica la dirección. Hoy no hay ninguna publicada.</p>'
            '<div class="tabla-pulso"><table><thead><tr><th>Zona</th><th>Indicio</th><th>Evidencia</th><th>Fuentes</th><th>Lo que no dice</th></tr></thead><tbody>%s</tbody></table></div>'
            '<p class="sub">Consultado el %s (UTC).</p></div>' % ("".join(filas), e(fecha)))


# ---------------------------------------------------------------- alertas candidatas (sólo para la curaduría, nunca se publican)
def candidatas(ind, ests, fecha, hist_reglas=None):
    """Reglas de disparo, con parámetros iniciales a calibrar. Una candidata es un aviso interno para quien cura, no una alerta."""
    out = []
    for z, nombre, _ in _pulso.ZONAS + [("gen", "Corredor en general", "")]:
        for i in ind.get(z, []):
            d = i["dato"]
            if i["id"].startswith("PRE-") and d.get("tema") in ("pirateria", "crimen_organizado", "narcotrafico") and d.get("medios", 0) >= MIN_MEDIOS:
                out.append({"clave": "PRENSA-1|%s|%s|%s" % (d["tema"], z, fecha), "regla": "PRENSA-1 · " + d["tema"], "zona": nombre,
                            "titulo": "Cobertura de prensa sobre %s en %s" % (TEMAS_PRENSA.get(d["tema"], d["tema"]).lower(), nombre.lower() if z != "gen" else "el corredor"),
                            "indicio": i["texto"], "evidencia": i["nivel"] + " (detección automática)", "estaciones": [],
                            "pregunta_posible": "¿Se confirmará por una fuente oficial un hecho de este tipo en la zona en los próximos 14 días?"})
            if i["id"] == "NAV" and d.get("ambas", 0) >= 2:
                bajos = [e["nombre"] for e in ests if e["pos"] and e["pos"]["zona"] == z and e["estado"] in ("bajo", "cerca") and e["var_cm"] is not None and e["var_cm"] <= VAR_BAJA_CM]
                out.append({"clave": "NAV-1|%s|%s" % (z, fecha), "regla": "NAV-1", "zona": nombre,
                            "titulo": "Nivel bajo y a la baja en %s" % nombre,
                            "indicio": i["texto"], "evidencia": i["nivel"], "estaciones": bajos,
                            "pregunta_posible": "¿Alguna de esas estaciones registrará un nuevo mínimo del año o una baja de 20 cm en los próximos 14 días?"})
            if i["id"] == "PRES" and d.get("sin_estado_seguidas", 0) >= CAPS_BRECHA and d.get("mediana", 0) >= MIN_BUQUES_BRECHA:
                out.append({"clave": "PRES-1|%s|%s" % (z, fecha), "regla": "PRES-1", "zona": nombre,
                            "titulo": "Brecha de presencia del Estado visible en %s" % nombre,
                            "indicio": i["texto"], "evidencia": i["nivel"], "estaciones": [],
                            "pregunta_posible": "¿Habrá una unidad del Estado visible por AIS en la zona en las próximas 24 horas?"})
    for c in out:
        previos = (hist_reglas or {})
        dias = [f for f, lst in previos.items() if f != fecha]
        disp = [f for f in dias if (c["regla"] + "|" + c["zona"]) in previos[f]]
        c["calibracion"] = ("Esta regla se disparó %d de %d días registrados antes de hoy en esta zona." % (len(disp), len(dias))) if dias else "Sin días previos registrados para calibrar."
    return out


def registrar_disparos(ruta_historial, fecha, cands):
    """Anota qué reglas se dispararon hoy en cada zona, para poder ver después si son demasiado sensibles."""
    p = Path(ruta_historial)
    hist = json.load(open(p, encoding="utf-8")) if p.exists() else {"zonas": {}}
    hist.setdefault("reglas", {})[fecha] = sorted({c["regla"] + "|" + c["zona"] for c in cands})
    for viejo in sorted(hist["reglas"])[:-120]:
        del hist["reglas"][viejo]
    json.dump(hist, open(p, "w", encoding="utf-8"), separators=(",", ":"), ensure_ascii=False)
    return hist["reglas"]
