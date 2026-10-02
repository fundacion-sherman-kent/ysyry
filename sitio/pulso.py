"""Pulso por zona: qué se observa en cada tramo del corredor a partir de las capturas de AIS de las últimas
24 horas, y cómo se compara con los días anteriores de ese mismo tramo.

Mide huellas observables (buques que transmiten, detenidos o en movimiento, unidades del Estado visibles), no
conductas de ningún actor: nada de esto dice qué hace un grupo criminal. Donde el AIS no llega, la zona sale
"sin datos" y no "sin tráfico". Las zonas son cajas aproximadas sobre el mapa, no límites administrativos.
"""
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


def calcular(marcos, es_estado):
    """Métricas por zona sobre las capturas dadas (las de las últimas 24 h)."""
    n = len(marcos)
    por_zona = {z[0]: {"conteos": [], "claves": set(), "estado_caps": 0, "estado_claves": set(), "mov": 0, "det": 0, "sv": 0, "caps_con": 0}
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
            if ult:
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
    out = {}
    for z, d in por_zona.items():
        out[z] = {"capturas": n, "mediana": statistics.median(d["conteos"]) if d["conteos"] else 0,
                  "distintos": len(d["claves"]), "en_movimiento": d["mov"], "detenidos": d["det"], "sin_velocidad": d["sv"],
                  "estado_capturas": d["estado_caps"], "estado_distintos": len(d["estado_claves"]),
                  "capturas_con_datos": d["caps_con"]}
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
            celdas = ["<td>%s</td>" % e(("%g" % m["mediana"]).replace(".", ",")), "<td>%d</td>" % m["distintos"],
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
               ('<p class="sub">%s Las cifras son de la provincia, departamento o estado completo que toca el tramo, no del tramo: una unidad grande suma más, y cada tramo toca las unidades que la Fundación listó en el código. '
                'ACLED codifica prensa y fuentes locales (base secundaria, no oficial) y un foco de calor es una anomalía térmica, no un incendio confirmado; «sin dato» no equivale a cero.</p>' % e(pie_contexto)) if contexto else ""))
