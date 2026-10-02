# Ysyry

*Ysyry* es «río» en guaraní.

Plataforma pública y gratuita de la [Fundación Sherman Kent](https://fundacionkent.org) sobre el
corredor de la Hidrovía Paraguay-Paraná: embarcaciones, puertos, comercio y hechos de riesgo,
cada dato con su origen y su fecha, y lo que todavía no sabemos o no cubrimos, dicho así.

**Sitio:** <https://fundacion-sherman-kent.github.io/ysyry/>

**Estado: versión inicial, en construcción.**

## Qué hay

- **Mapa del corredor** con embarcaciones (AIS), puertos y ciudades, zonas y hechos de riesgo con sus
  fuentes, y una capa satelital (NASA GIBS).
- **Método y límites** en el propio sitio: qué es cada capa, de dónde sale y qué no dice. Lo más
  importante: el AIS no cubre el río alto; los buques sin AIS no aparecen; las fotos de cada
  embarcación son verificadas por número IMO sólo en una parte de los casos y el resto son imágenes
  ilustrativas, rotuladas como tales.
- **Prospectiva:** todavía no se publica ninguna estimación.

## Cómo está hecho

- `colectores/`: robots que corren solos en GitHub Actions (sin gastar tokens de ningún modelo) y
  bajan datos abiertos: nivel del río, imágenes satelitales (`satelite_gibs.py`) y radar
  Sentinel-1 (`radar_*.py`, método en validación, **no se publica**).
- `sitio/`: el generador de la página (`construir.py`) y sus insumos. El flujo `sitio.yml` **se
  actualiza solo cada hora**: baja la última captura de AIS (`ais_marco.py`), la suma al historial
  de las últimas 24 horas (rama `datos-ais`), reconstruye la página con la imagen satelital más
  reciente y la despliega en GitHub Pages. Si el AIS no responde, el sitio conserva la última captura
  buena, con su fecha a la vista.

## Fuentes y licencias

- **Código:** GPL-3.0. **Datos propios:** CC BY 4.0. Los datos derivados de OpenStreetMap
  (rutas, geocodificación) se rigen por la ODbL.
- **AIS:** AISHub y aisstream.io, a través de Open Waters AIS. AISHub permite redistribuir citándolo;
  aisstream.io no publica términos de uso.
- **Límites:** geoBoundaries (CC BY 4.0). **Ríos:** Natural Earth. **Rutas:** © colaboradores de
  OpenStreetMap (ODbL).
- **Satélite:** NASA GIBS (NASA ESDIS); GOES-East de NOAA; VIIRS NOAA-20.
- **Radar:** contiene datos modificados de Copernicus Sentinel.
- **Fotos:** Wikipedia y Wikimedia Commons, con autor y licencia en cada ficha.
- **Comercio:** Bolsa de Comercio de Rosario.
- **Alertas tempranas:** las de [FEMÓNOE](https://fundacion-sherman-kent.github.io/femonoe-sitio/) que tocan a los cinco Estados del corredor o a la Triple Frontera, leídas de su sitio público al construir (todavía no publica un archivo de datos); si no se pueden leer, el sitio lo dice en vez de afirmar que no hay.
- **Contexto por provincia o departamento:** [SIWA](https://siwa.fundacionkent.org/sitio/index.html), Fundación Sherman Kent (CC BY 4.0): homicidios de la fuente oficial de cada Estado, ACLED (atribución) y focos de calor de NASA FIRMS. Se bajan al construir el sitio, con copia fechada en `sitio/datos/siwa/` si SIWA no responde.

## Correcciones y derecho de réplica

Si sos titular de una embarcación, de un lugar o de un dato y querés pedir una corrección, abrí un
[pedido en Issues](https://github.com/fundacion-sherman-kent/ysyry/issues).

Ysyry no tiene redes propias: todo sale por las cuentas de la Fundación Sherman Kent.
