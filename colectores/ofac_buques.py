#!/usr/bin/env python3
"""Buques de la lista de sanciones SDN de OFAC (Departamento del Tesoro de EE.UU., dominio público) que tienen número IMO.

Ysyry cruza luego esos IMO con los que transmiten las embarcaciones del corredor. Sólo por IMO, que es exacto: un nombre no alcanza
(hay homónimos), y un IMO transmitido por AIS puede estar mal cargado, así que una coincidencia es una pista para mirar y no una
acusación. Estar en la lista SDN no es, además, una condena de nadie en Argentina, Paraguay, Brasil, Bolivia o Uruguay: es una
decisión de un Estado extranjero.

Escribe DATOS_DIR/ofac_buques.json."""
import csv
import io
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

URL = "https://www.treasury.gov/ofac/downloads/sdn.csv"
UA = {"User-Agent": "Ysyry-FUSK/1.0 (+https://github.com/fundacion-sherman-kent/ysyry)"}


def main():
    carpeta = Path(os.environ.get("DATOS_DIR", "datos/publico"))
    carpeta.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(urllib.request.Request(URL, headers=UA), timeout=180) as r:
            texto = r.read().decode("latin-1")
    except Exception as e:
        print("OFAC no respondió: %s" % str(e)[:100])
        return 1
    buques = {}
    for r in csv.reader(io.StringIO(texto)):
        if len(r) >= 12 and r[2].strip().lower() == "vessel":
            m = re.search(r"IMO\s*(\d{7})", r[11])
            if m:
                buques[m.group(1)] = {"nombre": r[1].strip(), "programa": r[3].strip(), "tipo": r[6].strip().strip("-0- ") or "", "bandera": r[9].strip().strip("-0- ") or "", "ent": r[0].strip()}
    if len(buques) < 500:
        print("Sólo %d buques con IMO: el formato cambió, no se toca el archivo anterior" % len(buques))
        return 1
    salida = {"obtenido": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "fuente": {"nombre": "OFAC, lista SDN (Departamento del Tesoro de EE.UU.)", "url": "https://sanctionslist.ofac.treas.gov/",
                         "nota": "Dominio público. Estar en la lista es una decisión de un Estado extranjero, no una condena local. Sólo se cruza por IMO."},
              "buques": buques}
    with open(carpeta / "ofac_buques.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(salida, fh, ensure_ascii=False, separators=(",", ":"))
    print("Buques SDN con IMO: %d" % len(buques))
    return 0


if __name__ == "__main__":
    sys.exit(main())
