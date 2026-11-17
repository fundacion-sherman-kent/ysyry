"""Represas del Paraná en la página: marcadores de Itaipú y de Yacyretá con su ficha, y un indicador en la zona del Alto Paraná.
Itaipú, Jupiá y Porto Primavera vienen de los datos abiertos del ONS (colectores/represas_ons.py); Yacyretá, del Reporte hidrometeorológico diario de la
Subsecretaría de Recursos Hídricos de Argentina (colectores/reporte_sala_ar.py), que también da el caudal de Itaipú.
Ninguna es una medición independiente: los caudales de las represas son datos de sus operadores. Por eso cada ficha se rotula «fuente única» y el reporte de
Argentina no cuenta como segunda fuente del ONS. Dibuja sólo Itaipú y Yacyretá: Jupiá y Porto Primavera quedan fuera del recuadro del mapa."""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import indicios as _ind
import pulso as _pulso

FUENTE_ONS = {"nombre": "ONS (Operador Nacional do Sistema Elétrico, Brasil), datos abiertos", "familia": "oficial", "calificacion": "A2", "url": "https://dados.ons.org.br/"}
FUENTE_SSRH = {"nombre": "Subsecretaría de Recursos Hídricos de Argentina, Reporte hidrometeorológico diario", "familia": "oficial", "calificacion": "A2", "url": "https://hidraulica.gob.ar/"}
DIAS_VENCIDA = 3          # el ONS se renueva cada hora
DIAS_VENCIDA_REPORTE = 5  # el reporte sale los días hábiles: un fin de semana largo no lo vence
YACYRETA = ("Yacyretá", -27.4806, -56.7236)


def _n(x):
    return "{:,.0f}".format(x).replace(",", ".")


def _c(x):
    return ("%.2f" % x).replace(".", ",")


def _dia(s):
    return s[8:10] + "/" + s[5:7]


def _fecha(s):
    return datetime.strptime(s[:10], "%Y-%m-%d").date()


def _con_pos(p, lat, lon, segs_rio):
    x, y = _pulso.AX * lon + _pulso.BX, _pulso.AY * lat + _pulso.BY
    (x2, y2), dist = _ind._al_rio(x, y, segs_rio)
    p["pos"] = {"x": x2, "y": y2, "zona": _pulso.zona_de(x2, y2), "ajustada": 0.05 < dist <= _ind.AJUSTE_MAX_UNIDADES}


def _fila(rep, nombre):
    return next((c for c in (rep or {}).get("caudales", []) if c["estacion"] == nombre), None)


def cargar(ruta_ons, ruta_reporte, segs_rio, hoy):
    """Lista de presas: las del ONS más Yacyretá (del reporte de Argentina). Sólo Itaipú y Yacyretá llevan posición dibujable. Cada archivo falta o vence por separado."""
    out, rep = [], None
    if ruta_reporte and Path(ruta_reporte).exists():
        try:
            rep = json.load(open(ruta_reporte, encoding="utf-8"))
            if (hoy - _fecha(rep["fecha_reporte"])).days > DIAS_VENCIDA_REPORTE:
                rep = None
        except Exception:
            rep = None
    if ruta_ons and Path(ruta_ons).exists():
        d = json.load(open(ruta_ons, encoding="utf-8"))
        try:
            edad = (hoy - _fecha(d["obtenido"])).days
        except Exception:
            edad = 999
        if edad <= DIAS_VENCIDA:
            for r in d["represas"]:
                p = dict(r, estado="represa", red="ons", fuente="ons", reporte=_fila(rep, "Represa Itaipú") if r["clave"] == "ITAIPU" else None, fecha_reporte=(rep or {}).get("fecha_reporte"),
                         texto_reporte=(rep or {}).get("texto_itaipu") if r["clave"] == "ITAIPU" else None, pos=None)
                if r["clave"] == "ITAIPU":
                    _con_pos(p, r["lat"], r["lon"], segs_rio)
                out.append(p)
    if rep:
        af, ef = _fila(rep, "Yacyretá afluente"), _fila(rep, "Yacyretá efluente")
        if af and ef:
            y = {"clave": "YACYRETA", "nombre": YACYRETA[0], "lat": YACYRETA[1], "lon": YACYRETA[2], "estado": "represa", "red": "ssrh", "fuente": "ssrh", "afluente": af, "efluente": ef,
                 "fecha_reporte": rep["fecha_reporte"], "texto": rep.get("texto_yacyreta"), "pdf": rep.get("pdf"), "pos": None}
            _con_pos(y, y["lat"], y["lon"], segs_rio)
            out.append(y)
    return out


def _vertido_hace_una_semana(p):
    s = p.get("serie_diaria") or []
    return s[-7] if len(s) >= 7 else None


