"""Pulso por zona: qué se observa en cada tramo del corredor a partir de las capturas de AIS de las últimas
24 horas, y cómo se compara con los días anteriores de ese mismo tramo.

Mide huellas observables (buques que transmiten, detenidos o en movimiento, unidades del Estado visibles), no
conductas de ningún actor: nada de esto dice qué hace un grupo criminal. Donde el AIS no llega, la zona sale
"sin datos" y no "sin tráfico". Las zonas son cajas aproximadas sobre el mapa, no límites administrativos.
"""
import collections
import html
import json
import statistics
from pathlib import Path

AX, BX, AY, BY = 38.9572, 2781.788, -43.2531, -653.764   # proyección lineal del mapa (ver construir.py)
ZONAS = [
    ("z1", "Delta y Río de la Plata", "Del estuario hasta el sur del Gran Rosario (al sur de 33,7° S)"),
    ("z2", "Rosario – San Lorenzo", "Entre 33,7° S y 32,0° S"),
    ("z3", "Paraná medio", "Entre 32,0° S y 27,6° S, hasta la confluencia con el Paraguay"),
    ("z4", "Alto Paraná y Triple Frontera", "Al norte de 27,6° S y al este de 57,2° O"),
    ("z5", "Río Paraguay", "Al norte de 27,6° S y al oeste de 57,2° O, de Asunción a Corumbá"),
]
# ubicación orientativa de la boya de cada zona (sobre el río, no un punto de medición): lat, lon
BOYAS = {"z1": (-34.00, -58.60), "z2": (-32.75, -60.70), "z3": (-30.75, -59.60), "z4": (-26.00, -54.70), "z5": (-23.20, -57.45)}
DIAS_PARA_COMPARAR = 7
MAX_DIAS = 120


def latlon(x, y):
    return (y - BY) / AY, (x - BX) / AX


def zona_de(x, y):
    lat, lon = latlon(x, y)
    if lat > -27.6:
        return "z4" if lon >= -57.2 else "z5"
    if lat > -32.0:
        return "z3"
    if lat > -33.7:
        return "z2"
    return "z1"


def _clave(p):
    return "%s|%s|%s" % (p.get("imo") or "", (p.get("nombre") or "").strip().upper(), p.get("callsign") or "")


def calcular(marcos, es_estado, categoria=None, fuerza=None):
    """Métricas por zona sobre las capturas dadas (las de las últimas 24 h)."""
    n = len(marcos)
    por_zona = {z[0]: {"conteos": [], "claves": set(), "estado_caps": 0, "estado_claves": set(), "mov": 0, "det": 0, "sv": 0, "caps_con": 0,
                       "estado_serie": [], "tipos": collections.Counter(), "banderas": collections.Counter(), "unidades": {}}
                for z in ZONAS}
    for i, m in enumerate(marcos):
        ult = i == n - 1
        vistos_estado = set()
        cuenta = {z: 0 for z in por_zona}
        for p in m["puntos"]:
            z = zona_de(p["x"], p["y"])
            cuenta[z] += 1
            por_zona[z]["claves"].add(_clave(p))
            if es_estado(p):
                vistos_estado.add(z)
                por_zona[z]["estado_claves"].add(_clave(p))
                u = por_zona[z]["unidades"].setdefault(_clave(p), {"nombre": (p.get("nombre") or "sin nombre").strip(), "fuerza": fuerza(p) if fuerza else "", "caps": 0})
                u["caps"] += 1
            if ult:
                por_zona[z]["tipos"][categoria(p.get("tipo_ais"))[0] if categoria else "sin clasificar"] += 1
                por_zona[z]["banderas"][p.get("bandera") or "sin bandera"] += 1
                v = p.get("velocidad")
                if v is None:
                    por_zona[z]["sv"] += 1
                elif v > 1:
                    por_zona[z]["mov"] += 1
                else:
                    por_zona[z]["det"] += 1
        for z, c in cuenta.items():
            por_zona[z]["conteos"].append(c)
            if c:
                por_zona[z]["caps_con"] += 1
        for z in vistos_estado:
            por_zona[z]["estado_caps"] += 1
        for z in por_zona:
            por_zona[z]["estado_serie"].append(1 if z in vistos_estado else 0)
    out = {}
    for z, d in por_zona.items():
        out[z] = {"capturas": n, "mediana": statistics.median(d["conteos"]) if d["conteos"] else 0,
                  "distintos": len(d["claves"]), "en_movimiento": d["mov"], "detenidos": d["det"], "sin_velocidad": d["sv"],
                  "estado_capturas": d["estado_caps"], "estado_distintos": len(d["estado_claves"]),
                  "capturas_con_datos": d["caps_con"], "serie": d["conteos"], "estado_serie": d["estado_serie"],
                  "horas": [m["hora"][11:16] for m in marcos], "tipos": d["tipos"].most_common(6), "banderas": d["banderas"].most_common(5),
                  "unidades": sorted(d["unidades"].values(), key=lambda u: -u["caps"])}
    return out


