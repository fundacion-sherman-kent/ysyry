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
from datetime import datetime, timezone
from pathlib import Path

import pulso as _pulso

NIVELES = ("Fuente única", "Corroborado", "Fuerte")
PCT_BAJO = 25.0          # «cuarto inferior de su rango histórico»: parámetro inicial, a calibrar por la curaduría
VAR_BAJA_CM = -2         # baja de 2 cm o más en 24 h
DIAS_VENCIDA = 3         # una lectura de más de 3 días ya no describe el río de hoy
MIN_BUQUES_BRECHA = 20   # tráfico por captura desde el que la ausencia del Estado en el AIS es un indicio
CAPS_BRECHA = 12         # capturas seguidas (horas) sin ninguna unidad del Estado visible
AJUSTE_MAX_UNIDADES = 2.3   # ~6 km: se acerca la estación al cauce dibujado sólo si ya está cerca

FUENTE_NIVEL = {"nombre": "Dirección de Meteorología e Hidrología, Paraguay", "familia": "oficial", "calificacion": "A2",
                "url": "https://www.meteorologia.gov.py/nivel-rio/indexconvencional.php"}
FUENTE_AIS = {"nombre": "AIS vía Open Waters (AISHub y aisstream.io)", "familia": "sensor", "calificacion": "B3"}
FUENTE_ACLED = {"nombre": "ACLED vía SIWA", "familia": "base secundaria", "calificacion": "B2"}
FUENTE_FIRMS = {"nombre": "NASA FIRMS vía SIWA", "familia": "sensor", "calificacion": "A2"}


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


def indicios(calc, marcos_ventana, es_estado, ests, fuentes_siwa, unidades_por_zona, hechos_fuentes, siwa_mod):
    """{zona: [indicio]}; cada indicio: id, titulo, texto, fuentes, nivel, no_dice, tipo."""
    por_nivel = _nivel_por_zona(ests)
    res = {z[0]: [] for z in _pulso.ZONAS}
    for z, lista in por_nivel.items():
        vivas = [e for e in lista if e["estado"] not in ("vencida", "regulada")]
        if not vivas:
            continue
        bajas = [e for e in vivas if e["estado"] == "bajo"]
        bajando = [e for e in vivas if e["var_cm"] is not None and e["var_cm"] <= VAR_BAJA_CM]
        txt = "%d estaciones con lectura al día; %d en el cuarto inferior de su rango histórico; %d bajan %d cm o más en 24 h." % (len(vivas), len(bajas), len(bajando), abs(VAR_BAJA_CM))
        res[z].append({"id": "NAV", "tipo": "Navegabilidad", "titulo": "Nivel del río frente a su historia", "texto": txt, "fuentes": [FUENTE_NIVEL],
                       "nivel": nivel_evidencia([FUENTE_NIVEL]),
                       "no_dice": "No es el calado ni una restricción de navegación; mide el nivel de cada estación contra su propia historia. Varias estaciones del mismo organismo son una sola fuente.",
                       "dato": {"vivas": len(vivas), "bajas": len(bajas), "bajando": len(bajando), "ambas": len([e for e in vivas if e in bajas and e in bajando])}})
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
        if n:
            res[z].append({"id": "INT", "tipo": "Calidad de la señal", "titulo": "Buques con interrupciones de señal", "texto": "%d buques dejaron de verse durante 3 o más capturas seguidas y reaparecieron en la zona." % n,
                           "fuentes": [FUENTE_AIS], "nivel": nivel_evidencia([FUENTE_AIS]),
                           "no_dice": "Una interrupción no es un apagado deliberado: hay tramos sin receptores, buques que entran a puerto y fallas de la propia fuente.", "dato": {"n": n}})
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
    return res


def _interrupciones(marcos):
    """Buques vistos antes y después de una pausa de 3 o más capturas, contados por la zona de su última posición."""
    if len(marcos) < 5:
        return {z[0]: 0 for z in _pulso.ZONAS}
    vistos = {}
    for i, m in enumerate(marcos):
        for p in m["puntos"]:
            k = _pulso._clave(p)
            vistos.setdefault(k, []).append((i, _pulso.zona_de(p["x"], p["y"])))
    out = {z[0]: 0 for z in _pulso.ZONAS}
    for k, lst in vistos.items():
        for (i0, _), (i1, z1) in zip(lst, lst[1:]):
            if i1 - i0 >= 4:        # faltó en 3 o más capturas seguidas
                out[z1] += 1
                break
    return out


