#!/usr/bin/env python3
"""Represas del Paraná: nivel del embalse y caudales de Itaipú, Jupiá y Porto Primavera, de los datos abiertos del ONS (Operador Nacional do Sistema
Elétrico, Brasil): «Dados Hidráulicos por Reservatório – Base horária» (dados.ons.org.br, licencia CC BY 4.0, acceso libre y sin clave). El archivo es
uno por mes y se renueva cada hora; la hora es la de Brasilia. Es el dato del propio operador del sistema: no es una medición independiente.

Itaipú regula el Paraná aguas arriba de Ciudad del Este y Foz do Iguaçu: cuando vierte (abre el vertedero), el caudal que baja por el corredor sube aunque
no llueva en ese tramo. Se guarda la última lectura horaria y 14 días de medias diarias.
Escribe DATOS_DIR/represas-ons.json."""
import csv
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

URL = "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/dados_hidrologicos_ho/DADOS_HIDROLOGICOS_HO_%s.csv"
UA = {"User-Agent": "Ysyry-FUSK/1.0 (+https://github.com/fundacion-sherman-kent/ysyry)"}
# clave ONS -> nombre y posición de la presa (lat, lon)
REPRESAS = {"ITAIPU": ("Itaipú", -25.4086, -54.5886), "JUPIA": ("Jupiá", -20.7783, -51.6322), "PORTO PRIMAVERA": ("Porto Primavera", -22.4864, -52.9528)}
CAMPOS = {"val_nivelmontante": "cota_m", "val_niveljusante": "cota_jusante_m", "val_vazaoafluente": "afluente_m3s", "val_vazaodefluente": "defluente_m3s",
          "val_vazaoturbinada": "turbinada_m3s", "val_vazaovertida": "vertida_m3s"}


def bajar(mes):
    """Filas de las tres presas en el archivo del mes (YYYY_MM), leyendo línea a línea (el archivo pesa 12 a 22 MB)."""
    filas = []
    req = urllib.request.Request(URL % mes, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        lineas = (l.decode("utf-8", "replace") for l in r)
        lector = csv.DictReader(lineas, delimiter=";")
        for f in lector:
            clave = (f.get("nom_reservatorio") or "").strip()
            if clave in REPRESAS:
                filas.append((clave, f))
    return filas


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main():
    carpeta = Path(os.environ.get("DATOS_DIR", "datos/publico"))
    carpeta.mkdir(parents=True, exist_ok=True)
    ahora = datetime.now(timezone.utc)
    meses = [ahora.strftime("%Y_%m")]
    if ahora.day <= 14:           # para tener 14 días de serie al principio del mes
        meses.insert(0, (ahora.replace(day=1) - timedelta(days=1)).strftime("%Y_%m"))
    filas = []
    for m in meses:
        try:
            filas += bajar(m)
            print("  %s: %d filas de las tres presas" % (m, len(filas)))
        except Exception as e:
            print("  %s no respondió: %s" % (m, str(e)[:80]))
    if not filas:
        print("El ONS no devolvió datos: no se toca el archivo anterior")
        return 1
    salida = []
    for clave, (nombre, lat, lon) in REPRESAS.items():
        rs = sorted((f for c, f in filas if c == clave), key=lambda f: f["din_instante"])
        rs = [f for f in rs if num(f.get("val_nivelmontante")) is not None]
        if not rs:
            continue
        ult = rs[-1]
        por_dia = {}
        for f in rs:
            por_dia.setdefault(f["din_instante"][:10], []).append(f)
        serie = []
        for dia in sorted(por_dia)[-14:]:
            v = por_dia[dia]
            media = lambda k: (lambda xs: round(sum(xs) / len(xs), 2) if xs else None)([num(y.get(k)) for y in v if num(y.get(k)) is not None])
            serie.append({"dia": dia, "n_horas": len(v), **{CAMPOS[k]: media(k) for k in CAMPOS}})
        salida.append({"clave": clave, "nombre": nombre, "lat": lat, "lon": lon, "hora_brasilia": ult["din_instante"][:16],
                       **{CAMPOS[k]: num(ult.get(k)) for k in CAMPOS}, "serie_diaria": serie})
        print("  %-16s %s cota %.2f m, defluente %s, vertida %s m3/s" % (nombre, ult["din_instante"][:16], num(ult["val_nivelmontante"]), ult.get("val_vazaodefluente"), ult.get("val_vazaovertida")))
    doc = {"obtenido": ahora.strftime("%Y-%m-%dT%H:%M:%SZ"),
           "fuente": {"nombre": "ONS (Operador Nacional do Sistema Elétrico, Brasil), datos abiertos: Dados Hidráulicos por Reservatório, base horária", "url": "https://dados.ons.org.br/",
                      "licencia": "CC BY 4.0", "nota": "Hora de Brasilia. Dato del operador del sistema; el nivel es el del embalse (cota sobre el nivel del mar) y los caudales son medios de la hora, en m³/s."},
           "represas": salida}
    with open(carpeta / "represas-ons.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, ensure_ascii=False, separators=(",", ":"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