def actualizar_historial(ruta, fecha, calc):
    """Suma (o reemplaza) la entrada del día; la última corrida del día es la que queda."""
    p = Path(ruta)
    hist = json.load(open(p, encoding="utf-8")) if p.exists() else {"zonas": {}}
    for z, met in calc.items():
        dias = hist["zonas"].setdefault(z, {})
        dias[fecha] = {k: met[k] for k in ("mediana", "distintos", "estado_capturas", "capturas", "capturas_con_datos")}
        for viejo in sorted(dias)[:-MAX_DIAS]:
            del dias[viejo]
    p.parent.mkdir(parents=True, exist_ok=True)
    json.dump(hist, open(p, "w", encoding="utf-8"), separators=(",", ":"), ensure_ascii=False)
    return hist


def spark_svg(serie, estado=None, ancho=110, alto=26):
    """Barras de buques por captura (una por hora); un punto arriba marca las capturas con unidades del Estado."""
    if not serie or not max(serie):
        return ""
    n, mx = len(serie), max(serie)
    w = ancho / n
    barras = "".join('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f"/>' % (i * w + 0.5, alto - 5 - (alto - 8) * v / mx, max(w - 1, 1), (alto - 8) * v / mx) for i, v in enumerate(serie))
    puntos = "".join('<circle cx="%.1f" cy="2" r="1.6" class="pe"/>' % (i * w + w / 2) for i, v in enumerate(estado or []) if v)
    return '<svg class="spark" viewBox="0 0 %d %d" width="%d" height="%d" role="img" aria-label="Buques por captura en las últimas %d capturas">%s%s</svg>' % (ancho, alto, ancho, alto, n, barras, puntos)


def comparar(hist, z, fecha, mediana):
    previos = [v["mediana"] for f, v in hist["zonas"].get(z, {}).items() if f < fecha and v.get("capturas_con_datos")]
    if len(previos) < DIAS_PARA_COMPARAR:
        return "Sin base de comparación: %d de %d días de historia" % (len(previos), DIAS_PARA_COMPARAR)
    prom = statistics.mean(previos)
    if prom == 0:
        return "Promedio previo de %d días: 0" % len(previos)
    return "%+.0f %% frente al promedio de sus %d días previos" % (100 * (mediana - prom) / prom, len(previos))


