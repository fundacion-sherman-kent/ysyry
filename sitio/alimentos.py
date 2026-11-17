"""Alertas de la UE (RASFF) por contaminación o adulteración de alimentos y piensos cuyo origen es un país del corredor: indicador de «Adulteración y contaminación».
Los datos los baja colectores/rasff.py. Es una señal oficial pero indirecta: mide lo que detectan las autoridades de la UE, no lo que ocurre en el río ni dónde nació el problema."""
import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

FUENTE = {"nombre": "RASFF Window, Comisión Europea (alertas sobre alimentos y piensos)", "familia": "oficial", "calificacion": "A2", "url": "https://webgate.ec.europa.eu/rasff-window/screen/search"}
PAISES = {"AR": "Argentina", "BR": "Brasil", "PY": "Paraguay", "BO": "Bolivia", "UY": "Uruguay"}
ROTULOS = {"micotoxinas": "micotoxinas", "microbiologia": "microorganismos patógenos", "plaguicidas": "residuos de plaguicidas", "metales": "metales y contaminantes químicos",
           "fraude": "fraude o sustancias no autorizadas", "gmo": "organismos modificados no autorizados", "fisico": "cuerpos extraños", "veterinario": "residuos veterinarios",
           "conservacion": "conservación y cadena de frío", "otro": "otros"}
DIAS_VENCIDO = 5


def _f(s):
    return datetime.strptime(s, "%Y-%m-%d")


def indicios(ruta, hoy):
    """{zona: [indicio]}; todo va a «gen»: el origen es un país, no un tramo del río. `hoy` es un datetime."""
    if not ruta or not Path(ruta).exists():
        return {}
    d = json.load(open(ruta, encoding="utf-8"))
    try:
        if (hoy - datetime.strptime(d["obtenido"][:10], "%Y-%m-%d")).days > DIAS_VENCIDO:
            return {}
    except Exception:
        return {}
    n = d["notificaciones"]
    c90, c180, c365 = (hoy - timedelta(days=90)).strftime("%Y-%m-%d"), (hoy - timedelta(days=180)).strftime("%Y-%m-%d"), d["desde"]
    ult = [x for x in n if x["fecha"] >= c90]
    ant = [x for x in n if c180 <= x["fecha"] < c90]
    por_pais = Counter(o for x in ult for o in x["origen"])
    por_pel = Counter(x["peligro"] for x in ult)
    rechazos = sum(1 for x in ult if "border rejection" in (x.get("clasificacion") or ""))
    graves = sum(1 for x in ult if (x.get("riesgo") or "").strip().lower() == "serious")
    partes = ["%s %d" % (PAISES[k], v) for k, v in por_pais.most_common()]
    pel = ["%s %d" % (ROTULOS[k], v) for k, v in por_pel.most_common(4)]
    reciente = ult[0] if ult else None
    texto = ("En los últimos 90 días la Comisión Europea registró %d notificaciones de alimentos y piensos con origen en países del corredor (%s)%s: %d fueron rechazos en la frontera de la UE y %d se calificaron de riesgo serio. "
             "Peligros más frecuentes: %s. En los 90 días anteriores hubo %d, y en los últimos 12 meses %d.%s"
             % (len(ult), "; ".join(partes) or "ninguno", "" if ult else " (sin notificaciones)", rechazos, graves, "; ".join(pel) or "sin datos", len(ant), len([x for x in n if x["fecha"] >= c365]),
                (" La más reciente (%s/%s): «%s»." % (reciente["fecha"][8:10], reciente["fecha"][5:7], reciente["asunto"][:140])) if reciente else ""))
    return {"gen": [{"id": "RAS", "tipo": "Adulteración y contaminación", "titulo": "Alertas de la UE por contaminación o adulteración de alimentos del corredor (RASFF)",
                     "texto": texto, "fuentes": [FUENTE], "nivel": "Fuente única",
                     "no_dice": "Cada notificación es una detección de una autoridad de un país de la UE sobre un producto de origen en Argentina, Brasil, Paraguay, Bolivia o Uruguay. NO prueba que la contaminación ocurriera "
                                "durante el transporte por el río (casi siempre nace en el campo, el acopio o la planta), ni que el producto viajara por la hidrovía, y no nombra empresas. Sólo mide lo que la UE detecta: "
                                "no cubre lo que se vende dentro de la región ni los combustibles, minerales o fertilizantes. El tipo de peligro se clasifica con palabras clave sobre un texto libre y puede equivocarse.",
                     "dato": {"ultimos_90_dias": len(ult), "anteriores_90_dias": len(ant), "ultimos_12_meses": len([x for x in n if x["fecha"] >= c365]), "rechazos_frontera_90": rechazos,
                              "por_pais_90": dict(por_pais), "por_peligro_90": dict(por_pel)}}]}
