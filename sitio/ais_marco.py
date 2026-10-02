#!/usr/bin/env python3
"""Suma la captura horaria de AIS al historial que usa el sitio.

Consulta Open Waters AIS (todas sus fuentes: AISHub y aisstream.io; decisión de la dirección,
2/10/2026) en los mismos cinco tramos que el colector, arma un cuadro con una posición por MMSI y
lo agrega a marcos.json, conservando los últimos CUADROS. Si ya hay un cuadro de esta misma hora, lo
reemplaza. Si ningún tramo responde, NO toca el archivo y sale con error: mejor que el sitio siga
mostrando la última captura buena, con su fecha, a que muestre una vacía.

Uso: python3 ais_marco.py RUTA/marcos.json
"""
import datetime
import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "colectores"))
import ais_vivo  # noqa: E402

CUADROS = 24
P = json.loads((AQUI / "datos" / "proyeccion.json").read_text(encoding="utf-8"))


def capturar():
    por_mmsi = {}
    ok = 0
    for nombre, (lo_lat, lo_lon, hi_lat, hi_lon) in ais_vivo.TRAMOS.items():
        estado, resp = ais_vivo.pedir((lo_lat, lo_lon, hi_lat, hi_lon))
        if estado != 200 or not isinstance(resp, dict):
            print("  %s -> ERROR %s" % (nombre, str(resp)[:100]), flush=True)
            continue
        ok += 1
        for f in resp.get("features", []):
            p = f.get("properties") or {}
            lon, lat = f["geometry"]["coordinates"]
            mmsi = str(f.get("id") or p.get("mmsi"))
            por_mmsi[mmsi] = {
                "x": round(P["ax"] * lon + P["bx"], 1), "y": round(P["ay"] * lat + P["by"], 1),
                "cog": p.get("cog"), "nombre": (p.get("name") or "").strip() or None, "bandera": p.get("flag"),
                "tipo_ais": p.get("type"), "destino": (p.get("destination") or "").strip() or None,
                "velocidad": p.get("sog"), "callsign": (p.get("callsign") or "").strip() or None,
                "imo": p.get("imo") or None, "visto": p.get("seen"), "fuente": p.get("source")}
        print("  %s -> %d" % (nombre, len(resp.get("features", []))), flush=True)
    return ok, list(por_mmsi.values())


def main():
    ruta = Path(sys.argv[1])
    cuadros = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else []
    ok, puntos = capturar()
    if ok == 0 or not puntos:
        print("Ningún tramo respondió: se conserva el historial sin cambios.")
        return 1
    hora = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:00:00Z")
    cuadros = [c for c in cuadros if c["hora"] != hora] + [{"hora": hora, "puntos": puntos}]
    cuadros.sort(key=lambda c: c["hora"])
    cuadros = cuadros[-CUADROS:]
    ruta.write_text(json.dumps(cuadros, ensure_ascii=False), encoding="utf-8")
    print("Captura de %s: %d embarcaciones; historial: %d cuadros." % (hora, len(puntos), len(cuadros)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