def bloque_html(calc, hist, fecha, hechos, contexto=None, pie_contexto=""):
    """hechos: {zona: [textos ya redactados]}; todo se escapa."""
    e = html.escape
    filas = []
    for z, nombre, cobertura in ZONAS:
        m = calc[z]
        if m["distintos"] == 0:
            celdas = ['<td colspan="4" class="sd">Sin datos de AIS en este tramo en las últimas 24 h. <b>No significa que no haya tráfico:</b> significa que no lo vemos.</td>']
        else:
            celdas = ["<td>%s%s</td>" % (e(("%g" % m["mediana"]).replace(".", ",")), spark_svg(m["serie"], m["estado_serie"])), "<td>%d</td>" % m["distintos"],
                      "<td>%d en movimiento (más de 1 nudo) · %d detenidos o fondeados%s</td>" % (m["en_movimiento"], m["detenidos"],
                                                                                    (" · %d sin velocidad informada" % m["sin_velocidad"]) if m["sin_velocidad"] else ""),
                      "<td>%d de %d capturas (%d %s)</td>" % (m["estado_capturas"], m["capturas"], m["estado_distintos"], "unidad" if m["estado_distintos"] == 1 else "unidades")]
        comp = comparar(hist, z, fecha, m["mediana"]) if m["distintos"] else "—"
        hx = "<br>".join(e(t) for t in hechos.get(z, [])) or "Ninguno cargado"
        c = (contexto or {}).get(z)
        if c and c["acled"] and c["focos"]:
            ac, fo = c["acled"], c["focos"]
            cx = ("ACLED %s: %d %s, %d %s (%d de %d unidades con dato)<br>Focos de calor, %s días: %d (%d de %d unidades con dato)"
                  % (ac["anio"], ac["eventos"], "evento" if ac["eventos"] == 1 else "eventos", ac["victimas"],
                     "víctima" if ac["victimas"] == 1 else "víctimas", ac["con_dato"], c["unidades"],
                     fo["dias"], fo["total"], fo["con_dato"], c["unidades"]))
        else:
            cx = "Sin contexto cargado"
        filas.append('<tr><th scope="row">%s<small>%s</small></th>%s<td>%s</td><td>%s</td><td>%s</td></tr>'
                     % (e(nombre), e(cobertura), "".join(celdas), e(comp), hx, cx))
    return ('<div class="pulso" id="pulso-zonas"><h2>Pulso por zona · últimas 24 horas</h2>'
            '<p class="sub">Qué se observa en cada tramo del corredor a partir de las posiciones AIS, y cómo se compara con los días anteriores del mismo tramo. '
            'Mide huellas observables de buques que transmiten, <b>no la conducta de ningún actor</b>: no dice qué hace un grupo criminal ni qué patrulla una fuerza, '
            'sólo qué unidades con AIS se ven y dónde. Un tramo vacío puede ser un tramo sin cobertura.</p>'
            '<div class="tabla-pulso"><table><thead><tr><th>Zona</th><th>Buques por captura (mediana)</th><th>Distintos en 24 h</th><th>Ahora</th>'
            '<th>Unidades del Estado visibles</th><th>Comparación con su propia historia</th><th>Hechos informados en la zona</th><th>Contexto de las provincias que toca (SIWA)</th></tr></thead><tbody>%s</tbody></table></div>'
            '<p class="sub">Las zonas son cajas aproximadas sobre el mapa, no límites administrativos. «Estado» cuenta sólo las unidades que transmiten AIS con tipo militar o de fuerzas del orden, '
            'o con el prefijo de su designación (ARA, GC, ARP, PGN, LP): las que apagan el AIS o no lo tienen no figuran. '
            'Un buque se cuenta como distinto por su IMO, nombre e indicativo. La comparación necesita %d días de historia en el mismo tramo y se calcula sobre la mediana de buques por captura. Día de referencia: %s (UTC).</p>%s</div>'
            % ("".join(filas), DIAS_PARA_COMPARAR, e(fecha),
               ('<p class="sub">%s Las cifras son de la provincia, departamento o estado completo que toca el tramo, no del tramo: una unidad grande suma más, y cada tramo toca las unidades que la Fundación listó en el código. Se dejaron fuera Mato Grosso do Sul y Paraná (Brasil): son estados muy grandes que tocan el corredor de costado y dominaban las sumas. '
                'ACLED codifica prensa y fuentes locales (base secundaria, no oficial) y un foco de calor es una anomalía térmica, no un incendio confirmado; «sin dato» no equivale a cero.</p>' % e(pie_contexto)) if contexto else ""))


def _fmt_ctx(c):
    if not (c and c.get("acled") and c.get("focos")):
        return []
    ac, fo = c["acled"], c["focos"]
    return ["ACLED %s en las provincias que toca: %d %s y %d %s (%d de %d unidades con dato; base secundaria, no oficial)"
            % (ac["anio"], ac["eventos"], "evento" if ac["eventos"] == 1 else "eventos", ac["victimas"], "víctima" if ac["victimas"] == 1 else "víctimas", ac["con_dato"], c["unidades"]),
            "Focos de calor de NASA FIRMS en esas provincias, últimos %s días: %d (%d de %d unidades con dato; no son incendios confirmados)" % (fo["dias"], fo["total"], fo["con_dato"], c["unidades"])]


