#!/usr/bin/env python3
"""Resuelve solas las preguntas publicadas que ya vencieron, contra un criterio mecánico fijado al nacer.

Criterio admitido (único, por ahora):
  {"tipo": "nivel_estacion", "estacion": "Asunción", "operador": "<=" | ">=", "umbral_m": 0.30,
   "desde": "AAAA-MM-DD", "hasta": "AAAA-MM-DD", "red": "py" (por defecto) | "ar"}
  «py»: Meteorología de Paraguay (nivel-rio-py-historial.jsonl). «ar»: escalas de la Prefectura vía INA (nivel-rio-ar-historial.jsonl).
  {"tipo": "pulso_zona", "zona": "z2", "campo": "mediana" | "estado_capturas", "operador": "<=" | ">=" | "==", "umbral": 130,
   "minimo_dias": 1, "desde": "AAAA-MM-DD", "hasta": "AAAA-MM-DD"}
  Cuenta los días del período en que el valor diario de la zona (pulso por zona, rama datos-pulso) cumple el operador contra el umbral;
  «ocurrió» si esos días son `minimo_dias` o más. Un día cuenta sólo si tuvo 12 capturas de AIS o más; si los días con datos son
  menos de la mitad del período, la pregunta queda «sin datos suficientes». `mediana` = buques por captura (mediana del día);
  `estado_capturas` = capturas del día con alguna unidad del Estado visible por AIS (de 24).
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


def _lecturas_ar(historial, estacion, desde, hasta):
    out = []
    for linea in open(historial, encoding="utf-8"):
        if not linea.strip():
            continue
        j = json.loads(linea)
        if j["estacion"] != estacion:
            continue
        f = datetime.strptime(j["fecha"], "%Y-%m-%d").date()
        if desde <= f <= hasta:
            out.append((f, j["nivel_m"]))
    return out


def _pulso_remoto():
    import urllib.request
    url = "https://raw.githubusercontent.com/fundacion-sherman-kent/ysyry/datos-pulso/pulso.json"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Ysyry-FUSK/1.0"}), timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def _resolver_pulso(c, pulso, hoy):
    desde, hasta = _d(c["desde"]), _d(c["hasta"])
    if hoy <= hasta:
        return None, "todavía no venció"
    dias = (hasta - desde).days + 1
    zona = pulso["zonas"].get(c["zona"], {})
    validos, cumplen = [], []
    for k, v in zona.items():
        f = _d(k)
        if not (desde <= f <= hasta) or v.get("capturas", 0) < 12:
            continue
        validos.append(f)
        x, u, op = v[c["campo"]], c["umbral"], c["operador"]
        if (op == "<=" and x <= u) or (op == ">=" and x >= u) or (op == "==" and x == u):
            cumplen.append(f)
    if len(validos) * 2 < dias:
        return None, "sin datos suficientes (%d días con datos en %d)" % (len(validos), dias)
    return {"resultado": len(cumplen) >= c.get("minimo_dias", 1), "valor_observado": "%d días que cumplen, de %d con datos" % (len(cumplen), len(validos))}, "ok"


def resolver(q, historial, hoy, pulso=None):
    c = q["criterio"]
    if c.get("tipo") == "pulso_zona":
        return _resolver_pulso(c, pulso, hoy)
    if c.get("tipo") != "nivel_estacion":
        return None, "criterio no admitido"
    hasta, desde = _d(c["hasta"]), _d(c["desde"])
    if hoy <= hasta:
        return None, "todavía no venció"
    lect = (_lecturas_ar if c.get("red") == "ar" else _lecturas)(historial, c["estacion"], desde, hasta)
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
    historiales = {"py": RAIZ / "datos" / "publico" / "nivel-rio-py-historial.jsonl", "ar": RAIZ / "datos" / "publico" / "nivel-rio-ar-historial.jsonl"}
    cambios = 0
    for f in sorted((RAIZ / "preguntas").glob("*.json")):
        q = json.load(open(f, encoding="utf-8"))
        if q.get("estado") != "publicada" or q.get("resultado") in (True, False):
            continue
        if q["criterio"].get("tipo") == "pulso_zona":
            try:
                res, motivo = resolver(q, None, hoy, _pulso_remoto())
            except Exception as ex:
                print("%s: no se pudo leer el pulso (%s)" % (q.get("id"), str(ex)[:80]))
                continue
            historial = True
        else:
            historial = historiales.get(q["criterio"].get("red", "py"))
        if historial is None or (historial is not True and not historial.exists()):
            print("%s: no hay historial de niveles" % q.get("id"))
            continue
        if q["criterio"].get("tipo") != "pulso_zona":
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
