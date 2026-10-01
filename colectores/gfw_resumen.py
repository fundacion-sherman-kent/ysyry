#!/usr/bin/env python3
"""Cuenta eventos de Global Fishing Watch por tramo del corredor de la Hidrovía.

NO guarda datos crudos: pide sólo el total (limit=1) y no baja ningún evento.
Lo que imprime son conteos por tramo y tipo de evento, nada más.

Los tramos son cajas aproximadas, inferidas de la ubicación de las ciudades
puerto. NO son el trazado oficial de la vía navegable: un evento dentro de la
caja puede no estar sobre el río. Hay que refinarlas antes de publicar nada.

Fuente: Global Fishing Watch, CC BY-NC 4.0, sólo uso no comercial.
La clave llega por la variable de entorno GFW_TOKEN y nunca se imprime.
"""
import datetime
import json
import time
import os
import sys
import urllib.error
import urllib.request

BASE = "https://gateway.api.globalfishingwatch.org/v3"
# Nos identificamos con nombre: el filtro de Cloudflare rechaza el cliente anónimo de Python.
USER_AGENT = "Ysyry/0.1 (Fundacion Sherman Kent; +https://github.com/fundacion-sherman-kent/ysyry)"
DIAS = int(os.environ.get("DIAS", "90"))
TIEMPO = 25  # segundos por consulta; si GFW demora más, se anota y se sigue
SOLO_PRUEBA = os.environ.get("PRUEBA") == "1"  # una sola consulta, para medir tiempo y respuesta

# (lon_min, lat_min, lon_max, lat_max). Aproximadas.
TRAMOS = {
    "1 Alto Paraguay (Cáceres-Corumbá)": (-58.4, -19.3, -56.8, -15.8),
    "2 Medio Paraguay (Corumbá-Asunción)": (-58.3, -25.5, -57.0, -19.0),
    "3 Paraguay-Paraná (Asunción-Corrientes)": (-59.0, -27.7, -57.4, -25.2),
    "4 Paraná medio (Corrientes-Rosario)": (-61.0, -33.2, -58.3, -27.3),
    "5 Paraná inferior y Delta (Rosario-Río de la Plata)": (-60.9, -34.95, -57.6, -32.9),
}

# Cada tipo con los nombres de dataset a probar, en orden.
TIPOS = {
    "ENCUENTROS": ["public-global-encounters-events:latest", "public-global-encounter-events:latest"],
    "MERODEOS": ["public-global-loitering-events:latest"],
    "APAGADOS AIS": ["public-global-gaps-events:latest"],
    "VISITAS A PUERTO": ["public-global-port-visits-events:latest"],
}


def caja(b):
    x0, y0, x1, y1 = b
    return {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}


def llamar(token, dataset, geometria, desde, hasta, paginacion_en_cuerpo=False):
    cuerpo = {"datasets": [dataset], "startDate": desde, "endDate": hasta, "geometry": geometria}
    url = BASE + "/events"
    if paginacion_en_cuerpo:
        cuerpo.update({"offset": 0, "limit": 1})
    else:
        url += "?offset=0&limit=1"
    req = urllib.request.Request(
        url,
        data=json.dumps(cuerpo).encode(),
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIEMPO) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            texto = e.read().decode()[:200]
        except Exception:
            texto = ""
        return e.code, texto
    except Exception as e:  # red, tiempo de espera
        return 0, str(e)[:200]


def contar(token, nombres, geometria, desde, hasta):
    """Devuelve (total o None, nota). Prueba cada nombre de dataset y las dos formas de paginar."""
    ultimo = ""
    for ds in nombres:
        for en_cuerpo in (False, True):
            estado, resp = llamar(token, ds, geometria, desde, hasta, en_cuerpo)
            if estado == 200 and isinstance(resp, dict):
                return resp.get("total"), f"{ds}{' (paginación en cuerpo)' if en_cuerpo else ''}"
            ultimo = f"HTTP {estado}: {resp}"
            if estado not in (400, 422):
                break
    return None, ultimo


