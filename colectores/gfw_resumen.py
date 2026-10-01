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
TIEMPO = 120  # segundos por consulta: las de geometría tardan de 30 a 70 s
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
    "ENCUENTROS": ["public-global-encounters-events:latest"],
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
            if estado in (200, 201) and isinstance(resp, dict):
                return resp.get("total"), f"{ds}{' (paginación en cuerpo)' if en_cuerpo else ''}"
            ultimo = f"HTTP {estado}: {resp}"
            if estado not in (400, 422):
                break
    return None, ultimo


def pedir(token, metodo, ruta, cuerpo=None, tiempo=None):
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
        with urllib.request.urlopen(req, timeout=tiempo or TIEMPO) as r:
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
    # Caja chica alrededor de Rosario (puerto grande del tramo inferior).
    chica = caja((-60.9, -33.1, -60.5, -32.7))
    cuerpo_g = {"datasets": [enc], "startDate": desde, "endDate": hasta, "geometry": g}
    cuerpo_c = {"datasets": [enc], "startDate": desde, "endDate": hasta, "geometry": chica}
    variantes = [
        ("F POST encuentros, caja chica (Rosario), 7 días", "POST", "/events?offset=0&limit=1",
         dict(cuerpo_c, startDate=(hoy - datetime.timedelta(days=7)).isoformat()), 100),
        ("G POST encuentros, caja chica (Rosario), 30 días", "POST", "/events?offset=0&limit=1", cuerpo_c, 100),
        ("H POST encuentros, tramo 5 completo, 30 días", "POST", "/events?offset=0&limit=1", cuerpo_g, 100),
    ]
    print("DIAGNÓSTICO de la consulta de eventos con geometría (sólo códigos y tiempos)\n", flush=True)
    for nombre, metodo, ruta, cuerpo, tiempo in variantes:
        t0 = time.time()
        estado, texto = pedir(token, metodo, ruta, cuerpo, tiempo)
        print("%s -> HTTP %s [%.1fs] %s" % (nombre, estado, time.time() - t0, texto), flush=True)
    return 0


def demora(token):
    """Mide cuánto tarda GFW en publicar una visita a puerto, en el tramo 5.

    Trae los eventos de los últimos 2 días SÓLO EN MEMORIA y escribe en la
    salida: la hora actual, la hora del evento más reciente y la demora; el
    conteo por tipo de buque; y los NOMBRES de los campos (no sus valores).
    No imprime ni guarda identidades de buques.
    """
    hoy = datetime.datetime.now(datetime.timezone.utc)
    hasta = (hoy.date() + datetime.timedelta(days=1)).isoformat()
    g = caja(TRAMOS["5 Paraná inferior y Delta (Rosario-Río de la Plata)"])
    resp = None
    # Se amplía la ventana hacia atrás hasta encontrar el primer evento.
    for d in (2, 4, 7, 10, 14, 21, 30, 45, 60):
        desde = (hoy.date() - datetime.timedelta(days=d)).isoformat()
        cuerpo = {"datasets": ["public-global-port-visits-events:latest"],
                  "startDate": desde, "endDate": hasta, "geometry": g}
        t0 = time.time()
        estado, resp = llamar_cuerpo(token, "/events?offset=0&limit=500", cuerpo)
        total = resp.get("total") if isinstance(resp, dict) else None
        print("Últimos %2d días: HTTP %s total=%s [%.1fs]" % (d, estado, total, time.time() - t0), flush=True)
        if estado in (200, 201) and isinstance(resp, dict) and resp.get("entries"):
            break
    if not isinstance(resp, dict):
        print("sin dato:", str(resp)[:200])
        return 1
    entradas = resp.get("entries", [])
    print("Hora actual (UTC): %s" % hoy.strftime("%Y-%m-%dT%H:%M:%SZ"))
    print("Eventos en la ventana: total=%s, traídos=%d" % (resp.get("total"), len(entradas)))
    if resp.get("total") and resp["total"] > len(entradas):
        print("AVISO: hay más eventos que los traídos; el máximo puede estar incompleto.")

    def a_fecha(t):
        try:
            return datetime.datetime.fromisoformat(t.replace("Z", "+00:00"))
        except Exception:
            return None

    inicios = [f for f in (a_fecha(e.get("start", "")) for e in entradas) if f]
    fines = [f for f in (a_fecha(e.get("end", "") or "") for e in entradas) if f]
    if inicios:
        ult = max(inicios)
        print("Inicio más reciente: %s (hace %.1f h)" % (ult.strftime("%Y-%m-%dT%H:%M:%SZ"), (hoy - ult).total_seconds() / 3600))
    if fines:
        ulf = max(fines)
        print("Fin más reciente: %s (hace %.1f h)" % (ulf.strftime("%Y-%m-%dT%H:%M:%SZ"), (hoy - ulf).total_seconds() / 3600))
    abiertos = sum(1 for e in entradas if not e.get("end"))
    print("Eventos sin hora de fin (visita abierta): %d" % abiertos)
    tipos = {}
    for e in entradas:
        t = (e.get("vessel") or {}).get("type") or "(sin tipo)"
        tipos[t] = tipos.get(t, 0) + 1
    print("Por tipo de buque (conteo):", json.dumps(dict(sorted(tipos.items(), key=lambda x: -x[1])), ensure_ascii=False))
    if entradas:
        e0 = entradas[0]
        print("Campos del evento:", sorted(e0.keys()))
        print("Campos del buque:", sorted((e0.get("vessel") or {}).keys()))
        pv = e0.get("port_visit") or e0.get("portVisit") or {}
        if pv:
            print("Campos de la visita:", sorted(pv.keys()))
    return 0


def llamar_cuerpo(token, ruta, cuerpo):
    """POST suelto que devuelve (estado, JSON o texto corto)."""
    req = urllib.request.Request(
        BASE + ruta,
        data=json.dumps(cuerpo).encode(),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIEMPO) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]
    except Exception as e:
        return 0, str(e)[:200]


def main():
    token = os.environ.get("GFW_TOKEN", "")
    if not token:
        print("SIN CLAVE: GFW_TOKEN está vacío")
        return 1
    if os.environ.get("MODO") == "demora":
        return demora(token)
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
