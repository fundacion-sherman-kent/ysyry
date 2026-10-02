"""Geocodifica con Nominatim (OpenStreetMap) las estaciones de nivel de río de la Dirección de Meteorología e
Hidrología de Paraguay, para ponerlas en el mapa. Se corre a mano, una vez: python geocodificar_estaciones.py
desde sitio/datos/ (lee ../../datos/publico/nivel-rio-py.json, escribe estaciones_geo.json).

Cada resultado se acepta sólo si cae dentro de la caja del corredor y se guarda con el nombre que devolvió OSM,
para que se pueda auditar. Lo que no se encuentra queda sin marcar: no se inventa una ubicación. Una estación
llamada «Rosario» es la de Paraguay, no la ciudad argentina: por eso se consulta con el país y la caja."""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CAJA = {"PY": (-27.9, -62.0, -18.8, -54.0), "BR": (-23.0, -59.0, -15.0, -54.0)}  # lat_min, lon_min, lat_max, lon_max
# nombre de la estación -> consulta y país; lo que difiere del nombre usual se explica en la nota
CONSULTAS = {
    "Puerto Ladario - Brasil": ("Ladário, Mato Grosso do Sul, Brasil", "BR"),
    "Puerto Murtinho - Brasil": ("Porto Murtinho, Mato Grosso do Sul, Brasil", "BR"),
    "Cáceres - Brasil": ("Cáceres, Mato Grosso, Brasil", "BR"),
    "San Cosme y San Damían": ("San Cosme y Damián, Itapúa, Paraguay", "PY"),
    "Vallemi": ("Vallemí, Concepción, Paraguay", "PY"),
    "Rosario": ("Rosario, San Pedro, Paraguay", "PY"),
    "Ita Enramada": ("Itá Enramada, Asunción, Paraguay", "PY"),
    "Ita Pirú": ("Itapirú, Paraguay", "PY"),
    "Ita Corá": ("Itacorá, Paraguay", "PY"),
    "Estación Arirai": ("Ariraí, Paraguay", "PY"),
}


def pedir(q, pais):
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": q, "format": "json", "limit": 3, "countrycodes": pais.lower()})
    req = urllib.request.Request(url, headers={"User-Agent": "YsyryFUSK/1.0 (+https://github.com/fundacion-sherman-kent/ysyry)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    est = json.load(open(RAIZ / "datos" / "publico" / "nivel-rio-py.json", encoding="utf-8"))["estaciones"]
    salida = {}
    for e in est:
        nombre = e["estacion"]
        q, pais = CONSULTAS.get(nombre, (nombre + ", Paraguay", "PY"))
        s, w, n, o = CAJA[pais]
        hallado = None
        try:
            for r in pedir(q, pais):
                lat, lon = float(r["lat"]), float(r["lon"])
                if s <= lat <= n and w <= lon <= o:
                    hallado = {"lat": round(lat, 5), "lon": round(lon, 5), "osm": r["display_name"][:160], "consulta": q}
                    break
        except Exception as ex:
            print("fallo", nombre, str(ex)[:60])
        salida[nombre] = hallado
        print(("OK   " if hallado else "SIN  ") + nombre, hallado["osm"][:70] if hallado else "")
        time.sleep(1.2)
    Path(sys.argv[1] if len(sys.argv) > 1 else "estaciones_geo.json").write_text(
        json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