# ---------------------------------------------------------------- tabla de la página
def tabla_html(ind, fecha):
    import html
    e = html.escape
    filas = []
    for z, nombre, _ in _pulso.ZONAS:
        lst = ind.get(z, [])
        if not lst:
            filas.append('<tr><th scope="row">%s</th><td colspan="4" class="sd">Sin indicios con datos en esta zona hoy. No significa que no pase nada: significa que no lo vemos.</td></tr>' % e(nombre))
            continue
        for k, i in enumerate(lst):
            f = "; ".join("%s (%s)" % (x["nombre"], x["familia"]) for x in i["fuentes"])
            filas.append('<tr>%s<td><b>%s</b><br>%s</td><td><span class="ev ev-%s">%s</span></td><td>%s</td><td>%s</td></tr>'
                         % ('<th scope="row" rowspan="%d">%s</th>' % (len(lst), e(nombre)) if k == 0 else "",
                            e(i["titulo"]), e(i["texto"]), e(i["nivel"].split()[0].lower()), e(i["nivel"]), e(f), e(i["no_dice"])))
    return ('<div class="pulso" id="indicios-zonas"><h2>Libro de indicios por zona</h2>'
            '<p class="sub">Cada observación con sus fuentes, su familia de fuente y su nivel de evidencia. <b>Fuente única</b>: una sola. <b>Corroborado</b>: dos o más fuentes independientes de la misma familia. '
            '<b>Fuerte</b>: dos o más independientes de al menos dos familias. Varias estaciones de un mismo organismo, o las dos redes de AIS, cuentan como una fuente. '
            '<b>Un indicio no es una alerta:</b> las alertas las escribe una persona, las impugna el décimo hombre y las publica la dirección. Hoy no hay ninguna publicada.</p>'
            '<div class="tabla-pulso"><table><thead><tr><th>Zona</th><th>Indicio</th><th>Evidencia</th><th>Fuentes</th><th>Lo que no dice</th></tr></thead><tbody>%s</tbody></table></div>'
            '<p class="sub">Consultado el %s (UTC).</p></div>' % ("".join(filas), e(fecha)))


# ---------------------------------------------------------------- alertas candidatas (sólo para la curaduría, nunca se publican)
def candidatas(ind, ests, fecha):
    """Reglas de disparo, con parámetros iniciales a calibrar. Una candidata es un aviso interno para quien cura, no una alerta."""
    out = []
    for z, nombre, _ in _pulso.ZONAS:
        for i in ind.get(z, []):
            d = i["dato"]
            if i["id"] == "NAV" and d.get("ambas", 0) >= 2:
                bajos = [e["nombre"] for e in ests if e["pos"] and e["pos"]["zona"] == z and e["estado"] == "bajo" and e["var_cm"] is not None and e["var_cm"] <= VAR_BAJA_CM]
                out.append({"clave": "NAV-1|%s|%s" % (z, fecha), "regla": "NAV-1", "zona": nombre,
                            "titulo": "Nivel bajo y a la baja en %s" % nombre,
                            "indicio": i["texto"], "evidencia": i["nivel"], "estaciones": bajos,
                            "pregunta_posible": "¿Alguna de esas estaciones registrará un nuevo mínimo del año o una baja de 20 cm en los próximos 14 días?"})
            if i["id"] == "PRES" and d.get("sin_estado_seguidas", 0) >= CAPS_BRECHA and d.get("mediana", 0) >= MIN_BUQUES_BRECHA:
                out.append({"clave": "PRES-1|%s|%s" % (z, fecha), "regla": "PRES-1", "zona": nombre,
                            "titulo": "Brecha de presencia del Estado visible en %s" % nombre,
                            "indicio": i["texto"], "evidencia": i["nivel"], "estaciones": [],
                            "pregunta_posible": "¿Habrá una unidad del Estado visible por AIS en la zona en las próximas 24 horas?"})
    return out
