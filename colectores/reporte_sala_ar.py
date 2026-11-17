#!/usr/bin/env python3
"""Reporte hidrometeorológico diario de la Cuenca del Plata, de la Subsecretaría de Recursos Hídricos de Argentina (hidraulica.gob.ar).
Es un PDF diario de 12 páginas (ReporteSala_AAAAMMDD.pdf, sólo los días hábiles) con una tabla de caudales (Guaíra, Itaipú, Andresito, confluencia y
Yacyretá afluente y efluente), con tendencia, caudal de alerta y de evacuación y perspectiva, más un texto de situación y pronóstico. Se lee el texto del PDF.

Es el único lugar abierto donde están juntos el caudal de Itaipú y el de Yacyretá. Los caudales de las represas probablemente los toma de los operadores
(Itaipú y la Entidad Binacional Yacyretá): por eso NO se cuentan como una segunda fuente independiente de lo que mide el ONS.
Si el PDF cambia de formato, no se escribe nada y el robot de salud lo avisa: preferible a publicar un número mal leído.
Requiere pypdf. Escribe DATOS_DIR/reporte-sala-ar.json."""
import io
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

URL = "https://hidraulica.gob.ar/informes_hidrologicos/reporte/ReporteSala_%s.pdf"
UA = {"User-Agent": "Ysyry-FUSK/1.0 (+https://github.com/fundacion-sherman-kent/ysyry)"}
ESTACIONES = ["Guaíra Porto", "Represa Itaipú", "Andresito", "Confluencia", "Yacyretá afluente", "Yacyretá efluente"]
FILA = re.compile(r"^(?P<est>%s)\s+(?P<rio>\S+)\s+(?P<q>\d{3,6})\s*(?P<t>[↑↓=])\s*(?P<al>\d{3,6})\s+(?P<ev>\d{3,6})\s*(?P<p>[^⚠]*?)\s*(?P<aviso>⚠|Atención)?\s*$" % "|".join(re.escape(e) for e in ESTACIONES))
TENDENCIA = {"↑": "sube", "↓": "baja", "=": "estable"}


def bajar_pdf(fecha):
    try:
        with urllib.request.urlopen(urllib.request.Request(URL % fecha.strftime("%Y%m%d"), headers=UA), timeout=90) as r:
            datos = r.read()
    except Exception:
        return None
    return datos if datos[:4] == b"%PDF" else None


def texto_de(datos):
    import pypdf
    lector = pypdf.PdfReader(io.BytesIO(datos))
    return [(p.extract_text() or "") for p in lector.pages]


def analizar(paginas):
    texto = "\n".join(paginas)
    m = re.search(r"Fecha de actualización:\s*(\d\d)/(\d\d)/(\d{4})", texto)
    if not m:
        raise ValueError("no se encontró la fecha de actualización")
    fecha = "%s-%s-%s" % (m.group(3), m.group(2), m.group(1))
    lineas = texto.split("\n")
    caudales = []
    for i, l in enumerate(lineas):
        f = FILA.match(l.strip())
        if not f:
            continue
        persp = f.group("p").strip()
        if i + 1 < len(lineas) and re.match(r"^[a-záéíóúñ/ ]{3,30}$", lineas[i + 1].strip()) and not FILA.match(lineas[i + 1].strip()):
            persp = (persp + " " + lineas[i + 1].strip()).strip()      # la perspectiva se parte en dos renglones
        est = f.group("est")
        caudales.append({"estacion": {"Guaíra Porto": "Guaíra"}.get(est, est), "rio": f.group("rio"), "caudal_m3s": int(f.group("q")), "tendencia": TENDENCIA[f.group("t")],
                         "alerta_m3s": int(f.group("al")), "evacuacion_m3s": int(f.group("ev")), "perspectiva": persp, "aviso": bool(f.group("aviso"))})
    nombres = {c["estacion"] for c in caudales}
    faltan = {"Represa Itaipú", "Yacyretá afluente", "Yacyretá efluente"} - nombres
    if faltan:
        raise ValueError("faltan filas de la tabla de caudales: %s" % sorted(faltan))
    plano = re.sub(r"\s+", " ", texto)

    def pasaje(clave, largo):
        i = plano.find(clave)
        if i < 0:
            return None
        trozo = plano[i:i + largo]
        k = trozo.rfind(". ")
        return (trozo[:k + 1] if k > 80 else trozo).strip()
    return {"fecha_reporte": fecha, "caudales": caudales,
            "texto_itaipu": pasaje("la erogación en Itaipú", 520),
            "texto_yacyreta": pasaje("En Yacyretá,", 620)}


def main():
    carpeta = Path(os.environ.get("DATOS_DIR", "datos/publico"))
    carpeta.mkdir(parents=True, exist_ok=True)
    hoy = datetime.now(timezone.utc).date()
    for atras in range(0, 9):
        dia = hoy - timedelta(days=atras)
        datos = bajar_pdf(dia)
        if datos is None:
            continue
        try:
            doc = analizar(texto_de(datos))
        except Exception as e:
            print("  %s: el PDF no se pudo leer (%s)" % (dia, str(e)[:100]))
            return 1
        doc.update({"obtenido": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "pdf": URL % dia.strftime("%Y%m%d"),
                    "fuente": {"nombre": "Subsecretaría de Recursos Hídricos de Argentina, Reporte hidrometeorológico diario de la Cuenca del Plata", "url": "https://hidraulica.gob.ar/",
                               "nota": "Los caudales de las represas probablemente provienen de sus operadores: no son una medición independiente de la del ONS."}})
        with open(carpeta / "reporte-sala-ar.json", "w", encoding="utf-8", newline="\n") as fh:
            json.dump(doc, fh, ensure_ascii=False, separators=(",", ":"))
        for c in doc["caudales"]:
            print("  %-18s %6d m3/s %-8s (alerta %d)%s" % (c["estacion"], c["caudal_m3s"], c["tendencia"], c["alerta_m3s"], " AVISO" if c["aviso"] else ""))
        print("Reporte del %s (archivo del %s)" % (doc["fecha_reporte"], dia))
        return 0
    print("No hay ningún reporte en los últimos 9 días: no se toca el archivo anterior")
    return 1


if __name__ == "__main__":
    sys.exit(main())
