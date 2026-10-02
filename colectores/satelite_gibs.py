#!/usr/bin/env python3
"""Imágenes satelitales recientes del corredor, vía NASA GIBS (sin clave).

Baja dos capas, ya recortadas al área del mapa de Ysyry:
  - GOES-East GeoColor: color real, un cuadro cada 10 minutos, ~1-2 km por píxel.
    Los cuadros de menos de ~1 h pueden estar incompletos; se toma el más
    reciente que esté completo, hacia atrás.
  - VIIRS NOAA-20, color real: composición diaria, ~750 m. Se toma el día UTC
    anterior (el del día en curso todavía está incompleto).

No es tiempo real: es lo más cercano que existe gratis a resolución útil, y el
archivo de metadatos dice exactamente de qué momento es cada imagen. NO se ven
buques ni muelles a esta resolución; sirve para nubes, humo, sedimento y
crecidas.

Fuente: NASA Global Imagery Browse Services (GIBS), parte de NASA ESDIS
<https://earthdata.nasa.gov/gibs>. Las imágenes son de uso libre con
atribución.

Variables de entorno:
  DATOS_DIR   carpeta de salida (por defecto "datos/publico")
"""
import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

WMS = "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi"
USER_AGENT = "Ysyry/0.1 (Fundacion Sherman Kent; +https://github.com/fundacion-sherman-kent/ysyry)"

# Mismo recuadro (con un grado de margen) que el mapa de Ysyry. La proyección
# del mapa es lineal en lon y lat, así que la imagen entra sin deformarse.
BBOX = (-72.4, -37.4, -50.9, -14.1)  # lon_min, lat_min, lon_max, lat_max
ANCHO = 1300
ALTO = round(ANCHO * (BBOX[3] - BBOX[1]) / (BBOX[2] - BBOX[0]))

# Una imagen vacía (sin datos) pesa muy poco; una real, bastante más.
MINIMO_BYTES = 25_000

ATRIBUCION = ("Imágenes: NASA GIBS (NASA ESDIS). GOES-East GeoColor: NOAA, producto de "
              "CIRA/CSU. VIIRS: satélite NOAA-20.")


def pedir(capa, tiempo):
    q = urllib.parse.urlencode({
        "SERVICE": "WMS", "VERSION": "1.1.1", "REQUEST": "GetMap", "SRS": "EPSG:4326",
        "FORMAT": "image/jpeg", "STYLES": "", "LAYERS": capa, "TIME": tiempo,
        "BBOX": ",".join(str(v) for v in BBOX), "WIDTH": ANCHO, "HEIGHT": ALTO,
    })
    req = urllib.request.Request(WMS + "?" + q, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            cuerpo = r.read()
            if r.headers.get_content_type() != "image/jpeg":
                return None
            return cuerpo
    except (urllib.error.URLError, TimeoutError) as e:
        print("  error de red: %s" % str(e)[:100], flush=True)
        return None


def ahora():
    return datetime.datetime.now(datetime.timezone.utc)


def tiene_huecos(img):
    """True si la imagen trae bloques negros de datos que aún no entraron (un
    cuadro de GOES recién publicado puede venir con un tramo del barrido
    faltante). Necesita Pillow; sin él no se puede juzgar y se acepta."""
    try:
        import io
        from PIL import Image
    except ImportError:
        return False
    chica = Image.open(io.BytesIO(img)).convert("RGB").resize((260, 282))
    datos = chica.tobytes()
    negros = sum(1 for i in range(0, len(datos), 3) if max(datos[i:i + 3]) <= 4)
    return negros / (260 * 282) > 0.01


def goes_reciente():
    """(imagen, 'AAAA-MM-DDTHH:MM:00Z') del cuadro más nuevo y completo.

    Se parte de hace 60 min y se retrocede hasta hallar uno no vacío. Si trae
    huecos se prueban hasta 6 cuadros más viejos buscando uno completo; de noche
    GeoColor es oscuro y todos parecerían incompletos, así que si ninguno pasa
    se usa el más nuevo no vacío."""
    # GIBS completa cada cuadro a medida que entran los datos: uno de hace menos de
    # ~1 h puede venir con bloques sin rellenar, y hasta llegar vacío un minuto
    # después de haber llegado completo. Medido el 2/10/2026: los de más de 1 h son estables.
    t = ahora() - datetime.timedelta(minutes=60)
    t = t.replace(minute=t.minute - t.minute % 10, second=0, microsecond=0)
    respaldo = None
    probados_con_hueco = 0
    for _ in range(36):  # hasta 6 h hacia atrás
        marca = t.strftime("%Y-%m-%dT%H:%M:00Z")
        img = pedir("GOES-East_ABI_GeoColor", marca)
        if img and len(img) >= MINIMO_BYTES:
            if not tiene_huecos(img):
                return img, marca
            if respaldo is None:
                respaldo = (img, marca)
            probados_con_hueco += 1
            if probados_con_hueco > 6:
                break
        elif respaldo is not None:
            break
        t -= datetime.timedelta(minutes=10)
    return respaldo if respaldo else (None, None)


def viirs_reciente():
    dia = ahora().date()
    for atras in (1, 2, 3):
        marca = (dia - datetime.timedelta(days=atras)).isoformat()
        img = pedir("VIIRS_NOAA20_CorrectedReflectance_TrueColor", marca)
        if img and len(img) >= MINIMO_BYTES:
            return img, marca
    return None, None


def main():
    carpeta = Path(os.environ.get("DATOS_DIR", "datos/publico")) / "satelite"
    carpeta.mkdir(parents=True, exist_ok=True)
    meta = {"obtenido": ahora().strftime("%Y-%m-%dT%H:%M:%SZ"), "bbox": BBOX,
            "ancho": ANCHO, "alto": ALTO, "atribucion": ATRIBUCION, "fuente": "NASA GIBS"}
    fallos = 0

    for nombre, capa, funcion in (
            ("goes", "GOES-East_ABI_GeoColor", goes_reciente),
            ("viirs", "VIIRS_NOAA20_CorrectedReflectance_TrueColor", viirs_reciente)):
        img, marca = funcion()
        if img is None:
            fallos += 1
            print("%s -> sin imagen utilizable (se conserva la anterior, si hay)" % nombre, flush=True)
            continue
        (carpeta / (nombre + ".jpg")).write_bytes(img)
        meta[nombre] = {"capa": capa, "tiempo": marca, "bytes": len(img), "archivo": nombre + ".jpg"}
        print("%s -> %s, %d KB" % (nombre, marca, len(img) // 1024), flush=True)

    if fallos < 2:
        anterior = carpeta / "satelite.json"
        if fallos and anterior.exists():  # no pisar los metadatos de la capa que no se pudo renovar
            previo = json.loads(anterior.read_text(encoding="utf-8"))
            for k in ("goes", "viirs"):
                if k not in meta and k in previo:
                    meta[k] = previo[k]
        anterior.write_text(json.dumps(meta, ensure_ascii=False, indent=1) + chr(10),
                            encoding="utf-8", newline=chr(10))
    print("Fuente: NASA GIBS.")
    return 1 if fallos == 2 else 0


if __name__ == "__main__":
    sys.exit(main())
