"""Alertas tempranas de FEMÓNOE (Fundación Sherman Kent) que tocan a los cinco Estados del corredor o a la
Triple Frontera. FEMÓNOE todavía no publica un archivo de datos de sus alertas: se leen las páginas HTML
públicas al construir el sitio, así que si cambian de forma el bloque dice que no pudo consultar y no
afirma que no hay alertas. Ysyry no reescribe ningún juicio: muestra el enunciado, la probabilidad y el
vencimiento tal como FEMÓNOE los publica, y manda a su página.
"""
import html
import re
import urllib.request

BASE = "https://fundacion-sherman-kent.github.io/femonoe-sitio/"
CORREDOR = {"ARG": "Argentina", "BRA": "Brasil", "BOL": "Bolivia", "PRY": "Paraguay", "URY": "Uruguay"}
EJES = {"G": "gobernabilidad", "S": "seguridad", "I": "entorno informativo"}


def _bajar(ruta):
    req = urllib.request.Request(BASE + ruta, headers={"User-Agent": "Ysyry-FUSK/1.0 (+https://fundacion-sherman-kent.github.io/ysyry/)"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")


def _texto(fragmento):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragmento)).split())


def _alerta(ruta):
    t = _bajar(ruta)
    sello = re.search(r'<div class="sello">(.*?)</div>', t, re.S)
    enun = re.search(r"<h2>(.*?)</h2>", t, re.S)
    prob = re.search(r'aria-label="Probabilidad: ([^"]+)"', t)
    resumen = re.search(r'<p class="resumen">(.*?)</p>', t, re.S)
    if not (sello and enun and prob):
        raise ValueError("la página de la alerta cambió de forma")
    partes = [p.strip() for p in _texto(sello.group(1)).split("·")]
    estado = re.search(r"<b>(.*?)</b>", sello.group(1), re.S)
    return {"ruta": ruta, "estado": _texto(estado.group(1)).lower() if estado else "", "nacida": partes[-1],
            "enunciado": _texto(enun.group(1)), "probabilidad": html.unescape(prob.group(1)),
            "resumen": _texto(resumen.group(1)) if resumen else ""}


def consultar():
    """{"ok": bool, "alertas": [...], "total_vigentes": str|None, "error": str|None}"""
    try:
        idx = _bajar("index.html")
        rutas = sorted(set(re.findall(r'href="(alerta/\d{4}-\d{2}-\d{2}-([A-Z0-9]+)-([GSI])\.html)"', idx)))
        if not rutas:
            raise ValueError("el índice no lista alertas ni siquiera de otros Estados: no se puede distinguir 'ninguna' de 'cambió la página'")
        vig = re.search(r"Alertas vigentes</span>\s*<span class=\"cifra\">\s*(\d+)", idx)
        alertas = []
        for ruta, codigo, eje in rutas:
            zona = codigo not in CORREDOR and len(codigo) != 3   # una zona transfronteriza no lleva código de país
            if codigo not in CORREDOR and not (zona and "Triple Frontera" in _bajar(ruta)):
                continue
            a = _alerta(ruta)
            a.update(codigo=codigo, pais=CORREDOR.get(codigo, "Triple Frontera"), eje=EJES.get(eje, eje))
            alertas.append(a)
        return {"ok": True, "alertas": alertas, "total_vigentes": vig.group(1) if vig else None, "error": None, "listadas": len(rutas)}
    except Exception as e:
        print("FEMÓNOE no se pudo consultar: %s" % str(e)[:120])
        return {"ok": False, "alertas": [], "total_vigentes": None, "error": str(e)[:120], "listadas": 0}


def bloque_html(res, fecha):
    """HTML del bloque de la página; escapa todo lo que viene de afuera."""
    e = html.escape
    enlace = '<a href="%s">FEMÓNOE</a>' % BASE
    if not res["ok"]:
        cuerpo = "<p class=\"sub\">Hoy no pudimos consultar las alertas de %s, así que no afirmamos que no haya: miralas directamente en su sitio.</p>" % enlace
    else:
        vig = [a for a in res["alertas"] if a["estado"] == "vigente"]
        otras = [a for a in res["alertas"] if a["estado"] != "vigente"]
        if not vig:
            cuerpo = ("<p class=\"sub\">%s no tiene hoy alertas vigentes sobre los cinco Estados del corredor (Argentina, Brasil, Bolivia, Paraguay y Uruguay)%s. "
                      "Esto no significa que no pase nada: significa que su panel no anunció ningún hecho con fecha de vencimiento para ellos. "
                      "Su zona transfronteriza de la Triple Frontera (Argentina, Brasil y Paraguay) también está incluida en esta consulta.</p>"
                      % (enlace, "" if res["total_vigentes"] is None else " (hay %s vigentes en toda la región)" % e(res["total_vigentes"])))
        else:
            cuerpo = '<p class="sub">Alertas vigentes de %s que tocan al corredor, tal como las publica, con su probabilidad y su vencimiento:</p><ul class="alertas-fem">' % enlace
            for a in vig:
                cuerpo += ('<li><b>%s · %s</b> · nacida el %s<br>%s<br><span class="gris">Probabilidad: %s · %s</span> · <a href="%s">Leer el juicio y el disenso</a></li>'
                           % (e(a["pais"]), e(a["eje"]), e(a["nacida"]), e(a["enunciado"]), e(a["probabilidad"]), e(a["resumen"]), e(BASE + a["ruta"])))
            cuerpo += "</ul>"
        if otras:
            cuerpo += "<p class=\"sub\">%d más de estos Estados no están vigentes (por ejemplo, descartadas por el panel) y no se muestran.</p>" % len(otras)
    return ('<div class="prospectiva" id="alertas-femonoe"><h2>Alertas tempranas de FEMÓNOE sobre el corredor</h2>%s'
            '<p class="sub">Un juicio con probabilidad, plazo y criterio fijado de antemano; Ysyry no lo reescribe ni lo reinterpreta. Consultado el %s.</p></div>'
            % (cuerpo, e(fecha)))
