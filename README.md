# Ysyry

*Ysyry* es «río» en guaraní.

Plataforma pública y gratuita de la [Fundación Sherman Kent](https://fundacionkent.org) sobre el
corredor de la Hidrovía Paraguay-Paraná: embarcaciones, puertos, comercio y hechos de riesgo,
cada dato con su origen y su fecha, y lo que todavía no sabemos o no cubrimos, dicho así.

**Sitio:** <https://fundacion-sherman-kent.github.io/ysyry/>

**Estado: versión inicial, en construcción.**

## Regla de verificación

**Dos fuentes independientes como mínimo.** Ningún dato se presenta como un hecho verificado con una sola: se rotula «fuente única, no verificado». Con dos o más independientes de la misma familia (por ejemplo, varios medios) es «corroborado»; con dos o más de al menos dos familias (por ejemplo, prensa y una fuente oficial), «fuerte». Varias estaciones de un mismo organismo, las dos redes de AIS o varios medios que copian a una misma agencia cuentan como una sola fuente. Un detector automático, como el escáner de titulares, nunca pasa de «corroborado». La corroboración es por afirmación: dos hechos distintos no se corroboran entre sí. Está en `sitio/indicios.py` y se ve en la página.

## Qué hay

- **Mapa del corredor** con embarcaciones (AIS), puertos y ciudades, zonas y hechos de riesgo con sus
  fuentes, y una capa satelital (NASA GIBS).
- **Método y límites** en el propio sitio: qué es cada capa, de dónde sale y qué no dice. Lo más
  importante: el AIS no cubre el río alto; los buques sin AIS no aparecen; las fotos de cada
  embarcación son verificadas por número IMO sólo en una parte de los casos y el resto son imágenes
  ilustrativas, rotuladas como tales.
- **Pulso por zona:** cinco tramos del corredor con los buques que se ven en las últimas 24 horas, cuántos están en movimiento, qué unidades del Estado transmiten AIS y cómo se compara con los días anteriores de ese mismo tramo (la comparación aparece con 7 días de historia, que se guarda en la rama `datos-pulso`). Mide huellas observables, no la conducta de ningún actor; donde el AIS no llega dice «sin datos», no «sin tráfico». Cada tramo suma además, de las provincias, departamentos o estados que toca, los eventos de violencia política de ACLED (último año del conjunto) y los focos de calor de NASA FIRMS (últimos días), tomados de [SIWA](https://siwa.fundacionkent.org/sitio/index.html): son cifras de la unidad completa, no del tramo, y cada celda dice cuántas unidades tenían dato. Se dejaron fuera Mato Grosso do Sul y Paraná (Brasil) porque, por su tamaño, dominaban las sumas.
- **Libro de indicios:** cada observación del corredor con sus fuentes, la familia de cada fuente y su nivel de evidencia (*fuente única*, *corroborado* o *fuerte*; varias estaciones de un mismo organismo cuentan como una sola fuente), y lo que no dice. Incluye el nivel del río (estaciones de la Dirección de Meteorología e Hidrología de Paraguay, en el mapa como gotas), la presencia visible del Estado por AIS, las interrupciones de señal, la violencia política de ACLED y los hechos citados con sus fuentes. Un indicio no es una alerta.
- **Alertas candidatas y preguntas con probabilidad:** las reglas de `sitio/indicios.py` proponen candidatas en un repositorio privado para la curaduría; nada se publica solo. Las preguntas publicadas viven en `preguntas/` (ver su `LEEME.md`): binarias, con plazo, banda de probabilidad en el léxico de Kent y criterio mecánico; el robot diario las resuelve al vencer y el marcador (Brier) se muestra «en calibración» hasta las 20 vencidas.
- **Prensa como segunda familia de fuentes:** titulares de los últimos 7 días de la API abierta de GDELT, por tema y zona, contando medios distintos (detección automática por palabras clave, no verificada por una persona). GDELT limita las consultas: si un tema no se puede actualizar, queda vacío y no se inventa.
- **Focos de calor cerca del río:** NASA FIRMS (VIIRS Suomi NPP y NOAA-20, archivos regionales de acceso libre, sin clave), los detectados a menos de 25 km del río en los últimos 3 días, como puntos en el mapa y como indicio por tramo. Una anomalía térmica no es un incendio confirmado ni dice su causa; dos satélites pueden ver el mismo foco.
- **Flujos ilícitos que usan el corredor (de SIWA):** las rutas registradas por terceros que SIWA publica y que pasan a menos de 40 km del río (20 de 289), en el mapa (pestaña «Flujos ilícitos») y por tramo en el libro de indicios, cruzadas con el termómetro de frescura de los flujos, la cola de refresco y el Vigía de fuentes de SIWA. Son registros, no flujos medidos; «activa» significa registrada en los últimos 24 meses. Datos: SIWA, Fundación Sherman Kent (CC BY 4.0), con copia fechada en `sitio/datos/siwa/flujos_corredor.json`.
- **Escáner propio, sin modelo (cero tokens):** `colectores/escaner.py` + `escaner.yml` (cada 3 horas) lee 11 canales RSS/Atom públicos de medios regionales y de organismos (SENAD y Policía Nacional de Paraguay entre ellos), descarta lo que no nombra un lugar del corredor o el río, clasifica por palabras clave (decomiso, detención, piratería, siniestro, bajante, regulatorio o gremial, operativo del Estado), extrae lugar, zona y cantidades con expresiones regulares, junta los titulares casi iguales, comprueba el enlace y guarda 14 días. Se ve como rombos en el mapa (el lugar mencionado, no el del hecho), como tabla «Hechos detectados» y como indicio por tramo, nunca por encima de «corroborado». Son candidatos: no entiende el texto ni prueba independencia entre medios.
- **Segunda red de escalas de nivel del río, con umbrales oficiales:** 29 escalas de la Prefectura Naval Argentina publicadas por el INA (API pública), de Posadas al Río de la Plata, con sus umbrales de aguas bajas, alerta y evacuación. Cubren los tramos del Delta, el Gran Rosario y el Paraná medio, donde la red de Paraguay no llega, y corroboran a la de Paraguay donde se solapan.
- **Sanciones:** cruce por número IMO de los buques que transmiten AIS con la lista SDN de OFAC (dominio público, 1.524 buques con IMO). Hoy no hay coincidencias; una coincidencia sería una pista para mirar, no una acusación.
- **Actores del corredor:** registro de 16 actores (crimen organizado, delitos en el río, Estado y organismos, sector privado, grupos de presión) con qué se sabe y con qué fuentes y nivel de evidencia, qué NO se sabe, y los rastros propios que mide Ysyry; más los operadores de puertos y muelles que figuran en OpenStreetMap. Un actor no es un acusado.
- **Datos abiertos y canal Atom:** `datos/indicios.json` (libro de indicios y hechos detectados, CC BY 4.0 citando a Ysyry) y `feed.xml` para suscribirse desde un lector de noticias.
- **Avisos oficiales:** INMET (Brasil), Meteorología de Paraguay y GDACS (ONU y Comisión Europea), cada 3 horas, sin clave; el SMN de Argentina entra por su feed GeoRSS abierto (CC BY 4.0; su API de pronósticos sí pide clave y no se usa) y el INUMET de Uruguay no tiene API pública, y la página lo dice. Canales recuperados para el escáner: ANNP, Armada Paraguaya, Página/12, NPY, La Diaria y MPF.
- **Estado de las fuentes en vivo:** tabla pública con la cadencia prevista y la última lectura de cada fuente.
- **Parámetros de las reglas:** en `sitio/datos/parametros_reglas.json`, editables sin tocar código; cada alerta candidata dice cuántos días se disparó su regla.
- **Autoescala y salud (privados):** un robot semanal propone unidades del Estado, puntos del mapa y fuentes candidatas a partir de los datos, sin ningún modelo, y uno diario mide la salud de las fuentes. Proponen; nunca aplican.
- **Ayuda:** botón-robot que responde con textos escritos de antemano (no es un modelo de IA) y lleva a buques, puertos y estaciones del mapa.
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

## Robots que corren solos (GitHub Actions, sin tokens de ningún modelo)

| Flujo | Cuándo | Qué hace |
|---|---|---|
| `sitio.yml` | cada hora | Baja la captura de AIS, reconstruye la página y la despliega |
| `satelite.yml` | cada 3 horas | Imagen satelital más reciente (GOES y VIIRS) |
| `focos.yml` | cada 3 horas | Focos de calor a menos de 25 km del río (NASA FIRMS) |
| `nivel-rio.yml` | diario | Lee el nivel del río y suma al historial |
| `escaner.yml` | cada 3 horas | Escáner propio de hechos del corredor en canales RSS (sin modelo) |
| `nivel-rio-ar.yml` | diario (dos veces) | Escalas de la Prefectura vía INA, con umbrales oficiales |
| `ofac.yml` | semanal | Buques con IMO de la lista de sanciones SDN de OFAC |
| `avisos.yml` | cada 3 horas | Avisos oficiales (INMET, Meteorología de Paraguay, GDACS) |
| `noticias.yml` | a mano | GDELT (programación apagada: bloquea las consultas) |
| `preguntas.yml` | diario | Resuelve las preguntas publicadas que ya vencieron |
| `radar.yml` | diario | Procesa pasadas de radar (en validación, no se publica) |

Hay además robots privados (alertas candidatas para la curaduría, salud de las fuentes y autoescala) que abren Issues en un repositorio privado y nunca publican ni aplican nada solos.

## Fuentes y licencias

- **Código:** GPL-3.0. **Datos propios:** CC BY 4.0. Los datos derivados de OpenStreetMap
  (rutas, geocodificación) se rigen por la ODbL.
- **AIS:** AISHub y aisstream.io, a través de Open Waters AIS. AISHub permite redistribuir citándolo;
  aisstream.io no publica términos de uso.
- **Nivel del río:** Dirección de Meteorología e Hidrología de Paraguay (lecturas diarias; historial en `datos/publico/nivel-rio-py-historial.jsonl`); ubicación de las estaciones geocodificada con OpenStreetMap.
- **Cauces del Paraná bajo, el Delta y el Uruguay:** © colaboradores de OpenStreetMap (ODbL), simplificados (`sitio/datos/agua_osm.json`).
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
