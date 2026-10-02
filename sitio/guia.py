"""Catálogo de la guía de ayuda de Ysyry. La guía NO es un modelo de IA: busca en estas respuestas escritas de antemano y en los
nombres del mapa (buques, puertos, estaciones, zonas). No inventa: si no encuentra, lo dice. No gasta tokens ni llama a ningún servicio.

Cada entrada: k = palabras clave (sin tildes ni mayúsculas, el buscador también las quita), r = respuesta, a = acciones
opcionales [tipo, valor, rótulo]: sec = ir a una sección, tab = abrir una pestaña del mapa, ir = ir a un punto del mapa."""

PREGUNTAS_SUGERIDAS = [
    "¿Qué es Ysyry?",
    "¿Cómo leo el mapa?",
    "¿Por qué no veo buques en el Río Paraguay?",
    "¿Qué es un indicio?",
    "¿Hay alertas publicadas?",
    "¿Cómo pido una corrección?",
]


TITULOS = [
    "Qué es Ysyry", "Cómo leer el mapa", "De dónde vienen los buques", "Por qué faltan buques en el río alto", "Cada cuánto se actualiza",
    "El latido y las boyas", "Las fotos de los buques", "El nivel del río", "Indicios y evidencia", "Las alertas", "Preguntas y marcador", "El pulso por zona",
    "Unidades del Estado", "Zonas atribuidas al PCC", "Piratería en el km 340", "Puertos y muelles", "ACLED, focos y homicidios", "SIWA y FEMÓNOE",
    "Satélite y radar", "Cómo pedir una corrección", "Licencias y créditos", "Privacidad", "Auspicios y independencia", "Cómo usar el mapa", "Tema claro y oscuro", "Límites",
]


