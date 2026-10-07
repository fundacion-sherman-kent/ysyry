#!/usr/bin/env python3
"""Salud de las fuentes y de la propia plataforma: pulso, frescura y cobertura. Mide y propone; NUNCA cambia nada solo.

Lo corre un flujo privado una vez por día. Escribe un resumen en JSON y sale con 1 si algo se degradó, para que el flujo abra un
Issue con lo que hay que mirar. Cada chequeo dice qué midió, con qué umbral y qué encontró."""
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone

UA = {"User-Agent": "Ysyry-FUSK/1.0 (+https://github.com/fundacion-sherman-kent/ysyry)"}
SITIO = "https://fundacion-sherman-kent.github.io/ysyry/"
RAW = "https://raw.githubusercontent.com/fundacion-sherman-kent/ysyry/"
SIWA = "https://siwa.fundacionkent.org/datos/publico/"
FEM = "https://fundacion-sherman-kent.github.io/femonoe-sitio/index.html"


def bajar(url, t=40):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=t) as r:
        return r.read().decode("utf-8", "replace")


def horas(iso):
    return (datetime.now(timezone.utc) - datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)).total_seconds() / 3600


def chequeos():
    out = []

    def uno(nombre, umbral, f):
        try:
            ok, hallado = f()
        except Exception as e:
            ok, hallado = False, "no respondió: %s" % str(e)[:90]
        out.append({"chequeo": nombre, "umbral": umbral, "ok": bool(ok), "hallado": hallado})

    def sitio():
        h = bajar(SITIO)
        return ('id="latido"' in h and 'id="svg-mapa"' in h), "responde, %d KB" % (len(h) // 1024)

    def ais():
        m = json.loads(bajar(RAW + "datos-ais/marcos.json"))
        edad = horas(m[-1]["hora"])
        return edad < 3, "última captura hace %.1f h, con %d buques; %d capturas guardadas" % (edad, len(m[-1]["puntos"]), len(m))

    def nivel():
        d = json.loads(bajar(RAW + "main/datos/publico/nivel-rio-py.json"))
        edad = horas(d["obtenido"])
        return edad < 36, "leído hace %.0f h, %d estaciones" % (edad, len(d["estaciones"]))

    def historial():
        n = len([l for l in bajar(RAW + "main/datos/publico/nivel-rio-py-historial.jsonl").splitlines() if l.strip()])
        return n > 0, "%d lecturas acumuladas" % n

    def siwa():
        fallas = []
        for f in ("subnacional_homicidios", "subnacional_acled", "subnacional_focos"):
            try:
                assert json.loads(bajar(SIWA + f + ".json"))["registros"]
            except Exception:
                fallas.append(f)
        return not fallas, "responden los 3 conjuntos" if not fallas else "fallan: " + ", ".join(fallas)

    def femonoe():
        h = bajar(FEM)
        n = len(re.findall(r'href="alerta/\d{4}-\d{2}-\d{2}-[A-Z0-9]+-[GSI]\.html"', h))
        return n > 0, "el índice lista %d alertas (si bajara a 0 es que cambió la página)" % n

    def pulso():
        d = json.loads(bajar(RAW + "datos-pulso/pulso.json"))
        dias = max(len(v) for v in d["zonas"].values())
        return dias >= 1, "%d días de historia del pulso" % dias

    def frescura(archivo, campo, horas_max, etiqueta):
        d = json.loads(bajar(RAW + "main/datos/publico/" + archivo))
        edad = horas(d[campo])
        return edad < horas_max, "%s: hace %.0f h (máximo %d h)" % (etiqueta, edad, horas_max)

    uno("Nivel del río en Argentina (Prefectura vía INA)", "leído hace menos de 36 horas", lambda: frescura("nivel-rio-ar.json", "obtenido", 36, "leído"))
    uno("Escáner propio de hechos", "corrió hace menos de 12 horas", lambda: frescura("escaner.json", "obtenido", 12, "corrió"))
    uno("Focos de calor cerca del río", "corrió hace menos de 12 horas", lambda: frescura("focos_corredor.json", "obtenido", 12, "corrió"))
    uno("Lista de sanciones OFAC", "leída hace menos de 10 días", lambda: frescura("ofac_buques.json", "obtenido", 240, "leída"))
    uno("Sitio público", "responde y trae el mapa y el latido", sitio)
    uno("Capturas de AIS", "última captura de menos de 3 horas", ais)
    uno("Nivel del río (Meteorología de Paraguay)", "leído hace menos de 36 horas", nivel)
    uno("Historial del nivel del río", "al menos una lectura", historial)
    uno("SIWA, conjuntos subnacionales", "los 3 responden con registros", siwa)
    uno("FEMÓNOE, índice de alertas", "se puede leer y lista al menos una alerta", femonoe)
    uno("Historial del pulso", "al menos un día guardado", pulso)
    return out


def main():
    res = chequeos()
    json.dump({"hecho": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "chequeos": res}, open("salud.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in res:
        print(("OK    " if r["ok"] else "FALLA ") + r["chequeo"] + " — " + r["hallado"])
    return 0 if all(r["ok"] for r in res) else 1


if __name__ == "__main__":
    sys.exit(main())
