#!/usr/bin/env python3
"""Nivel del río Paraguay en Brasil: telemetría de la ANA (Agência Nacional de Águas), con lecturas cada 15 minutos, de escalas operadas por el
Serviço Geológico do Brasil (SGB-CPRM): Cáceres, Ladário y Porto Esperança. Es la fuente primaria de las mismas escalas que la Dirección de
Meteorología de Paraguay republica como «Puerto Ladario - Brasil» y «Cáceres - Brasil»: NO son dos fuentes distintas para esas escalas, pero sí
una lectura más fresca y, en Cáceres, el caudal.

Servicio de acceso libre (telemetriaws1.ana.gov.br). Porto Murtinho sólo trae lluvia por telemetría; queda con la lectura de Paraguay.
Escribe DATOS_DIR/nivel-rio-br.json."""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

URL = "https://telemetriaws1.ana.gov.br/ServiceANA.asmx/DadosHidrometeorologicos?codEstacao=%s&dataInicio=%s&dataFim=%s"
UA = {"User-Agent": "Mozilla/5.0 (compatible; YsyryFUSK/1.0; +https://github.com/fundacion-sherman-kent/ysyry)"}
ESTACIONES = [("66070004", "Cáceres (ANA)", -16.0761, -57.7022), ("66825000", "Ladário (ANA)", -19.0017, -57.5942), ("66960008", "Porto Esperança (ANA)", -19.6006, -57.4372)]


def leer(cod, ini, fin):
    with urllib.request.urlopen(urllib.request.Request(URL % (cod, ini, fin), headers=UA), timeout=90) as r:
        t = r.read().decode("utf-8", "replace")
    filas = []
    for f in re.findall(r"<DadosHidrometereologicos[^>]*>(.*?)</DadosHidrometereologicos>", t, re.S):
        d = dict(re.findall(r"<(\w+)>([^<]*)</\1>", f))
        if d.get("Nivel", "").strip() and d.get("DataHora"):
            filas.append((d["DataHora"].strip(), float(d["Nivel"]), float(d["Vazao"]) if d.get("Vazao", "").strip() else None))
    return sorted(filas)


def main():
    carpeta = Path(os.environ.get("DATOS_DIR", "datos/publico"))
    carpeta.mkdir(parents=True, exist_ok=True)
    hoy = datetime.now(timezone.utc)
    ini, fin = (hoy - timedelta(days=3)).strftime("%Y-%m-%d"), (hoy + timedelta(days=1)).strftime("%Y-%m-%d")
    est = []
    for cod, nombre, lat, lon in ESTACIONES:
        try:
            filas = leer(cod, ini, fin)
        except Exception as e:
            print("  %s no respondió: %s" % (nombre, str(e)[:60]))
            continue
        if not filas:
            print("  %s sin lecturas de nivel" % nombre)
            continue
        ult = filas[-1]
        t_ult = datetime.strptime(ult[0][:16], "%Y-%m-%d %H:%M")
        previo = min(filas, key=lambda f: abs((datetime.strptime(f[0][:16], "%Y-%m-%d %H:%M") - (t_ult - timedelta(hours=24))).total_seconds()))
        antes24 = previo if abs((datetime.strptime(previo[0][:16], "%Y-%m-%d %H:%M") - (t_ult - timedelta(hours=24))).total_seconds()) < 4 * 3600 else None
        est.append({"codigo": cod, "nombre": nombre, "lat": lat, "lon": lon, "hora_local": ult[0][:16], "nivel_m": round(ult[1] / 100.0, 2), "caudal_m3s": ult[2],
                    "var_cm": round(ult[1] - antes24[1]) if antes24 else None})
        print("  %s: %.2f m, %s cm en 24 h" % (nombre, ult[1] / 100.0, est[-1]["var_cm"]))
    if not est:
        print("ANA no devolvió lecturas: no se toca el archivo anterior")
        return 1
    salida = {"obtenido": hoy.strftime("%Y-%m-%dT%H:%M:%SZ"),
              "fuente": {"nombre": "ANA (Brasil), telemetría; escalas del Serviço Geológico do Brasil (SGB-CPRM)", "url": "https://telemetriaws1.ana.gov.br/",
                         "nota": "Lecturas cada 15 minutos (hora local de Brasil). Altura de la escala, no el calado de la vía. Sin umbrales oficiales en esta interfaz."},
              "estaciones": est}
    with open(carpeta / "nivel-rio-br.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(salida, fh, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