def catalogo(c):
    """c: n_buques, ultima (texto), n_estaciones, n_bajas, nivel_obtenido (texto), n_unidades_estado."""
    lista = [
        {"k": "que es ysyry esto pagina sitio para que sirve plataforma proposito objetivo quienes somos fundacion", "a": [["sec", "metodo", "Ver método y límites"]],
         "r": "Ysyry («río» en guaraní) es una plataforma pública y gratuita de la Fundación Sherman Kent sobre el corredor de la Hidrovía Paraguay-Paraná. Muestra embarcaciones, puertos, el nivel del río y hechos de riesgo, cada dato con su fuente y su fecha, y arma un libro de indicios con su nivel de evidencia. Lo que no sabemos o no cubrimos, lo decimos."},
        {"k": "como leo mapa simbolos leyenda colores significado iconos que significan puntos", "a": [["tab", "", "Ir al mapa"]],
         "r": "Los puntos de colores son embarcaciones con AIS: amarillo carga, naranja tanque, verde claro pesca o remolque, verde pasajeros, gris otras. El triángulo azul es una unidad del Estado. Las gotas son estaciones de nivel del río (naranja: en el cuarto inferior de su rango histórico). Los círculos con anillos son las boyas de pulso de cada zona. Los cuadrados chicos son puertos y muelles de OpenStreetMap y aparecen al acercar. Tocá cualquier punto para ver su ficha con la fuente."},
        {"k": "buques embarcaciones ais de donde vienen datos fuente posiciones barcos", "a": [],
         "r": "Las posiciones las transmiten los propios buques por AIS y las recopilan redes colaborativas (AISHub y aisstream.io, a través de Open Waters AIS), una captura por hora. La última tiene %s buques (%s). La identidad es la que cada buque transmite: Ysyry no identifica personas, sólo embarcaciones." % (c["n_buques"], c["ultima"])},
        {"k": "rio paraguay triple frontera no veo buques vacio sin datos cobertura alto parana faltan", "a": [["sec", "pulso-zonas", "Ver el pulso por zona"]],
         "r": "El AIS no cubre el río alto: en la prueba, Alto Paraguay, Medio Paraguay y Asunción–Corrientes no devolvieron datos. Parece falta de receptores (es lo que se infiere, no está confirmado). Por eso esas zonas salen «sin datos de AIS» y su boya queda punteada. No significa que no haya tráfico: significa que no lo vemos."},
        {"k": "cada cuanto actualiza actualizacion tiempo real en vivo frecuencia ultima captura hora retraso", "a": [],
         "r": "El sitio se reconstruye solo cada hora con la última captura de AIS y guarda las últimas 24. El nivel del río se lee una vez por día. La última captura es de %s. No es tiempo real estricto: es una captura por hora." % c["ultima"]},
        {"k": "latido senal viva sonar boya pulso que significa punto late cabecera mapa", "a": [["sec", "pulso-zonas", "Ver el pulso por zona"]],
         "r": "El latido de la cabecera del mapa dice si la última captura llegó a tiempo: «viva» si tiene menos de 95 minutos, «retrasada» hasta 4 horas, «sin captura reciente» después. Sólo dice que el sistema recibe datos, no que el río esté tranquilo. Las boyas son una por zona: con anillos si hay AIS, punteada si no, y naranja si hay un indicio a mirar."},
        {"k": "fotos fotografias imagenes de buques verificadas imo ilustrativas nombre", "a": [],
         "r": "Hay tres niveles y cada ficha dice cuál es: foto verificada por el número IMO del buque; coincidencia por nombre, sólo cuando el buque no transmite IMO; o imagen ilustrativa de su tipo, que no es una foto de ese buque. Autor y licencia figuran en cada una."},
        {"k": "nivel del rio altura estaciones gota hidrometrica sequia bajante calado agua metros", "a": [["tab", "indicios", "Ver estaciones en el mapa"]],
         "r": "Las gotas son estaciones de nivel de río de la Dirección de Meteorología e Hidrología de Paraguay: hoy %d con ubicación en el mapa, %d en el cuarto inferior de su rango histórico. Cada ficha muestra el nivel, la variación en 24 horas y dónde está frente a su mínimo y máximo históricos. No es el calado ni un límite de navegación, y el organismo actualiza a diario, no en vivo. Las estaciones entre las represas de Itaipú y Yacyretá están reguladas y no miden sequía." % (c["n_estaciones"], c["n_bajas"])},
        {"k": "indicio indicios evidencia fuente unica corroborado fuerte nivel de evidencia libro como se califica", "a": [["sec", "indicios-zonas", "Ver el libro de indicios"]],
         "r": "Un indicio es una observación con sus fuentes. «Fuente única»: una sola. «Corroborado»: dos o más fuentes independientes de la misma familia (por ejemplo, varios medios). «Fuerte»: dos o más independientes de al menos dos familias (por ejemplo, prensa y una fuente oficial). Varias estaciones de un mismo organismo, o las dos redes de AIS, cuentan como una fuente. Un indicio no es una alerta."},
        {"k": "alertas alerta publicadas hay avisos como se genera candidata curaduria decimo hombre", "a": [["sec", "alertas-femonoe", "Ver alertas de FEMÓNOE"]],
         "r": "Hoy Ysyry no tiene alertas publicadas. Una alerta es un juicio con probabilidad y plazo: el sistema detecta indicios y puede proponer una candidata en privado; dos analistas la leen sin verse, el décimo hombre la impugna con evidencia propia y la dirección decide si se publica. Nada se publica solo. Las alertas de FEMÓNOE sobre los cinco Estados del corredor se muestran aparte, tal como las publica."},
        {"k": "prospectiva preguntas probabilidad marcador brier calibracion prediccion pronostico kent", "a": [["sec", "prospectiva", "Ver la prospectiva"]],
         "r": "Las preguntas son binarias, con plazo, una banda de probabilidad en el léxico de Kent y un criterio mecánico fijado de antemano. Al vencer se resuelven solas contra los datos y se puntúan con Brier. El marcador se muestra «en calibración» hasta reunir 20 preguntas vencidas. Hoy no hay ninguna publicada; preferimos dejar el espacio vacío antes que mostrar un número sin respaldo."},
        {"k": "pulso por zona zonas tramos que mide huellas actores tabla boyas", "a": [["sec", "pulso-zonas", "Ver el pulso por zona"]],
         "r": "El pulso divide el corredor en cinco tramos y muestra, con el AIS de las últimas 24 horas, cuántos buques hay, cuántos se mueven, qué unidades del Estado se ven y cómo se compara con la historia del mismo tramo (la comparación aparece con 7 días de historia). Mide huellas observables de buques que transmiten, no la conducta de ningún grupo."},
        {"k": "estado unidades fuerzas seguridad prefectura armada triangulo azul presencia patrulla gendarmeria", "a": [["tab", "estado", "Ver Fuerzas del Estado"]],
         "r": "El triángulo azul marca una unidad del Estado cuando el buque transmite tipo militar (35) o de fuerzas del orden (55), o por el prefijo de su nombre (ARA, GC, ARP, PGN, LP). La fuerza que figura en la ficha está inferida del nombre, no la transmite el buque. Hoy se ven %s unidades. No ver una unidad no significa que el Estado no esté: las que apagan el AIS o no lo tienen no aparecen." % c["n_unidades_estado"]},
        {"k": "pcc comando vermelho crimen organizado canindeyu alto parana zonas atribuidas presencia criminal", "a": [["tab", "seguridad", "Ver Crimen organizado y riesgo"]],
         "r": "Las zonas punteadas de Canindeyú y Alto Paraná marcan presencia atribuida al PCC según dos medios (La Política Online y ABC Color) y comunicados de la Presidencia de Paraguay. Es una atribución periodística y oficial, no una sentencia: no implica que ocurra en todo el departamento ni involucra a sus habitantes. La fuente oficial no es independiente del Estado."},
        {"k": "pirateria robo carga km 340 san nicolas asalto rosa naviship", "a": [],
         "r": "El punto naranja del km 340 es un hecho puntual de octubre de 2025: el asalto a la motonave «Rosa» (Naviship Paraguay S.A.), informado por cuatro medios. Es presunto, sin condena, y un hecho puntual no establece un patrón ni dice que el lugar sea hoy peligroso."},
        {"k": "puertos muelles amarraderos rampas caletas openstreetmap terminales dolsenas atracaderos", "a": [],
         "r": "Los puertos, muelles, rampas y amarraderos salen de OpenStreetMap, un aporte colaborativo con licencia ODbL: pueden faltar, estar desactualizados o ser privados, y que figuren no significa que operen hoy. Aparecen por niveles al acercar el mapa. OpenStreetMap casi no registra «caletas»: si conocés una, pedí una corrección."},
        {"k": "acled focos de calor homicidios provincia contexto siwa violencia politica incendios fuego", "a": [["sec", "indicios-zonas", "Ver el libro de indicios"]],
         "r": "Las fichas de puertos y ciudades suman, de la provincia o departamento donde están, los homicidios de la fuente oficial, los eventos de violencia política de ACLED y los focos de calor de NASA FIRMS, tomados de los datos abiertos de SIWA. Son cifras de toda la unidad, no del puerto, y no son tasas. ACLED es una base secundaria sobre prensa; un foco de calor no es un incendio confirmado; «sin dato» no equivale a cero."},
        {"k": "femonoe siwa ecosistema hermanas plataformas fundacion alertas tempranas relacion", "a": [["sec", "alertas-femonoe", "Ver alertas de FEMÓNOE"]],
         "r": "Ysyry es la tercera plataforma del ecosistema de la Fundación Sherman Kent, junto a SIWA (datos abiertos de la región) y FEMÓNOE (alerta temprana para 33 Estados). Se apoyan por datos, no por código: Ysyry lee lo que SIWA publica y muestra las alertas de FEMÓNOE sobre el corredor sin reescribirlas."},
        {"k": "satelite goes viirs radar sentinel imagenes capas nubes", "a": [["sec", "mapa", "Ir al mapa"]],
         "r": "En el mapa podés encender una capa satelital: GOES-East (cuadro reciente) o VIIRS (diario), de NASA GIBS. El radar Sentinel-1 para ver buques sin AIS está en validación y no se publica: todavía no medimos cuántos buques conocidos detecta."},
        {"k": "corregir corrijo corrigen corregis correccion error reclamo replica derecho contacto titular dato incorrecto denuncia", "a": [["sec", "metodo", "Ver método y límites"]],
         "r": "Si sos titular de una embarcación, de un lugar o de un dato y querés una corrección, escribinos por el formulario de contacto de fundacionkent.org o abrí un pedido en Issues del repositorio de Ysyry. Una corrección posterior a la publicación se muestra con su fecha."},
        {"k": "licencia licencias codigo abierto datos creditos derechos uso reutilizar citar", "a": [],
         "r": "El código es GPL-3.0 y los datos propios CC BY 4.0. Los datos de OpenStreetMap se rigen por la ODbL; las fotos son de Wikipedia y Wikimedia Commons con autor y licencia en cada ficha; los contextos vienen de SIWA (CC BY 4.0) con las fuentes de base. Al reutilizar, citá a Ysyry y a la fuente original."},
        {"k": "privacidad identidades personas nombres datos personales anonimato registro", "a": [],
         "r": "Ysyry sólo muestra lo que cada embarcación transmite por AIS y nunca identifica a una persona. Las identidades acumuladas se guardan en un registro privado, no en este sitio; publicar una identidad exige revisión de la dirección."},
        {"k": "auspicio auspiciantes publicidad independencia editorial financiamiento quien paga dinero", "a": [],
         "r": "Ysyry es gratuito. Si algún día hay auspicios de actores privados, rige una regla escrita: un auspicio nunca compra ni condiciona un dato, no da derecho a revisar o demorar una publicación, se declara a la vista y no borra lo ya publicado."},
        {"k": "zoom acercar alejar mover arrastrar rueda pestañas filtros familias usar manejo como uso", "a": [["tab", "", "Ir al mapa"]],
         "r": "Usá la rueda del mouse o los botones + y − para acercar, arrastrá para moverte y el botón ↺ para volver a la vista completa. Tocá un punto para ver su ficha. Las pestañas de arriba filtran por tema (crimen organizado y riesgo, comercio y puertos, fuerzas del Estado, regulatorio, indicios). El reloj de abajo reproduce las últimas capturas."},
        {"k": "tema oscuro claro modo fondo colores apariencia", "a": [],
         "r": "El botón «Fondo oscuro» de la cabecera cambia el tema; la página abre siempre en claro y recuerda tu elección en este navegador."},
        {"k": "no hace limites que no cubre limitaciones confiable seguro verdad precision", "a": [["sec", "metodo", "Ver método y límites"]],
         "r": "Límites principales: el AIS no cubre el río alto ni a las embarcaciones menores; las unidades del Estado sin AIS no figuran; el nivel del río es de una sola fuente oficial y diaria; las zonas del pulso son cajas aproximadas; y los indicios no son alertas. La sección «Método y límites» los detalla uno por uno."},
    ]
    assert len(lista) == len(TITULOS), (len(lista), len(TITULOS))
    for e, t in zip(lista, TITULOS):
        e["t"] = t
    return lista
