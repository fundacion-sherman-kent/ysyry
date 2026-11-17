#!/usr/bin/env python3
"""Capa viva del tráfico aéreo liviano y mediano del corredor, de ADS-B abierto (adsb.lol, ODbL: https://adsb.lol/).
Se queda con aeronaves pequeñas y medianas (aviación general, turbohélices, jets ejecutivos, helicópteros) y descarta los aviones de línea. NO guarda matrículas ni indicativos:
la página muestra tipo, altura y velocidad, nunca quién es el operador.

LÍMITE CENTRAL: ADS-B abierto lo aportan receptores de voluntarios. En buena parte del Paraguay, el Chaco y el Pantanal no hay cobertura abierta (se comprobó el 17/11/2026:
cero aeronaves visibles alrededor de Asunción, Pedro Juan Caballero y Corumbá). Y quien vuela con el transpondedor apagado no aparece en ninguna parte. Por eso la ausencia de
aeronaves en el mapa NO significa ausencia de vuelos, y este colector guarda cuántas celdas respondieron para decirlo en la página.
Uso: aereo.py SALIDA.json"""
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

AX, BX, AY, BY = 38.9572, 2781.788, -43.2531, -653.764
CENTROS = [(lat, lon) for lat in (-18.0, -24.0, -30.0) for lon in (-66.0, -60.0, -54.0)]    # 9 consultas de 250 millas náuticas cubren el recuadro del mapa
RADIO_NM = 250
URL = "https://api.adsb.lol/v2/point/%s/%s/%d"
# aviones de línea y de carga pesada: no son «pequeños ni medianos»
GRANDES = ("A3", "A2", "B7", "B3", "B4", "E1", "E7", "E9", "CRJ", "AT7", "AT4", "DH8", "A1", "MD", "DC", "IL", "AN", "C17", "C5", "K35", "KC", "B1", "B2", "B5", "B6")


def _liviana(a):
    cat, t = (a.get("category") or ""), (a.get("t") or "")
    if cat in ("A3", "A4", "A5", "A6"):
        return False
    if cat in ("A1", "A2", "A7", "B1", "B2", "B4", "B6"):
        return True
    return bool(t) and not t.startswith(GRANDES)


def pedir(lat, lon):
    r = urllib.request.Request(URL % (lat, lon, RADIO_NM), headers={"User-Agent": "Ysyry-FUSK/1.0 (+https://github.com/fundacion-sherman-kent/ysyry)"})
    with urllib.request.urlopen(r, timeout=30) as x:
        return json.loads(x.read().decode("utf-8")).get("ac", [])


def main():
    vistos, respondieron, total_pedidos = {}, 0, 0
    for lat, lon in CENTROS:
        total_pedidos += 1
        try:
            for a in pedir(lat, lon):
                vistos[a["hex"]] = a
            respondieron += 1
        except Exception as e:
            print("aviso: celda %s,%s falló: %s" % (lat, lon, str(e)[:60]))
        time.sleep(1.2)
    out = []
    for a in vistos.values():
        if a.get("lat") is None or a.get("lon") is None or not _liviana(a):
            continue
        if isinstance(a.get("alt_baro"), (int, float)) and a["alt_baro"] > 25000:
            continue                       # por encima de 25.000 pies vuela la aviación de línea
        x, y = AX * a["lon"] + BX, AY * a["lat"] + BY
        if not (0 < x < 760 and 0 < y < 920):
            continue
        alt = a.get("alt_baro")
        suelo = alt == "ground"
        alt_ft = None if suelo or not isinstance(alt, (int, float)) else int(alt)
        out.append({"x": round(x, 1), "y": round(y, 1), "la": round(a["lat"], 4), "lo": round(a["lon"], 4), "t": a.get("t"), "a": alt_ft, "g": 1 if suelo else 0,
                    "v": round(a["gs"]) if isinstance(a.get("gs"), (int, float)) else None, "c": round(a["track"]) if isinstance(a.get("track"), (int, float)) else None,
                    "mil": 1 if (a.get("dbFlags") or 0) & 1 else 0, "s": a.get("seen") if isinstance(a.get("seen"), (int, float)) else None})
    res = {"hora_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "fuente": "adsb.lol (ADS-B abierto, ODbL)", "celdas": total_pedidos, "celdas_ok": respondieron,
           "n_todas": len(vistos), "n_livianas": len(out), "ac": out}
    Path(sys.argv[1]).parent.mkdir(parents=True, exist_ok=True)
    Path(sys.argv[1]).write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")
    print("Aeronaves visibles %d, livianas/medianas en el recuadro %d (celdas ok %d/%d)" % (len(vistos), len(out), respondieron, total_pedidos))
    return 0


if __name__ == "__main__":
    sys.exit(main())
