#!/usr/bin/env python3
"""Capa viva: posiciones de AIS de todo el corredor, para actualizarse cada pocos minutos sin reconstruir la página (8 MB).
Pide los mismos cinco tramos que la captura horaria (Open Waters AIS: AISHub y aisstream.io), se queda con lo visto en los últimos
VIVO_MAX_MIN minutos y escribe un JSON compacto (unas decenas de KB) que el mapa lee cada minuto. La clasificación (color, buque del Estado)
es la misma de la página horaria (sitio/buques.py).
Si ningún tramo responde, NO escribe nada y sale con error: es mejor que el mapa siga con lo último bueno, con su hora, que mostrar vacío.
Uso: vivo.py SALIDA.json"""
import datetime
import json
import os
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent / "sitio"))
import ais_vivo  # noqa: E402
from buques import categoria_ais, es_estado  # noqa: E402

P = json.loads((AQUI.parent / "sitio" / "datos" / "proyeccion.json").read_text(encoding="utf-8"))
MAX_MIN = int(os.environ.get("VIVO_MAX_MIN", "120"))


def main():
    destino = Path(sys.argv[1])
    ahora = datetime.datetime.now(datetime.timezone.utc)
    por_mmsi, tramos = {}, []
    for nombre, bbox in ais_vivo.TRAMOS.items():
        estado, resp = ais_vivo.pedir(bbox)
        if estado != 200 or not isinstance(resp, dict):
            tramos.append({"tramo": nombre, "ok": False})
            print("  %s -> ERROR %s" % (nombre, str(resp)[:80]), flush=True)
            continue
        n = 0
        for f in resp.get("features", []):
            p = f.get("properties") or {}
            seen = p.get("seen")
            try:
                edad = (ahora - datetime.datetime.strptime(seen, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)).total_seconds() / 60
            except Exception:
                continue
            if edad > MAX_MIN:
                continue
            lon, lat = f["geometry"]["coordinates"]
            mmsi = str(f.get("id") or p.get("mmsi"))
            nombre_b = (p.get("name") or "").strip() or None
            punto = {"nombre": nombre_b, "bandera": p.get("flag"), "tipo_ais": p.get("type")}
            categoria, color = categoria_ais(p.get("type"))
            anterior = por_mmsi.get(mmsi)
            if anterior and anterior["s"] >= seen:
                continue
            por_mmsi[mmsi] = {"i": mmsi, "x": round(P["ax"] * lon + P["bx"], 1), "y": round(P["ay"] * lat + P["by"], 1), "la": round(lat, 5), "lo": round(lon, 5),
                              "c": p.get("cog"), "k": color, "t": categoria, "n": nombre_b, "b": p.get("flag"), "v": p.get("sog"),
                              "d": (p.get("destination") or "").strip() or None, "q": p.get("draught"), "e": p.get("eta"), "l": p.get("length"),
                              "s": seen, "u": 1 if es_estado(punto) else 0}
            n += 1
        tramos.append({"tramo": nombre, "ok": True, "n": n})
        print("  %s -> %d" % (nombre, n), flush=True)
    if not any(t["ok"] for t in tramos) or not por_mmsi:
        print("Ningún tramo respondió: no se escribe nada.")
        return 1
    salida = {"hora_utc": ahora.strftime("%Y-%m-%dT%H:%M:%SZ"), "vigencia_min": MAX_MIN,
              "fuente": "AIS vía Open Waters (AISHub y aisstream.io). Posiciones tal como las transmiten los buques; sin validar.",
              "tramos": tramos, "n": len(por_mmsi), "buques": list(por_mmsi.values())}
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(salida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")
    print("Capa viva de %s: %d embarcaciones (vistas en los últimos %d min), %d KB." % (salida["hora_utc"], len(por_mmsi), MAX_MIN, destino.stat().st_size // 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
