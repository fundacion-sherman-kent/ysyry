#!/usr/bin/env python3
"""Autoescala: propone actores, puntos y fuentes nuevos a partir de los datos reales; nunca los agrega solo.

No usa ningún modelo: son reglas sobre lo que ya recolecta Ysyry y comprobaciones de que detrás de una fuente candidata haya un dato
que responde. Cada propuesta entra «sin calificar» y la revisa una persona. Lo corre un flujo privado una vez por semana.

Uso: autoescala.py MARCOS.json SALIDA.md   (la raíz del código es la carpeta que contiene colectores/)"""
import collections
import json
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
UA = {"User-Agent": "Ysyry-FUSK/1.0 (+https://github.com/fundacion-sherman-kent/ysyry)"}
YA_MARCADAS = re.compile(r"^(ARA|GC|ARP|PGN)[\s\-]")
SOSPECHOSAS = re.compile(r"\b(PNA|PREF|PREFECTURA|ARMADA|NAVAL|GENDARM|POLICIA|PATRULL|PATROL|RESCATE|SALVAMENTO|SAR|BOMBEROS|MARINA)\b")
FUENTES_CANDIDATAS = [
    ("IODA (CAIDA), cortes de internet por región", "https://api.ioda.caida.org/v2/entities/query?entityType=country&entityCode=AR",
     "Cobertura de comunicaciones a nivel de región; falta confirmar la lista de regiones del corredor."),
    ("ANTAQ (Brasil), datos abiertos de transporte fluvial", "https://web3.antaq.gov.br/ea/sense/download.html",
     "Estadística de carga y movimiento portuario de Brasil."),
    ("ANA (Brasil), telemetría de ríos", "https://www.snirh.gov.br/hidroweb/",
     "Niveles del Río Paraguay y afluentes del lado brasileño; complementaría las estaciones de Paraguay con una segunda fuente."),
    ("Prefectura Naval Argentina, AIS y altura de río", "https://ais.prefecturanaval.gob.ar/",
     "Posición de buques y altura de río en vivo; requiere que la dirección complete el registro: sin acceso programático hoy."),
    ("DAHITI (TU München), nivel de ríos por satélite", "https://dahiti.dgfi.tum.de/en/",
     "Segunda familia (satelital) para el nivel del río; requiere registro gratuito, que hace la dirección."),
    ("CIH, Comité Intergubernamental de la Hidrovía", "http://hidrovia.org/",
     "Estadísticas oficiales de tráfico y carga; el certificado HTTPS estaba vencido."),
]


def norm(s):
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()).split())


def unidades_sospechosas(marcos):
    vistas = {}
    for m in marcos[-6:]:
        for p in m["puntos"]:
            nom = (p.get("nombre") or "").strip().upper()
            if not nom or YA_MARCADAS.match(nom) or p.get("tipo_ais") in (35, 55):
                continue
            razon = None
            if p.get("tipo_ais") in (51, 54, 58):
                razon = "tipo AIS %s (búsqueda y rescate, antipolución o transporte médico)" % p["tipo_ais"]
            elif SOSPECHOSAS.search(nom):
                razon = "el nombre contiene una palabra de fuerza o servicio de rescate"
            if razon:
                vistas[nom] = {"nombre": nom, "bandera": p.get("bandera") or "?", "tipo": p.get("tipo_ais"), "razon": razon, "visto": m["hora"]}
    return sorted(vistas.values(), key=lambda x: x["nombre"])


def destinos_sin_punto(marcos):
    d = json.load(open(RAIZ / "sitio" / "datos" / "mapa_v10.json", encoding="utf-8"))
    conocidos = {norm(q["nombre"]) for q in d["poi"]}
    try:
        for a in json.load(open(RAIZ / "sitio" / "datos" / "amarres_osm.json", encoding="utf-8")).get("items", []):
            if a and a[1]:
                conocidos.add(norm(a[1]))
    except Exception:
        pass
    cuenta = collections.Counter()
    ejemplos = {}
    for m in marcos[-6:]:
        vistos = set()
        for p in m["puntos"]:
            dest = re.sub(r" y esc.*$", "", re.sub(r"^(ar|pto|puerto) ", "", norm(p.get("destino")).replace("0", "o")))
            if len(dest) < 4 or dest in ("0", "00") or re.fullmatch(r"[0-9 ]+", dest) or dest in vistos:
                continue
            vistos.add(dest)
            cuenta[dest] += 1
            ejemplos.setdefault(dest, (p.get("destino") or "").strip())
    out = []
    for dest, n in cuenta.most_common(60):
        if any(dest in c or c in dest for c in conocidos if len(c) >= 4):
            continue
        if n >= 3:
            out.append({"destino": ejemplos[dest], "capturas": n})
    return out[:15]


def fuentes_que_responden():
    out = []
    for nombre, url, nota in FUENTES_CANDIDATAS:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25) as r:
                cuerpo = r.read(4000)
                out.append((nombre, url, nota, "responde HTTP %s, %d bytes leídos" % (r.status, len(cuerpo))))
        except Exception as e:
            out.append((nombre, url, nota, "NO responde desde este entorno: %s" % str(e)[:70]))
    return out


def main():
    marcos = json.load(open(sys.argv[1], encoding="utf-8"))
    L = ["# Autoescala: propuestas sin calificar\n",
         "Las generó el robot con reglas sobre los datos reales, **sin ningún modelo**. Ninguna se agregó sola: cada una espera que una persona la confirme o la descarte.\n"]
    u = unidades_sospechosas(marcos)
    L.append("## Posibles unidades del Estado que hoy no se marcan (%d)\n" % len(u))
    L += ["- **%s** (bandera %s): %s; visto %s" % (x["nombre"], x["bandera"], x["razon"], x["visto"]) for x in u] or ["- Ninguna en las últimas capturas."]
    d = destinos_sin_punto(marcos)
    L.append("\n## Destinos que declaran los buques y no tienen punto en el mapa (%d)\n" % len(d))
    L.append("Texto libre que el capitán escribió, sin validar. Si es un puerto real, se puede sumar al mapa con su fuente.\n")
    L += ["- «%s», declarado en %d de las últimas 6 capturas" % (x["destino"], x["capturas"]) for x in d] or ["- Ninguno repetido."]
    L.append("\n## Fuentes candidatas y si hay un dato que responde\n")
    for nombre, url, nota, est in fuentes_que_responden():
        L.append("- **%s** (%s): %s. %s" % (nombre, url, est, nota))
    L.append("\n## Lo que esto NO hace\n\nNo agrega actores, puntos ni fuentes por su cuenta; no verifica identidades; no reemplaza la revisión del décimo hombre.")
    Path(sys.argv[2]).write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
