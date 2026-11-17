#!/usr/bin/env python3
"""Registro de identidades de AIS con historia, por MMSI: qué nombres, IMO e indicativos transmitió cada embarcación y cuándo se vio cada uno.
Se alimenta de la capa viva (colectores/vivo.py, cada 5 minutos). Sirve para detectar inconsistencias de identidad (sitio/anomalias.py): un IMO distinto
para el mismo MMSI, el mismo IMO en dos MMSI a la vez, nombres o indicativos que cambian. Son hechos transmitidos por los propios equipos AIS; una
inconsistencia NO prueba ningún delito (la mayoría son errores de carga de datos del equipo).

Cada mensaje cuenta una sola vez: la capa viva repite la misma posición durante horas, y se cuenta cuando la hora del mensaje es posterior a la ya contada.
Uso: identidades_ais.py VIVO.json PREVIO.json SALIDA.json"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

MAX_VALORES = 8        # valores distintos que se guardan por campo y por buque
DIAS_CONSERVAR = 90    # un MMSI sin verse tanto tiempo sale del registro


def _norm(x):
    if x is None:
        return None
    x = str(x).strip()
    return x or None


def anotar(campo, valor, visto):
    """campo: {valor: [primera, última, veces]}; guarda como mucho MAX_VALORES, descartando el menos visto."""
    if valor is None:
        return
    r = campo.get(valor)
    if r:
        r[1] = max(r[1], visto)
        r[0] = min(r[0], visto)
        r[2] += 1
    else:
        campo[valor] = [visto, visto, 1]
        if len(campo) > MAX_VALORES:
            menos = min(campo, key=lambda k: (campo[k][2], campo[k][1]))
            del campo[menos]


def fusionar(previo, vivo, ahora):
    reg = (previo or {}).get("v", {})
    desde = (previo or {}).get("desde") or ahora.strftime("%Y-%m-%dT%H:%M:%SZ")
    nuevos = 0
    for b in vivo.get("buques", []):
        mmsi, visto = str(b.get("i")), b.get("s")
        if not mmsi or not visto:
            continue
        r = reg.get(mmsi)
        if r is None:
            r = reg[mmsi] = {"p": visto, "u": visto, "s": "", "n": 0, "nom": {}, "imo": {}, "cs": {}, "ban": {}, "tip": {}}
        if visto <= r["s"]:
            continue                      # ese mensaje ya se contó
        r["s"], r["u"] = visto, visto
        r["n"] += 1
        anotar(r["nom"], _norm(b.get("n")), visto)
        anotar(r["imo"], _norm(b.get("m")), visto)
        anotar(r["cs"], _norm(b.get("cs")), visto)
        anotar(r["ban"], _norm(b.get("b")), visto)
        anotar(r["tip"], _norm(b.get("ty")), visto)
        r["x"], r["y"] = b.get("x"), b.get("y")
        nuevos += 1
    corte = (ahora - timedelta(days=DIAS_CONSERVAR)).strftime("%Y-%m-%dT%H:%M:%SZ")
    reg = {k: v for k, v in reg.items() if v["u"] >= corte}
    return {"actualizado": ahora.strftime("%Y-%m-%dT%H:%M:%SZ"), "desde": desde, "n_mmsi": len(reg), "v": reg}, nuevos


def main():
    vivo = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    previo = {}
    if Path(sys.argv[2]).exists():
        try:
            previo = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        except Exception:
            previo = {}
    nuevo, n = fusionar(previo, vivo, datetime.now(timezone.utc))
    Path(sys.argv[3]).write_text(json.dumps(nuevo, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")
    print("Registro de identidades: %d MMSI (desde %s); %d mensajes nuevos contados." % (nuevo["n_mmsi"], nuevo["desde"][:10], n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
