#!/usr/bin/env python3
"""Resumen semanal de candidatos para la curaduría: junta lo que propone el scanner de flujos de SIWA (rama pública `propuestas-flujos`,
que se lee sin pedirle nada a SIWA y sin modificarlo) y lo que detectó el escáner propio de Ysyry en los últimos 7 días.

Imprime un resumen en Markdown y sale con 10 si hay algo para revisar, con 0 si no hay nada (para que el flujo no abra un Issue vacío).
Nada de esto está calificado: son candidatos para los analistas, el décimo hombre y la dirección. No usa ningún modelo."""
import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

UA = {"User-Agent": "Ysyry-FUSK/1.0 (+https://github.com/fundacion-sherman-kent/ysyry)"}
SIWA_API = "https://api.github.com/repos/fundacion-sherman-kent/siwa/contents/flujos?ref=propuestas-flujos"
SIWA_RAW = "https://raw.githubusercontent.com/fundacion-sherman-kent/siwa/propuestas-flujos/flujos/"
ESCANER = "https://raw.githubusercontent.com/fundacion-sherman-kent/ysyry/main/datos/publico/escaner.json"


def bajar(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))


def siwa():
    try:
        archivos = [f["name"] for f in bajar(SIWA_API) if f["name"].startswith("flujos-")][-7:]
    except Exception as e:
        return ["_No se pudo leer la rama `propuestas-flujos` de SIWA: %s_" % str(e)[:80]], 0
    lineas, total = [], 0
    for a in archivos:
        try:
            d = bajar(SIWA_RAW + a)
        except Exception:
            continue
        for p in d.get("propuestas", []):
            for e in p.get("eventos_candidatos", []):
                total += 1
                lineas.append("- **%s** · %s · %s · %s" % (p.get("id", "?"), p.get("nombre", "")[:70], e.get("lugar", ""), e.get("titular", "")[:140]))
    return lineas, total


def escaner():
    try:
        d = bajar(ESCANER)
    except Exception as e:
        return ["_No se pudo leer el escáner de Ysyry: %s_" % str(e)[:80]], 0
    corte = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    lst = [e for e in d.get("eventos", []) if e["fecha"] >= corte and (e["puntaje"] >= 7 or len(e["medios"]) >= 2)]
    lineas = []
    for e in sorted(lst, key=lambda x: (x["puntaje"], len(x["medios"])), reverse=True)[:25]:
        q = (" · %s %s" % (e["cantidad"]["valor"], e["cantidad"]["unidad"])) if e.get("cantidad") else ""
        lineas.append("- %s · **%s** · %s%s · %d medio(s): %s — %s" % (e["fecha"], "; ".join(r for _, r in e["tipos"]), ", ".join(e.get("lugares") or ["—"]), q,
                                                                  len(e["medios"]), e["titulo"][:130], e["medios"][0]["url"]))
    return lineas, len(lst)


def main():
    ls, ns = siwa()
    le, ne = escaner()
    if ns == 0 and ne == 0:
        print("Nada para revisar esta semana: el scanner de SIWA no propuso eventos y el escáner de Ysyry no detectó candidatos con puntaje alto o 2 medios.")
        return 0
    print("# Candidatos de la semana para la curaduría\n")
    print("Ninguno está calificado ni verificado: los analistas leen sin verse, el décimo hombre impugna y la dirección decide. Nada de esto se publicó.\n")
    print("## Scanner de flujos de SIWA (rama pública `propuestas-flujos`): %d eventos candidatos\n" % ns)
    print("\n".join(ls) if ls else "- Ninguno.")
    print("\n## Escáner propio de Ysyry (sin modelo): %d candidatos de los últimos 7 días\n" % ne)
    print("\n".join(le) if le else "- Ninguno.")
    return 10


if __name__ == "__main__":
    sys.exit(main())
