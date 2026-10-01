#!/usr/bin/env python3
"""Registro de embarcaciones del corredor, para trazabilidad (fuente: Global Fishing Watch).

Este código es público. Los DATOS que produce van a un repositorio PRIVADO
(`ysyry-registro`) y nunca a este. Cada evento se guarda tal como lo devuelve la
fuente, con su origen, la fecha de obtención, la licencia y la atribución.

Escribe en DATOS_DIR (por defecto `datos`):
  eventos/AAAA-MM.jsonl  un evento por línea, sin repetir por id
  embarcaciones.json     índice: id de la embarcación -> identidad y primera/última vez vista
  estado.json            marca de la última corrida

NUNCA imprime identidades: la salida sólo trae conteos.

Variables de entorno: GFW_TOKEN (obligatoria), DIAS (30), EVENTOS (visitas|todos),
DATOS_DIR (datos).

Fuente: Global Fishing Watch, CC BY-NC 4.0, sólo uso no comercial.
Atribución exigida: «Powered by Global Fishing Watch».
"""
import datetime
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gfw_resumen import BASE, TRAMOS, caja, llamar_cuerpo  # noqa: E402

PAGINA = 500

DATASETS = {
    "VISITA_A_PUERTO": "public-global-port-visits-events:latest",
    "ENCUENTRO": "public-global-encounters-events:latest",
    "MERODEO": "public-global-loitering-events:latest",
    "APAGADO_AIS": "public-global-gaps-events:latest",
    "PESCA": "public-global-fishing-events:latest",
}

FUENTE = {
    "nombre": "Global Fishing Watch",
    "api": BASE + "/events",
    "licencia": "CC BY-NC 4.0",
    "atribucion": "Powered by Global Fishing Watch",
}


def cargar_ids(carpeta):
    ids = set()
    for f in (carpeta / "eventos").glob("*.jsonl"):
        with open(f, encoding="utf-8") as fh:
            for linea in fh:
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    ids.add(json.loads(linea)["evento"]["id"])
                except Exception:
                    pass
    return ids


def guardar_indice(ruta, indice):
    with open(ruta, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(indice, fh, ensure_ascii=False, indent=1, sort_keys=True)


def actualizar_indice(indice, evento, tramo):
    buque = evento.get("vessel") or {}
    clave = buque.get("id") or buque.get("ssvid")
    if not clave:
        return
    r = indice.setdefault(clave, {
        "nombre": buque.get("name"), "bandera": buque.get("flag"), "ssvid": buque.get("ssvid"),
        "tipo": buque.get("type"), "visto_primera": None, "visto_ultima": None,
        "eventos": 0, "tramos": [],
    })
    for c, k in (("nombre", "name"), ("bandera", "flag"), ("ssvid", "ssvid"), ("tipo", "type")):
        if not r.get(c) and buque.get(k):
            r[c] = buque[k]
    for t in (evento.get("start"), evento.get("end")):
        if t:
            if not r["visto_primera"] or t < r["visto_primera"]:
                r["visto_primera"] = t
            if not r["visto_ultima"] or t > r["visto_ultima"]:
                r["visto_ultima"] = t
    r["eventos"] += 1
    if tramo not in r["tramos"]:
        r["tramos"].append(tramo)


def main():
    token = os.environ.get("GFW_TOKEN", "")
    if not token:
        print("SIN CLAVE: GFW_TOKEN está vacío")
        return 1
    dias = int(os.environ.get("DIAS", "30"))
    cuales = os.environ.get("EVENTOS", "visitas")
    carpeta = Path(os.environ.get("DATOS_DIR", "datos"))
    (carpeta / "eventos").mkdir(parents=True, exist_ok=True)
    ruta_indice = carpeta / "embarcaciones.json"
    indice = json.load(open(ruta_indice, encoding="utf-8")) if ruta_indice.exists() else {}
    ids = cargar_ids(carpeta)

    ahora = datetime.datetime.now(datetime.timezone.utc)
    obtenido = ahora.strftime("%Y-%m-%dT%H:%M:%SZ")
    hasta = (ahora.date() + datetime.timedelta(days=1)).isoformat()
    desde = (ahora.date() - datetime.timedelta(days=dias)).isoformat()
    tipos = ["VISITA_A_PUERTO"] if cuales == "visitas" else list(DATASETS)
    print("Ventana %s a %s | tipos: %s | eventos ya guardados: %d" % (desde, hasta, ", ".join(tipos), len(ids)), flush=True)

    nuevos_total = 0
    errores = 0
    for tipo in tipos:
        ds = DATASETS[tipo]
        for tramo, b in TRAMOS.items():
            offset = 0
            vistos = nuevos = 0
            por_mes = {}
            while True:
                cuerpo = {"datasets": [ds], "startDate": desde, "endDate": hasta, "geometry": caja(b)}
                t0 = time.time()
                estado, resp = llamar_cuerpo(token, "/events?offset=%d&limit=%d" % (offset, PAGINA), cuerpo)
                if estado not in (200, 201) or not isinstance(resp, dict):
                    errores += 1
                    print("  %s | %s | HTTP %s: %s" % (tipo, tramo, estado, str(resp)[:120]), flush=True)
                    break
                entradas = resp.get("entries", [])
                for e in entradas:
                    vistos += 1
                    eid = e.get("id")
                    if not eid or eid in ids:
                        continue
                    ids.add(eid)
                    nuevos += 1
                    mes = (e.get("start") or obtenido)[:7]
                    por_mes.setdefault(mes, []).append({
                        "tipo": tipo, "tramo": tramo, "evento": e,
                        "fuente": dict(FUENTE, dataset=ds, obtenido=obtenido),
                    })
                    actualizar_indice(indice, e, tramo)
                siguiente = resp.get("nextOffset")
                print("  %s | %s | offset %d: %d traídos [%.0fs]" % (tipo, tramo, offset, len(entradas), time.time() - t0), flush=True)
                if not entradas or len(entradas) < PAGINA or siguiente is None:
                    break
                offset = siguiente
            for mes, filas in por_mes.items():
                with open(carpeta / "eventos" / (mes + ".jsonl"), "a", encoding="utf-8", newline="\n") as fh:
                    for fila in filas:
                        fh.write(json.dumps(fila, ensure_ascii=False, sort_keys=True) + "\n")
            guardar_indice(ruta_indice, indice)
            nuevos_total += nuevos
            print("%s | %s: %d vistos, %d nuevos" % (tipo, tramo, vistos, nuevos), flush=True)

    with open(carpeta / "estado.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"ultima_corrida": obtenido, "ventana": [desde, hasta], "tipos": tipos,
                   "nuevos": nuevos_total, "embarcaciones_distintas": len(indice)}, fh, ensure_ascii=False, indent=1)
    print("\nNuevos: %d | embarcaciones distintas en el índice: %d | errores: %d" % (nuevos_total, len(indice), errores))
    print("Fuente: Global Fishing Watch (CC BY-NC 4.0). Powered by Global Fishing Watch.")
    return 0 if errores == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