def _info_yacyreta(i, p):
    af, ef = p["afluente"], p["efluente"]
    t = ["Caudal afluente %s m³/s (%s) y efluente %s m³/s (%s), según el reporte del %s" % (_n(af["caudal_m3s"]), af["tendencia"], _n(ef["caudal_m3s"]), ef["tendencia"], _dia(p["fecha_reporte"]) + "/" + p["fecha_reporte"][:4]),
         "Caudal de alerta %s m³/s y de evacuación %s m³/s%s" % (_n(ef["alerta_m3s"]), _n(ef["evacuacion_m3s"]), (": el efluente " + ("supera la alerta" if ef["caudal_m3s"] >= ef["alerta_m3s"] else "está por debajo de la alerta")) if ef.get("alerta_m3s") else ""),
         "Perspectiva del reporte: %s" % (ef.get("perspectiva") or "sin dato")]
    ctx = ["Evidencia: Fuente única (Subsecretaría de Recursos Hídricos de Argentina). El caudal de la represa lo informa su operador, la Entidad Binacional Yacyretá: no es una medición independiente."]
    if p.get("texto"):
        ctx.append("Pronóstico del reporte (resumen textual del PDF): " + p["texto"])
    ctx.append("Lo que no dice: no trae la cota del embalse (la publica aparte la Entidad Binacional Yacyretá en un PDF) ni es el nivel del río en Ituzaingó o Ayolas. El reporte sale los días hábiles: puede tener hasta unos días.")
    return {"id": "es%d" % i, "categoria": "Represa · caudales (Argentina)", "titulo": "Yacyretá · caudales", "tipo": " · ".join(t),
            "fuente": "Subsecretaría de Recursos Hídricos de Argentina, Reporte hidrometeorológico diario del %s · fuente única" % p["fecha_reporte"], "clase": "estacion", "coord": "%.4f, %.4f" % (p["lat"], p["lon"]),
            "foto": None, "ctx": ctx, "ctx_t": "Indicio y su evidencia", "ctx_f": "Se publican las cifras tal como las informa el reporte."}


def info_represa(i, p):
    if p["clave"] == "YACYRETA":
        return _info_yacyreta(i, p)
    t = ["Embalse en cota %s m (lectura de las %s, hora de Brasilia)" % (_c(p["cota_m"]), p["hora_brasilia"][11:16])]
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
    ctx = ["Evidencia: Fuente única (ONS, datos abiertos). Es el dato del propio operador del sistema eléctrico, no una medición independiente: no hay una segunda fuente que lo corrobore."]
    if p.get("reporte"):
        r = p["reporte"]
        ctx.append("Contraste: el Reporte de la Subsecretaría de Recursos Hídricos de Argentina del %s da %s m³/s de erogación (%s)%s. Coincide con el ONS, pero probablemente toma el dato del mismo operador, por eso no cuenta como segunda fuente."
                   % (_dia(p["fecha_reporte"]) + "/" + p["fecha_reporte"][:4], _n(r["caudal_m3s"]), r["tendencia"], (" y describe el vertido como en gradual disminución para el control del nivel del embalse" if p.get("texto_reporte") and "vertidos" in p["texto_reporte"] else "")))
    ctx.append("Qué significa: lo que Itaipú vierte se suma al caudal del Paraná aguas abajo (Ciudad del Este, Foz do Iguaçu, Posadas...). El vertedero se abre cuando el embalse llega a su cota máxima operativa y no alcanza con turbinar.")
    ctx.append("Lo que no dice: no es el nivel del río en Ciudad del Este ni una alerta de inundación.")
    return {"id": "es%d" % i, "categoria": "Represa · operación (ONS)", "titulo": "Itaipú · embalse y caudales", "tipo": " · ".join(t),
            "fuente": "ONS (Operador Nacional do Sistema Elétrico, Brasil), datos abiertos CC BY 4.0, lectura de las %s (hora de Brasilia) · fuente única" % p["hora_brasilia"],
            "clase": "estacion", "coord": "%.4f, %.4f" % (p["lat"], p["lon"]), "foto": None, "ctx": ctx, "ctx_t": "Indicio y su evidencia", "ctx_f": "Se publican las lecturas tal como las informa el operador."}


def indicios(presas):
    """{zona: [indicio]} para el Alto Paraná (z4), donde están Itaipú y Yacyretá."""
    ita = next((p for p in presas if p["clave"] == "ITAIPU"), None)
    yac = next((p for p in presas if p["clave"] == "YACYRETA"), None)
    if not ita and not yac:
        return {}
    partes, fuentes = [], []
    if ita:
        fuentes.append(FUENTE_ONS)
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
            if p["clave"] not in ("ITAIPU", "YACYRETA") and p.get("defluente_m3s") is not None:
                partes.append("%s: %s m³/s, %s" % (p["nombre"], _n(p["defluente_m3s"]), ("vertiendo %s m³/s" % _n(p["vertida_m3s"])) if p.get("vertida_m3s") else "sin vertido"))
    if yac:
        fuentes.append(FUENTE_SSRH)
        ef = yac["efluente"]
        partes.append("Yacyretá (reporte de Argentina del %s): afluente %s y efluente %s m³/s, en %s, con la alerta en %s m³/s" % (_dia(yac["fecha_reporte"]) + "/" + yac["fecha_reporte"][:4], _n(yac["afluente"]["caudal_m3s"]), _n(ef["caudal_m3s"]), {"baja": "descenso", "sube": "ascenso", "estable": "estabilidad"}[ef["tendencia"]], _n(ef["alerta_m3s"])))
    z = ((ita or yac)["pos"] or {}).get("zona", "z4")
    return {z: [{"id": "REP", "tipo": "Represas", "titulo": "Itaipú, Yacyretá y las represas del Paraná", "texto": "; ".join(partes) + ".", "fuentes": fuentes, "nivel": _ind.nivel_evidencia([f for f in fuentes[:1]]),
                 "no_dice": "Los caudales de las represas son datos de sus operadores, no mediciones independientes: el reporte de Argentina probablemente reproduce los del ONS y de la Entidad Binacional Yacyretá, por eso el nivel de evidencia sigue siendo el de una sola fuente. No es el nivel del río aguas abajo ni una alerta. Lo que las represas vierten o erogan se suma al caudal del Paraná en Ciudad del Este, Foz do Iguaçu y Corrientes.",
                 "dato": {"vertida_m3s": (ita or {}).get("vertida_m3s"), "defluente_m3s": (ita or {}).get("defluente_m3s"), "yacyreta_efluente_m3s": (yac or {}).get("efluente", {}).get("caudal_m3s")}}]}
