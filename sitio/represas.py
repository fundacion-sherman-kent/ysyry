"""Represas del Paraná (ONS) en la página: un marcador de Itaipú con su ficha, y un indicador en la zona del Alto Paraná con Itaipú, Jupiá y Porto Primavera.
Los datos los baja colectores/represas_ons.py (datos abiertos del ONS, Brasil). Es el dato del operador del sistema: fuente única, no una medición independiente.
Sólo Itaipú se dibuja en el mapa: Jupiá y Porto Primavera quedan fuera del recuadro del corredor y entran sólo en el indicador."""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import indicios as _ind
import pulso as _pulso

FUENTE_ONS = {"nombre": "ONS (Operador Nacional do Sistema Elétrico, Brasil), datos abiertos", "familia": "oficial", "calificacion": "A2", "url": "https://dados.ons.org.br/"}
DIAS_VENCIDA = 3


def _n(x):
    """Número con punto de miles: 15252 -> 15.252"""
    return "{:,.0f}".format(x).replace(",", ".")


def _c(x):
    return ("%.2f" % x).replace(".", ",")


def _dia(s):
    return s[8:10] + "/" + s[5:7]


def cargar(ruta, segs_rio, hoy):
    """Lista de presas con su lectura más reciente; [] si no hay archivo o es viejo. Sólo Itaipú lleva posición dibujable."""
    if not ruta or not Path(ruta).exists():
        return []
    d = json.load(open(ruta, encoding="utf-8"))
    try:
        edad = (hoy - datetime.strptime(d["obtenido"][:10], "%Y-%m-%d").date()).days
    except Exception:
        return []
    if edad > DIAS_VENCIDA:
        return []
    out = []
    for r in d["represas"]:
        p = dict(r, estado="represa", red="ons", edad=edad, pos=None)
        if r["clave"] == "ITAIPU":
            x, y = _pulso.AX * r["lon"] + _pulso.BX, _pulso.AY * r["lat"] + _pulso.BY
            (x2, y2), dist = _ind._al_rio(x, y, segs_rio)
            p["pos"] = {"x": x2, "y": y2, "zona": _pulso.zona_de(x2, y2), "ajustada": 0.05 < dist <= _ind.AJUSTE_MAX_UNIDADES}
        out.append(p)
    return out


def _vertido_hace_una_semana(p):
    s = p.get("serie_diaria") or []
    return s[-7] if len(s) >= 7 else None


def info_represa(i, p):
    t = []
    t.append(("Embalse en cota %s m (lectura de las %s, hora de Brasilia)" % (_c(p["cota_m"]), p["hora_brasilia"][11:16])))
    if p.get("defluente_m3s") is not None:
        if p.get("vertida_m3s", 0) and p["vertida_m3s"] > 0:
            t.append("Caudal defluente %s m³/s: %s turbinados y %s vertidos sin turbinar, es decir, con el vertedero abierto" % (_n(p["defluente_m3s"]), _n(p["turbinada_m3s"]), _n(p["vertida_m3s"])))
        else:
            t.append("Caudal defluente %s m³/s, todo turbinado: sin vertido" % _n(p["defluente_m3s"]))
    if p.get("cota_jusante_m") is not None:
        t.append("Nivel aguas abajo de la presa %s m" % _c(p["cota_jusante_m"]))
    s = p.get("serie_diaria") or []
    if len(s) >= 2 and s[0].get("vertida_m3s") is not None:
        t.append("Vertido medio diario: " + ", ".join("%s (%s)" % (_n(x["vertida_m3s"]), _dia(x["dia"])) for x in s[-7:] if x.get("vertida_m3s") is not None) + " m³/s")
    ctx = ["Evidencia: Fuente única (ONS, datos abiertos). Es el dato del propio operador del sistema eléctrico, no una medición independiente: no hay una segunda fuente que lo corrobore.",
           "Qué significa: lo que Itaipú vierte se suma al caudal del Paraná aguas abajo (Ciudad del Este, Foz do Iguaçu, Posadas...). El vertedero se abre cuando el embalse llega a su cota máxima operativa y no alcanza con turbinar.",
           "Lo que no dice: no es el nivel del río en Ciudad del Este ni una alerta de inundación, y no incluye Yacyretá, más abajo, cuya operación no está en esta fuente."]
    return {"id": "es%d" % i, "categoria": "Represa · operación (ONS)", "titulo": "Itaipú · embalse y caudales", "tipo": " · ".join(t),
            "fuente": "ONS (Operador Nacional do Sistema Elétrico, Brasil), datos abiertos CC BY 4.0, lectura de las %s (hora de Brasilia) · fuente única" % p["hora_brasilia"],
            "clase": "estacion", "coord": "%.4f, %.4f" % (p["lat"], p["lon"]), "foto": None, "ctx": ctx, "ctx_t": "Indicio y su evidencia",
            "ctx_f": "Se publican las lecturas tal como las informa el operador."}


def indicios(presas):
    """{zona: [indicio]} para el Alto Paraná (z4), donde está Itaipú."""
    ita = next((p for p in presas if p["clave"] == "ITAIPU"), None)
    if not ita:
        return {}
    partes = []
    if ita.get("defluente_m3s") is not None:
        if ita.get("vertida_m3s", 0) and ita["vertida_m3s"] > 0:
            frase = "Itaipú: embalse en %s m y caudal defluente de %s m³/s, de los que %s se vierten sin turbinar (vertedero abierto)" % (_c(ita["cota_m"]), _n(ita["defluente_m3s"]), _n(ita["vertida_m3s"]))
        else:
            frase = "Itaipú: embalse en %s m y caudal defluente de %s m³/s, todo turbinado (sin vertido)" % (_c(ita["cota_m"]), _n(ita["defluente_m3s"]))
        antes = _vertido_hace_una_semana(ita)
        if antes and antes.get("vertida_m3s") is not None and ita["serie_diaria"]:
            frase += "; el vertido medio diario fue de %s m³/s el %s y de %s m³/s el %s" % (_n(antes["vertida_m3s"]), _dia(antes["dia"]), _n(ita["serie_diaria"][-1]["vertida_m3s"]), _dia(ita["serie_diaria"][-1]["dia"]))
        partes.append(frase)
    for p in presas:
        if p["clave"] != "ITAIPU" and p.get("defluente_m3s") is not None:
            partes.append("%s: %s m³/s, %s" % (p["nombre"], _n(p["defluente_m3s"]), ("vertiendo %s m³/s" % _n(p["vertida_m3s"])) if p.get("vertida_m3s") else "sin vertido"))
    fuentes = [FUENTE_ONS]
    z = (ita["pos"] or {}).get("zona", "z4")
    return {z: [{"id": "REP", "tipo": "Represas", "titulo": "Itaipú y las represas del Paraná superior", "texto": "; ".join(partes) + ".", "fuentes": fuentes, "nivel": _ind.nivel_evidencia(fuentes),
                 "no_dice": "Es el dato del operador del sistema eléctrico (ONS), no una medición independiente. No es el nivel del río aguas abajo ni una alerta, y no incluye Yacyretá. Lo que Itaipú vierte se suma al caudal del Paraná en Ciudad del Este y Foz do Iguaçu.",
                 "dato": {"vertida_m3s": ita.get("vertida_m3s"), "defluente_m3s": ita.get("defluente_m3s"), "cota_m": ita.get("cota_m")}}]}
