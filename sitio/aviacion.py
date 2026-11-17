"""Pistas de aterrizaje habilitadas (registradas) cerca del corredor, de sitio/datos/pistas.json (OurAirports, dominio público; lo genera sitio/herramientas/pistas.py).
Se dibujan chicas y sólo se ven al elegir la pestaña «Tráfico aéreo y pistas». Las CLANDESTINAS no figuran en ninguna base abierta y no se pueden mapear con datos abiertos: la página lo dice."""
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pulso as _pulso


def pistas_svg(ruta):
    if not ruta or not Path(ruta).exists():
        return "", 0
    d = json.load(open(ruta, encoding="utf-8"))
    e = html.escape
    out = []
    for a in d["pistas"]:
        x, y = _pulso.AX * a["lo"] + _pulso.BX, _pulso.AY * a["la"] + _pulso.BY
        out.append('<g class="pista pista-%s solo-aereo" data-familia="aereo" transform="translate(%.1f,%.1f)" data-id="%s" data-n="%s" data-t="%s" data-p="%s" data-m="%s" data-ft="%s" data-r="%d" data-f="%d" data-c="%.4f, %.4f">'
                   '<circle class="hit" r="7"/><circle class="pista-p" r="%s"/></g>'
                   % (a["t"], x, y, e(a["id"]), e(a["n"]), a["t"], a["p"], e(a["m"] or ""), a["ft"] if a["ft"] is not None else "", a["km_rio"], a["km_fr"], a["la"], a["lo"], "2.6" if a["t"] != "small_airport" else "1.8"))
    return "".join(out), len(d["pistas"])
