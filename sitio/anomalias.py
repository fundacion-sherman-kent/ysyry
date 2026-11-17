"""Anomalías de identidad en el AIS: un IMO distinto para el mismo MMSI, el mismo IMO en dos MMSI a la vez, nombres o indicativos que cambian.
Se calculan sobre el registro de identidades (colectores/identidades_ais.py), que guarda lo que cada equipo transmitió y cuándo.

Qué es y qué no es: son INCONSISTENCIAS de lo transmitido, no pruebas de nada. Un capitán que carga mal el nombre, un equipo reconfigurado, un buque que cambia de bandera
o de nombre legalmente producen las mismas señales que una falsificación. Por eso la página pública sólo muestra CONTEOS por zona, nunca nombres de buques; el detalle
con nombres va a un informe privado para quien cura (colectores/anomalias_semana.py), y cada hallazgo sigue siendo un indicio, no una acusación.

Reglas (cada valor debe haberse visto al menos MIN_VISTAS veces, para descartar un mensaje corrupto suelto):
  IMO-VARIOS      el mismo MMSI transmitió dos o más IMO distintos
  IMO-DUPLICADO   el mismo IMO lo transmitieron dos o más MMSI con ventanas de tiempo que se superponen (puede ser un casco clonado)
  NOMBRE-VARIOS   el mismo MMSI transmitió nombres claramente distintos (no un truncado ni un error de una letra)
  INDICATIVO-VARIOS  el mismo MMSI transmitió dos o más indicativos de llamada distintos"""
import difflib
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import indicios as _ind
import pulso as _pulso

MIN_VISTAS = 3
VENTANA_DIAS = 14
REGLAS = {"IMO-VARIOS": "más de un IMO para el mismo MMSI", "IMO-DUPLICADO": "el mismo IMO en dos MMSI a la vez", "NOMBRE-VARIOS": "más de un nombre distinto para el mismo MMSI",
          "INDICATIVO-VARIOS": "más de un indicativo de llamada para el mismo MMSI"}


def _norm(n):
    return re.sub(r"[^A-Z0-9]", "", (n or "").upper())


def _distintos(a, b):
    a, b = _norm(a), _norm(b)
    if not a or not b or a == b or a.startswith(b) or b.startswith(a) or a.isdigit() or b.isdigit():
        return False
    return difflib.SequenceMatcher(None, a, b).ratio() < 0.6


def _firmes(campo):
    """Valores vistos al menos MIN_VISTAS veces: {valor: [primera, última, veces]}"""
    return {k: v for k, v in (campo or {}).items() if v[2] >= MIN_VISTAS}


def _solapan(a, b):
    return a[0] < b[1] and b[0] < a[1]


def evaluar(reg, ahora, ventana=VENTANA_DIAS):
    """[{regla, mmsis, detalle}]: las inconsistencias de las embarcaciones vistas en la ventana. `ahora` es un datetime."""
    corte = (ahora - timedelta(days=ventana)).strftime("%Y-%m-%dT%H:%M:%SZ")
    activos = {m: r for m, r in reg["v"].items() if r["u"] >= corte}
    out = []
    for m, r in activos.items():
        imos = _firmes(r["imo"])
        if len(imos) >= 2:
            out.append({"regla": "IMO-VARIOS", "mmsis": [m], "detalle": "IMO " + ", ".join(sorted(imos))})
        nombres = list(_firmes(r["nom"]))
        if any(_distintos(a, b) for i, a in enumerate(nombres) for b in nombres[i + 1:]):
            out.append({"regla": "NOMBRE-VARIOS", "mmsis": [m], "detalle": "nombres " + ", ".join(sorted(nombres))})
        calls = {_norm(c) for c in _firmes(r["cs"]) if _norm(c)}
        if len(calls) >= 2:
            out.append({"regla": "INDICATIVO-VARIOS", "mmsis": [m], "detalle": "indicativos " + ", ".join(sorted(calls))})
    por_imo = {}
    for m, r in activos.items():
        for imo, v in _firmes(r["imo"]).items():
            por_imo.setdefault(imo, []).append((m, v))
    for imo, lst in por_imo.items():
        if len(lst) >= 2 and any(_solapan(a[1], b[1]) for i, a in enumerate(lst) for b in lst[i + 1:] if a[0] != b[0]):
            out.append({"regla": "IMO-DUPLICADO", "mmsis": sorted(m for m, _ in lst), "detalle": "IMO %s en %d MMSI" % (imo, len(lst))})
    return out


def _zona(r):
    if r.get("x") is None:
        return "gen"
    return _pulso.zona_de(r["x"], r["y"])


def _fecha(s):
    return "%s/%s" % (s[8:10], s[5:7])


