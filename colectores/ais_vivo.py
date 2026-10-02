#!/usr/bin/env python3
"""Posiciones de embarcaciones en vivo, vía la API de Open Waters AIS.

Open Waters (openwaters.io/ais) agrega dos redes comunitarias — AISHub y
aisstream.io — en un solo endpoint HTTP, sin necesidad de clave para leer.
Escrito contra su protocolo público y documentado, sin copiar código de
ningún repositorio de terceros.

Además de los eventos crudos, mantiene un índice de identidades por MMSI
(datos/identidades-ais.json) con el número IMO, que identifica de verdad un
casco (el nombre se repite entre buques distintos). Sólo lo transmiten las
embarcaciones de clase A; las menores no. Un IMO se guarda únicamente si pasa
su dígito de control (7 dígitos; el último verifica a los seis primeros).

Guarda sólo en el repositorio PRIVADO de registro. No imprime identidades;
sólo conteos. Si el servidor responde con un error, se informa como tal,
nunca se confunde con "no hay buques".

Fuente: Open Waters AIS <https://openwaters.io/ais/>, que a su vez atribuye
a AISHub <https://www.aishub.net> y a aisstream.io. Términos de reutilización
institucional no verificados aparte de su documentación pública.

Variables de entorno:
  DATOS_DIR   carpeta de salida (por defecto "datos")
  AIS_API     base de la API (por defecto la de Open Waters)
"""
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = os.environ.get("AIS_API", "https://ais.openwaters.io/v1/vessels")
USER_AGENT = "Ysyry/0.1 (Fundacion Sherman Kent; +https://github.com/fundacion-sherman-kent/ysyry)"

TRAMOS = {
    "1 Alto Paraguay (Cáceres-Corumbá)": (-19.3, -58.4, -15.8, -56.8),
    "2 Medio Paraguay (Corumbá-Asunción)": (-25.5, -58.3, -19.0, -57.0),
    "3 Paraguay-Paraná (Asunción-Corrientes)": (-27.7, -59.0, -25.2, -57.4),
    "4 Paraná medio (Corrientes-Rosario)": (-33.2, -61.0, -27.3, -58.3),
    "5 Paraná inferior y Delta (Rosario-Río de la Plata)": (-34.95, -60.9, -32.9, -57.6),
}


CAMPOS_IDENTIDAD = ("name", "callsign", "flag", "type", "length", "beam")


def imo_valido(valor):
    """IMO de 7 dígitos con dígito de control correcto; si no, None."""
    try:
        s = str(int(valor))
    except (TypeError, ValueError):
        return None
    if len(s) != 7:
        return None
    suma = sum(int(c) * w for c, w in zip(s[:6], range(7, 1, -1)))
    return int(s) if suma % 10 == int(s[6]) else None


def actualizar_identidades(indice, evento, obtenido):
    """Funde un evento en el índice. Nunca pisa un dato conocido con uno vacío.
    Devuelve True si el MMSI es nuevo en el índice."""
    p = evento.get("properties") or {}
    mmsi = str(evento.get("id") or p.get("mmsi") or "")
    if not mmsi:
        return False
    nuevo = mmsi not in indice
    reg = indice.setdefault(mmsi, {"visto_primera": obtenido})
    reg["visto_ultima"] = max(obtenido, reg.get("visto_ultima", obtenido))
    reg["visto_primera"] = min(obtenido, reg["visto_primera"])
    for campo in CAMPOS_IDENTIDAD:
        v = p.get(campo)
        if v not in (None, "", 0):
            reg[campo] = v.strip() if isinstance(v, str) else v
    crudo = p.get("imo")
    imo = imo_valido(crudo)
    if imo:
        if reg.get("imo") and reg["imo"] != imo:
            anteriores = reg.setdefault("imo_anteriores", [])
            if reg["imo"] not in anteriores:
                anteriores.append(reg["imo"])
        reg["imo"] = imo
    elif crudo not in (None, "", 0):
        reg["imo_invalido_visto"] = True
    return nuevo


