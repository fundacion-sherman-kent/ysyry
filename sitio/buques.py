"""Clasificación de buques por lo que transmiten por AIS. La usan la página horaria (construir.py) y la capa viva (colectores/vivo.py):
un solo lugar para que una embarcación del Estado se vea igual en las dos."""
import re as _re

# Categoría de buque por el código numérico de tipo AIS (ITU-R M.1371 §3.3.2):
# 3x pesca/remolque/buceo, 5x servicios de puerto, 6x pasajeros, 7x carga, 8x tanque.
def categoria_ais(tipo):
    if tipo is None: return ("desconocido", "#ffd400")
    t = int(tipo)
    if 30 <= t < 40: return ("pesca/remolque", "#8fd9c4")
    if 50 <= t < 60: return ("servicio portuario", "#dfe6e9")
    if 60 <= t < 70: return ("pasajeros", "#b8f06a")
    if 70 <= t < 80: return ("carga", "#ffd400")
    if 80 <= t < 90: return ("tanque", "#ff8a5c")
    return ("otro/sin clasificar", "#9aa7ad")


RE_ESTADO = _re.compile(r"^(ARA|GC)[\s\-]")
# Paraguay: la Armada Paraguaya designa sus unidades con prefijo ARP (p. ej. ARP P-05
# «Itaipú») y la Prefectura General Naval con PGN; las lanchas patrulleras rápidas
# se llaman LP-101, LP-102... (armadaparaguaya.mil.py y es.wikipedia.org/wiki/Armada_Paraguaya,
# 2/10/2026). El nombre solo NO alcanza —«Itaipú» o «Humaitá» también son remolcadores
# civiles—, por eso se exige el prefijo, y LP sólo con bandera paraguaya.
RE_ESTADO_PY = _re.compile(r"^(ARP|PGN)[\s\-]")
RE_LP_PY = _re.compile(r"^LP[\s\-]?\d{2,3}$")


def es_estado_py(p):
    n = (p.get("nombre") or "").strip().upper()
    return bool(RE_ESTADO_PY.match(n)) or (p.get("bandera") == "PY" and bool(RE_LP_PY.match(n)))


def es_estado(p):
    n = (p.get("nombre") or "").strip().upper()
    return p.get("tipo_ais") in (35, 55) or bool(RE_ESTADO.match(n)) or es_estado_py(p)
