"""Genera la página de Ysyry (una sola página estática) a partir de los insumos de datos/ y de las
capturas de AIS (marcos.json). Lo ejecuta el flujo sitio.yml cada hora; también se puede correr a mano.

Variables de entorno (todas opcionales):
  SITIO_DATOS      carpeta de insumos (por defecto, datos/ junto a este archivo)
  SITIO_MARCOS     capturas de AIS en JSON (por defecto, datos/marcos.json)
  SITIO_SATELITE   carpeta con goes.jpg, viirs.jpg y satelite.json (por defecto, datos/satelite)
  SITIO_SALIDA     archivo de salida (por defecto, salida/index.html)
"""
import json
import os
from pathlib import Path

D = Path(os.environ.get("SITIO_DATOS") or (Path(__file__).resolve().parent / "datos"))
MARCOS = os.environ.get("SITIO_MARCOS") or str(D / "marcos.json")
SAT_DIR = Path(os.environ.get("SITIO_SATELITE") or (D / "satelite"))
SALIDA = os.environ.get("SITIO_SALIDA") or "salida/index.html"


def _imo_valido(valor):
    """IMO de 7 dígitos con dígito de control correcto, o None. Mismo algoritmo que el colector de AIS."""
    try:
        t = str(int(valor))
    except (TypeError, ValueError):
        return None
    if len(t) != 7:
        return None
    suma = sum(int(c) * w for c, w in zip(t[:6], range(7, 1, -1)))
    return int(t) if suma % 10 == int(t[6]) else None


d = json.load(open(D / "mapa_v10.json", encoding="utf-8"))
marcos = json.load(open(MARCOS, encoding="utf-8"))

# Categoría de buque por el código numérico de tipo AIS (ITU-R M.1371 §3.3.2):
# 3x pesca/remolque/buceo, 5x servicios de puerto, 6x pasajeros, 7x carga, 8x tanque.
def categoria_ais(tipo):
    if tipo is None: return ("desconocido", "#ffd400")
    t = int(tipo)
    if 30 <= t < 40: return ("pesca/remolque", "#8fd9c4")
    if 50 <= t < 60: return ("servicio portuario", "#dfe6e9")
    if 60 <= t < 70: return ("pasajeros", "#b8f06a")
    if 70 <= t < 80: return ("carga", "#ffd400")
    if 80 <= t < 90: return ("tanque", "#ff8a5c")
    return ("otro/sin clasificar", "#9aa7ad")
colores = d["colores_pais"]
# Ysyry es azul: los países se distinguen por tonos del gris azul de la casa (el violeta es de FEMÓNOE)
colores = {"ARG": "#667B89", "PRY": "#C6C6C5", "BRA": "#3d5566", "URY": "#8aa0ae", "BOL": "#2b3a44", "CHL": "#1f3b4d"}
W, H = d["W"], d["H"]

# --- coordenadas reales (lat/lon), ya geocodificadas con Nominatim/OSM antes
# en la sesión — se reusan acá sólo para mostrar la posición en la ficha ---
COORD = {}
for _archivo in ("ciudades_geocodificadas.json", "puertos.json"):
    for _item in json.load(open(D / _archivo, encoding="utf-8")):
        _clave = _item["consulta"].split(",")[0].strip()
        COORD[_clave] = (_item["lat"], _item["lon"])

def coord_de(nombre):
    par = COORD.get(nombre)
    if not par:
        return None
    lat, lon = par
    return "%.4f, %.4f" % (lat, lon)

# --- foto de portada para la ficha de ciudades/puertos: imagen real de
# Wikimedia Commons (vía la API pública de Wikipedia), con la página de
# Wikipedia como fuente citable — nunca una imagen inventada o sin origen.
# No hay foto por buque ni por zona/riesgo: no tenemos fuente verificada
# para eso (ver README, pendiente si se consigue una después). ---
_WIKI = json.load(open(D / "wiki_fotos.json", encoding="utf-8"))["paginas"]

_CRED = json.load(open(D / "fotos_credito.json", encoding="utf-8"))

def limpiar_autor(a):
    """Los campos de autor de Commons vienen con HTML aplanado: textos duplicados, «Unknown author»
    en inglés, o larguísimos. Se normalizan para que el crédito sea legible."""
    a = " ".join((a or "").split())
    if not a or "nknown" in a:
        return "autor no identificado"
    mitad = len(a) // 2
    if len(a) % 2 == 0 and mitad >= 3 and a[:mitad] == a[mitad:]:   # texto repetido dos veces
        a = a[:mitad].strip()
    if len(a) > 60:
        a = a.split("(")[0].strip() or a[:60]
    return a

def _con_credito(src, pagina_wikipedia, generica, prefijo=None):
    """Autor, licencia y enlace al ARCHIVO en Commons (que muestra licencia y autor): lo que exige
    CC BY / CC BY-SA. Si no se pudo obtener, la foto no se usa (None)."""
    c = _CRED.get(src)
    if not c:
        return None
    autor = limpiar_autor(c["autor"])
    pref = prefijo or ("Imagen ilustrativa · " if generica else "Foto: ")
    d = {"src": src, "pagina": c["pagina"], "credito": "%s%s, %s (Wikimedia Commons)" % (pref, autor, c["licencia"])}
    if generica:
        d["generica"] = True
    return d

def foto_generica(clave):
    pag = _WIKI.get(clave)
    if not pag or not pag.get("thumb"):
        return None
    return _con_credito(pag["thumb"], pag["url"], True)

WIKI_POR_POI = {
    "Asunción": "Asunción", "Puerto Iguazú": "Puerto Iguazú", "Foz do Iguaçu": "Foz do Iguaçu",
    "Ciudad del Este": "Ciudad del Este", "Corrientes": "Corrientes (ciudad)",
    "Santa Fe": "Santa Fe (Argentina)", "Rosario": "Rosario (Argentina)", "Buenos Aires": "Buenos Aires",
    "Montevideo": "Montevideo", "Colonia del Sacramento": "Colonia del Sacramento",
    "Nueva Palmira": "Nueva Palmira", "Zárate": "Zárate", "Corumbá": "Corumbá",
    "Porto Cáceres": "Cáceres (Mato Grosso)", "Concepción": "Concepción (Paraguay)",
    "Puerto de Rosario": "Rosario (Argentina)", "Puerto General San Martín": "San Lorenzo (Santa Fe)",
    "Puerto de Zárate": "Zárate", "Puerto de Buenos Aires": "Buenos Aires",
    "Puerto Nueva Palmira": "Nueva Palmira", "Puerto de Asunción": "Asunción",
    "Puerto de Villeta": "Villeta (Paraguay)", "Puerto de Corumbá": "Corumbá",
    "Porto Murtinho": "Porto Murtinho",
}

def foto_de(nombre):
    clave = WIKI_POR_POI.get(nombre)
    pag = _WIKI.get(clave) if clave else None
    if not pag or not pag.get("thumb"):
        return None
    # Para una terminal portuaria la foto es de la CIUDAD, no de la terminal: se dice así.
    es_puerto = nombre in {q["nombre"] for q in d["poi"] if q["clase"] == "puerto"}
    prefijo = "Foto de la ciudad, no de la terminal · " if es_puerto else None
    return _con_credito(pag["thumb"], pag["url"], False, prefijo)

# --- puertos: tipo real donde lo tenemos (BCR, 1/10/2026), genérico el resto ---
TIPO_PUERTO = {
    "Puerto de Rosario": ("TPR — Terminal Puerto Rosario", "multipropósito (contenedores)", "Bolsa de Comercio de Rosario, 1/10/2026"),
    "Puerto General San Martín": ("Clúster San Lorenzo–San Martín", "agroindustrial (granos, aceites)", "Bolsa de Comercio de Rosario, 1/10/2026"),
    "Terminal Timbúes": ("Proyecto Terminal Multipropósito Timbúes", "multipropósito, en desarrollo", "Bolsa de Comercio de Rosario, 1/10/2026"),
}

def datos_poi(q):
    nombre = q["nombre"]
    if nombre in TIPO_PUERTO:
        nombre_real, tipo, fuente = TIPO_PUERTO[nombre]
        return nombre_real, tipo, fuente
    if q["clase"] == "puerto":
        return nombre, "terminal portuaria (tipo sin diferenciar)", "Geocodificado con Nominatim/OSM, 1/10/2026 (fuente única)"
    return nombre, "ciudad del corredor", "Geocodificado con Nominatim/OSM, 1/10/2026 (fuente única)"

# --- capas geométricas ---
paises_svg = ['<path class="pais" d="%s" fill="none" stroke="#dfe6e9" stroke-opacity="0.85" stroke-width="2"/>' % p["d"] for p in d["paths_pais"]]
prov_svg = ['<path class="prov" d="%s" fill="%s" fill-opacity="0.20" stroke="none"/>' % (p["d"], colores.get(p["pais"], "#667B89")) for p in d["paths_prov"]]
# cauces anchos (Paraná, Delta, Uruguay) de OpenStreetMap, ODbL: el río como superficie de agua, no sólo como línea,
# para que los buques y puertos queden sobre el agua. Cuadros que fallaron: ver el README (el Paraná medio y el alto
# quedan con la línea más una franja de ancho aproximado).
_AGUA = json.load(open(D / "agua_osm.json", encoding="utf-8"))
agua_osm_html = '<path class="agua-osm" d="%s" fill-rule="evenodd"/>' % _AGUA["d"]
# Aguas arriba de Rosario no hay cauce de OpenStreetMap: el río es la línea de Natural Earth más una franja de ancho
# geográfico aproximado (crece al acercar), porque medimos que los buques quedan hasta ~3 km a un lado de esa línea.
rio_parana_html = ('<path class="rio-banda" d="%s" fill="none" stroke-width="1.2"/>' % d["rio_parana"]
                   + '<path class="rio-real" d="%s" fill="none"/>' % d["rio_parana"])
rio_paraguay_html = ('<path class="rio-banda" d="%s" fill="none" stroke-width="0.8"/>' % d["rio_paraguay"]
                     + '<path class="rio-paraguay" d="%s" fill="none"/>' % d["rio_paraguay"])
rio_pilco_html = '<path class="afluente" d="%s" fill="none"/>' % d["rio_pilcomayo"]
rio_bermejo_html = '<path class="afluente" d="%s" fill="none"/>' % d["rio_bermejo"]
rutas_html = '<path class="ruta" d="%s" fill="none"/>' % d["rutas_reales"]
bioceanico_html = '<path class="bioceanico" d="%s" fill="none"/>' % d["bioceanico"]
import re as _re

def _centroide(d_path):
    nums = [float(n) for n in _re.findall(r"-?\d+\.?\d*", d_path)]
    xs, ys = nums[0::2], nums[1::2]
    return sum(xs) / len(xs), sum(ys) / len(ys)

zonas_svg = []
zonas_etq_svg = []
NOMBRE_CORTO = {
    "Canindeyú (PCC, presencia documentada)": "Canindeyú · PCC",
    "Alto Paraná (PCC, presencia documentada)": "Alto Paraná · PCC",
}

# --- etiquetas con línea + nube de texto, para que no tapen el mapa al
# superponerse — mismo patrón que un tag de reconocimiento de imagen.
# El desplazamiento fijo no alcanza cuando hay varios puntos pegados (ej.
# Triple Frontera), así que además JS hace una pasada de colisión en
# tiempo real y oculta la de menor prioridad cuando dos cajas se pisan. ---
DIRS = [(18, -13), (18, 15), (-18, -13), (-18, 15), (18, 2), (-18, 2)]
_contador_callout = [0]
PRIORIDAD = {"boya": 2, "puerto": 4, "riesgo": 3, "tf": 3, "zona": 2, "ciudad": 1}

def callout(x, y, texto, clase, familia):
    indice = _contador_callout[0]
    _contador_callout[0] += 1
    dx, dy = DIRS[indice % len(DIRS)]
    lx, ly = x + dx, y + dy
    ancho = min(190, max(56, int(len(texto) * 4.5) + 20))
    alto = 20
    fx = lx if dx >= 0 else lx - ancho
    fy = ly - alto / 2
    alin = "left" if dx >= 0 else "right"
    return ('<g class="etq-g" data-familia="%s" data-prioridad="%d" pointer-events="none">'
            '<line class="etq-linea" x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>'
            '<circle class="etq-ancla" cx="%.1f" cy="%.1f" r="1.6"/>'
            '<foreignObject class="etq-fo" x="%.1f" y="%.1f" width="%d" height="%d" pointer-events="none">'
            '<div xmlns="http://www.w3.org/1999/xhtml" class="etq-chip chip-%s" '
            'style="text-align:%s;pointer-events:none">%s</div>'
            '</foreignObject></g>'
            % (familia, PRIORIDAD.get(clase, 1), x, y, lx, ly, lx, ly, fx, fy, ancho, alto, clase, alin, texto))

for i, z in enumerate(d["actores"]["zonas"]):
    zonas_svg.append('<path class="zona-actor" data-i="za%d" d="%s"/>' % (i, z["d"]))
    cx, cy = _centroide(z["d"])
    corto = NOMBRE_CORTO.get(z["nombre"], z["nombre"])
    zonas_etq_svg.append(callout(cx, cy, corto, "zona", "seguridad"))

# --- familias de riesgo, con datos reales — mismo espíritu que flujos.html de SIWA ---
FAMILIA_PUERTO = "comercio"
FAMILIA_TIMBUES_EXTRA = "regulatorio"  # Timbúes es además el límite de la licitación

# --- contexto por provincia/departamento (SIWA, CC BY 4.0): homicidios oficiales, ACLED y focos de calor ---
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import contexto_siwa as _siwa
_FUENTES_SIWA = _siwa.cargar(D / "siwa")
# unidad de primer orden de cada punto, leída de la geocodificación (ciudad o provincia de OSM)
UNIDAD_POI = {
    "Asunción": ("PRY", "Asunción"), "Puerto de Asunción": ("PRY", "Asunción"), "Puerto de Villeta": ("PRY", "Central"),
    "Concepción": ("PRY", "Concepción"), "Ciudad del Este": ("PRY", "Alto Paraná"),
    "Puerto Iguazú": ("ARG", "Misiones"), "Foz do Iguaçu": ("BRA", "Paraná"),
    "Corrientes": ("ARG", "Corrientes"), "Santa Fe": ("ARG", "Santa Fe"), "Rosario": ("ARG", "Santa Fe"),
    "Puerto de Rosario": ("ARG", "Santa Fe"), "Puerto General San Martín": ("ARG", "Santa Fe"), "Terminal Timbúes": ("ARG", "Santa Fe"),
    "Buenos Aires": ("ARG", "Ciudad Autónoma de Buenos Aires"), "Puerto de Buenos Aires": ("ARG", "Ciudad Autónoma de Buenos Aires"),
    "Zárate": ("ARG", "Buenos Aires"), "Puerto de Zárate": ("ARG", "Buenos Aires"),
    "Montevideo": ("URY", "Montevideo"), "Colonia del Sacramento": ("URY", "Colonia"),
    "Nueva Palmira": ("URY", "Colonia"), "Puerto Nueva Palmira": ("URY", "Colonia"),
    "Corumbá": ("BRA", "Mato Grosso do Sul"), "Puerto de Corumbá": ("BRA", "Mato Grosso do Sul"),
    "Porto Murtinho": ("BRA", "Mato Grosso do Sul"), "Porto Cáceres": ("BRA", "Mato Grosso"),
}
_SIN_UNIDAD = [q["nombre"] for q in d["poi"] if q["nombre"] not in UNIDAD_POI]
assert not _SIN_UNIDAD, "puntos sin unidad de primer orden asignada: %s" % _SIN_UNIDAD

def contexto_poi(nombre):
    iso, unidad = UNIDAD_POI[nombre]
    return _siwa.lineas(_FUENTES_SIWA, iso, unidad), "%s (%s)" % (unidad, iso)