def cargar_indice(carpeta):
    """Lee el índice; si todavía no existe, lo reconstruye desde lo acumulado
    para no arrancar de cero y perder el historial."""
    ruta = carpeta / "identidades-ais.json"
    if ruta.exists():
        return json.loads(ruta.read_text(encoding="utf-8"))
    return indice_desde_vivo(carpeta)


def guardar_indice(carpeta, indice):
    ruta = carpeta / "identidades-ais.json"
    ruta.write_text(json.dumps(indice, ensure_ascii=False, sort_keys=True, indent=1) + chr(10),
                    encoding="utf-8", newline=chr(10))


def resumen_indice(indice):
    con_imo = sum(1 for r in indice.values() if r.get("imo"))
    return "Identidades en el índice: %d, con IMO válido: %d" % (len(indice), con_imo)


def indice_desde_vivo(carpeta):
    """Índice a partir de los eventos ya guardados (datos/vivo/*.jsonl)."""
    indice = {}
    for archivo in sorted((carpeta / "vivo").glob("*.jsonl")):
        with open(archivo, encoding="utf-8") as fh:
            for linea in fh:
                r = json.loads(linea)
                if "evento" in r:
                    actualizar_identidades(indice, r["evento"], r["obtenido"])
    return indice


def reconstruir(carpeta):
    indice = indice_desde_vivo(carpeta)
    guardar_indice(carpeta, indice)
    print(resumen_indice(indice))


def pedir(bbox):
    """(estado, dict|texto). Nunca confunde un error de red con 'sin buques'."""
    url = BASE + "?bbox=%s,%s,%s,%s" % bbox
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]
    except Exception as e:
        return 0, str(e)[:200]


def main():
    carpeta = Path(os.environ.get("DATOS_DIR", "datos"))
    (carpeta / "vivo").mkdir(parents=True, exist_ok=True)

    obtenido = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    mes = obtenido[:7]
    eventos = []
    conteo = {}
    embarcaciones = set()
    errores = 0
    indice = cargar_indice(carpeta)
    nuevos = 0

    for nombre, (lo_lat, lo_lon, hi_lat, hi_lon) in TRAMOS.items():
        t0 = time.time()
        estado, resp = pedir((lo_lat, lo_lon, hi_lat, hi_lon))
        if estado != 200 or not isinstance(resp, dict):
            errores += 1
            print("%s -> ERROR HTTP %s: %s [%.1fs]" % (nombre, estado, str(resp)[:150], time.time() - t0), flush=True)
            conteo[nombre] = None
            continue
        feats = resp.get("features", [])
        conteo[nombre] = len(feats)
        for f in feats:
            mmsi = f.get("id") or (f.get("properties") or {}).get("mmsi")
            if mmsi:
                embarcaciones.add(mmsi)
            nuevos += actualizar_identidades(indice, f, obtenido)
            eventos.append({"obtenido": obtenido, "tramo": nombre, "evento": f,
                             "fuente": {"nombre": "Open Waters AIS", "atribucion": resp.get("attribution")}})
        print("%s -> %d buques [%.1fs]" % (nombre, len(feats), time.time() - t0), flush=True)

    if eventos:
        with open(carpeta / "vivo" / (mes + ".jsonl"), "a", encoding="utf-8", newline="\n") as fh:
            for e in eventos:
                fh.write(json.dumps(e, ensure_ascii=False, sort_keys=True) + "\n")

    print("\nResumen:")
    for t, n in conteo.items():
        print("  %s: %s" % (t, "sin dato (error)" if n is None else n))
    if eventos:
        guardar_indice(carpeta, indice)
    print("Embarcaciones distintas vistas:", len(embarcaciones), "| nuevas en el índice:", nuevos)
    print(resumen_indice(indice))
    print("Fuente: Open Waters AIS (agrega AISHub + aisstream.io).")
    return 1 if errores == len(TRAMOS) else 0


if __name__ == "__main__":
    if "--reconstruir" in sys.argv:
        reconstruir(Path(os.environ.get("DATOS_DIR", "datos")))
        sys.exit(0)
    sys.exit(main())
