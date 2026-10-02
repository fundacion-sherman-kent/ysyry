#!/usr/bin/env python3
"""Resuelve solas las preguntas publicadas que ya vencieron, contra un criterio mecánico fijado al nacer.

Criterio admitido (único, por ahora):
  {"tipo": "nivel_estacion", "estacion": "Asunción", "operador": "<=" | ">=", "umbral_m": 0.30,
   "desde": "AAAA-MM-DD", "hasta": "AAAA-MM-DD"}
Resultado: «ocurrió» si alguna lectura de esa estación entre `desde` y `hasta` cumple el operador contra el umbral. Se lee
`datos/publico/nivel-rio-py-historial.jsonl`. Si en el período hay menos lecturas que la mitad de los días, la pregunta NO se
resuelve: queda marcada «sin datos suficientes» y la dirección decide, porque contar un «no» por falta de lecturas sería falsear.

Sólo escribe el resultado en el archivo de la pregunta; no cambia el enunciado, la banda ni el criterio."""
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _d(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def _lecturas(historial, estacion, desde, hasta):
    out = []
    for linea in open(historial, encoding="utf-8"):
        if not linea.strip():
            continue
        j = json.loads(linea)
        if j["estacion"] != estacion:
            continue
        f = datetime.strptime(j["lectura"], "%d-%m-%Y").date()
        if desde <= f <= hasta:
            out.append((f, j["nivel_m"]))
    return out


def resolver(q, historial, hoy):
    c = q["criterio"]
    if c.get("tipo") != "nivel_estacion":
        return None, "criterio no admitido"
    hasta, desde = _d(c["hasta"]), _d(c["desde"])
    if hoy <= hasta:
        return None, "todavía no venció"
    lect = _lecturas(historial, c["estacion"], desde, hasta)
    dias = (hasta - desde).days + 1
    if len({f for f, _ in lect}) * 2 < dias:
        return None, "sin datos suficientes (%d lecturas en %d días)" % (len({f for f, _ in lect}), dias)
    if c["operador"] == "<=":
        valor, ocurrio = min(v for _, v in lect), any(v <= c["umbral_m"] for _, v in lect)
    else:
        valor, ocurrio = max(v for _, v in lect), any(v >= c["umbral_m"] for _, v in lect)
    return {"resultado": ocurrio, "valor_observado": "%.2f m" % valor}, "ok"


def main():
    hoy = datetime.utcnow().date()
    historial = RAIZ / "datos" / "publico" / "nivel-rio-py-historial.jsonl"
    cambios = 0
    for f in sorted((RAIZ / "preguntas").glob("*.json")):
        q = json.load(open(f, encoding="utf-8"))
        if q.get("estado") != "publicada" or q.get("resultado") in (True, False):
            continue
        if not historial.exists():
            print("%s: no hay historial de niveles" % q.get("id"))
            continue
        res, motivo = resolver(q, historial, hoy)
        if res is None:
            print("%s: %s" % (q.get("id"), motivo))
            if motivo.startswith("sin datos"):
                q["nota_resolucion"] = motivo
                json.dump(q, open(f, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
                cambios += 1
            continue
        q.update(res)
        q["estado"] = "resuelta"
        q["resuelta_el"] = hoy.isoformat()
        json.dump(q, open(f, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
        print("%s: resuelta, %s" % (q["id"], "ocurrió" if res["resultado"] else "no ocurrió"))
        cambios += 1
    print("Preguntas actualizadas: %d" % cambios)
    return 0


if __name__ == "__main__":
    sys.exit(main())