def pedir(token, metodo, ruta, cuerpo=None):
    """Una llamada suelta; devuelve (estado, texto corto). Para el diagnóstico."""
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(
        BASE + ruta,
        data=datos,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method=metodo,
    )
    try:
        with urllib.request.urlopen(req, timeout=TIEMPO) as r:
            texto = r.read().decode()
            try:
                j = json.loads(texto)
                return r.status, "total=%s entradas=%s" % (j.get("total"), len(j.get("entries", [])))
            except Exception:
                return r.status, texto[:80]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:160].replace("\n", " ")
    except Exception as e:
        return 0, str(e)[:120]


def diagnostico(token):
    """Prueba variantes de la consulta de eventos para saber cuál acepta la API."""
    hoy = datetime.datetime.now(datetime.timezone.utc).date()
    desde = (hoy - datetime.timedelta(days=30)).isoformat()
    hasta = (hoy + datetime.timedelta(days=1)).isoformat()
    g = caja(TRAMOS["5 Paraná inferior y Delta (Rosario-Río de la Plata)"])
    enc = "public-global-encounters-events:latest"
    enc1 = "public-global-encounter-events:latest"
    pesca = "public-global-fishing-events:latest"
    qs = "?offset=0&limit=1&start-date=%s&end-date=%s" % (desde, hasta)
    variantes = [
        ("A GET  eventos pesca (el ejemplo de la documentación)", "GET", "/events?datasets[0]=" + pesca + "&offset=0&limit=1", None),
        ("B GET  encuentros (plural) con fechas", "GET", "/events?datasets[0]=" + enc + qs.replace("?", "&"), None),
        ("C GET  encuentros (singular) con fechas", "GET", "/events?datasets[0]=" + enc1 + qs.replace("?", "&"), None),
        ("D POST encuentros (plural) con geometría", "POST", "/events?offset=0&limit=1",
         {"datasets": [enc], "startDate": desde, "endDate": hasta, "geometry": g}),
        ("E POST pesca con geometría", "POST", "/events?offset=0&limit=1",
         {"datasets": [pesca], "startDate": desde, "endDate": hasta, "geometry": g}),
    ]
    print("DIAGNÓSTICO de la consulta de eventos (sólo códigos de respuesta)\n", flush=True)
    for nombre, metodo, ruta, cuerpo in variantes:
        t0 = time.time()
        estado, texto = pedir(token, metodo, ruta, cuerpo)
        print("%s -> HTTP %s [%.1fs] %s" % (nombre, estado, time.time() - t0, texto), flush=True)
    return 0


def main():
    token = os.environ.get("GFW_TOKEN", "")
    if not token:
        print("SIN CLAVE: GFW_TOKEN está vacío")
        return 1
    if os.environ.get("DIAGNOSTICO") == "1":
        return diagnostico(token)
    hoy = datetime.datetime.now(datetime.timezone.utc).date()
    desde = (hoy - datetime.timedelta(days=DIAS)).isoformat()
    hasta = (hoy + datetime.timedelta(days=1)).isoformat()
    print(f"Ventana: {desde} a {hasta} (fin exclusivo). Conteos, sin datos crudos.\n")
    ok = 0
    for nombre, b in TRAMOS.items():
        print(nombre, flush=True)
        for tipo, nombres in TIPOS.items():
            t0 = time.time()
            total, nota = contar(token, nombres, caja(b), desde, hasta)
            seg = time.time() - t0
            if total is None:
                print(f"   {tipo:<17} sin dato  ({nota}) [{seg:.1f}s]", flush=True)
            else:
                ok += 1
                print(f"   {tipo:<17} {total}  [{seg:.1f}s]", flush=True)
            if SOLO_PRUEBA:
                print("\nPRUEBA: una sola consulta, se corta acá.")
                return 0 if ok else 1
    print("\nFuente: Global Fishing Watch (CC BY-NC 4.0), sólo uso no comercial.")
    print("Tramos: cajas aproximadas, no el trazado oficial de la vía.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