def indicios(reg, ahora):
    """{zona: [indicio]}: sólo conteos, sin nombres. Siempre hay uno en «gen» que dice cuánta historia tiene el registro."""
    if not reg or not reg.get("v"):
        return {}
    corte = (ahora - timedelta(days=VENTANA_DIAS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    activos = {m: r for m, r in reg["v"].items() if r["u"] >= corte}
    anom = evaluar(reg, ahora)
    dias_historia = max(0, (ahora - datetime.strptime(reg["desde"][:10], "%Y-%m-%d")).days)
    por_zona, mmsi_zona, por_regla = {}, {}, {}
    for a in anom:
        for m in a["mmsis"]:
            z = _zona(reg["v"][m])
            mmsi_zona.setdefault(z, set()).add(m)
            por_zona.setdefault(z, {}).setdefault(a["regla"], set()).add(m)
            por_regla.setdefault(a["regla"], set()).add(m)
    fuentes = [_ind.FUENTE_AIS]
    nivel = _ind.nivel_evidencia(fuentes)
    no_dice = ("Una inconsistencia de identidad NO prueba ningún delito: la mayoría son errores de carga de datos del equipo, reconfiguraciones o cambios legales de nombre o de bandera, "
               "y producen las mismas señales que una falsificación. No se publican nombres de buques: el detalle va a un informe privado para quien cura.")
    res = {}
    todos = set().union(*mmsi_zona.values()) if mmsi_zona else set()
    parcial = " El registro tiene sólo %d días de historia: la cifra es parcial y crece con el tiempo." % dias_historia if dias_historia < VENTANA_DIAS else ""
    res["gen"] = [{"id": "ANI", "tipo": "Operaciones sospechosas", "titulo": "Identidad inconsistente en el AIS (todo el corredor)",
                   "texto": "De %d embarcaciones (MMSI) vistas en los últimos %d días, %d transmitieron identidades inconsistentes: %s.%s Registro de identidades desde el %s."
                            % (len(activos), VENTANA_DIAS, len(todos), ("; ".join("%d con %s" % (len(v), REGLAS[k]) for k, v in por_regla.items()) or "ninguna regla se activó"),
                               parcial, _fecha(reg["desde"])),
                   "fuentes": fuentes, "nivel": nivel, "no_dice": no_dice, "dato": {"mmsi_vistos": len(activos), "mmsi_inconsistentes": len(todos), "dias_historia": dias_historia}}]
    for z, reglas in por_zona.items():
        if z == "gen":
            continue
        res.setdefault(z, []).append({"id": "ANI", "tipo": "Operaciones sospechosas", "titulo": "Identidad inconsistente en el AIS",
                                      "texto": "%d %s vista%s en este tramo en los últimos %d días %s identidades inconsistentes: %s." % (len(mmsi_zona[z]), "embarcación" if len(mmsi_zona[z]) == 1 else "embarcaciones", "" if len(mmsi_zona[z]) == 1 else "s", VENTANA_DIAS, "transmitió" if len(mmsi_zona[z]) == 1 else "transmitieron", "; ".join("%d con %s" % (len(v), REGLAS[k]) for k, v in reglas.items())),
                                      "fuentes": fuentes, "nivel": nivel, "no_dice": no_dice, "dato": {"mmsi_inconsistentes": len(mmsi_zona[z])}})
    return res


def informe_md(reg, ahora):
    """Informe PRIVADO con nombres, para quien cura. Devuelve (texto, cantidad)."""
    anom = evaluar(reg, ahora)
    if not anom:
        return "", 0
    nombres_zona = {z[0]: z[1] for z in _pulso.ZONAS}
    nombres_zona["gen"] = "sin posición"
    lin = ["# Anomalías de identidad en el AIS · %s" % ahora.strftime("%Y-%m-%d"),
           "",
           "Registro de identidades desde el %s; ventana de %d días; cada valor visto al menos %d veces." % (reg["desde"][:10], VENTANA_DIAS, MIN_VISTAS),
           "",
           "**Esto no es una alerta ni una acusación.** Una inconsistencia de identidad no prueba ningún delito: hay errores de carga, reconfiguraciones y cambios legales de nombre o bandera que producen las mismas señales. "
           "Cada caso es un indicio de fuente única (AIS) para que lo vea un analista; antes de cualquier uso, contrastar con una segunda fuente (registro del buque, prensa, SIWA).",
           ""]
    for regla in REGLAS:
        casos = [a for a in anom if a["regla"] == regla]
        if not casos:
            continue
        lin.append("## %s (%d)" % (REGLAS[regla], len(casos)))
        for a in casos:
            for m in a["mmsis"]:
                r = reg["v"][m]
                nom = ", ".join("%s (%d)" % (k, v[2]) for k, v in sorted(r["nom"].items(), key=lambda kv: -kv[1][2])) or "sin nombre"
                imo = ", ".join("%s (%d)" % (k, v[2]) for k, v in sorted(r["imo"].items(), key=lambda kv: -kv[1][2])) or "sin IMO"
                cs = ", ".join("%s (%d)" % (k, v[2]) for k, v in sorted(r["cs"].items(), key=lambda kv: -kv[1][2])) or "sin indicativo"
                lin.append("- **MMSI %s** · %s · último mensaje %s · %s · nombres: %s · IMO: %s · indicativos: %s · %d mensajes" % (m, ", ".join(r["ban"]) or "bandera sin dato", r["u"][:16].replace("T", " "), nombres_zona.get(_zona(r), "?"), nom, imo, cs, r["n"]))
            if regla == "IMO-DUPLICADO":
                lin.append("  - %s" % a["detalle"])
        lin.append("")
    return "\n".join(lin), len(anom)
