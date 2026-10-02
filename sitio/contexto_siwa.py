"""Contexto por provincia/departamento para las fichas de puertos, ciudades y zonas, tomado de los datos
abiertos de SIWA (Fundación Sherman Kent, CC BY 4.0): homicidios oficiales, violencia política (ACLED) y
focos de calor (NASA FIRMS). Se baja al construir la página; si SIWA no responde se usa la copia fechada
de sitio/datos/siwa/. Son recuentos por unidad de primer orden, no tasas, y SIWA los rotula prototipo.
"""
import json
import unicodedata
import urllib.request
from pathlib import Path

BASE = "https://siwa.fundacionkent.org/datos/publico/"
ARCHIVOS = {"homicidios": "subnacional_homicidios.json", "acled": "subnacional_acled.json", "focos": "subnacional_focos.json"}
SIGLA_BR = {"mato grosso do sul": "MS", "mato grosso": "MT", "parana": "PR"}


def norm(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


def cargar(carpeta_copia):
    """Devuelve {clave: {"datos": json, "en_vivo": bool}}; la copia local cubre la falta de red."""
    out = {}
    for clave, archivo in ARCHIVOS.items():
        d, vivo = None, False
        try:
            req = urllib.request.Request(BASE + archivo, headers={"User-Agent": "Ysyry-FUSK/1.0 (+https://fundacion-sherman-kent.github.io/ysyry/)"})
            with urllib.request.urlopen(req, timeout=40) as r:
                d = json.loads(r.read().decode("utf-8"))
            assert isinstance(d.get("registros"), list)
            vivo = True
        except Exception as e:
            print("SIWA %s no respondió (%s): se usa la copia fechada" % (archivo, str(e)[:60]))
            p = Path(carpeta_copia) / archivo
            d = json.load(open(p, encoding="utf-8")) if p.exists() else None
        if d:
            out[clave] = {"datos": d, "en_vivo": vivo}
    return out


def _unidad(d, iso, nombre, br_sigla=False):
    buscado = norm(nombre)
    if br_sigla:
        buscado = SIGLA_BR.get(buscado, buscado)
    for r in d["registros"]:
        if r.get("iso") != iso:
            continue
        for u in r["unidades"]:
            if norm(u["nombre"]) == norm(buscado):
                return u
    return None


def lineas(fuentes, iso, nombre):
    """Líneas de texto para la ficha de una unidad; vacío si SIWA no trae nada de ella."""
    res = []
    if "homicidios" in fuentes:
        u = _unidad(fuentes["homicidios"]["datos"], iso, nombre, br_sigla=(iso == "BRA"))
        if u and u.get("ultimo"):
            res.append("Homicidios %s en %s: %s (recuento de la fuente oficial, no tasa; no comparable entre países)"
                       % (u["ultimo"]["anio"], nombre, format(u["ultimo"]["valor"], ",").replace(",", ".")))
    if "acled" in fuentes:
        u = _unidad(fuentes["acled"]["datos"], iso, nombre)
        if u:
            ult = u.get("ultimo")
            if ult:
                res.append("Violencia política según ACLED, %s: %s %s y %s %s (base secundaria sobre prensa y fuentes locales, no oficial)"
                           % (ult["anio"], ult["eventos"], "evento" if ult["eventos"] == 1 else "eventos", ult["victimas"], "víctima" if ult["victimas"] == 1 else "víctimas"))
            elif u.get("serie"):
                res.append("Violencia política según ACLED: sin eventos en el último año; el más reciente es de %s (base secundaria, no oficial)"
                           % max(s["anio"] for s in u["serie"]))
    if "focos" in fuentes:
        d = fuentes["focos"]["datos"]
        if any(r.get("iso") == iso for r in d["registros"]):
            u = _unidad(d, iso, nombre)
            dias = (d.get("resumen") or {}).get("ventana_dias", "pocos")
            if u:
                res.append("Focos de calor (NASA FIRMS), últimos %s días: %s en %s (anomalía térmica detectada por satélite; no es un incendio confirmado)"
                           % (dias, u["focos"], nombre))
            else:
                res.append("Focos de calor (NASA FIRMS), últimos %s días: sin dato de %s en el conjunto de SIWA (no equivale a cero focos)" % (dias, nombre))
    return res


def pie(fuentes):
    fechas = sorted({(f["datos"].get("procedencia") or {}).get("obtenido_en", "")[:10] for f in fuentes.values()} - {""})
    vivo = all(f["en_vivo"] for f in fuentes.values())
    return ("Contexto por unidad: SIWA, Fundación Sherman Kent (CC BY 4.0), prototipo; datos de base de los organismos oficiales de cada Estado, "
            "ACLED (atribución) y NASA FIRMS · consultado el %s%s" % (", ".join(fechas), "" if vivo else " (copia fechada: SIWA no respondió)"))


# provincias, departamentos y estados que tocan cada tramo del pulso (juicio de la Fundación sobre el mapa, no un límite
# administrativo: un tramo puede tocar parte de una unidad y la cifra es la de toda la unidad). Quedan fuera Mato Grosso do Sul
# y Paraná (Brasil), por decisión del director del 2/10/2026: son estados enormes que tocan el corredor de costado y dominaban la suma)
UNIDADES_POR_ZONA = {
    "z1": [("ARG", "Buenos Aires"), ("ARG", "Ciudad Autónoma de Buenos Aires"), ("ARG", "Entre Ríos"), ("URY", "Colonia"), ("URY", "Soriano"), ("URY", "Montevideo")],
    "z2": [("ARG", "Santa Fe"), ("ARG", "Buenos Aires")],
    "z3": [("ARG", "Santa Fe"), ("ARG", "Entre Ríos"), ("ARG", "Corrientes"), ("ARG", "Chaco")],
    "z4": [("ARG", "Misiones"), ("PRY", "Alto Paraná"), ("PRY", "Canindeyú"), ("PRY", "Itapúa"), ("PRY", "Misiones")],
    "z5": [("PRY", "Asunción"), ("PRY", "Central"), ("PRY", "Presidente Hayes"), ("PRY", "Concepción"), ("PRY", "Alto Paraguay"), ("PRY", "Ñeembucú"), ("ARG", "Formosa")],
}


def resumen_unidades(fuentes, unidades):
    """ACLED (último año del conjunto) y focos de calor sumados sobre las unidades dadas. Distingue «cero» de «sin dato»."""
    r = {"unidades": len(unidades), "acled": None, "focos": None}
    if "acled" in fuentes:
        d = fuentes["acled"]["datos"]
        anio = max((u["ultimo"]["anio"] for reg in d["registros"] for u in reg["unidades"] if u.get("ultimo")), default=None)
        ev = vi = con_dato = 0
        for iso, nombre in unidades:
            u = _unidad(d, iso, nombre)
            if u is None:
                continue
            con_dato += 1
            if u.get("ultimo") and u["ultimo"]["anio"] == anio:
                ev += u["ultimo"]["eventos"]
                vi += u["ultimo"]["victimas"]
        r["acled"] = {"anio": anio, "eventos": ev, "victimas": vi, "con_dato": con_dato}
    if "focos" in fuentes:
        d = fuentes["focos"]["datos"]
        total = con_dato = 0
        for iso, nombre in unidades:
            if not any(reg.get("iso") == iso for reg in d["registros"]):
                continue
            u = _unidad(d, iso, nombre)
            if u is not None:
                con_dato += 1
                total += u["focos"]
        r["focos"] = {"dias": (d.get("resumen") or {}).get("ventana_dias", "pocos"), "total": total, "con_dato": con_dato}
    return r