def info_zona(z, calc, hist, fecha, hechos, contexto):
    """Ficha de la zona para el panel del mapa (se abre al tocar su boya)."""
    nombre, cobertura = [(n, c) for i, n, c in ZONAS if i == z][0]
    m = calc[z]
    if m["distintos"] == 0:
        tipo = " · ".join([cobertura, "Sin datos de AIS en las últimas 24 h: no significa que no haya tráfico, significa que no lo vemos"])
        ctx = []
    else:
        ult = m["serie"][-1] if m["serie"] else 0
        tipo = " · ".join([cobertura,
                           "%d buques en la última captura (mediana de %s por captura, %d distintos en 24 h)" % (ult, ("%g" % m["mediana"]).replace(".", ","), m["distintos"]),
                           "%d en movimiento (más de 1 nudo), %d detenidos o fondeados" % (m["en_movimiento"], m["detenidos"])])
        if m["unidades"]:
            u = "; ".join("%s: %s, en %d de %d capturas" % (x["nombre"], x["fuerza"] or "fuerza no inferida", x["caps"], m["capturas"]) for x in m["unidades"][:6])
            ctx = ["Unidades del Estado visibles: " + u + (" y %d más" % (len(m["unidades"]) - 6) if len(m["unidades"]) > 6 else "")]
        else:
            ctx = ["Unidades del Estado visibles: ninguna con AIS en las últimas 24 h (las que apagan el AIS o no lo tienen no figuran)"]
        if m["tipos"]:
            ctx.append("Tipos de buque en la última captura: " + ", ".join("%s %d" % (k, v) for k, v in m["tipos"]))
        if m["banderas"]:
            ctx.append("Banderas más frecuentes: " + ", ".join("%s %d" % (k, v) for k, v in m["banderas"]))
        ctx.append("Comparación con su propia historia: " + comparar(hist, z, fecha, m["mediana"]))
    ctx += ["Según las fuentes citadas en el mapa: " + t for t in hechos.get(z, [])]
    ctx += _fmt_ctx(contexto.get(z))
    out = {"id": "p" + z, "categoria": "Pulso de la zona · AIS, últimas 24 horas", "titulo": nombre, "tipo": tipo,
           "fuente": "AIS vía Open Waters (AISHub y aisstream.io) y SIWA (CC BY 4.0) · cálculo propio de Ysyry, día de referencia %s UTC" % fecha,
           "clase": "boya", "coord": "%.2f, %.2f" % BOYAS[z] + " (ubicación orientativa de la boya)", "foto": None,
           "ctx": ctx, "ctx_t": "Qué se observa en la zona",
           "ctx_f": "Mide huellas observables de buques que transmiten AIS, no la conducta de ningún actor: no dice qué hace un grupo criminal ni qué patrulla una fuerza. Un tramo sin datos puede ser un tramo sin cobertura."}
    if m["distintos"]:
        out["spark_svg"] = spark_svg(m["serie"], m["estado_serie"], ancho=260, alto=54)
        out["spark_pie"] = "Buques por captura, de las %s a las %s UTC (una barra por hora). Los puntos de arriba marcan las capturas con unidades del Estado visibles." % (m["horas"][0], m["horas"][-1])
    return out


def boya(z, calc):
    """(svg de la boya, x, y, etiqueta). Con anillos animados si la zona tiene datos; punteada y quieta si no."""
    lat, lon = BOYAS[z]
    x, y = AX * lon + BX, AY * lat + BY
    vivo = calc[z]["distintos"] > 0
    nombre = [n for i, n, c in ZONAS if i == z][0]
    svg = ('<g class="boya-g clicable %s" data-i="p%s" data-familia="seguridad comercio estado regulatorio" transform="translate(%.1f,%.1f)">'
           '<circle class="hit" r="14"/><circle class="boya-aro" r="9"/><circle class="boya-aro a2" r="9"/><circle class="boya-n" r="3.6"/></g>'
           % ("boya-vivo" if vivo else "boya-sd", z, x, y))
    return svg, x, y, "Pulso · " + nombre + ("" if vivo else " (sin datos)")