# --- alertas tempranas de FEMÓNOE sobre el corredor (se leen de su sitio público al construir) ---
import alertas_femonoe as _fem
import datetime as _dt
_ALERTAS_FEM = _fem.bloque_html(_fem.consultar(), _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d"))

# --- puntos de interés: clicables, con panel ---
poi_svg = []
poi_etq_svg = []
poi_info = []
for i, q in enumerate(d["poi"]):
    tf = q["nombre"] in ("Puerto Iguazú", "Foz do Iguaçu", "Ciudad del Este")
    if q["clase"] == "puerto":
        cls, r, clase_chip = "poi puerto", 4.2, "puerto"
    else:
        cls, r, clase_chip = ("poi tf" if tf else "poi ciudad"), 3.4, ("tf" if tf else "ciudad")
    gid = "poi%d" % i
    familia = FAMILIA_PUERTO if q["clase"] == "puerto" else ""
    if q["nombre"] == "Terminal Timbúes":
        familia = FAMILIA_PUERTO + " " + FAMILIA_TIMBUES_EXTRA
    poi_svg.append('<g class="%s clicable" data-i="%s" data-familia="%s" transform="translate(%s,%s)">'
                    '<circle class="hit" r="14"/><circle r="%s" class="punto"/></g>'
                    % (cls, gid, familia, q["x"], q["y"], r))
    poi_etq_svg.append(callout(q["x"], q["y"], q["nombre"], clase_chip, familia))
    nombre_real, tipo, fuente = datos_poi(q)
    if q["nombre"] == "Terminal Timbúes":
        tipo += " · límite de la concesión de dragado a 40 pies, Res. 36/2026 (Jan De Nul–Servimagnus)"
    cat_poi = "Terminal portuaria" if q["clase"] == "puerto" else "Ciudad del corredor"
    _ctx, _unid = contexto_poi(q["nombre"])
    poi_info.append({"id": gid, "categoria": cat_poi, "titulo": nombre_real, "tipo": tipo, "fuente": fuente,
                      "clase": clase_chip, "coord": coord_de(q["nombre"]), "foto": foto_de(q["nombre"]),
                      "ctx": _ctx, "ctx_t": "Contexto de la unidad: " + _unid, "ctx_f": _siwa.pie(_FUENTES_SIWA)})

riesgo_info = []
riesgos_svg = []
riesgos_etq_svg = []
for i, r in enumerate(d["riesgos"]):
    gid = "rz%d" % i
    riesgos_svg.append('<g class="riesgo-g clicable" data-i="%s" data-familia="seguridad" transform="translate(%s,%s)">'
                        '<circle class="hit" r="14"/><circle class="riesgo" r="5"/></g>'
                        % (gid, r["x"], r["y"]))
    riesgos_etq_svg.append(callout(r["x"], r["y"], "Piratería, km 340", "riesgo", "seguridad"))
    riesgo_info.append({"id": gid, "categoria": "Hecho informado por prensa", "titulo": "Piratería fluvial, km 340 (hecho puntual)",
                         "tipo": "Motonave «Rosa» (Naviship Paraguay S.A.) · 2.628 t · Buenos Aires→Asunción · oct. 2025 · Hecho puntual informado por cuatro medios; presunto, sin condena, y no se atribuye autor · No indica que el lugar sea hoy una zona peligrosa",
                         "fuente": "SL24, La Nación, Weekend/Perfil y Diario El Norte: cuatro medios",
                         "clase": "riesgo", "coord": None, "foto": foto_generica("Río Paraná")})

zona_info = [
    {"id": "za0", "categoria": "Zona con presencia atribuida (según las fuentes citadas)", "titulo": "Canindeyú (Paraguay)",
     "tipo": "Según La Política Online y ABC Color (medios) y comunicados de la Presidencia de Paraguay (fuente oficial, no independiente del Estado), se informó presencia atribuida al PCC · Localidades que mencionan las fuentes: Pindó, Siete Montes y Catueté · Es una atribución periodística y oficial, no una sentencia: no implica que ocurra en todo el departamento ni involucra a sus habitantes",
     "fuente": "La Política Online y ABC Color (medios) y Presidencia de Paraguay (oficial): 3 fuentes, dos de ellas medios",
     "clase": "zona", "coord": None, "foto": foto_generica("Departamento de Canindeyú")},
    {"id": "za1", "categoria": "Zona con presencia atribuida (según las fuentes citadas)", "titulo": "Alto Paraná (Paraguay)",
     "tipo": "Según La Política Online y ABC Color (medios) y la Presidencia de Paraguay (fuente oficial), se informó presencia atribuida al PCC y un operativo en la cárcel de Ciudad del Este · Atribución periodística y oficial, no una sentencia: no implica que ocurra en todo el departamento ni involucra a sus habitantes",
     "fuente": "La Política Online y ABC Color (medios) y Presidencia de Paraguay (oficial): 3 fuentes, dos de ellas medios",
     "clase": "zona", "coord": None, "foto": foto_generica("Departamento de Alto Paraná")},
]
# contexto adicional para las zonas (ACLED codifica prensa y fuentes locales, así que no se la presenta como independiente): mide violencia política, no al PCC; por eso se rotula
# como contexto y no como confirmación ni desmentida de la atribución
for _z, _u in ((zona_info[0], "Canindeyú"), (zona_info[1], "Alto Paraná")):
    _l = [x for x in _siwa.lineas(_FUENTES_SIWA, "PRY", _u) if x.startswith("Violencia política")]
    if _l:
        _z["ctx"] = _l + ["Este conjunto cuenta eventos y víctimas por departamento, sin atribuirlos a ningún grupo: sirve de contexto, no confirma ni desmiente lo que informan los medios y la Presidencia"]
        _z["ctx_t"] = "Contexto adicional, no es la misma fuente: " + _u + " (PRY)"
        _z["ctx_f"] = _siwa.pie(_FUENTES_SIWA)
# ambas zonas de actor son de la familia «seguridad»
zonas_svg = [z.replace('class="zona-actor"', 'class="zona-actor clicable" data-familia="seguridad"', 1) for z in zonas_svg]

# --- posiciones AIS por hora, con flecha de rumbo cuando hay cog, clicables ---
# arranca mostrando el marco con más posiciones, no el primero (si el primero
# está casi vacío, un viewer no ve ningún buque al abrir la página)
marco_inicial = len(marcos) - 1 if marcos else 0  # abre en la captura más reciente

BANDERAS = {"AR": "Argentina", "PY": "Paraguay", "BR": "Brasil", "UY": "Uruguay", "BO": "Bolivia"}

# Imagen por tipo de embarcación (código AIS), siempre ilustrativa salvo las
# pocas con página propia en Wikipedia (se marcan "especifica"). No hay foto
# por buque en general: no hay una fuente verificable para cada casco.
IMG_POR_TIPO = [
    (range(30, 31), "Barco pesquero"), (range(31, 33), "Remolcador"),
    (range(36, 38), "Yate"), (range(50, 55), "Remolcador"), (range(56, 60), "Remolcador"),
    (range(60, 70), "Transbordador"), (range(70, 80), "Buque de carga"),
    (range(80, 90), "Petrolero"),
]
ESPECIFICAS = {  # nombre AIS exacto -> página de Wikipedia de ese mismo buque
    "GC-24 MANTILLA": "Clase Halcón", "GC-25 AZOPARDO": "PNA Azopardo (GC-25)",
    "ARA CDAD ZARATE": "ARA Ciudad de Zárate (Q-61)", "ALMIRANTE IRIZAR": "ARA Almirante Irízar (Q-5)",
}
RE_ESTADO = _re.compile(r"^(ARA|GC)[\s\-]")
# Paraguay: la Armada Paraguaya designa sus unidades con prefijo ARP (p. ej. ARP P-05
# «Itaipú») y la Prefectura General Naval con PGN; las lanchas patrulleras rápidas
# se llaman LP-101, LP-102... (armadaparaguaya.mil.py y es.wikipedia.org/wiki/Armada_Paraguaya,
# 2/10/2026). El nombre solo NO alcanza —«Itaipú» o «Humaitá» también son remolcadores
# civiles—, por eso se exige el prefijo, y LP sólo con bandera paraguaya.
RE_ESTADO_PY = _re.compile(r"^(ARP|PGN)[\s\-]")
RE_LP_PY = _re.compile(r"^LP[\s\-]?\d{2,3}$")

def es_estado_py(p):
    n = (p.get("nombre") or "").strip().upper()
    return bool(RE_ESTADO_PY.match(n)) or (p.get("bandera") == "PY" and bool(RE_LP_PY.match(n)))

def es_estado(p):
    n = (p.get("nombre") or "").strip().upper()
    return p.get("tipo_ais") in (35, 55) or bool(RE_ESTADO.match(n)) or es_estado_py(p)

def fuerza_inferida(p):
    n = (p.get("nombre") or "").strip().upper()
    if n.startswith("ARP"): return "Armada Paraguaya (inferido por el prefijo ARP)"
    if n.startswith("PGN"): return "Prefectura General Naval de Paraguay (inferido por el prefijo PGN)"
    if es_estado_py(p): return "Armada Paraguaya, lancha patrullera (inferido por la designación LP y la bandera)"
    if n.startswith("GC"): return "Prefectura Naval Argentina (inferido por el prefijo GC)"
    if n.startswith("ARA") or p.get("tipo_ais") == 35: return "Armada Argentina (inferido por el prefijo ARA / tipo AIS 35)"
    return "fuerza no identificada por el nombre"

_VER = json.load(open(D / "buques_verificados.json", encoding="utf-8"))
_FOTOS_IMO = json.load(open(D / "fotos_imo.json", encoding="utf-8"))

def _norm(s):
    return _re.sub(r"[^A-Z0-9]+", " ", (s or "").upper()).strip()

def foto_buque(p):
    n = (p.get("nombre") or "").strip().upper()
    imo = _imo_valido(p.get("imo"))
    # 1) Verificada por número IMO: el IMO identifica el casco aunque cambie de nombre
    if imo and str(imo) in _FOTOS_IMO:
        v = _FOTOS_IMO[str(imo)]
        nota = "Verificada por número IMO %s (%s)" % (imo, v["verificado_por"])
        if _norm(n) not in _norm(v["archivo"]):
            nota += ". En la foto el casco figura con otro nombre"
        autor = limpiar_autor(v.get("autor")) + ", "
        return {"src": v["thumb"], "pagina": v["pagina"],
                "credito": "Foto: %s%s (Wikimedia Commons)" % (autor, v["licencia"] or "licencia libre"),
                "nota": nota}
    # 2) Coincidencia por nombre: sólo si el buque no transmite IMO (no hay otra forma de verificar)
    if n in _VER and not imo:
        v = _VER[n]
        return {"src": v["src"], "pagina": v["pagina"],
                "credito": "Foto: %s, %s (Wikimedia Commons)" % (limpiar_autor(v["autor"]), v["licencia"]),
                "nota": "Coincidencia por nombre, bandera y tipo; este buque no transmite IMO, no verificable"}
    if n in ESPECIFICAS:
        f = foto_de_pagina(ESPECIFICAS[n])
        if f: return f
    if es_estado(p):
        return foto_generica("Prefectura Naval Argentina" if not n.startswith("ARA") else "Guardia costera")
    t = p.get("tipo_ais")
    for rango, clave in IMG_POR_TIPO:
        if t is not None and t in rango:
            return foto_generica(clave)
    return foto_generica("Barcaza")

def foto_de_pagina(clave):
    pag = _WIKI.get(clave)
    if not pag or not pag.get("thumb"):
        return None
    return _con_credito(pag["thumb"], pag["url"], False)

# --- puertos, terminales, muelles y amarraderos de OpenStreetMap (instantánea fechada) ---
P_ = json.load(open(D / "proyeccion.json"))
_AM = json.load(open(D / "amarres_osm.json", encoding="utf-8"))
NIVEL_A = {"puerto", "area_portuaria", "ferry", "marina", "darsena", "atracadero"}   # se ven desde un zoom moderado
GRUPO_AM = {"puerto": "pu", "area_portuaria": "pu", "darsena": "pu", "ferry": "pu",
            "marina": "mu", "atracadero": "mu", "muelle": "mu", "rampa": "ra", "amarradero": "ra"}
amarres_svg = []
amarres_json = []
for _i, _a in enumerate(_AM["items"]):
    _x = round(P_["ax"] * _a["lon"] + P_["bx"], 1)
    _y = round(P_["ay"] * _a["lat"] + P_["by"], 1)
    _niv = "a" if _a["t"] in NIVEL_A else "b"
    _g = GRUPO_AM[_a["t"]]
    amarres_svg.append('<g class="amar amar-%s amar-%s clicable" data-i="am%d" data-familia="comercio" transform="translate(%s,%s)">'
                       '<circle class="hit" r="11"/><rect class="m" x="-3" y="-3" width="6" height="6"/></g>'
                       % (_niv, _g, _i, _x, _y))
    amarres_json.append([_a["t"], _a["n"], _a["lon"], _a["lat"], _a["x"]])

AZUL_ESTADO = "#2f7bff"
# buques de la lista SDN de OFAC con IMO (dominio público): se cruzan sólo por IMO, que es exacto
try:
    _OFAC = json.load(open(Path(os.environ.get("SITIO_OFAC") or (Path(__file__).resolve().parents[1] / "datos" / "publico" / "ofac_buques.json")), encoding="utf-8"))
except Exception:
    _OFAC = None
_OFAC_VISTOS = {}     # imo -> (nombre transmitido, ficha de OFAC)
buque_info = []
grupos_hora = []
for i, m in enumerate(marcos):
    partes = []
    partes_estado = []  # se dibujan al final: quedan encima de los demás en los racimos
    for j, p in enumerate(m["puntos"]):
        bid = "bq%d_%d" % (i, j)
        cat, color = categoria_ais(p.get("tipo_ais"))
        nombre = (p.get("nombre") or "").strip() or "(sin nombre transmitido)"
        estado = es_estado(p)
        fam = "estado" if estado else "comercio"
        if estado:
            # triángulo azul, más grande y con borde blanco: se distingue de todo lo demás
            cog = p.get("cog") if p.get("cog") is not None else 0
            partes_estado.append('<g class="buque-g buque-estado clicable" data-i="%s" data-familia="%s" '
                           'transform="translate(%s,%s) rotate(%s)">'
                           '<circle class="hit" r="13"/><path d="M0,-8 L6,6 L-6,6 Z" style="fill:%s;stroke:#fff;stroke-width:1.2;stroke-linejoin:round"/></g>'
                           % (bid, fam, p["x"], p["y"], round(cog, 1), AZUL_ESTADO))
            rumbo = "%s°" % round(cog) if p.get("cog") is not None else "sin dato"
            cat = "embarcación del Estado (AIS tipo %s)" % p.get("tipo_ais")
        elif p.get("cog") is not None:
            partes.append('<g class="buque-g clicable" data-i="%s" data-familia="%s" '
                           'transform="translate(%s,%s) rotate(%s)">'
                           '<circle class="hit" r="13"/><path class="buque-flecha" d="M0,-5 L3.4,3.6 L0,1.4 L-3.4,3.6 Z" style="fill:%s"/></g>'
                           % (bid, fam, p["x"], p["y"], round(p["cog"], 1), color))
            rumbo = "%s°" % round(p["cog"])
        else:
            partes.append('<g class="buque-g clicable" data-i="%s" data-familia="%s" transform="translate(%s,%s)">'
                           '<circle class="hit" r="13"/><circle class="buque" r="4" style="fill:%s"/></g>'
                           % (bid, fam, p["x"], p["y"], color))
            rumbo = "sin dato"
        bandera = BANDERAS.get(p.get("bandera"), p.get("bandera") or "sin dato")
        vel = p.get("velocidad")
        destino = (p.get("destino") or "").strip() or "sin dato"
        if vel is None:
            mov = "velocidad sin dato"
        elif vel < 0.5:
            mov = "sin movimiento"        # con velocidad ~0 el rumbo es ruido: no se muestra
        else:
            mov = "rumbo %s, %s nudos" % (rumbo, vel)
        if destino in ("sin dato", "0", "00"):
            dest_txt = "destino no declarado"
        else:
            dest_txt = "destino declarado por el buque, sin validar: %s" % destino
        tipo_txt = "Bandera %s · %s (tipo autodeclarado) · %s · %s" % (bandera, cat, mov, dest_txt)
        _imo = _imo_valido(p.get("imo"))
        if _imo:
            tipo_txt += " · IMO %s" % _imo
            if _OFAC and _imo in _OFAC["buques"]:
                _o = _OFAC["buques"][_imo]
                _OFAC_VISTOS[_imo] = (nombre, _o)
                tipo_txt += " · El IMO que transmite este buque figura en la lista de sanciones SDN de OFAC (EE.UU.), programa %s, con el nombre «%s». Es una pista para mirar, no una acusación: el IMO transmitido por AIS puede estar mal cargado y estar en esa lista es una decisión de un Estado extranjero" % (_o["programa"], _o["nombre"])
        if estado:
            tipo_txt += " · Fuerza probable (inferida del nombre, no la transmite el buque y puede ser incorrecta): " + fuerza_inferida(p)
        buque_info.append({"id": bid,
                            "categoria": "Embarcación del Estado, captura AIS" if estado else "Embarcación, captura AIS",
                            "titulo": nombre, "tipo": tipo_txt,
                            "fuente": "AIS vía Open Waters (AISHub y aisstream.io) · captura del %s, no es tiempo real · identidad tal como la transmite el propio buque"
                                      % (m["hora"][:16].replace("T", " ") + " UTC"),
                            "clase": "estado" if estado else "buque", "coord": None, "foto": foto_buque(p)})
    oculto = "" if i == marco_inicial else ' style="display:none"'
    grupos_hora.append('<g class="marco-hora" data-i="%d"%s>%s</g>' % (i, oculto, "".join(partes + partes_estado)))

# --- guía de ayuda (catálogo escrito de antemano; ver guia.py) ---
import guia as _guia
_GUIA = []   # se completa más abajo, cuando se conocen las estaciones y las unidades del Estado

# --- prospectiva: preguntas publicadas por la dirección (carpeta preguntas/ del repositorio) y su marcador ---
import preguntas as _preg
_RAIZ_P = Path(os.environ.get("SITIO_RAIZ") or Path(__file__).resolve().parents[1])
_PREGUNTAS = _preg.cargar(Path(os.environ.get("SITIO_PREGUNTAS") or (_RAIZ_P / "preguntas")))
_prospectiva_html = _preg.bloque_html(_PREGUNTAS, __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%d"))

# --- pulso por zona: qué se observa en cada tramo (AIS de las últimas 24 h) y su comparación con días anteriores ---
import pulso as _pulso
from datetime import datetime as _dtm, timedelta as _td
PULSO = os.environ.get("SITIO_PULSO") or str(D / "pulso.json")
_pulso_html = ""
_vivas_html = ""
_actores_html = ""
_escaner_html = ""
_flujos_html = ""
_indicios_html = ""
zona_pulso_info = []
if marcos:
    _fin = _dtm.strptime(marcos[-1]["hora"], "%Y-%m-%dT%H:%M:%SZ")
    _ventana = [m for m in marcos if _dtm.strptime(m["hora"], "%Y-%m-%dT%H:%M:%SZ") > _fin - _td(hours=24)]
    _calc = _pulso.calcular(_ventana, es_estado, categoria_ais, fuerza_inferida)
    _fecha = marcos[-1]["hora"][:10]
    _hist = _pulso.actualizar_historial(PULSO, _fecha, _calc)
    _hechos = {}
    for _r in d["riesgos"]:
        _hechos.setdefault(_pulso.zona_de(_r["x"], _r["y"]), []).append("Piratería, km 340 (hecho puntual informado por prensa, oct. 2025)")
    _hechos.setdefault("z4", []).append("Presencia atribuida al PCC, según medios y la Presidencia de Paraguay, en Canindeyú y Alto Paraná: atribución, no sentencia")
    _ctx_zonas = {z: _siwa.resumen_unidades(_FUENTES_SIWA, un) for z, un in _siwa.UNIDADES_POR_ZONA.items()}
    _pulso_html = _pulso.bloque_html(_calc, _hist, _fecha, _hechos, _ctx_zonas, _siwa.pie(_FUENTES_SIWA))
    # --- libro de indicios: nivel del río, presencia del Estado, interrupciones, violencia política y hechos citados ---
    import indicios as _ind
    _raiz = Path(os.environ.get("SITIO_RAIZ") or Path(__file__).resolve().parents[1])
    _geo = json.load(open(D / "estaciones_geo.json", encoding="utf-8")) if (D / "estaciones_geo.json").exists() else {}
    _nivel = Path(os.environ.get("SITIO_NIVEL") or (_raiz / "datos" / "publico" / "nivel-rio-py.json"))
    _segs = _ind._segmentos(d["rio_parana"]) + _ind._segmentos(d["rio_paraguay"])
    _ests, _nivel_obtenido = ([], "")
    if _nivel.exists():
        _ests, _nivel_obtenido = _ind.estaciones(_nivel, _geo, _segs, _dtm.strptime(_fecha, "%Y-%m-%d").date())
    _ests_ar, _ = _ind.estaciones_ar(os.environ.get("SITIO_NIVEL_AR") or (_raiz / "datos" / "publico" / "nivel-rio-ar.json"), _segs, _dtm.strptime(_fecha, "%Y-%m-%d").date())
    _ests = _ests + _ests_ar
    _prensa = lambda n: {"nombre": n, "familia": "prensa", "calificacion": "C3"}
    _hechos_f = {
        _pulso.zona_de(d["riesgos"][0]["x"], d["riesgos"][0]["y"]) if d["riesgos"] else "z2": [{
            "id": "HEC-PIR", "tipo": "Seguridad", "titulo": "Piratería fluvial, km 340 (hecho puntual, oct. 2025)",
            "texto": "Motonave «Rosa» asaltada en octubre de 2025; informado por cuatro medios. Presunto, sin condena.",
            "fuentes": [_prensa("SL24"), _prensa("La Nación"), _prensa("Weekend / Perfil"), _prensa("Diario El Norte")],
            "no_dice": "Un hecho puntual no establece un patrón ni dice que el lugar sea hoy peligroso; no se atribuye autor."}],
        "z4": [{
            "id": "HEC-PCC", "tipo": "Seguridad", "titulo": "Presencia atribuida al PCC en Canindeyú y Alto Paraná",
            "texto": "La informan dos medios y comunicados de la Presidencia de Paraguay: atribución periodística y oficial, no sentencia.",
            "fuentes": [_prensa("La Política Online"), _prensa("ABC Color"), {"nombre": "Presidencia de la República del Paraguay", "familia": "oficial", "calificacion": "B2"}],
            "no_dice": "No implica que ocurra en todo el departamento ni involucra a sus habitantes; la fuente oficial no es independiente del Estado."}],
    }
    _prensa_ind = _ind.indicios_prensa(os.environ.get("SITIO_NOTICIAS") or (_raiz / "datos" / "publico" / "noticias.json"))
    _focos_pts, _focos_ind = _ind.focos(os.environ.get("SITIO_FOCOS") or (_raiz / "datos" / "publico" / "focos_corredor.json"))
    for _fp in sorted(_focos_pts, key=lambda q: (q["conf"] != "h", -q["frp"]))[:1500]:      # tope de peso de la página: primero los de confianza alta y más intensos
        poi_svg.append(_ind.marca_foco(_fp))
    # --- flujos ilícitos que usan el corredor, tomados de SIWA (rutas, frescura de los flujos y Vigía de fuentes) ---
    import flujos_siwa as _flu
    _flu_datos = _flu.cargar(D / "siwa" / "flujos_corredor.json")
    _flu_rutas, _flu_ind, _flujos_html = [], {}, ""
    if _flu_datos:
        _flu_rutas = _flu.seleccionar(_flu_datos, _segs, int(_fecha[:4]))
        for _k, _r in enumerate(_flu_rutas):
            poi_svg.append(_flu.trazo_svg(_k, _r))
            zona_pulso_info.append(_flu.info_ruta(_k, _r, _fecha))
        _flu_ind = _flu.indicios_por_zona(_flu_rutas)
        _flujos_html = _flu.tabla_html(_flu_rutas, _flu_datos, _fecha)
        if os.environ.get("SITIO_GUARDAR_FLUJOS") and _flu_datos.get("en_vivo"):
            json.dump(_flu.instantanea(_flu_datos, _flu_rutas), open(os.environ["SITIO_GUARDAR_FLUJOS"], "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    _esc_rec, _esc_evs, _esc_ind = _ind.escaner(os.environ.get("SITIO_ESCANER") or (_raiz / "datos" / "publico" / "escaner.json"), _fecha)
    _esc_svgs, _esc_infos = _ind.marcas_escaner(_esc_rec)
    poi_svg.extend(_esc_svgs)
    zona_pulso_info.extend(_esc_infos)
    _escaner_html = _ind.tabla_escaner(_esc_evs, _fecha)
    # --- actores del corredor y los rastros propios que se miden de cada uno ---
    import actores as _act
    _actores = _act.cargar(D / "actores.json")
    _ais_fuerza = {}
    for _p in marcos[-1]["puntos"]:
        if es_estado(_p):
            _ais_fuerza.setdefault(fuerza_inferida(_p), []).append((_p.get("nombre") or "sin nombre").strip())
    _vinc = _act.vincular(_actores, _esc_evs, _flu_rutas, _ais_fuerza)
    _ops, _fecha_ops = _act.operadores_osm(D / "amarres_osm.json")
    _actores_html = _act.tabla_html(_actores, _vinc, _ops, _fecha_ops, _fecha)
    import fuentes_vivas as _fv
    _vivas_html = _fv.tabla_html(_raiz / "datos" / "publico", marcos[-1]["hora"])

    _flu_extra = {z: [i] for z, i in _flu_ind.items()}
    for _z, _l in _ind.avisos(os.environ.get("SITIO_AVISOS") or (_raiz / "datos" / "publico" / "avisos_oficiales.json")).items():
        _flu_extra.setdefault(_z, []).extend(_l)
    if _OFAC:
        _imos_vistos = {str(_imo_valido(p.get("imo"))) for m in _ventana for p in m["puntos"] if _imo_valido(p.get("imo"))}
        _coinc = {k: v for k, v in _OFAC_VISTOS.items()}
        _f_ofac = {"nombre": "OFAC, lista SDN (Departamento del Tesoro de EE.UU.)", "familia": "oficial", "calificacion": "A2"}
        _flu_extra.setdefault("gen", []).append({
            "id": "SAN", "tipo": "Sanciones", "titulo": "Buques del corredor cuyo IMO figura en la lista SDN de OFAC",
            "texto": ("%d coincidencias entre %d números IMO transmitidos en las últimas 24 h y %d buques de la lista SDN%s." % (
                len(_coinc), len(_imos_vistos), len(_OFAC["buques"]), (": " + "; ".join("%s (IMO %s, programa %s)" % (n, i, o["programa"]) for i, (n, o) in _coinc.items())) if _coinc else "")),
            "fuentes": [_f_ofac], "nivel": "Fuente única",
            "no_dice": "Se cruza sólo por IMO. Una coincidencia es una pista para mirar, no una acusación: el IMO transmitido por AIS puede estar mal cargado, estar en la lista es una decisión de un Estado extranjero y los buques sin IMO transmitido no se pueden cruzar.",
            "dato": {"coincidencias": len(_coinc)}})
    for _z, _i in _esc_ind.items():
        _flu_extra.setdefault(_z, []).append(_i)
    _indicios = _ind.indicios(_calc, _ventana, es_estado, _ests, _FUENTES_SIWA, _siwa.UNIDADES_POR_ZONA, _hechos_f, _siwa, _prensa_ind, _focos_ind, _flu_extra)
    _indicios_html = _ind.tabla_html(_indicios, _fecha)
    # --- datos abiertos: el libro de indicios en JSON y un canal Atom con los hechos detectados y los indicios ---
    import xml.sax.saxutils as _sx
    _base = "https://fundacion-sherman-kent.github.io/ysyry/"
    _dir_salida = Path(SALIDA).parent
    (_dir_salida / "datos").mkdir(parents=True, exist_ok=True)
    _nombre_z = {z[0]: z[1] for z in _pulso.ZONAS}
    _nombre_z["gen"] = "Corredor en general"
    _abierto = {"generado": marcos[-1]["hora"], "licencia": "Datos propios de Ysyry: CC BY 4.0, citando «Ysyry, Fundación Sherman Kent». Cada indicio cita sus fuentes, que conservan sus licencias (ODbL, CC BY 4.0, dominio público, atribución de ACLED).",
                "aviso": "Un indicio no es una alerta. Los hechos detectados por el escáner son candidatos sin verificar.",
                "indicios": {_nombre_z.get(z, z): [{"id": i["id"], "tipo": i["tipo"], "titulo": i["titulo"], "texto": i["texto"], "nivel_de_evidencia": i["nivel"],
                                                   "fuentes": [{"nombre": f["nombre"], "familia": f["familia"]} for f in i["fuentes"]], "lo_que_no_dice": i["no_dice"]} for i in lst]
                             for z, lst in _indicios.items() if lst},
                "hechos_detectados": [{"fecha": h["fecha"], "tipo": [r for _, r in h["tipos"]], "lugares": h.get("lugares"), "titulo": h["titulo"], "medios": [{"dominio": m["dominio"], "url": m["url"]} for m in h["medios"]]} for h in _esc_evs[:100]]}
    json.dump(_abierto, open(_dir_salida / "datos" / "indicios.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    _ahora = marcos[-1]["hora"]
    _ent = []
    for _h in sorted(_esc_evs, key=lambda x: x["fecha"], reverse=True)[:25]:
        _ent.append("<entry><id>%s</id><title>%s</title><updated>%sT00:00:00Z</updated><link href=\"%s\"/><summary>%s</summary></entry>" % (
            _sx.escape("ysyry:escaner:" + _h["id"]), _sx.escape("Hecho detectado: " + _h["titulo"][:160]), _h["fecha"], _sx.escape(_h["medios"][0]["url"]),
            _sx.escape("Candidato detectado por reglas, no verificado. %s. Medios: %s." % ("; ".join(r for _, r in _h["tipos"]), ", ".join(m["dominio"] for m in _h["medios"])))))
    for _z, _lst in _indicios.items():
        for _i in _lst:
            if _i["id"] in ("NAV", "PRES", "FLU", "SAN", "ESC", "FOC") or _i["id"].startswith(("PRE-", "HEC-")):
                _ent.append("<entry><id>%s</id><title>%s</title><updated>%s</updated><link href=\"%s\"/><summary>%s</summary></entry>" % (
                    _sx.escape("ysyry:indicio:%s:%s:%s" % (_z, _i["id"], _fecha)), _sx.escape("%s · %s" % (_nombre_z.get(_z, _z), _i["titulo"])), _ahora, _base + "#indicios-zonas",
                    _sx.escape("%s Evidencia: %s. %s" % (_i["texto"], _i["nivel"], _i["no_dice"]))))
    (_dir_salida / "feed.xml").write_text('<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom"><id>%s</id><title>Ysyry: hechos detectados e indicios del corredor</title><updated>%s</updated>'
                                          '<link rel="self" href="%sfeed.xml"/><link href="%s"/><author><name>Fundación Sherman Kent</name></author><rights>Datos propios CC BY 4.0; cada entrada cita sus fuentes.</rights>%s</feed>'
                                          % (_base, _ahora, _base, _base, "".join(_ent)), encoding="utf-8")
    _GUIA = _guia.catalogo({"n_buques": len(marcos[-1]["puntos"]), "ultima": marcos[-1]["hora"][:16].replace("T", " ") + " UTC",
                            "n_estaciones": len([e for e in _ests if e["pos"]]), "n_bajas": len([e for e in _ests if e["estado"] == "bajo"]),
                            "n_unidades_estado": len([p for p in marcos[-1]["puntos"] if es_estado(p)])})
    _reglas_previas = (json.load(open(PULSO, encoding="utf-8")).get("reglas", {}) if Path(PULSO).exists() else {})
    _candidatas = _ind.candidatas(_indicios, _ests, _fecha, _reglas_previas)
    _ind.registrar_disparos(PULSO, _fecha, _candidatas)
    if os.environ.get("SITIO_CANDIDATAS"):
        json.dump({"fecha": _fecha, "candidatas": _candidatas}, open(os.environ["SITIO_CANDIDATAS"], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for _i, _e in enumerate(_ests):
        if _e["pos"]:
            poi_svg.append(_ind.marca_estacion(_i, _e))
            zona_pulso_info.append(_ind.info_estacion(_i, _e, _nivel_obtenido))
    _con_aviso = {c["zona"] for c in _candidatas}
    for _z, _nom, _cob in _pulso.ZONAS:
        _zi = _pulso.info_zona(_z, _calc, _hist, _fecha, _hechos, _ctx_zonas)
        _zi["ctx"] = ["Evidencia %s · %s: %s" % (i["nivel"], i["titulo"], i["texto"]) for i in _indicios.get(_z, [])] + _zi["ctx"]
        zona_pulso_info.append(_zi)
        _sv, _bx, _by, _bt = _pulso.boya(_z, _calc, aviso=(_nom in _con_aviso))
        poi_svg.append(_sv)
        poi_etq_svg.append(callout(_bx, _by, _bt, "boya", "seguridad comercio estado regulatorio indicios"))

# Las imágenes se incrustan en la página (data URI), una sola vez por imagen:
# el visor de artefactos no carga imágenes enlazadas desde otro dominio.
import base64, hashlib
_srcs = set()
for _lista in (poi_info, riesgo_info, zona_info):
    for _x in _lista:
        if _x.get("foto"): _srcs.add(_x["foto"]["src"])
for _x in buque_info:
    if _x.get("foto"): _srcs.add(_x["foto"]["src"])
FOTOS = {}
for _s in _srcs:
    _ruta = D / "fotos_cache_min" / ("%s.jpg" % hashlib.md5(_s.encode()).hexdigest())
    if not _ruta.exists():          # una foto sin archivo no debe tirar el sitio entero
        print("aviso: falta la imagen", _ruta.name)
        continue
    _bin = open(_ruta, "rb").read()
    _mime = "image/png" if _bin[1:4] == b"PNG" else "image/jpeg"
    FOTOS[_s] = "data:%s;base64," % _mime + base64.b64encode(_bin).decode()
fotos_json = json.dumps(FOTOS)

# --- capa satelital (NASA GIBS: GOES-East y VIIRS), bajada por colectores/satelite_gibs.py ---
# La proyección del mapa es lineal en lon y lat (ajustada con 24 ciudades de posición
# conocida, error máximo 0,06 px), así que la imagen entra sin deformarse.
_P = json.load(open(D / "proyeccion.json"))
_SAT = json.load(open(SAT_DIR / "satelite.json", encoding="utf-8"))
_lon0, _lat0, _lon1, _lat1 = _SAT["bbox"]
_sx = _P["ax"] * _lon0 + _P["bx"]
_sy = _P["ay"] * _lat1 + _P["by"]          # ay < 0: el borde norte queda arriba
_sw = _P["ax"] * (_lon1 - _lon0)
_sh = -_P["ay"] * (_lat1 - _lat0)
sat_imgs = []
for _k in ("viirs", "goes"):               # GOES encima de VIIRS
    _b64 = base64.b64encode(open(SAT_DIR / ("%s.jpg" % _k), "rb").read()).decode()
    sat_imgs.append('<image id="sat-%s" class="sat-img" x="%.2f" y="%.2f" width="%.2f" height="%.2f" '
                    'preserveAspectRatio="none" href="data:image/jpeg;base64,%s"/>' % (_k, _sx, _sy, _sw, _sh, _b64))
sat_meta_json = json.dumps({k: _SAT.get(k) for k in ("goes", "viirs")} | {"obtenido": _SAT["obtenido"], "atribucion": _SAT["atribucion"]},
                           ensure_ascii=False)

horas_json = json.dumps([m["hora"] for m in marcos])
def _comprimir(lista):
    """Las fichas de buques se repiten casi iguales en las 24 capturas: los textos y fotos que se repiten van a una tabla y cada ficha guarda un número.
    El navegador los vuelve a expandir al cargar, así que lo que se ve no cambia; sólo baja el peso de la página."""
    from collections import Counter
    cuenta = Counter()
    for x in lista:
        for k in ("fuente", "categoria", "ctx_f", "ctx_t", "foto"):
            v = x.get(k)
            if isinstance(v, (str, dict)) and len(json.dumps(v, ensure_ascii=False)) > 24:
                cuenta[json.dumps(v, ensure_ascii=False, sort_keys=True)] += 1
        for t in (x.get("tipo") or "").split(" · "):
            if len(t) > 12:
                cuenta["t:" + t] += 1
    ref, idx = [], {}

    def numero(clave, valor):
        if clave not in idx:
            idx[clave] = len(ref)
            ref.append(valor)
        return idx[clave]
    out = []
    for x in lista:
        y = dict(x)
        for k in ("fuente", "categoria", "ctx_f", "ctx_t", "foto"):
            v = y.get(k)
            if isinstance(v, (str, dict)) and len(json.dumps(v, ensure_ascii=False)) > 24:
                clave = json.dumps(v, ensure_ascii=False, sort_keys=True)
                if cuenta[clave] >= 2:
                    y[k] = {"$": numero(clave, v)}
        partes = (y.get("tipo") or "").split(" · ")
        if len(partes) > 1 or (partes and len(partes[0]) > 12):
            y["tipo"] = {"$t": [numero("t:" + t, t) if (len(t) > 12 and cuenta["t:" + t] >= 2) else t for t in partes]}
        out.append(y)
    return out, ref


_info_lista, _info_ref = _comprimir(poi_info + riesgo_info + zona_info + zona_pulso_info + buque_info)
info_json = json.dumps(_info_lista, ensure_ascii=False, separators=(",", ":"))

TPL = r"""<!doctype html>
<title>Ysyry — corredor Hidrovía</title>
<link rel="alternate" type="application/atom+xml" title="Ysyry: hechos detectados e indicios" href="feed.xml">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&display=swap">
<style>
:root{
  /* Ysyry usa el AZUL de la casa (navy y gris azul), como SIWA usa el naranja y FEMÓNOE el violeta.
     Paleta cerrada: no se agrega ningún azul nuevo. El naranja queda sólo como señal. */
  --azul-profundo:#00121E; --azul-noche:#07131E; --naranja:#FB6500; --gris-acero:#667B89;
  --acento:#00121E; --acento-sobre:#F9F9F7; --acento-texto:#00121E;
  --papel:#FFFFFF; --linea:#DDE2E5; --fondo:#F9F9F7; --bg:#F9F9F7; --fg:#00121E;
}
:root[data-theme="dark"]{--acento:#667B89;--acento-texto:#C6C6C5;--bg:#07131E;--fg:#F9F9F7;--papel:#0d1b28;--linea:#223241;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font-family:Inter,system-ui,sans-serif;font-weight:500;line-height:1.6;padding-inline:16px}
.envoltorio{max-width:1480px;margin:0 auto}
.aviso{background:var(--azul-profundo);color:#F9F9F7;font-weight:700;letter-spacing:.06em;
  text-transform:uppercase;font-size:11px;text-align:center;padding:9px;margin:12px -16px 0;border-radius:10px}
header{padding:16px 0;border-bottom:1px solid var(--linea);display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}
/* Franja superior como la de SIWA: siempre clara, también en modo oscuro, porque el texto del logo
   de la Fundación es azul oscuro y desaparecería sobre un fondo oscuro. */
.topbar{background:var(--papel);color:var(--fg);border-bottom:1px solid var(--linea);margin-inline:-16px;position:sticky;top:0;z-index:50}
html{scroll-padding-top:var(--alto-cab,72px)}
.topbar-in{max-width:1480px;margin:0 auto;padding:14px 24px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:20px;min-width:0}
.marca-enlace{display:flex;align-items:center}
.logo{height:44px;width:auto;display:block}
.logo.oscuro{display:none}
:root[data-theme="dark"] .aviso{background:var(--gris-acero)}
:root[data-theme="dark"] .logo.claro{display:none}
:root[data-theme="dark"] .logo.oscuro{display:block}
.sep{width:1px;height:38px;background:var(--linea);flex:0 0 auto}
.inicio{display:flex;align-items:center;gap:12px;text-decoration:none;color:var(--fg)}
.inicio .isotipo{color:var(--acento-texto)}
.inicio .nombre{display:block;font-weight:700;letter-spacing:-0.02em;font-size:22px;line-height:1.15;margin-bottom:4px}
.inicio small{display:block;font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--gris-acero);line-height:1.25}
.franja-derecha{display:flex;align-items:center;gap:28px;flex-wrap:wrap}
.topbar nav{gap:26px}
.topbar nav a{color:var(--gris-acero)}
.topbar nav a:hover{color:var(--fg)}
.ultima{font-size:12px;color:var(--gris-acero);white-space:nowrap}
.ultima b{color:var(--fg)}
.tema{border:1px solid var(--linea);background:var(--papel);color:var(--fg);border-radius:20px;padding:5px 12px;font-size:12px;font-weight:500;cursor:pointer;font-family:inherit}
.tema:hover{border-color:var(--gris-acero)}
@media (max-width:560px){.logo{height:34px}.inicio small{display:none}.sep{height:24px}.topbar nav{gap:12px;font-size:12.5px}.ultima{display:none}}
/* cabecera fija y compacta en el teléfono: la web de la Fundación queda en el logo, y el enlace de texto se oculta para ganar alto */
@media (max-width:560px){.topbar-in{padding:6px 14px;gap:4px}.franja-derecha{width:100%;justify-content:space-between;gap:10px;flex-wrap:nowrap}
.topbar nav a:nth-child(3){display:none}.tema{padding:4px 10px;font-size:12px}.logo{height:30px}.inicio .nombre{font-size:19px;margin-bottom:0}}
.isotipo{flex:0 0 auto;animation:latido2 2.4s ease-out infinite}
.isotipo .punta{animation:latido 2.4s ease-out infinite}
@keyframes latido{0%{filter:drop-shadow(0 0 0 rgba(251,101,0,.5))}70%{filter:drop-shadow(0 0 5px rgba(251,101,0,0))}100%{filter:drop-shadow(0 0 0 rgba(251,101,0,0))}}
@keyframes latido2{0%,100%{opacity:1}50%{opacity:.88}}
.nombre{font-weight:700;letter-spacing:-0.02em;font-size:20px}
.metricas{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:1px;background:var(--linea);
  margin:14px 0;border:1px solid var(--linea);border-radius:12px;overflow:hidden}
.metrica{background:var(--papel);padding:12px 14px}
.metrica .n{font-weight:700;font-size:19px;font-variant-numeric:tabular-nums}
.metrica .k{font-size:10.5px;color:var(--gris-acero);margin-top:2px}
.col-mapa{background:var(--azul-noche);border-radius:14px;padding:14px;position:relative;margin-bottom:0}
.mapa-cab{font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:#C6C6C5;
  margin-bottom:8px;display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
.zoom-ctrl{display:flex;gap:6px;order:-1;flex:0 0 auto}
.zoom-ctrl button{width:38px;height:38px;border-radius:8px;border:1px solid rgba(255,255,255,.25);
  background:rgba(255,255,255,.1);color:#fff;font-size:19px;font-weight:700;cursor:pointer;
  display:flex;align-items:center;justify-content:center;font-family:inherit;line-height:1}
.zoom-ctrl button:hover{background:rgba(255,255,255,.2)}
.mapa-marco{overflow:hidden;border-radius:8px;touch-action:none}
svg.mapa{width:100%;height:auto;display:block;max-height:70vh;cursor:grab;user-select:none;-webkit-user-select:none}
svg.mapa.arrastrando{cursor:grabbing}
.sat-img{display:none}
svg.mapa[data-sat="goes"] #sat-goes,svg.mapa[data-sat="viirs"] #sat-viirs{display:inline}
svg.mapa[data-sat] .prov{display:none}
.sat-ctrl{display:flex;flex-wrap:wrap;align-items:center;gap:6px 8px;margin:0 0 8px;font-size:11px;color:#b6c2cc}
.sat-tit{font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#C6C6C5;font-size:10.5px}
.sat-btn{border:1px solid rgba(255,255,255,.22);background:rgba(255,255,255,.07);color:#e6edf2;border-radius:16px;
  padding:5px 11px;font-size:11.5px;font-weight:700;cursor:pointer;font-family:inherit}
.sat-btn:hover{background:rgba(255,255,255,.15)}
.sat-btn.activa{background:var(--gris-acero);border-color:var(--gris-acero);color:#F9F9F7}
.sat-op{display:none;align-items:center;gap:6px}
.sat-ctrl.encendida .sat-op{display:flex}
.sat-op input{width:90px;accent-color:var(--gris-acero)}
.sat-info{flex:1 1 100%;font-size:10.5px;color:#93a3af;line-height:1.4}
/* Trazos de ancho constante en pantalla (vector-effect): sin esto, al acercar
   el río y las rutas se vuelven bandas enormes que tapan a los buques. Los
   anchos están en píxeles. */
.rio-real,.rio-paraguay,.afluente,.ruta,.bioceanico,.pais,.zona-actor{vector-effect:non-scaling-stroke}
.pais{stroke-width:1.6px}
.agua-osm{fill:#23475f;fill-opacity:.9;stroke:none}
.rio-banda{stroke:#23475f;stroke-opacity:.9;stroke-linejoin:round;stroke-linecap:round}
.rio-real{stroke:var(--gris-acero);stroke-width:3.5px;stroke-linejoin:round;stroke-linecap:round}
.rio-paraguay{stroke:var(--gris-acero);stroke-width:3px;stroke-linejoin:round;stroke-linecap:round;opacity:.6}
.afluente{stroke:#6b8fa3;stroke-width:1.6px;stroke-linejoin:round;stroke-linecap:round;opacity:.65}
.ruta{stroke:#f0c674;stroke-width:1.2px;stroke-linejoin:round;stroke-linecap:round;opacity:.6}
.bioceanico{stroke:var(--naranja);stroke-width:2.2px;stroke-linejoin:round;stroke-linecap:round;stroke-dasharray:6 7;opacity:.8}
.zona-actor{fill:var(--naranja);fill-opacity:.14;stroke:var(--naranja);stroke-opacity:.55;stroke-width:1.6px;stroke-dasharray:5 5;cursor:pointer}
.zona-actor:hover{fill-opacity:.26}
.punto{fill:#fff;stroke:var(--azul-noche);stroke-width:1.1}
.clicable,.clicable *{cursor:pointer}
.amar{display:none}
svg.zoom-a .amar-a,svg.zoom-b .amar-b{display:inline}
.amar-pu .m{fill:#667B89;stroke:#F9F9F7;stroke-width:.9}
.amar-mu .m{fill:#C6C6C5;stroke:#07131E;stroke-width:.8;transform:scale(.8)}
.amar-ra .m{fill:transparent;stroke:#C6C6C5;stroke-width:1.1;transform:scale(.8)}
.cuad{width:9px;height:9px;display:inline-block;flex:0 0 auto}
.hit{fill:transparent;stroke:none;pointer-events:all}
.clicable:hover .hit{fill:rgba(249,249,247,.18)}
.poi.puerto .punto{fill:var(--gris-acero)}
.poi.tf .punto{fill:var(--naranja)}
.buque{fill:#ffd400;stroke:var(--azul-noche);stroke-width:.8}
.buque-flecha{fill:#ffd400;stroke:var(--azul-noche);stroke-width:.5}
.riesgo{fill:var(--naranja);stroke:#fff;stroke-width:1.4}
/* Etiquetas como nube de texto con línea al punto — no texto suelto que se
   solape; sólo aparecen acercando el mapa, para que la vista general no se
   llene de texto. */
.etq-g{display:none;pointer-events:none}
.zoom-cerca .etq-g{display:block}
.etq-g.etq-oculta{display:none}
.etq-linea{stroke:rgba(255,255,255,.55);stroke-width:.6}
.etq-ancla{fill:#fff}
.etq-fo{overflow:visible}
.etq-chip{font-family:Inter,sans-serif;font-size:7.6px;font-weight:700;line-height:20px;
  padding:0 7px;border-radius:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  max-width:100%;display:inline-block;box-shadow:0 1px 4px rgba(0,0,0,.35)}
.chip-puerto{background:var(--gris-acero);color:#F9F9F7}
.chip-ciudad{background:#1b2a38;color:#dfe6e9;border:.6px solid rgba(255,255,255,.25)}
.chip-tf{background:var(--naranja);color:var(--azul-profundo)}
.chip-riesgo{background:var(--naranja);color:var(--azul-profundo)}
.est-g .gota{fill:#8fd9c4;stroke:var(--azul-noche);stroke-width:1}
.est-bajo .gota{fill:var(--naranja)}
.est-alto .gota{fill:#cdeee4}
.est-cerca .gota{fill:#ffb27a}
.est-regulada .gota{fill:#7fb0d6;opacity:.7}
.est-vencida .gota{fill:transparent;stroke:#667B89;stroke-dasharray:2 1.5}
.boya-aviso .boya-n{fill:var(--naranja)}
.boya-aviso .boya-aro{stroke:var(--naranja)}
.ev{display:inline-block;font-size:10.5px;font-weight:700;letter-spacing:.03em;padding:2px 7px;border-radius:999px;border:1px solid var(--gris-acero);color:var(--gris-acero);white-space:nowrap}
.ev-fuerte{background:var(--azul-profundo);color:#F9F9F7;border-color:var(--azul-profundo)}
.ev-corroborado{border-color:var(--azul-profundo);color:var(--fg)}
.gauge{width:100%;height:auto;display:block}
.guia-btn{position:fixed;right:18px;bottom:18px;z-index:35;display:flex;align-items:center;gap:8px;padding:9px 16px 9px 11px;border-radius:999px;border:2px solid #667B89;background:#F9F9F7;color:#00121E;font:700 13px/1 inherit;font-family:inherit;cursor:pointer;box-shadow:0 6px 20px rgba(0,18,30,.35)}
.guia-btn svg{width:26px;height:26px;stroke:#00121E;fill:none;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
.guia-btn:hover{background:#ffffff;border-color:#00121E}
.guia-btn:focus-visible{outline:3px solid #FB6500;outline-offset:2px}
body.ficha-abierta .guia-btn{right:calc(340px + 18px)}
.guia{position:fixed;right:18px;bottom:74px;z-index:36;width:380px;max-width:calc(100vw - 24px);height:min(560px,calc(100vh - 150px));display:none;flex-direction:column;background:var(--papel);color:var(--fg);border:1px solid var(--linea);border-radius:14px;box-shadow:0 14px 40px rgba(0,18,30,.35);overflow:hidden}
.guia.abierta{display:flex}
body.ficha-abierta .guia{right:calc(340px + 18px)}
.guia-cab{display:flex;align-items:center;gap:10px;padding:12px 14px;background:var(--azul-profundo);color:#F9F9F7}
.guia-cab svg{width:26px;height:26px;stroke:#F9F9F7;fill:none;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round;flex:0 0 auto}
.guia-cab b{font-size:14px;display:block}
.guia-cab small{font-size:11px;opacity:.8;display:block}
.guia-cab button{margin-left:auto;background:transparent;border:0;color:#F9F9F7;font-size:22px;line-height:1;cursor:pointer;padding:2px 6px}
.guia-msgs{flex:1;overflow-y:auto;padding:12px 14px;display:flex;flex-direction:column;gap:10px;font-size:13px;line-height:1.5}
.guia-m{max-width:92%;padding:9px 12px;border-radius:12px;background:var(--linea);color:var(--fg);white-space:pre-line}
.guia-m.yo{align-self:flex-end;background:var(--azul-profundo);color:#F9F9F7}
.guia-m.nota{font-size:11.5px;color:var(--gris-acero);background:transparent;padding:0 2px}
.guia-acc{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.guia-acc button,.guia-chips button{font:600 12px/1.2 inherit;font-family:inherit;padding:6px 10px;border-radius:999px;border:1px solid var(--azul-profundo);background:transparent;color:var(--fg);cursor:pointer;text-align:left}
.guia-acc button:hover,.guia-chips button:hover{background:var(--azul-profundo);color:#F9F9F7}
.guia-chips{display:flex;flex-wrap:wrap;gap:6px;padding:0 14px 10px}
.guia-in{display:flex;gap:8px;padding:10px 12px;border-top:1px solid var(--linea)}
.guia-in input{flex:1;min-width:0;padding:9px 11px;border-radius:9px;border:1px solid var(--linea);background:var(--papel);color:var(--fg);font:inherit;font-size:13px}
.guia-in button{padding:0 14px;border-radius:9px;border:0;background:var(--azul-profundo);color:#F9F9F7;font:700 13px/1 inherit;font-family:inherit;cursor:pointer}
@media (max-width:760px){.guia{right:8px;left:8px;bottom:70px;width:auto;max-width:none;height:min(70vh,520px)}body.ficha-abierta .guia-btn{display:none}body.ficha-abierta .guia{display:none}.guia-btn{right:12px;bottom:12px}}
@media print{.guia-btn,.guia{display:none!important}}
.foco{fill:var(--naranja);fill-opacity:.55;stroke:none}
.foco-alto{fill-opacity:.9;stroke:#fff;stroke-width:.5}
.solo-fam{display:none}
svg.fam-flujos .solo-fam{display:inline}
.flujo{fill:none;stroke:#e9e3d2;stroke-width:1.8px;stroke-dasharray:6 4;stroke-linecap:round;stroke-linejoin:round;opacity:.75;vector-effect:non-scaling-stroke}
.flujo-act{stroke:var(--naranja);opacity:.95;stroke-width:2.2px}
.flujo-hit{fill:none;stroke:transparent;stroke-width:12px;vector-effect:non-scaling-stroke;pointer-events:stroke}
.flujo-pt{fill:#e9e3d2;stroke:var(--azul-noche);stroke-width:1}
.flujo-pt.flujo-act{fill:var(--naranja)}
.esc{fill:#e9e3d2;stroke:var(--naranja);stroke-width:1.4}
details.actor{border:1px solid var(--linea);border-radius:8px;padding:8px 12px;margin:0 0 8px;max-width:980px}
details.actor summary{cursor:pointer;font-size:14px}
details.actor p,details.actor li{font-size:13px;line-height:1.55}
details.actor .afirm{padding-left:18px}
details.actor .gris{color:var(--gris-acero);font-size:12px;margin-left:8px}
.pulso h3{font-size:15px;margin:16px 0 8px}
.chip-boya{background:#0f2a2a;color:#cdeee4;border:.6px solid #8fd9c4}
.boya-n{fill:#8fd9c4;stroke:var(--azul-noche);stroke-width:.8}
.boya-aro{fill:none;stroke:#8fd9c4;stroke-width:1.2;opacity:0;transform-box:fill-box;transform-origin:center;animation:sonar 3s ease-out infinite;pointer-events:none}
.boya-aro.a2{animation-delay:1.5s}
.boya-sd .boya-n{fill:transparent;stroke:#667B89;stroke-width:1.2;stroke-dasharray:2 1.5}
.boya-sd .boya-aro{animation:none;display:none}
@keyframes sonar{0%{transform:scale(.4);opacity:.9}100%{transform:scale(1.7);opacity:0}}
@media (prefers-reduced-motion:reduce){.boya-aro{animation:none;opacity:.45}}
.spark{display:block;margin:4px 0 2px}
.spark rect{fill:var(--gris-acero)}
.spark .pe{fill:#2f7bff}
.panel .spark-panel{padding:8px 0;border-top:1px solid var(--linea)}
.panel .spark-panel svg{width:100%;height:auto}
.latido{display:inline-flex;align-items:center;gap:7px;letter-spacing:.06em;white-space:nowrap}
.latido i{width:9px;height:9px;border-radius:50%;background:#8fd9c4;position:relative;flex:0 0 auto}
.latido i::after{content:"";position:absolute;inset:-1px;border-radius:50%;border:1.5px solid #8fd9c4;animation:sonar 2.4s ease-out infinite}
.latido.retrasada i,.latido.sinsenal i{background:var(--naranja)}
.latido.retrasada i::after,.latido.sinsenal i::after{border-color:var(--naranja)}
.latido.sinsenal i::after{animation:none}
@media (prefers-reduced-motion:reduce){.latido i::after{animation:none}}
.chip-zona{background:#2a1808;color:#ffd9bf;border:.6px solid var(--naranja)}
.reproductor{display:flex;align-items:center;gap:10px;padding:12px 2px;flex-wrap:wrap}
.reproductor button{background:var(--acento);border:none;color:var(--acento-sobre);width:32px;height:32px;border-radius:50%;
  font-size:13px;cursor:pointer;flex:0 0 auto}
.reproductor input[type=range]{flex:1;min-width:120px;accent-color:var(--acento)}
.reproductor .hora{font-weight:700;font-size:13px;min-width:110px}
.reproductor .conteo{color:var(--gris-acero);font-size:11.5px}
.leyenda{display:flex;gap:12px;flex-wrap:wrap;padding:10px 0;font-size:10px;color:var(--gris-acero);border-top:1px solid var(--linea)}
.leyenda span{display:flex;align-items:center;gap:5px;max-width:100%;line-height:1.35}
.sw{width:12px;height:2.5px;display:inline-block}
.dot{width:7px;height:7px;border-radius:50%;display:inline-block}
/* Barra lateral de ficha — fija a la derecha en pantallas anchas, hoja
   inferior en celular. Nunca se superpone al mapa: lo empuja. */
.panel{position:fixed;right:0;top:var(--alto-cab,0px);bottom:0;width:340px;max-width:88vw;background:var(--papel);
  border-left:1px solid var(--linea);box-shadow:-8px 0 24px rgba(0,0,0,.18);
  transform:translateX(100%);transition:transform .25s ease;z-index:20;overflow-y:auto}
.panel.abierto{transform:translateX(0)}
.panel-cover{position:relative;height:132px;padding:14px 20px 10px;display:flex;flex-direction:column;
  justify-content:flex-end;overflow:hidden;color:#fff}
.panel-cover .ini{position:absolute;right:10px;top:-14px;font-size:76px;font-weight:700;
  opacity:.16;line-height:1;font-family:Inter,sans-serif}
.panel-cover svg{width:26px;height:26px;stroke:#fff;opacity:.92;margin-bottom:8px}
.panel-cover img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:none}
.panel-cover.con-foto img{display:block}
.panel-cover.con-foto::after{content:"";position:absolute;inset:0;
  background:linear-gradient(0deg,rgba(0,0,0,.72),rgba(0,0,0,.08) 55%)}
.panel-cover.con-foto svg,.panel-cover.con-foto .ini{display:none}
.panel-cover .credito{position:relative;z-index:1;font-size:9.5px;color:rgba(255,255,255,.85);
  text-decoration:none;display:none;align-items:center;gap:4px}
.panel-cover.con-foto .credito{display:flex}
.cover-puerto{background:linear-gradient(135deg,#00121E,#667B89)}
.cover-ciudad{background:linear-gradient(135deg,#17222d,#324a5e)}
.cover-tf{background:linear-gradient(135deg,#7a3300,var(--naranja))}
.cover-riesgo{background:linear-gradient(135deg,#7a3300,var(--naranja))}
.cover-estacion{background:linear-gradient(135deg,#00121E,#2b5f7a)}
.cover-flujo{background:linear-gradient(135deg,#00121E,#6b4a1e)}
.cover-escaner{background:linear-gradient(135deg,#00121E,#3a3a1f)}
.cover-boya{background:linear-gradient(135deg,#00121E,#1f5c55)}
.cover-zona{background:linear-gradient(135deg,#5c1f00,var(--naranja))}
.cover-estado{background:linear-gradient(135deg,#0b2a66,#2f7bff)}
.cover-amarre{background:linear-gradient(135deg,#00121E,#667B89)}
.cover-buque{background:linear-gradient(135deg,var(--azul-noche),#223241)}
.panel .cerrar{position:absolute;top:12px;right:12px;background:rgba(255,255,255,.18);border:none;
  color:#fff;font-size:15px;cursor:pointer;width:26px;height:26px;border-radius:50%;z-index:1}
.panel-body{padding:16px 20px 20px}
.panel .etiqueta-tipo{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.06em;
  text-transform:uppercase;color:var(--azul-profundo);background:var(--fondo);border-radius:5px;
  padding:3px 7px;margin:0 0 10px}
.panel h3{margin:0 0 10px;font-size:17px;font-weight:700;line-height:1.2}
.panel .dato{font-size:12.5px;color:var(--fg);border-top:1px solid var(--linea);padding:8px 0}
.panel .dato b{display:block;font-size:10px;font-weight:700;color:var(--gris-acero);
  text-transform:uppercase;letter-spacing:.04em;margin-bottom:2px}
.panel .coord{font-size:11px;color:var(--gris-acero);font-variant-numeric:tabular-nums;
  display:flex;align-items:center;gap:5px;margin-top:10px}
.panel .dato.ctx{border-top:0;padding:3px 0 3px 10px;border-left:2px solid var(--linea)}
.panel .nota-foto{font-size:10.5px;color:var(--gris-acero);margin:0 0 8px;font-style:italic}
.panel .fuente{font-size:11px;color:var(--acento-texto);font-weight:700;margin-top:12px}
@media (max-width: 760px){
  .panel{right:0;left:0;top:auto;bottom:0;width:auto;max-width:none;max-height:76vh;
    border-left:none;border-top:1px solid var(--linea);border-radius:16px 16px 0 0;
    transform:translateY(100%)}
  .panel.abierto{transform:translateY(0)}
  .panel-cover{border-radius:16px 16px 0 0}
}
footer{padding:14px 0 24px;border-top:1px solid var(--linea);font-size:10px;color:var(--gris-acero);
  display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px}

nav{display:flex;gap:22px;font-size:13px;color:var(--gris-acero)}
nav a{color:inherit;text-decoration:none}
nav a:hover{color:var(--fg)}
.hero{padding:34px 0 10px;max-width:760px}
.hero .et{font-weight:700;letter-spacing:.16em;text-transform:uppercase;font-size:11px;color:var(--gris-acero);margin:0 0 10px}
.hero h1{font-weight:700;letter-spacing:-0.035em;font-size:clamp(28px,5.4vw,42px);line-height:1.04;margin:0 0 14px;text-wrap:balance}
.hero p{color:var(--gris-acero);font-size:15px;font-weight:400;margin:0;max-width:52ch}

.familias{display:flex;gap:6px;flex-wrap:wrap;margin:22px 0 10px}
.familia-tab{border:1px solid var(--linea);background:var(--papel);color:var(--fg);border-radius:20px;
  padding:7px 14px;font-size:12.5px;font-weight:700;cursor:pointer;font-family:inherit}
.familia-tab.activa{background:var(--acento);border-color:var(--acento);color:var(--acento-sobre)}
.dim{opacity:.1!important;transition:opacity .25s}

.prospectiva{padding:26px 0 8px}
.prospectiva h2{font-weight:700;letter-spacing:-0.02em;font-size:19px;margin:0 0 4px}
.prospectiva .sub{color:var(--gris-acero);font-size:12.5px;margin:0 0 16px}
.pulso{padding:22px 0 8px}
.pulso h2{font-weight:700;letter-spacing:-0.02em;font-size:19px;margin:0 0 4px}
.pulso .sub{color:var(--gris-acero);font-size:12.5px;margin:0 0 12px;max-width:880px}
.tabla-pulso{overflow-x:auto;margin:0 0 10px;border:1px solid var(--linea);border-radius:8px}
.tabla-pulso table{border-collapse:collapse;width:100%;min-width:1080px;font-size:12.5px}
.tabla-pulso th,.tabla-pulso td{padding:9px 10px;text-align:left;vertical-align:top;border-top:1px solid var(--linea)}
.tabla-pulso thead th{border-top:0;font-size:10.5px;text-transform:uppercase;letter-spacing:.04em;color:var(--gris-acero)}
.tabla-pulso tbody th small{display:block;font-weight:400;color:var(--gris-acero);font-size:11px;margin-top:2px}
.tabla-pulso td.sd{color:var(--gris-acero)}
.alertas-fem{margin:0 0 10px;padding-left:18px;max-width:880px}
.alertas-fem li{font-size:13px;line-height:1.55;margin:0 0 10px}
.alertas-fem .gris{color:var(--gris-acero);font-size:12px}
.metodo{padding:8px 0 20px}
.metodo a{color:var(--acento-texto);text-decoration:underline}
.hero .estados{margin:-6px 0 14px;font-size:13px;color:var(--gris-acero)}
.metodo h2{font-weight:700;letter-spacing:-0.02em;font-size:19px;margin:0 0 4px}
.metodo .sub{color:var(--gris-acero);font-size:12.5px;margin:0 0 12px}
.metodo ul{margin:0;padding-left:18px;max-width:880px}
.metodo li{font-size:13px;line-height:1.55;margin:0 0 9px;color:var(--fg)}
footer{flex-direction:column}
.pregunta{border:1px solid var(--linea);border-radius:12px;padding:16px 18px;background:var(--papel);margin-bottom:10px}
.pregunta .q{font-weight:700;font-size:14.5px;margin-bottom:6px}
.pregunta .meta{font-size:12px;color:var(--gris-acero)}
.pregunta .barra{height:6px;background:var(--linea);border-radius:3px;margin-top:10px;overflow:hidden}
.pregunta .barra i{display:block;height:100%;background:var(--acento);width:0;transition:width 1.1s ease}

@media (prefers-reduced-motion: no-preference){
  .entra{animation:entrar .5s ease both}
  .entra.r2{animation-delay:.08s} .entra.r3{animation-delay:.16s} .entra.r4{animation-delay:.24s}
  @keyframes entrar{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
}
</style>
<div class="topbar"><div class="topbar-in">
  <div class="brand">
    <a class="marca-enlace" href="https://fundacionkent.org/?utm_source=ysyry&amp;utm_medium=referral&amp;utm_campaign=marca&amp;utm_content=portada" target="_blank" rel="noopener" title="Ir a la web de la Fundación Sherman Kent"><img class="logo claro" src="__logo_color__" alt="Fundación Sherman Kent"><img class="logo oscuro" src="__logo_blanco__" alt="Fundación Sherman Kent"></a>
    <div class="sep"></div>
    <a class="inicio" id="ir-portada" href="./" title="Volver a la portada de Ysyry">
      <svg class="isotipo" width="30" height="30" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <path d="M16 5 L16 16 M16 16 L7 27 M16 16 L25 27" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
        <circle class="punta" cx="16" cy="5" r="2.8" fill="#FB6500"/>
      </svg>
      <span><span class="nombre">Ysyry</span><small>Corredor Hidrovía Paraguay-Paraná</small></span>
    </a>
  </div>
  <div class="franja-derecha">
    <nav><a href="#mapa">Corredor</a><a href="#metodo">Método</a><a href="https://fundacionkent.org/?utm_source=ysyry&amp;utm_medium=referral&amp;utm_campaign=marca&amp;utm_content=nav" target="_blank" rel="noopener">Fundación Sherman Kent ↗</a></nav>
    <span class="ultima">Última captura <b>__ultima_captura__</b></span>
    <button type="button" id="tema" class="tema" aria-pressed="false">Fondo oscuro</button>
  </div>
</div></div>
<div class="envoltorio">
<div class="aviso">Versión inicial — en construcción · datos abiertos, cada uno con su fuente y su fecha</div>

<div class="hero entra">
  <p class="et">Corredor Hidrovía Paraguay-Paraná</p>
  <h1>Cinco Estados, un río, cada dato con su fuente.</h1>
  <p class="estados">Argentina, Bolivia, Brasil, Paraguay y Uruguay.</p>
  <p>Embarcaciones, puertos, comercio y hechos de riesgo del corredor, con su origen y su fecha. Lo que todavía no sabemos o no cubrimos, lo decimos.</p>
</div>

<div class="metricas entra r2">
  <div class="metrica"><div class="n">75,7 Mt</div><div class="k">Gran Rosario, 1.º nodo agroexportador del mundo, 2025, según la Bolsa de Comercio de Rosario (fuente única)</div></div>
  <div class="metrica"><div class="n">+73,5%</div><div class="k">Exportaciones de Rosario, ene-may 2026 vs. 2025, según la Bolsa de Comercio de Rosario (fuente única; no se explica aquí la base de comparación)</div></div>
  <div class="metrica"><div class="n">__n_buques__</div><div class="k">Embarcaciones con AIS en la última captura (__ultima_captura__)</div></div>
  <div class="metrica"><div class="n">__n_capturas__</div><div class="k">Capturas horarias de AIS (≈ 1 día de historial); el AIS no cubre el río alto</div></div>
</div>

<div class="familias" id="mapa">
  <button class="familia-tab activa" data-familia="">Todo</button>
  <button class="familia-tab" data-familia="seguridad">Crimen organizado y riesgo</button>
  <button class="familia-tab" data-familia="comercio">Comercio y puertos</button>
  <button class="familia-tab" data-familia="estado">Fuerzas del Estado</button>
  <button class="familia-tab" data-familia="regulatorio">Regulatorio</button>
  <button class="familia-tab" data-familia="indicios">Indicios y nivel del río</button>
  <button class="familia-tab" data-familia="flujos">Flujos ilícitos (SIWA)</button>
</div>

<div class="col-mapa entra r3">
  <div class="mapa-cab">
    <span class="zoom-ctrl">
      <button id="zoom-mas" aria-label="Acercar">+</button>
      <button id="zoom-menos" aria-label="Alejar">&minus;</button>
      <button id="zoom-reset" aria-label="Restablecer">&#8634;</button>
    </span>
    <span class="latido" id="latido" data-ultima="__ultima_iso__" title="Viva: la captura horaria de AIS llegó a tiempo. No dice nada sobre el río ni sobre el tráfico: sólo que el sistema está recibiendo datos."><i></i><b id="latido-txt">Verificando señal…</b></span>
    <span>Corredor — click en un punto, zona o boya para ver su fuente · arrastrá o usá la rueda para acercar</span>
  </div>
  <div class="sat-ctrl" role="group" aria-label="Capa satelital">
    <span class="sat-tit">Satélite</span>
    <button class="sat-btn activa" data-sat="">Apagado</button>
    <button class="sat-btn" data-sat="goes">GOES-East · cuadro reciente</button>
    <button class="sat-btn" data-sat="viirs">VIIRS · diario</button>
    <label class="sat-op">Opacidad <input type="range" id="sat-op" min="20" max="100" value="90"></label>
    <span class="sat-info" id="sat-info"></span>
  </div>
  <div class="mapa-marco">
  <svg class="mapa" id="svg-mapa" viewBox="0 0 __W__ __H__" preserveAspectRatio="xMidYMid meet">
    __sat_imgs__
    __provincias__
    __agua_osm__
    __paises__
    __rutas__
    __bioceanico__
    __rio_pilco__
    __rio_bermejo__
    __rio_parana__
    __rio_paraguay__
    __zonas__
    __amarres__
    __poi__
    __grupos_hora__
    __riesgos__
    __zonas_etq__
    __poi_etq__
    __riesgos_etq__
  </svg>
  </div>
</div>

<div class="reproductor">
  <button id="btn-play" aria-label="Reproducir">&#9654;</button>
  <input type="range" id="slider" min="0" max="__max_marco__" value="0" step="1">
  <span class="hora" id="etq-hora">&mdash;</span>
  <span class="conteo" id="etq-conteo">&mdash;</span>
</div>

<div class="leyenda">
  <span><span class="sw" style="background:#dfe6e9"></span>Límite de país</span>
  <span><span class="sw" style="background:var(--gris-acero)"></span>Ríos (trazado real)</span>
  <span><span class="sw" style="background:#f0c674"></span>Ruta troncal</span>
  <span><span class="sw" style="background:var(--naranja);opacity:.8"></span>Corredor bioceánico (esquemático)</span>
  <span><span class="cuad" style="background:#667B89"></span>Puerto, terminal, ferry o dársena (OpenStreetMap)</span>
  <span><span class="cuad" style="background:#C6C6C5"></span>Muelle, atracadero o marina</span>
  <span><span class="cuad" style="background:transparent;border:1.5px solid #C6C6C5"></span>Rampa o amarradero · se ven al acercar</span>
  <span><span class="dot" style="background:#fff"></span>Ciudad</span>
  <span><span class="dot" style="background:var(--gris-acero)"></span>Terminal portuaria</span>
  <span><span class="dot" style="background:#ffd400"></span>Carga</span>
  <span><span class="dot" style="background:#b8f06a"></span>Pasajeros</span>
  <span><span class="dot" style="background:#ff8a5c"></span>Tanque</span>
  <span><span class="dot" style="background:#8fd9c4"></span>Pesca/remolque</span>
  <span><svg width="11" height="11" viewBox="-7 -9 14 16"><path d="M0,-8 L6,6 L-6,6 Z" fill="#2f7bff" stroke="#fff" stroke-width="1.2"/></svg>Embarcación del Estado (seguridad) — hoy sólo Argentina: el AIS no cubre el río alto, donde opera la Armada paraguaya</span>
  <span><span class="dot" style="background:#9aa7ad"></span>Otro — click para nombre, bandera y destino</span>
  <span><span class="dot" style="background:var(--naranja)"></span>Hecho informado (piratería) · ciudades de la Triple Frontera, nodo de contexto: no implica actividad ilícita</span>
  <span><span class="sw" style="background:var(--naranja);opacity:.3"></span>Zona con presencia atribuida (según fuentes citadas)</span>
  <span><svg width="11" height="13" viewBox="-6 -7 12 14"><path d="M0,-5.5C3,-1.3 4.6,1 4.6,2.9A4.6,4.6 0 1 1 -4.6,2.9C-4.6,1 -3,-1.3 0,-5.5Z" fill="#8fd9c4" stroke="#00121E" stroke-width="1"/></svg>Estación de nivel del río (Meteorología de Paraguay) · naranja: en el cuarto inferior de su rango (Paraguay) o por debajo del umbral oficial de aguas bajas (Argentina), naranja claro: a menos de 30 cm de ese umbral · azul apagado: tramo regulado por represas, no mide sequía · hueca: lectura vencida</span>
  <span><span class="sw" style="background:var(--naranja)"></span>Ruta de flujo ilícito registrada por SIWA en los últimos 24 meses (pestaña «Flujos ilícitos»); en claro, las más antiguas: registros de terceros, no flujos medidos</span>
  <span><svg width="12" height="12" viewBox="-7 -7 14 14"><path d="M0,-5.5L5.5,0L0,5.5L-5.5,0Z" fill="#e9e3d2" stroke="#FB6500" stroke-width="1.4"/></svg>Hechos detectados por el escáner en los últimos 7 días (candidatos sin verificar; el rombo marca el lugar mencionado, no el del hecho)</span>
  <span><span class="dot" style="background:var(--naranja);opacity:.6"></span>Foco de calor a menos de 25 km del río (NASA FIRMS, últimos 3 días; no es un incendio confirmado)</span>
  <span><span class="dot" style="background:#8fd9c4"></span>Boya de pulso por zona · naranja: hay un indicio a mirar · punteada: sin datos de AIS</span>
</div>

__pulso__

__indicios__

__flujos__

__escaner__

__actores__

__vivas__

__alertas_fem__

__prospectiva__

<div class="metodo" id="metodo">
  <h2>Método y límites</h2>
  <p class="sub">Qué es cada cosa del mapa, de dónde sale y qué no dice.</p>
  <ul>
    <li><b>Embarcaciones.</b> Posiciones que transmiten los propios buques por AIS, recopiladas por redes colaborativas (AISHub y aisstream.io, a través de Open Waters AIS), una captura por hora. La identidad es la que transmite cada buque. <b>Límite:</b> el AIS no cubre el río alto (Alto Paraguay y el tramo Asunción–Corrientes no devolvieron datos), y lo que no transmite AIS no aparece: un mapa sin buques en un tramo no significa que no haya tráfico.</li>
    <li><b>Triángulo azul — embarcación del Estado.</b> Se marca cuando el propio buque transmite el tipo militar (35) o de fuerzas del orden (55), o por el prefijo de su nombre (ARA, GC). La fuerza que aparece en la ficha está <b>inferida</b> del nombre, no transmitida. Hoy sólo se detectan unidades argentinas; no es que no existan otras, sino que no las vemos.</li>
    <li><b>Fotos.</b> Tres niveles, y cada ficha dice cuál es: foto verificada por el número IMO del buque; coincidencia por nombre, sólo cuando el buque no transmite IMO; o imagen ilustrativa de su tipo, que <b>no es una foto de ese buque</b>. Autor y licencia en cada una.</li>
    <li><b>Cauce de los ríos.</b> Del Paraná bajo, el Delta y el Uruguay se dibuja la superficie de agua con OpenStreetMap (© colaboradores, ODbL, simplificada: no es cartografía náutica y no sirve para navegar). Aguas arriba de Rosario, y donde la consulta falló, el río es una línea con una franja de ancho aproximado. Las posiciones AIS no se corrigen nunca: si un buque aparece fuera del agua dibujada, es el dibujo el que es aproximado.</li>
    <li><b>Puertos, muelles, amarraderos y rampas.</b> Salen de OpenStreetMap, una instantánea del __fecha_amarres__: son aportes de colaboradores, <b>fuente única</b>, y pueden faltar, estar desactualizados o ser privados; que figuren no significa que operen hoy. Hay unos 2.900 puntos, la mayoría muelles pequeños del Delta, y por eso se muestran por niveles al acercar el mapa. OpenStreetMap casi no registra «caletas» en este corredor: si conocés una, abrí un pedido de corrección.</li>
    <li><b>Regla de verificación: dos fuentes independientes como mínimo.</b> Ningún dato se presenta como un hecho verificado con una sola fuente. Con una, se rotula «fuente única, no verificado»; con dos o más fuentes independientes, «corroborado» (de la misma familia, por ejemplo varios medios) o «fuerte» (de dos o más familias, por ejemplo prensa y una fuente oficial). Varias estaciones de un mismo organismo, las dos redes de AIS o varios medios que copian a una misma agencia cuentan como una sola fuente. Un detector automático (como el escáner de titulares) nunca pasa de «corroborado», porque no puede probar independencia. Las atribuciones se rotulan como atribuciones.</li>
    <li><b>Contexto por provincia o departamento.</b> Cada ficha de puerto o ciudad suma tres cifras de la unidad donde está, tomadas de los datos abiertos de <a href="https://siwa.fundacionkent.org/sitio/index.html">SIWA</a> (Fundación Sherman Kent, CC BY 4.0, rotulados allí como prototipo): homicidios de la fuente oficial de cada Estado, eventos de violencia política de ACLED (base secundaria sobre prensa y fuentes locales, no oficial) y focos de calor de NASA FIRMS de los últimos días. Son recuentos de toda la provincia, no del puerto, y no son tasas: una provincia grande tiene más aunque sea más segura. Los homicidios no son comparables entre países. Un foco de calor no es un incendio confirmado. Donde el conjunto no trae la unidad, la ficha no inventa el dato.</li>
    <li><b>Puertos y ciudades.</b> Posición geocodificada con OpenStreetMap; el tipo de terminal figura sólo donde hay fuente (Bolsa de Comercio de Rosario).</li>
    <li><b>Zonas y riesgos.</b> Cada afirmación lleva dos fuentes independientes o se marca como fuente única. Las zonas son departamentos porque la fuente no da un punto exacto.</li>
    <li><b>Satélite.</b> Imágenes de NASA GIBS (GOES-East y VIIRS), capturas con su fecha y hora: no es tiempo real. Con esa resolución no se ven buques ni muelles; sirve para nubes, humo y sedimento.</li>
    <li><b>Lo que no mostramos.</b> No publicamos «buques sin AIS» detectados por radar: el método existe pero todavía no está validado contra el AIS, y señalar lugares concretos con una tasa de falsas alarmas desconocida sería irresponsable.</li>
    <li><b>Uso y límites.</b> No es un servicio de navegación ni de seguimiento de buques: los datos los declara cada embarcación, pueden tener errores y llegan con demora. El tipo (carga, tanque, etc.) es autodeclarado y no implica carga peligrosa ni ilícita. Cada ficha muestra de qué captura sale.</li>
    <li><b>Correcciones y derecho de réplica.</b> Si sos titular de una embarcación, de un lugar o de un dato y querés pedir una corrección, escribinos desde la <a href="https://fundacionkent.org/contacto/" target="_blank" rel="noopener">página de contacto de la Fundación Sherman Kent</a>, o abrí un pedido en <a href="https://github.com/fundacion-sherman-kent/ysyry/issues" target="_blank" rel="noopener">github.com/fundacion-sherman-kent/ysyry/issues</a>.</li>
    <li><b>Rutas y corredor bioceánico.</b> Esquemáticos, para orientar; no son cartografía de navegación.</li>
  </ul>
</div>

<footer>
  <span><a href="https://fundacionkent.org/?utm_source=ysyry&amp;utm_medium=referral&amp;utm_campaign=marca&amp;utm_content=pie" target="_blank" rel="noopener">Fundación Sherman Kent</a> · código GPL-3.0 · datos propios CC BY 4.0 · los datos derivados de OpenStreetMap (rutas y geocodificación) se rigen por la ODbL</span>
  <span>AIS: AISHub y aisstream.io, vía Open Waters AIS · Límites: geoBoundaries (CC BY 4.0) · Ríos: Natural Earth · Rutas y geocodificación: © colaboradores de OpenStreetMap (ODbL)</span>
  <span>Satélite: NASA GIBS (NASA ESDIS), GOES-East de NOAA, VIIRS NOAA-20 · Fotos: Wikipedia y Wikimedia Commons, con autor y licencia en cada ficha · Comercio: Bolsa de Comercio de Rosario</span>
</footer>
</div>

<div class="panel" id="panel">
  <div class="panel-cover" id="panel-cover">
    <button class="cerrar" id="panel-cerrar" aria-label="Cerrar">&times;</button>
    <img id="panel-foto" alt="">
    <span class="ini" id="panel-inicial"></span>
    <svg id="panel-icono" viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"></svg>
    <a class="credito" id="panel-credito" target="_blank" rel="noopener">Foto: Wikipedia &#8599;</a>
  </div>
  <div class="panel-body">
    <span class="etiqueta-tipo" id="panel-categoria"></span>
    <h3 id="panel-titulo"></h3>
    <div id="panel-datos"></div>
    <p class="nota-foto" id="panel-nota" style="display:none"></p>
    <div class="coord" id="panel-coord" style="display:none">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 21s7-6.2 7-12a7 7 0 10-14 0c0 5.8 7 12 7 12z"/><circle cx="12" cy="9" r="2.3"/></svg>
      <span id="panel-coord-txt"></span>
    </div>
    <p class="fuente" id="panel-fuente"></p>
  </div>
</div>

<button type="button" class="guia-btn" id="guia-btn" aria-expanded="false" aria-controls="guia" title="Ayuda de Ysyry: preguntá o buscá un buque, puerto o estación" aria-label="Abrir la ayuda de Ysyry">
  <svg viewBox="0 0 32 32" aria-hidden="true"><rect x="6" y="10" width="20" height="15" rx="4"/><path d="M16 10V5"/><circle cx="16" cy="4" r="1.6" fill="#FB6500" stroke="none"/><circle cx="12" cy="17" r="1.7" fill="#00121E" stroke="none"/><circle cx="20" cy="17" r="1.7" fill="#00121E" stroke="none"/><path d="M12.5 21.5h7"/><path d="M3 16v4M29 16v4"/></svg>
  Ayuda
</button>
<section class="guia" id="guia" role="dialog" aria-label="Ayuda de Ysyry" aria-modal="false">
  <div class="guia-cab">
    <svg viewBox="0 0 32 32" aria-hidden="true"><rect x="6" y="10" width="20" height="15" rx="4"/><path d="M16 10V5"/><circle cx="16" cy="4" r="1.6" fill="#FB6500" stroke="none"/><circle cx="12" cy="17" r="1.7" fill="#F9F9F7" stroke="none"/><circle cx="20" cy="17" r="1.7" fill="#F9F9F7" stroke="none"/><path d="M12.5 21.5h7"/></svg>
    <div><b>Ayuda de Ysyry</b><small>Respuestas escritas de antemano · no es un modelo de IA</small></div>
    <button type="button" id="guia-cerrar" aria-label="Cerrar la ayuda">&times;</button>
  </div>
  <div class="guia-msgs" id="guia-msgs" aria-live="polite"></div>
  <div class="guia-chips" id="guia-chips"></div>
  <form class="guia-in" id="guia-form" autocomplete="off">
    <input type="text" id="guia-q" placeholder="Preguntá o buscá un buque, puerto o estación" aria-label="Tu pregunta">
    <button type="submit">Enviar</button>
  </form>
</section>
<script>
const INFO = __info_json__;
const REF = __info_ref__;
INFO.forEach(function(x){
  for (const k in x){
    const v = x[k];
    if (v && typeof v === "object" && !Array.isArray(v)){
      if (v.$ !== undefined) x[k] = REF[v.$];
      else if (v.$t !== undefined) x[k] = v.$t.map(function(t){ return typeof t === "number" ? REF[t] : t; }).join(" · ");
    }
  }
});
const FOTOS = __fotos_json__;
const horas = __horas_json__;
const MARCO_INICIAL = __marco_inicial__;
const grupos = document.querySelectorAll(".marco-hora");
const slider = document.getElementById("slider");
const etqHora = document.getElementById("etq-hora");
const etqConteo = document.getElementById("etq-conteo");
const btnPlay = document.getElementById("btn-play");

function mostrar(i){
  grupos.forEach(function(g){ g.style.display = (parseInt(g.dataset.i,10)===i) ? "" : "none"; });
  if (horas[i]){
    const dt = new Date(horas[i]);
    etqHora.textContent = dt.toLocaleString("es-AR",{day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit",timeZone:"UTC"}) + " UTC";
    etqConteo.textContent = grupos[i].children.length + " posiciones";
  }
}
slider.value = MARCO_INICIAL;
mostrar(MARCO_INICIAL);
slider.addEventListener("input", function(){ mostrar(parseInt(slider.value,10)); });

/* --- capa satelital: imagen incrustada, georreferenciada al mapa --- */
const SAT = __sat_meta_json__;
(function(){
  const svg = document.getElementById("svg-mapa");
  const ctrl = document.querySelector(".sat-ctrl");
  const info = document.getElementById("sat-info");
  function hace(ms){
    const m = Math.round(ms / 60000);
    if (m < 90) return "hace " + m + " min";
    const h = m / 60;
    return h < 48 ? "hace " + Math.round(h) + " h" : "hace " + Math.round(h / 24) + " días";
  }
  function fecha(d){
    return d.toLocaleString("es-AR", {day:"numeric", month:"short", hour:"2-digit", minute:"2-digit", timeZone:"UTC"}) + " UTC";
  }
  function describir(capa){
    if (!capa || !SAT[capa]) return "Sin capa satelital: sólo el mapa vectorial.";
    const t = SAT[capa].tiempo;
    let txt;
    if (capa === "goes") {
      const d = new Date(t);
      txt = "GOES-East GeoColor, cuadro del " + fecha(d) + " (" + hace(Date.now() - d.getTime()) + "). ~1–2 km por píxel: se ven nubes, humo y el sedimento del río, no buques ni muelles.";
    } else {
      const d = new Date(t + "T12:00:00Z");
      txt = "VIIRS NOAA-20, composición diaria del " + d.toLocaleDateString("es-AR", {day:"numeric", month:"long", timeZone:"UTC"}) + " (día UTC), ~750 m por píxel. Las nubes tapan el suelo.";
    }
    return txt + " Captura incrustada al generar esta página; el robot la renueva en el repositorio, no acá. " + SAT.atribucion;
  }
  document.querySelectorAll(".sat-btn").forEach(function(btn){
    btn.addEventListener("click", function(){
      const capa = btn.dataset.sat;
      document.querySelectorAll(".sat-btn").forEach(function(b){ b.classList.toggle("activa", b === btn); });
      if (capa) svg.setAttribute("data-sat", capa); else svg.removeAttribute("data-sat");
      ctrl.classList.toggle("encendida", !!capa);
      info.textContent = describir(capa);
    });
  });
  const op = document.getElementById("sat-op");
  function opacidad(){ svg.querySelectorAll(".sat-img").forEach(function(i){ i.style.opacity = op.value / 100; }); }
  op.addEventListener("input", opacidad);
  opacidad();
  info.textContent = describir("");
})();

/* --- zoom y paneo sobre el viewBox del SVG --- */
(function(){
  const svg = document.getElementById("svg-mapa");
  const W0 = __W__, H0 = __H__;
  let vb = {x:0, y:0, w:W0, h:H0};
  // El desplazamiento fijo de cada nube no alcanza cuando hay varios puntos
  // juntos (ej. Triple Frontera): después de cada zoom/paneo se recalculan
  // las posiciones reales en pantalla y se oculta la de menor prioridad
  // entre las que se pisan — puerto > riesgo/zona > ciudad.
  let declutterRAF = null;
  function declutter(){
    if (!svg.classList.contains("zoom-cerca")) return;
    const grupos = Array.from(document.querySelectorAll(".etq-g"));
    grupos.forEach(function(g){ g.classList.remove("etq-oculta"); });
    grupos.sort(function(a,b){ return (+b.dataset.prioridad||0) - (+a.dataset.prioridad||0); });
    const ocupados = [];
    grupos.forEach(function(g){
      const chip = g.querySelector(".etq-chip");
      if (!chip) return;
      const r = chip.getBoundingClientRect();
      const choca = ocupados.some(function(o){
        return !(r.right < o.left || r.left > o.right || r.bottom < o.top || r.top > o.bottom);
      });
      if (choca) g.classList.add("etq-oculta");
      else ocupados.push({left:r.left, right:r.right, top:r.top, bottom:r.bottom});
    });
  }
  function solicitarDeclutter(){
    if (declutterRAF) return;
    declutterRAF = requestAnimationFrame(function(){ declutterRAF = null; declutter(); });
  }
  // Tamaño constante en pantalla: al acercar, el mapa se agranda pero los
  // marcadores y las etiquetas no. Así los buques de un racimo se separan de
  // verdad al hacer zoom, en vez de crecer juntos y taparse más.
  const RE_T = /translate\(([-\d.]+),\s*([-\d.]+)\)(?:\s*rotate\(([-\d.]+)\))?/;
  const items = [];
  svg.querySelectorAll("g[transform]").forEach(function(g){
    const m = RE_T.exec(g.getAttribute("transform"));
    if (m) {
      const h = g.querySelector(".hit");
      items.push({tipo:"g", el:g, x:+m[1], y:+m[2], r:(m[3]===undefined ? null : +m[3]),
        buque:g.classList.contains("buque-g"), amar:g.classList.contains("amar"), hit:h, rh:(h ? +h.getAttribute("r") : 0)});
    }
  });
  svg.querySelectorAll(".etq-g").forEach(function(g){
    const l = g.querySelector(".etq-linea");
    items.push({tipo:"e", el:g, x:+l.getAttribute("x1"), y:+l.getAttribute("y1")});
  });
  let escalaPrev = -1;
  function escalar(){
    const s = vb.w / W0;
    if (Math.abs(s - escalaPrev) < 1e-5) return;
    escalaPrev = s;
    // Constantes en pantalla, y algo más grandes cuanto más se acerca (b crece
    // de 1 a 2.4): con el mapa abierto del todo los marcadores chicos evitan
    // el amontonamiento; con zoom ya hay lugar y se ven mejor.
    const b = 1 + 1.4 * (1 - s);
    const sm = s * (0.8 + 0.2 * s) * b;    // marcadores
    const sc = s * (0.85 + 0.15 * s) * b;  // etiquetas
    // Con zoom, los buques crecen más que lo demás y los muelles menos: a escala de puerto lo que importa son los buques,
    // y los cientos de muelles de OpenStreetMap no deben taparlos. El área de clic del buque no crece con él.
    const smB = s * (0.8 + 0.2 * s) * (1 + 3.6 * (1 - s));
    const smA = s * (0.8 + 0.2 * s) * (1 + 0.6 * (1 - s));
    items.forEach(function(it){
      if (it.tipo === "g") {
        const k = it.buque ? smB : (it.amar ? smA : sm);
        if (it.buque && it.hit) it.hit.setAttribute("r", it.rh * sm / smB);
        it.el.setAttribute("transform", "translate(" + it.x + "," + it.y + ")" +
          (it.r === null ? "" : " rotate(" + it.r + ")") + " scale(" + k + ")");
      } else if (it.tipo === "c") {
        it.el.setAttribute("r", it.r0 * sm);
        it.el.style.strokeWidth = (0.8 * sm) + "px";  // el borde también, o queda un aro negro enorme
      } else {
        it.el.setAttribute("transform", "translate(" + it.x + "," + it.y + ") scale(" + sc +
          ") translate(" + (-it.x) + "," + (-it.y) + ")");
      }
    });
  }
  function aplicar(){
    svg.setAttribute("viewBox", vb.x+" "+vb.y+" "+vb.w+" "+vb.h);
    // más detalle (nombres de ciudad/puerto) sólo a partir de 2.3x de zoom
    svg.classList.toggle("zoom-cerca", (W0/vb.w) > 2.3);
    svg.classList.toggle("zoom-a", (W0/vb.w) > 1.7);
    svg.classList.toggle("zoom-b", (W0/vb.w) > 3.8);
    escalar();
    solicitarDeclutter();
  }
  function zoom(factor, cx, cy){
    const nw = Math.min(W0, Math.max(W0*0.0065, vb.w*factor));
    const nh = nw * (H0/W0);
    const px = (cx===undefined) ? vb.x+vb.w/2 : cx;
    const py = (cy===undefined) ? vb.y+vb.h/2 : cy;
    vb.x = px - (px - vb.x) * (nw/vb.w);
    vb.y = py - (py - vb.y) * (nh/vb.h);
    vb.w = nw; vb.h = nh;
    aplicar();
  }
  function puntoSvg(ev){
    // La matriz real de pantalla→mapa: el mapa es vertical y queda centrado en
    // un recuadro ancho (preserveAspectRatio), así que dividir por el ancho del
    // elemento corría el punto de anclaje lejos del cursor.
    const p = new DOMPoint(ev.clientX, ev.clientY).matrixTransform(svg.getScreenCTM().inverse());
    return {x: p.x, y: p.y};
  }
  document.getElementById("zoom-mas").addEventListener("click", function(){ zoom(0.7); });
  document.getElementById("zoom-menos").addEventListener("click", function(){ zoom(1/0.7); });
  document.getElementById("zoom-reset").addEventListener("click", function(){ vb={x:0,y:0,w:W0,h:H0}; aplicar(); });
  // la usa la guía: centra el mapa en un punto, acerca y abre su ficha
  window.__irA = function(id){
    const el = svg.querySelector('[data-i="' + id + '"]'); if (!el) return false;
    const m = /translate\(([-\d.]+),\s*([-\d.]+)\)/.exec(el.getAttribute("transform") || "");
    if (m){
      const w = W0 * 0.04, h = w * H0 / W0;
      vb = {x: Math.max(0, Math.min(W0 - w, +m[1] - w / 2)), y: Math.max(0, Math.min(H0 - h, +m[2] - h / 2)), w: w, h: h};
      aplicar();
    }
    setTimeout(function(){ el.dispatchEvent(new MouseEvent("click", {bubbles: true})); }, 80);
    return true;
  };
  svg.addEventListener("wheel", function(ev){
    ev.preventDefault();
    const p = puntoSvg(ev);
    zoom(ev.deltaY < 0 ? 0.85 : 1/0.85, p.x, p.y);
  }, {passive:false});
  // Distingue clic de arrastre: hasta que el puntero no se mueva más de
  // UMBRAL px no se captura ni se mueve el mapa, así un clic simple sobre
  // un buque/puerto sigue llegando a ese elemento y abre el panel.
  const UMBRAL = 4;
  let bajando = false, arrastrando = false, inicio = null, ultimo = null, pid = null;
  svg.addEventListener("pointerdown", function(ev){
    bajando = true; arrastrando = false; pid = ev.pointerId;
    inicio = {x: ev.clientX, y: ev.clientY}; ultimo = inicio;
  });
  svg.addEventListener("pointermove", function(ev){
    if (!bajando) return;
    if (!arrastrando){
      if (Math.hypot(ev.clientX - inicio.x, ev.clientY - inicio.y) < UMBRAL) return;
      arrastrando = true; svg.classList.add("arrastrando"); svg.setPointerCapture(pid);
    }
    const c = svg.getScreenCTM();
    const dx = (ev.clientX - ultimo.x) / c.a;
    const dy = (ev.clientY - ultimo.y) / c.d;
    vb.x -= dx; vb.y -= dy; ultimo = {x: ev.clientX, y: ev.clientY};
    aplicar();
  });
  function soltar(ev){ bajando = false; arrastrando = false; svg.classList.remove("arrastrando"); }
  svg.addEventListener("pointerup", soltar);
  svg.addEventListener("pointerleave", soltar);
})();

let repro = false, temporizador = null;
btnPlay.addEventListener("click", function(){
  repro = !repro;
  btnPlay.innerHTML = repro ? "&#10074;&#10074;" : "&#9654;";
  if (repro){
    temporizador = setInterval(function(){
      let i = parseInt(slider.value,10) + 1;
      if (i > parseInt(slider.max,10)) i = 0;
      slider.value = i; mostrar(i);
    }, 1400);
  } else { clearInterval(temporizador); }
});

const panel = document.getElementById("panel");
const pCov = document.getElementById("panel-cover"), pIco = document.getElementById("panel-icono"),
      pIni = document.getElementById("panel-inicial"), pFoto = document.getElementById("panel-foto"),
      pCred = document.getElementById("panel-credito"), pNota = document.getElementById("panel-nota"),
      pCat = document.getElementById("panel-categoria"), pT = document.getElementById("panel-titulo"),
      pD = document.getElementById("panel-datos"), pF = document.getElementById("panel-fuente"),
      pCo = document.getElementById("panel-coord"), pCoTxt = document.getElementById("panel-coord-txt");
const porId = {};
INFO.forEach(function(x){ porId[x.id] = x; });

// Sin foto real del lugar — no tenemos fuente verificada para eso. En su
// lugar, un ícono por categoría sobre un degradé de marca, honesto sobre
// lo que es (una categoría, no una fotografía del sitio).
const AMARRES = __amarres_json__;
const ETIQ_AM = {puerto:"Puerto", area_portuaria:"Área portuaria o terminal", ferry:"Terminal de ferry", marina:"Marina o club náutico",
  darsena:"Dársena o astillero", atracadero:"Atracadero", muelle:"Muelle", rampa:"Rampa de botadura", amarradero:"Amarradero"};
function infoAmarre(id){
  if (id.indexOf("am") !== 0) return null;
  const a = AMARRES[+id.slice(2)]; if (!a) return null;
  const x = a[4] || {}, lin = [ETIQ_AM[a[0]] || "Infraestructura"];
  if (x.operator) lin.push("Operador según OpenStreetMap: " + x.operator);
  if (x.access) lin.push("Acceso según OpenStreetMap: " + ({private:"privado", permissive:"permitido", yes:"público", no:"cerrado"}[x.access] || x.access));
  if (x.ref) lin.push("Referencia: " + x.ref);
  lin.push("Es un aporte colaborativo: puede estar incompleto o desactualizado, y no indica que opere hoy");
  return {categoria: ETIQ_AM[a[0]] + " (OpenStreetMap)", titulo: a[1] || (ETIQ_AM[a[0]] + " sin nombre en OpenStreetMap"),
    tipo: lin.join(" · "), fuente: "OpenStreetMap (© colaboradores, ODbL), instantánea del __fecha_amarres__ · fuente única",
    clase: "amarre", coord: a[3].toFixed(4) + ", " + a[2].toFixed(4), foto: null};
}
const ICONOS = {
  puerto: '<path d="M12 3v7m0 0l2.5-1.6M12 10l-2.5-1.6"/><path d="M5 11a7 7 0 0014 0" /><path d="M3 18h18" /><circle cx="12" cy="6" r="1.4" fill="#fff"/>',
  ciudad: '<rect x="6" y="3" width="12" height="18" rx="1"/><path d="M9 7h1.5M13.5 7H15M9 11h1.5M13.5 11H15M9 15h1.5M13.5 15H15"/>',
  tf: '<rect x="6" y="3" width="12" height="18" rx="1"/><path d="M9 7h1.5M13.5 7H15M9 11h1.5M13.5 11H15M9 15h1.5M13.5 15H15"/>',
  riesgo: '<path d="M12 3 22 20H2z"/><path d="M12 9v5"/><circle cx="12" cy="17" r="0.9" fill="#fff"/>',
  zona: '<path d="M12 3 22 20H2z"/><path d="M12 9v5"/><circle cx="12" cy="17" r="0.9" fill="#fff"/>',
  estado: '<path d="M12 3l8 3v6c0 4.5-3.2 7.8-8 9-4.8-1.2-8-4.5-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
  estacion: '<path d="M12 3c3 4 6 7 6 11a6 6 0 01-12 0c0-4 3-7 6-11z"/>',
  flujo: '<path d="M3 18c4-9 8-3 12-9 2-3 4-3 6-3" stroke-dasharray="3 3"/><circle cx="4" cy="18" r="1.5"/><circle cx="20" cy="6" r="1.5"/>',
  escaner: '<path d="M12 3l8 9-8 9-8-9z"/><path d="M12 9v3"/>',
  boya: '<circle cx="12" cy="12" r="3"/><circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="10.5" stroke-dasharray="2 2"/>',
  amarre: '<path d="M12 3v13m0 0l-4-3m4 3l4-3"/><path d="M5 14a7 7 0 0014 0"/><circle cx="12" cy="5" r="1.6" fill="#fff"/>',
  buque: '<path d="M4 16h16l-2.5 5h-11z"/><path d="M12 16V6"/><path d="M12 6l5 4h-5z"/>'
};

document.querySelectorAll(".familia-tab").forEach(function(btn){
  btn.addEventListener("click", function(){
    document.querySelectorAll(".familia-tab").forEach(function(b){ b.classList.remove("activa"); });
    btn.classList.add("activa");
    const fam = btn.dataset.familia;
    document.querySelectorAll("[data-familia]").forEach(function(el){
      const suyas = (el.dataset.familia || "").split(" ");
      const coincide = !fam || suyas.indexOf(fam) !== -1;
      el.classList.toggle("dim", !coincide);
    });
    document.getElementById("svg-mapa").classList.toggle("fam-flujos", fam === "flujos");
  });
});

document.querySelectorAll(".pregunta .barra i").forEach(function(b){
  const w = b.style.width; b.style.width = "0";
  requestAnimationFrame(function(){ setTimeout(function(){ b.style.width = w; }, 150); });
});

document.querySelectorAll(".clicable").forEach(function(el){
  el.addEventListener("click", function(){
    const info = porId[el.dataset.i] || infoAmarre(el.dataset.i);
    if (!info) return;
    const clase = info.clase || "ciudad";
    pCov.className = "panel-cover cover-" + clase + (info.foto ? " con-foto" : "");
    pIco.innerHTML = ICONOS[clase] || ICONOS.ciudad;
    pIni.textContent = (info.titulo || "?").trim().charAt(0).toUpperCase();
    if (info.foto){
      pFoto.src = FOTOS[info.foto.src] || "";
      pFoto.alt = info.titulo;
      pCred.href = info.foto.pagina;
      pCred.textContent = (info.foto.credito || (info.foto.generica ? "Imagen ilustrativa · Wikipedia" : "Foto: Wikipedia")) + " ↗";
      pNota.textContent = info.foto.nota || "";
      pNota.style.display = info.foto.nota ? "block" : "none";
    } else {
      pFoto.removeAttribute("src");
    }
    pCat.textContent = info.categoria || "";
    pT.textContent = info.titulo;
    pD.innerHTML = "";
    (info.tipo || "").split(" · ").forEach(function(linea){
      const row = document.createElement("div");
      row.className = "dato";
      row.textContent = linea;
      pD.appendChild(row);
    });
    if (info.ctx && info.ctx.length){
      const cab = document.createElement("div");
      cab.className = "dato";
      const b = document.createElement("b");
      b.textContent = info.ctx_t;
      cab.appendChild(b);
      pD.appendChild(cab);
      info.ctx.forEach(function(linea){
        const row = document.createElement("div");
        row.className = "dato ctx";
        linea.split(/(https?:\/\/[^\s]+)/).forEach(function(trozo){
          if (/^https?:\/\//.test(trozo)){
            const a = document.createElement("a");
            a.href = trozo; a.textContent = "nota ↗"; a.target = "_blank"; a.rel = "noopener nofollow";
            row.appendChild(a);
          } else if (trozo) { row.appendChild(document.createTextNode(trozo)); }
        });
        pD.appendChild(row);
      });
      const pie = document.createElement("div");
      pie.className = "nota-foto";
      pie.textContent = info.ctx_f;
      pD.appendChild(pie);
    }
    if (info.spark_svg){
      const sp = document.createElement("div");
      sp.className = "spark-panel";
      sp.innerHTML = info.spark_svg;
      const cap = document.createElement("div");
      cap.className = "nota-foto";
      cap.textContent = info.spark_pie || "";
      sp.appendChild(cap);
      pD.appendChild(sp);
    }
    if (info.coord){
      pCoTxt.textContent = info.coord + " (lat, lon)";
      pCo.style.display = "flex";
    } else {
      pCo.style.display = "none";
    }
    pF.textContent = info.fuente;
    panel.classList.add("abierto");
    panel.scrollTop = 0;
  });
});
(function(){
  const el = document.getElementById("latido"), tx = document.getElementById("latido-txt");
  if (!el || !tx) return;
  function pinta(){
    const t = Date.parse(el.dataset.ultima);
    if (isNaN(t)) { tx.textContent = "Sin dato de captura"; el.className = "latido sinsenal"; return; }
    const min = Math.max(0, Math.round((Date.now() - t) / 60000));
    const hh = new Date(t).toISOString().slice(11, 16) + " UTC";
    const hace = min < 90 ? min + " min" : Math.floor(min / 60) + " h " + (min % 60) + " min";
    if (min < 95) { el.className = "latido viva"; tx.textContent = "Señal viva · última captura " + hh + " · hace " + hace; }
    else if (min < 240) { el.className = "latido retrasada"; tx.textContent = "Captura retrasada · última " + hh + " · hace " + hace; }
    else { el.className = "latido sinsenal"; tx.textContent = "Sin captura reciente · última " + hh + " · hace " + hace; }
  }
  pinta(); setInterval(pinta, 60000);
})();
(function(){
  // la cabecera queda siempre a la vista: se mide su alto para que el panel y los anclas no queden debajo de ella
  const cab = document.querySelector(".topbar");
  function medir(){ if (cab) document.documentElement.style.setProperty("--alto-cab", Math.ceil(cab.getBoundingClientRect().height) + "px"); }
  medir(); window.addEventListener("resize", medir);
  if (window.ResizeObserver && cab) new ResizeObserver(medir).observe(cab);
})();

/* --- Guía de ayuda: busca en respuestas escritas de antemano y en los nombres del mapa; no usa ningún modelo ni servicio --- */
(function(){
  const CAT = __guia_json__, SUG = __guia_sug__;
  const btn = document.getElementById("guia-btn"), caja = document.getElementById("guia"), msgs = document.getElementById("guia-msgs"),
        chips = document.getElementById("guia-chips"), form = document.getElementById("guia-form"), q = document.getElementById("guia-q");
  if (!btn || !caja) return;
  const PARASITAS = new Set("de del la las el los lo un una unos unas que es son y o a en por para con se me mi mis tu tus al como cual cuales cuando donde hay esta este esto ese eso hola quiero puedo podes saber decime dime mostrame buscar busca buscame buscas encontrar encontrame ver mostra".split(" "));
  function norm(s){ return (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9ñ ]+/g, " ").replace(/\s+/g, " ").trim(); }
  function toks(s){ return norm(s).split(" ").filter(function(t){ return t && !PARASITAS.has(t); }); }
  CAT.forEach(function(e){ e._t = new Set(toks(e.k)); });
  function agrega(txt, clase){ const d = document.createElement("div"); d.className = "guia-m " + (clase || ""); d.textContent = txt; msgs.appendChild(d); msgs.scrollTop = msgs.scrollHeight; return d; }
  function acciones(d, lista){
    if (!lista || !lista.length) return;
    const w = document.createElement("div"); w.className = "guia-acc";
    lista.forEach(function(a){ const b = document.createElement("button"); b.type = "button"; b.textContent = a[2]; b.addEventListener("click", function(){ ejecuta(a[0], a[1]); }); w.appendChild(b); });
    d.appendChild(w); msgs.scrollTop = msgs.scrollHeight;
  }
  function irMapa(){ const m = document.getElementById("mapa"); if (m) m.scrollIntoView({behavior: "smooth", block: "start"}); }
  function ejecuta(tipo, v){
    if (tipo === "sec"){ const el = document.getElementById(v); if (el) el.scrollIntoView({behavior: "smooth", block: "start"}); cierra(); }
    else if (tipo === "tab"){ const t = document.querySelector('.familia-tab[data-familia="' + v + '"]'); if (t) t.click(); irMapa(); cierra(); }
    else if (tipo === "ir"){
      const t = document.querySelector('.familia-tab[data-familia=""]'); if (t) t.click();
      irMapa(); cierra();
      setTimeout(function(){ if (window.__irA) window.__irA(v); }, 350);
    }
  }
  function entidades(texto){
    const t = toks(texto).filter(function(x){ return x.length >= 3; });
    if (!t.length) return [];
    const vistos = {}, out = [];
    document.querySelectorAll("#svg-mapa [data-i]").forEach(function(el){
      const id = el.getAttribute("data-i");
      if (el.closest(".marco-hora") && el.closest(".marco-hora").style.display === "none") return;
      const x = (typeof porId !== "undefined") ? porId[id] : null; if (!x || !x.titulo) return;
      const n = norm(x.titulo); if (vistos[n]) return;
      if (t.every(function(w){ return n.indexOf(w) !== -1; })) { vistos[n] = 1; out.push({id: id, titulo: x.titulo, cat: x.categoria || ""}); }
    });
    return out.slice(0, 8);
  }
  function responde(texto){
    const t = toks(texto);
    const ents = entidades(texto);
    let mejor = null, puntaje = 0, otros = [];
    if (!t.length && !ents.length){ mejor = CAT[0]; puntaje = 9; }
    CAT.forEach(function(e){
      let p = 0, n = 0;
      t.forEach(function(w){
        if (e._t.has(w)) { p += 2; n += 1; }
        else if (w.length >= 4){ let hit = false; e._t.forEach(function(k){ if (k.length >= 4 && (k.indexOf(w) === 0 || w.indexOf(k) === 0)) hit = true; }); if (hit){ p += 1; n += 1; } }
      });
      if (n < Math.min(2, t.length)) p = 0;      // una sola palabra suelta en una pregunta larga no alcanza
      if (p > 0) otros.push([p, e]);
      if (p > puntaje){ puntaje = p; mejor = e; }
    });
    otros.sort(function(a, b){ return b[0] - a[0]; });
    if (ents.length && (!mejor || puntaje < 4)){
      const d = agrega("Encontré esto en el mapa. Tocá uno y te llevo hasta ahí:");
      acciones(d, ents.map(function(e){ return ["ir", e.id, e.titulo + (e.cat ? " · " + e.cat.split(" · ")[0] : "")]; }));
      return;
    }
    if (mejor && puntaje >= 2){
      const d = agrega(mejor.r);
      acciones(d, mejor.a);
      const rel = otros.filter(function(o){ return o[1] !== mejor && o[0] >= 2; }).slice(0, 2);
      if (rel.length){ const w = document.createElement("div"); w.className = "guia-acc"; rel.forEach(function(o){ const b = document.createElement("button"); b.type = "button"; b.textContent = "Ver también: " + o[1].t; b.addEventListener("click", function(){ const dd = agrega(o[1].r); acciones(dd, o[1].a); }); w.appendChild(b); });
        d.appendChild(w); }
      if (ents.length){ const d2 = agrega("Y esto en el mapa:"); acciones(d2, ents.map(function(e){ return ["ir", e.id, e.titulo]; })); }
      return;
    }
    const d = agrega("No encontré eso y prefiero no inventar. Probá con otras palabras, buscá un buque, puerto o estación por su nombre, o elegí una de estas preguntas. Si es un error de un dato, podés pedir una corrección desde «Método y límites».");
    acciones(d, [["sec", "metodo", "Ver método y límites"]]);
  }
  function abre(){
    caja.classList.add("abierta"); btn.setAttribute("aria-expanded", "true");
    if (!msgs.children.length){
      agrega("Hola, soy el ayudante de Ysyry. No soy un modelo de IA: respondo con textos escritos de antemano sobre esta plataforma y puedo buscar buques, puertos y estaciones en el mapa. Si no sé algo, te lo digo.");
      SUG.forEach(function(s){ const b = document.createElement("button"); b.type = "button"; b.textContent = s; b.addEventListener("click", function(){ agrega(s, "yo"); responde(s); }); chips.appendChild(b); });
    }
    setTimeout(function(){ q.focus(); }, 50);
  }
  function cierra(){ caja.classList.remove("abierta"); btn.setAttribute("aria-expanded", "false"); }
  btn.addEventListener("click", function(){ caja.classList.contains("abierta") ? cierra() : abre(); });
  document.getElementById("guia-cerrar").addEventListener("click", cierra);
  document.addEventListener("keydown", function(ev){ if (ev.key === "Escape" && caja.classList.contains("abierta")) cierra(); });
  form.addEventListener("submit", function(ev){ ev.preventDefault(); const v = q.value.trim(); if (!v) return; agrega(v, "yo"); q.value = ""; responde(v); });
  // cuando la ficha del mapa está abierta, la guía se corre para no taparla
  const panel = document.getElementById("panel");
  if (panel && window.MutationObserver) new MutationObserver(function(){ document.body.classList.toggle("ficha-abierta", panel.classList.contains("abierto")); }).observe(panel, {attributes: true, attributeFilter: ["class"]});
})();
document.getElementById("panel-cerrar").addEventListener("click", function(){ panel.classList.remove("abierto"); });
// Tema: el claro es siempre el predeterminado; «Fondo oscuro» lo cambia y se recuerda (con try/catch:
// si el navegador bloquea el almacenamiento, el botón igual funciona, sólo que no se recuerda).
(function(){
  const raiz = document.documentElement, boton = document.getElementById("tema");
  function aplicar(oscuro){
    if (oscuro) raiz.setAttribute("data-theme", "dark"); else raiz.removeAttribute("data-theme");
    boton.setAttribute("aria-pressed", oscuro ? "true" : "false");
    boton.textContent = oscuro ? "Fondo claro" : "Fondo oscuro";
  }
  let guardado = null;
  try { guardado = localStorage.getItem("ysyry-tema"); } catch (e) {}
  aplicar(guardado === "oscuro");
  boton.addEventListener("click", function(){
    const oscuro = raiz.getAttribute("data-theme") !== "dark";
    aplicar(oscuro);
    try { localStorage.setItem("ysyry-tema", oscuro ? "oscuro" : "claro"); } catch (e) {}
  });
})();
// El logo con la palabra Ysyry vuelve a la portada: cierra la ficha, restablece el mapa y sube al inicio.
document.getElementById("ir-portada").addEventListener("click", function(ev){
  ev.preventDefault();
  panel.classList.remove("abierto");
  document.getElementById("zoom-reset").click();
  window.scrollTo({top: 0, behavior: "smooth"});
});
</script>
"""
html = TPL
SUST = {
    "provincias": "\n    ".join(prov_svg),
    "paises": "\n    ".join(paises_svg),
    "rutas": rutas_html,
    "bioceanico": bioceanico_html,
    "rio_pilco": rio_pilco_html,
    "rio_bermejo": rio_bermejo_html,
    "rio_parana": rio_parana_html,
    "rio_paraguay": rio_paraguay_html,
    "zonas": "\n    ".join(zonas_svg),
    "zonas_etq": "\n    ".join(zonas_etq_svg),
    "poi": "\n    ".join(poi_svg),
    "amarres": "\n    ".join(amarres_svg),
    "amarres_json": json.dumps(amarres_json, ensure_ascii=False, separators=(",", ":")),
    "fecha_amarres": _AM["fecha"],
    "agua_osm": agua_osm_html,
    "alertas_fem": _ALERTAS_FEM,
    "pulso": _pulso_html,
    "flujos": _flujos_html,
    "escaner": _escaner_html,
    "actores": _actores_html,
    "vivas": _vivas_html,
    "prospectiva": _prospectiva_html,
    "guia_json": json.dumps(_GUIA, ensure_ascii=False),
    "guia_sug": json.dumps(_guia.PREGUNTAS_SUGERIDAS, ensure_ascii=False),
    "indicios": _indicios_html,
    "ultima_iso": marcos[-1]["hora"] if marcos else "",
    "poi_etq": "\n    ".join(poi_etq_svg),
    "grupos_hora": "\n    ".join(grupos_hora),
    "riesgos": "\n    ".join(riesgos_svg),
    "riesgos_etq": "\n    ".join(riesgos_etq_svg),
    "sat_imgs": "\n    ".join(sat_imgs),
    "sat_meta_json": sat_meta_json,
    "logo_color": "data:image/svg+xml;base64," + base64.b64encode(open(D / "marca" / "fusk-lockup-color.svg", "rb").read()).decode(),
    "logo_blanco": "data:image/svg+xml;base64," + base64.b64encode(open(D / "marca" / "fusk-lockup-blanco.svg", "rb").read()).decode(),
    "W": W, "H": H,
    "max_marco": max(0, len(marcos) - 1),
    "n_buques": len(marcos[-1]["puntos"]) if marcos else 0,
    "n_capturas": len(marcos),
    "ultima_captura": (__import__("datetime").datetime.strptime(marcos[-1]["hora"], "%Y-%m-%dT%H:%M:%SZ")
                       .strftime("%d/%m %H:%M UTC")) if marcos else "—",
    "marco_inicial": marco_inicial,
    "info_json": info_json,
    "info_ref": json.dumps(_info_ref, ensure_ascii=False, separators=(",", ":")),
    "fotos_json": fotos_json,
    "horas_json": horas_json,
}
for _k, _v in SUST.items():
    html = html.replace("__" + _k + "__", str(_v))


import re as _re2
# Sólo los marcadores propios: el AIS trae texto libre tipeado por los capitanes (hay destinos con «__»).
_sobran = [m for m in _re2.findall(r"__[a-z][a-z0-9_]*__", html)]
assert not _sobran, "marcadores sin reemplazar: %s" % sorted(set(_sobran))[:5]
assert "%(" not in html, "quedó un placeholder de formato sin resolver"
assert html.count("clicable") >= len(poi_info) + len(riesgo_info), "faltan elementos clicables de POI/riesgo"
Path(SALIDA).parent.mkdir(parents=True, exist_ok=True)
open(SALIDA, "w", encoding="utf-8", newline=chr(10)).write(html)
print("OK, escrito. bytes:", len(html.encode("utf-8")), "| clicables:", len(poi_info)+len(riesgo_info)+len(zona_info))
