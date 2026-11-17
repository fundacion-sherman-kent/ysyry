#!/usr/bin/env python3
"""Buques de la lista consolidada de sanciones del Reino Unido (FCDO/OFSI, Open Government Licence v3.0) que tienen número IMO.
Esa lista incluye las designaciones de buques del Consejo de Seguridad de la ONU (campo DesignationSource = UN, p. ej. los buques vinculados a Corea del Norte) y las del propio
Reino Unido (p. ej. la flota en la sombra de Rusia). La lista de la UE no sirve para esto: su archivo público no trae los buques como entidades con IMO.

Se cruza luego por IMO con los que transmiten AIS en el corredor. Estar en una lista es una decisión de un Estado extranjero (o del Consejo de Seguridad), no una condena local, y un IMO
transmitido por AIS puede estar mal cargado: una coincidencia es una pista para mirar, no una acusación.
Escribe DATOS_DIR/sanciones_uk_buques.json con el mismo formato que ofac_buques.json."""
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

URL = "https://sanctionslist.fcdo.gov.uk/docs/UK-Sanctions-List.xml"
UA = {"User-Agent": "Ysyry-FUSK/1.0 (+https://github.com/fundacion-sherman-kent/ysyry)"}


def _t(el, ruta):
    x = el.find(ruta)
    return (x.text or "").strip() if x is not None and x.text else ""


def main():
    carpeta = Path(os.environ.get("DATOS_DIR", "datos/publico"))
    carpeta.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(urllib.request.Request(URL, headers=UA), timeout=180) as r:
            raiz = ET.fromstring(r.read())
    except Exception as e:
        print("La lista del Reino Unido no respondió: %s" % str(e)[:100])
        return 1
    buques = {}
    for d in raiz.iter("Designation"):
        if _t(d, "IndividualEntityShip") != "Ship":
            continue
        nombre = ""
        for n in d.iter("Name"):
            if _t(n, "NameType") == "Primary name":
                nombre = _t(n, "Name6")
                break
        origen = _t(d, "DesignationSource")
        for imo in d.iter("IMONumber"):
            m = re.search(r"(\d{7})", imo.text or "")
            if m:
                buques[m.group(1)] = {"nombre": nombre, "programa": _t(d, "RegimeName") or "sin dato", "origen": "ONU" if origen == "UN" else "Reino Unido",
                                      "tipo": _t(d, "ShipDetails/Ship/TypeOfShipDetails/TypeOfShip"), "bandera": _t(d, "ShipDetails/Ship/CurrentBelievedFlagOfShips/CurrentBelievedFlagOfShip"), "ent": _t(d, "UniqueID")}
    if len(buques) < 300:
        print("Sólo %d buques con IMO: el formato cambió, no se toca el archivo anterior" % len(buques))
        return 1
    salida = {"obtenido": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "fuente": {"nombre": "Lista consolidada de sanciones del Reino Unido (FCDO), con designaciones de la ONU", "url": "https://www.gov.uk/government/publications/the-uk-sanctions-list",
                         "nota": "Open Government Licence v3.0. Estar en la lista es una decisión de un Estado extranjero o del Consejo de Seguridad de la ONU, no una condena local. Sólo se cruza por IMO."},
              "buques": buques}
    with open(carpeta / "sanciones_uk_buques.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(salida, fh, ensure_ascii=False, separators=(",", ":"))
    print("Buques con IMO en la lista del Reino Unido: %d (de la ONU: %d)" % (len(buques), sum(1 for b in buques.values() if b["origen"] == "ONU")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
