"""Tabla curada de restricciones de calado (sitio/datos/calados.json). La mantiene la dirección a mano; no se actualiza sola.
Cada fila nace «por verificar» y sólo pasa a «verificado» cuando alguien leyó la norma original y anotó quién y cuándo."""
import html
import json
from pathlib import Path


def _fecha(s):
    return "sin fecha" if not s else "%s/%s/%s" % (s[8:10], s[5:7], s[:4])


def bloque_html(ruta):
    if not ruta or not Path(ruta).exists():
        return ""
    d = json.load(open(ruta, encoding="utf-8"))
    e = html.escape
    filas = []
    for x in d["entradas"]:
        ok = x["estado"] == "verificado"
        estado = ('<span class="ev ev-fuerte">Verificado</span><br><small>por %s el %s%s</small>' % (e(x.get("verificado_por") or "—"), _fecha(x.get("verificado_el")),
                  (' · <a href="%s" target="_blank" rel="noopener nofollow">norma ↗</a>' % e(x["norma_url"])) if x.get("norma_url") else "")) if ok \
            else '<span class="ev ev-fuente">Por verificar</span>'
        filas.append('<tr><th scope="row">%s<br><small>%s</small></th><td>%s</td><td><b>%s</b><br>%s<br><small>%s</small></td><td>%s<br><a href="%s" target="_blank" rel="noopener nofollow">%s ↗</a></td><td>%s</td><td>%s</td></tr>'
                     % (e(x["tramo"]), e(x["pais"] + " · " + x["rio"]), e(x["calado"]), e(x["organismo"]), e(x["norma"]), "", _fecha(x.get("fecha_fuente")),
                        e(x["fuente_url"]), e(x["fuente_nombre"]), estado, e(x["falta_verificar"])))
    return ('<div class="pulso" id="calados"><h2>%s</h2>'
            '<p class="sub"><b>%s</b></p>'
            '<div class="tabla-pulso"><table><thead><tr><th>Tramo</th><th>Calado máximo según la fuente</th><th>Organismo y norma</th><th>Fecha y fuente</th><th>Estado</th><th>Qué falta verificar</th></tr></thead><tbody>%s</tbody></table></div>'
            '<p class="sub">Tabla curada por la dirección, no automática. Última revisión: %s. Cómo verificar una fila: %s</p></div>'
            % (e(d["titulo"]), e(d["aviso"]), "".join(filas), _fecha(d["ultima_revision"]), e(d["como_verificar"])))
