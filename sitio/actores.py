"""Registro de actores del corredor: quién es cada uno, qué se sabe con qué fuentes y qué nivel de evidencia, qué NO se sabe, y qué rastros
suyos mide Ysyry (titulares detectados, rutas de flujos de SIWA, unidades visibles por AIS, infraestructura de OpenStreetMap).

Un actor no es un acusado. El registro dice lo que las fuentes dicen, rotulado como atribución cuando lo es, y deja a la vista lo que no se
sabe. Nada acá atribuye un hecho a una persona. El nivel de evidencia de cada afirmación lo calcula la misma regla del libro de indicios."""
import html
import json
import re
import unicodedata
from pathlib import Path

import indicios as _ind
import pulso as _pulso


def norm(s):
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()).split())


def cargar(ruta):
    return json.load(open(ruta, encoding="utf-8"))["actores"] if Path(ruta).exists() else []


def vincular(actores, eventos, rutas, ais_fuerza):
    """Por actor: titulares del escáner que lo nombran, rutas de SIWA que lo nombran y unidades visibles por AIS."""
    out = {}
    for a in actores:
        rx = [re.compile(r) for r in a.get("alias", [])]
        evs = [e for e in eventos if any(r.search(norm(e["titulo"])) for r in rx)] if rx else []
        rts = [r for r in rutas if any(x.search(norm(r["nombre"] + " " + r.get("nota", "") + " " + r.get("fuente", ""))) for x in rx)] if rx else []
        ais = []
        if a.get("ais_fuerza"):
            for fuerza, nombres in ais_fuerza.items():
                if fuerza.startswith(a["ais_fuerza"]):
                    ais += nombres
        out[a["id"]] = {"eventos": evs, "rutas": rts, "ais": sorted(set(ais))}
    return out


def operadores_osm(ruta):
    """Operadores que figuran en OpenStreetMap en puertos, muelles y amarraderos: nombre, cantidad de puntos, zonas y ejemplos."""
    if not Path(ruta).exists():
        return []
    d = json.load(open(ruta, encoding="utf-8"))
    por = {}
    for a in d.get("items", []):
        op = ((a.get("x") or {}).get("operator") or "").strip()
        if not op:
            continue
        o = por.setdefault(op, {"operador": op, "n": 0, "zonas": set(), "ejemplos": []})
        o["n"] += 1
        o["zonas"].add(_pulso.zona_de(_pulso.AX * a["lon"] + _pulso.BX, _pulso.AY * a["lat"] + _pulso.BY))
        if a.get("n") and len(o["ejemplos"]) < 3:
            o["ejemplos"].append(a["n"])
    return sorted(por.values(), key=lambda o: (-o["n"], o["operador"])), d.get("fecha", "")


def tabla_html(actores, vinc, ops, fecha_ops, fecha):
    e = html.escape
    nombre_zona = {z[0]: z[1] for z in _pulso.ZONAS}
    tipos = []
    for a in actores:
        if a["tipo"] not in tipos:
            tipos.append(a["tipo"])
    bloques = []
    for tipo in tipos:
        det = []
        for a in [x for x in actores if x["tipo"] == tipo]:
            v = vinc.get(a["id"], {"eventos": [], "rutas": [], "ais": []})
            afs = []
            for af in a["afirmaciones"]:
                nivel = _ind.nivel_evidencia(af["fuentes"])
                fu = "; ".join("%s (%s)" % (x["nombre"], x["familia"]) for x in af["fuentes"])
                afs.append('<li><span class="ev ev-%s">%s</span> %s<br><small>Fuentes: %s</small></li>' % (e(nivel.split()[0].lower()), e(nivel), e(af["texto"]), e(fu)))
            rastros = []
            if v["eventos"]:
                rastros.append("%d titulares detectados por el escáner en 14 días lo nombran (ver «Hechos detectados»)" % len(v["eventos"]))
            if v["rutas"]:
                rastros.append("%d rutas de flujos de SIWA lo nombran: %s" % (len(v["rutas"]), "; ".join(r["id"] for r in v["rutas"][:6])))
            if v["ais"]:
                rastros.append("%d unidades visibles hoy por AIS: %s" % (len(v["ais"]), ", ".join(v["ais"][:8])))
            if not rastros:
                rastros.append("Ningún rastro propio hoy en los datos que lee Ysyry")
            zonas = ", ".join(nombre_zona.get(z, z) for z in a.get("zonas", []))
            nsi = "".join("<li>%s</li>" % e(x) for x in a["no_se_sabe"])
            det.append('<details class="actor"><summary><b>%s</b> <span class="gris">%s</span></summary><p>%s</p><ul class="afirm">%s</ul>'
                       '<p class="sub"><b>Rastros que mide Ysyry:</b> %s.</p><p class="sub"><b>Lo que no se sabe:</b></p><ul>%s</ul></details>'
                       % (e(a["nombre"]), e(zonas), e(a["resumen"]), "".join(afs), e("; ".join(rastros)), nsi))
        bloques.append("<h3>%s</h3>%s" % (e(tipo), "".join(det)))
    infra = ""
    if ops:
        filas = "".join("<tr><td>%s</td><td>%d</td><td>%s</td><td>%s</td></tr>" % (e(o["operador"]), o["n"], e(", ".join(nombre_zona.get(z, z) for z in sorted(o["zonas"]))), e("; ".join(o["ejemplos"]) or "—")) for o in ops[:25])
        infra = ('<h3>Operadores de puertos, muelles y amarraderos según OpenStreetMap</h3>'
                 '<p class="sub">Empresas y organismos que figuran como operadores en %d puntos del mapa. Es un aporte colaborativo (© colaboradores de OpenStreetMap, ODbL, instantánea del %s): puede estar incompleto o desactualizado, y que alguien figure no dice que opere hoy ni nada sobre su conducta.</p>'
                 '<div class="tabla-pulso"><table><thead><tr><th>Operador</th><th>Puntos</th><th>Tramo</th><th>Ejemplos</th></tr></thead><tbody>%s</tbody></table></div>' % (sum(o["n"] for o in ops), e(fecha_ops), filas))
    return ('<div class="pulso" id="actores"><h2>Actores del corredor</h2>'
            '<p class="sub">Quién es cada uno, qué se sabe y con qué fuentes, qué nivel de evidencia tiene cada afirmación y <b>qué no se sabe</b>, junto con los rastros propios que mide Ysyry (titulares detectados, rutas de SIWA, unidades visibles por AIS). '
            '<b>Un actor no es un acusado:</b> el registro repite lo que las fuentes dicen, rotulado como atribución cuando lo es, y nada de esto atribuye un hecho a una persona. El nivel de evidencia sigue la regla del libro de indicios.</p>%s%s'
            '<p class="sub">Registro curado por la Oficina a partir de las fuentes citadas. Consultado el %s (UTC).</p></div>' % ("".join(bloques), infra, e(fecha)))
