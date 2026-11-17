"""Decomisos e incautaciones en el corredor: indicador por zona a partir de datos/publico/decomisos-corredor.json (lo arma colectores/decomisos.py acumulando los hechos de tipo «decomiso»
que detecta el escáner propio sobre canales RSS de medios y de la SENAD). Cuenta HECHOS (no titulares) de los últimos 30 días y, de ellos, cuántos tienen al menos dos medios distintos
(mínimo de la regla de las dos fuentes; aun así pueden repetir una misma agencia, y un titular no es un hecho verificado). No hay bases oficiales abiertas de decomisos: la página lo dice."""
import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "colectores"))
import decomisos as _col
import indicios as _ind

ROT = {c[0]: c[1] for c in _col.CLASES}
ROT["otra"] = "otra mercadería"
DIAS_VENCIDO = 5
VENTANA = 30


def _zona(h):
    return "gen" if h.get("imprecisa") or h.get("zona") in (None, "general") else h["zona"]


def _medios(h):
    return {m["dominio"] for m in h["medios"]}


def _cita(h):
    c = h.get("cantidad")
    return "%s %s" % (("%g" % c["valor"]), c["unidad"]) if c else None


def indicios(ruta, hoy):
    """{zona|'gen': [indicio]}. `hoy` es un datetime."""
    if not ruta or not Path(ruta).exists():
        return {}
    d = json.load(open(ruta, encoding="utf-8"))
    try:
        if (hoy - datetime.strptime(d["obtenido"][:10], "%Y-%m-%d")).days > DIAS_VENCIDO:
            return {}
    except Exception:
        return {}
    corte = (hoy - timedelta(days=VENTANA)).strftime("%Y-%m-%d")
    previo = (hoy - timedelta(days=2 * VENTANA)).strftime("%Y-%m-%d")
    ult = [h for h in d["hechos"] if h["fecha"] >= corte]
    ant = [h for h in d["hechos"] if previo <= h["fecha"] < corte]
    por_zona = {}
    for h in ult:
        por_zona.setdefault(_zona(h), []).append(h)
    out = {}
    for z, lst in por_zona.items():
        por_merc = Counter(h["mercaderia"] for h in lst)
        dos = [h for h in lst if len(_medios(h)) >= 2]
        of = [h for h in lst if any(m.get("clase") == "oficial" for m in h["medios"])]
        lugares = Counter(l for h in lst for l in h.get("lugares", [])[:1])
        ej = sorted(lst, key=lambda h: (len(_medios(h)), h["fecha"]), reverse=True)[:2]
        fuentes_dos = [{"nombre": dom, "familia": "prensa", "calificacion": "C3"} for dom in sorted({m for h in dos for m in _medios(h)})]
        fuentes = fuentes_dos or [{"nombre": dom, "familia": "oficial" if any(m.get("clase") == "oficial" and m["dominio"] == dom for h in lst for m in h["medios"]) else "prensa", "calificacion": "C3"}
                                  for dom in sorted({m for h in lst for m in _medios(h)})]
        n, nd, no = len(lst), len(dos), len(of)
        texto = ("En los últimos %d días se %s %d %s %s (por tipo: %s). De ellos, %d %s titulares de al menos dos medios distintos y %d %s de un organismo oficial (por ejemplo la SENAD). "
                 "En los %d días anteriores se registraron %d en toda la base.%s Ejemplos: %s"
                 % (VENTANA, "informó" if n == 1 else "informaron", n, "decomiso o incautación" if n == 1 else "decomisos o incautaciones", "en esta zona" if z != "gen" else "sin lugar preciso (incluye hechos de un estado o provincia entera, rotulados «ubicación imprecisa»)",
                    "; ".join("%s %d" % (ROT[k].lower(), v) for k, v in por_merc.most_common(4)),
                    nd, "tiene" if nd == 1 else "tienen", no, "viene" if no == 1 else "vienen", VENTANA, len(ant),
                    (" Lugares más nombrados: %s." % ", ".join("%s (%d)" % kv for kv in lugares.most_common(3))) if lugares else "",
                    "; ".join("«%s» (%s%s)" % (h["titulo"][:110], h["dominio"], ", " + _cita(h) if _cita(h) else "") for h in ej)))
        out[z] = [{"id": "DEC", "tipo": "Decomisos y contrabando", "titulo": "Decomisos e incautaciones informados por la prensa y la SENAD",
                   "texto": texto, "fuentes": fuentes,
                   "nivel": _ind.nivel_evidencia(fuentes) if len(dos) >= 1 and len(fuentes_dos) >= 2 else "Fuente única",
                   "no_dice": "No es una estadística oficial: ni la Policía Federal y la Receita Federal de Brasil, ni la SENAD y la DNIT de Paraguay, ni la ARCA y las fuerzas federales de Argentina publican decomisos como datos abiertos "
                              "que un robot pueda leer. Son titulares de prensa y de la SENAD clasificados por palabras clave (mercadería y lugar) y pueden estar mal clasificados; los hechos de «erradicación» son destrucción de plantaciones o laboratorios, no "
                              "incautación de cargas. Varios medios pueden repetir la misma agencia, y un titular no es un hecho verificado. Sólo se ven los decomisos que la prensa y los organismos cuentan: no mide cuánto contrabando pasa "
                              "ni dónde. La base empezó el %s y acumula desde entonces." % d.get("desde_base", "?"),
                   "dato": {"hechos_30": len(lst), "hechos_con_dos_medios": len(dos), "hechos_oficiales": len(of), "hechos_30_anteriores": len(ant), "por_mercaderia": dict(por_merc)},
                   "enlaces": [h["url"] for h in ej]}]
    return out
