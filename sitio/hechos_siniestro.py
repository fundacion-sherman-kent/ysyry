"""Siniestros náuticos, derrames y cargas peligrosas: indicador a partir de datos/publico/siniestros-corredor.json (lo arma colectores/siniestros.py desde el escáner propio).
Se muestra aunque no haya hechos, porque «0 informados» es información, siempre con la aclaración de que no es una estadística y de que la base es reciente."""
import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "colectores"))
import siniestros as _col

CARGA = {c[0]: c[1] for c in _col.CARGAS}
CARGA["sin_dato"] = "carga sin dato en el titular"
DIAS_VENCIDO = 5
VENTANA = 30


def indicios(ruta, hoy):
    if not ruta or not Path(ruta).exists():
        return {}
    d = json.load(open(ruta, encoding="utf-8"))
    try:
        if (hoy - datetime.strptime(d["obtenido"][:10], "%Y-%m-%d")).days > DIAS_VENCIDO:
            return {}
    except Exception:
        return {}
    corte = (hoy - timedelta(days=VENTANA)).strftime("%Y-%m-%d")
    ult = [h for h in d["hechos"] if h["fecha"] >= corte]
    no_dice = ("No es una estadística: el IBAMA de Brasil bloquea el acceso automático a sus comunicados de accidentes ambientales, y la Prefectura, la Marinha y la Armada Paraguaya no publican siniestros como datos abiertos. "
               "Son titulares de prensa y de organismos detectados por palabras clave sobre canales RSS, sin verificar. «0 informados» no significa que no haya habido derrames o siniestros: significa que ningún canal "
               "que leemos los contó. La base empezó el %s y acumula desde entonces. Tampoco se sabe aquí la calidad de los combustibles: la ANP de Brasil sólo publica cifras nacionales, y Argentina y Paraguay no publican "
               "controles de calidad por zona." % d.get("desde_base", "?"))
    fuentes = [{"nombre": "Escáner propio (canales RSS de medios y organismos)", "familia": "prensa", "calificacion": "C3"}]
    if not ult:
        return {"gen": [{"id": "SIN", "tipo": "Siniestros y cargas peligrosas", "titulo": "Siniestros náuticos, derrames y cargas peligrosas informados",
                         "texto": "En los últimos %d días ningún canal que leemos informó siniestros náuticos, derrames o incendios con buques o barcazas del corredor (la base acumula desde el %s)." % (VENTANA, d.get("desde_base", "?")),
                         "fuentes": fuentes, "nivel": "Fuente única", "no_dice": no_dice, "dato": {"hechos_30": 0}}]}
    out = {}
    por = {}
    for h in ult:
        por.setdefault("gen" if h.get("zona") in (None, "general") else h["zona"], []).append(h)
    for z, lst in por.items():
        tip, car = Counter(h["siniestro"] for h in lst), Counter(h["carga"] for h in lst)
        ej = lst[:2]
        out[z] = [{"id": "SIN", "tipo": "Siniestros y cargas peligrosas", "titulo": "Siniestros náuticos, derrames y cargas peligrosas informados",
                   "texto": "En los últimos %d días se informaron %d siniestros o derrames (%s; carga: %s). Ejemplos: %s" % (
                       VENTANA, len(lst), "; ".join("%s %d" % kv for kv in tip.most_common(4)), "; ".join("%s %d" % (CARGA[k].lower(), v) for k, v in car.most_common(3)),
                       "; ".join("«%s» (%s)" % (h["titulo"][:110], h["dominio"]) for h in ej)),
                   "fuentes": [{"nombre": dom, "familia": "prensa", "calificacion": "C3"} for dom in sorted({m["dominio"] for h in lst for m in h["medios"]})],
                   "nivel": "Fuente única", "no_dice": no_dice, "dato": {"hechos_30": len(lst), "por_tipo": dict(tip), "por_carga": dict(car)}, "enlaces": [h["url"] for h in ej]}]
    return out
