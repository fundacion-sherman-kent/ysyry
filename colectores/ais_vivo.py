#!/usr/bin/env python3
"""Posiciones de embarcaciones en vivo, vía AISstream.io (WebSocket).

Escrito contra el protocolo público y documentado de AISstream.io
(https://aisstream.io/documentation) — no copia código de ningún repositorio
de terceros. Guarda sólo en el repositorio PRIVADO de registro, igual que el
colector de GFW. No imprime identidades; sólo conteos.

Fuente: AISstream.io. No se encontró una página de términos de servicio
separada de su documentación y su política de privacidad — sin verificar
restricciones de uso institucional. Se usa con esa reserva anotada.

Variables de entorno:
  AISSTREAM_KEY   obligatoria — clave de cuenta gratuita de AISstream.io
  DURACION        segundos que escucha antes de cortar (por defecto 60)
  DATOS_DIR       carpeta de salida (por defecto "datos")
"""
import datetime
import json
import os
import sys
import time
from pathlib import Path

try:
    import websocket  # websocket-client, MIT — se declara como dependencia, no se embebe
except ImportError:
    print("Falta el paquete 'websocket-client' (pip install websocket-client)")
    sys.exit(1)

URL = os.environ.get("AIS_WS_URL", "wss://stream.aisstream.io/v0/stream")
# Alternativa compatible, sin cuenta: wss://ais.openwaters.io/v0/stream

# Mismos cinco tramos que el colector de GFW, como [[lat_min,lon_min],[lat_max,lon_max]]
TRAMOS = {
    "1 Alto Paraguay (Cáceres-Corumbá)": [[-19.3, -58.4], [-15.8, -56.8]],
    "2 Medio Paraguay (Corumbá-Asunción)": [[-25.5, -58.3], [-19.0, -57.0]],
    "3 Paraguay-Paraná (Asunción-Corrientes)": [[-27.7, -59.0], [-25.2, -57.4]],
    "4 Paraná medio (Corrientes-Rosario)": [[-33.2, -61.0], [-27.3, -58.3]],
    "5 Paraná inferior y Delta (Rosario-Río de la Plata)": [[-34.95, -60.9], [-32.9, -57.6]],
}


def main():
    clave = os.environ.get("AISSTREAM_KEY", "")
    if not clave:
        print("SIN CLAVE: AISSTREAM_KEY está vacía")
        return 1
    duracion = int(os.environ.get("DURACION", "60"))
    carpeta = Path(os.environ.get("DATOS_DIR", "datos"))
    (carpeta / "vivo").mkdir(parents=True, exist_ok=True)

    cajas = [[[lo[0], lo[1]], [hi[0], hi[1]]] for lo, hi in TRAMOS.values()]

    conteo_por_tramo = {t: 0 for t in TRAMOS}
    embarcaciones_distintas = set()
    eventos = []  # sólo en memoria durante la corrida; se escribe al final

    def dentro_de_tramo(lat, lon):
        for nombre, (lo, hi) in TRAMOS.items():
            if lo[0] <= lat <= hi[0] and lo[1] <= lon <= hi[1]:
                return nombre
        return None

    ws = websocket.create_connection(URL, timeout=15)
    try:
        ws.send(json.dumps({
            "APIKey": clave,
            "BoundingBoxes": cajas,
            "FilterMessageTypes": ["PositionReport"],
        }))
        inicio = time.time()
        print("Conectado. Escuchando %d s en los cinco tramos del corredor..." % duracion, flush=True)
        while time.time() - inicio < duracion:
            ws.settimeout(max(1, duracion - (time.time() - inicio)))
            try:
                raw = ws.recv()
            except Exception:
                break
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            if msg.get("MessageType") != "PositionReport":
                continue
            pr = msg.get("Message", {}).get("PositionReport", {})
            meta = msg.get("MetaData", {})
            lat, lon = pr.get("Latitude"), pr.get("Longitude")
            if lat is None or lon is None:
                continue
            tramo = dentro_de_tramo(lat, lon)
            if not tramo:
                continue
            conteo_por_tramo[tramo] += 1
            mmsi = meta.get("MMSI")
            if mmsi:
                embarcaciones_distintas.add(mmsi)
            eventos.append({
                "obtenido": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "tramo": tramo,
                "mmsi": mmsi,
                "lat": lat, "lon": lon,
                "rumbo": pr.get("Cog"), "velocidad": pr.get("Sog"),
                "fuente": {"nombre": "AISstream.io", "protocolo": "WebSocket v0/stream"},
            })
    finally:
        ws.close()

    mes = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m")
    if eventos:
        with open(carpeta / "vivo" / (mes + ".jsonl"), "a", encoding="utf-8", newline="\n") as fh:
            for e in eventos:
                fh.write(json.dumps(e, ensure_ascii=False, sort_keys=True) + "\n")

    print("\nPosiciones por tramo, últimos %d s:" % duracion)
    for t, n in conteo_por_tramo.items():
        print("  %s: %d" % (t, n))
    print("Embarcaciones distintas (MMSI) vistas:", len(embarcaciones_distintas))
    print("Fuente: AISstream.io. Términos de reutilización no verificados aparte de su documentación.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
