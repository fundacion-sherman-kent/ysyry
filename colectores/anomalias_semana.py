#!/usr/bin/env python3
"""Informe PRIVADO de anomalías de identidad en el AIS, con nombres, para quien cura (nunca se publica). Lee el registro de identidades público
(rama datos-identidades) y escribe un informe en Markdown. Sale con código 10 si hay casos, para que el robot privado abra un Issue.
Uso: anomalias_semana.py REGISTRO.json|URL SALIDA.md"""
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sitio"))
import anomalias


def main():
    fuente = sys.argv[1]
    if fuente.startswith("http"):
        with urllib.request.urlopen(urllib.request.Request(fuente, headers={"User-Agent": "Ysyry-FUSK/1.0"}), timeout=60) as r:
            reg = json.loads(r.read().decode("utf-8"))
    else:
        reg = json.load(open(fuente, encoding="utf-8"))
    md, n = anomalias.informe_md(reg, datetime.now(timezone.utc).replace(tzinfo=None))
    print("MMSI en el registro: %d (desde %s); casos de anomalía: %d" % (reg.get("n_mmsi", len(reg["v"])), reg["desde"][:10], n))
    if n == 0:
        return 0
    Path(sys.argv[2]).write_text(md, encoding="utf-8", newline="\n")
    return 10


if __name__ == "__main__":
    sys.exit(main())
