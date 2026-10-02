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
- `docs/`: el sitio, una sola página estática.

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

## Correcciones y derecho de réplica

Si sos titular de una embarcación, de un lugar o de un dato y querés pedir una corrección, abrí un
[pedido en Issues](https://github.com/fundacion-sherman-kent/ysyry/issues).

Ysyry no tiene redes propias: todo sale por las cuentas de la Fundación Sherman Kent.
